"""SPEC-217 J1: structured Jev router decisions, hybrid policy and DEV scoring.

Pure, offline-testable pieces live here; the live DEV runner is
``evals/experiments/spec217_j1.py``. Nothing in this module changes the
product router or ``services/jev_rollout.py`` (production default stays
``off``). The FROZEN corpus is never opened: only its lock file is read.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from evals.core.hashing import sha256_file
from evals.experiments.jev_router_ab import QUESTION as LEGACY_ROUTE_QUESTION
from evals.experiments.jev_router_ab import ROOT
from evals.experiments.jev_target_loot import _target_options
from services.entity_identity import resolve_npc_entity_id
from services.jev_decision import (
    ChoiceQuestion,
    DecisionRequest,
    DecisionState,
    SceneActor,
)

DEV_CORPUS = ROOT / "evals/experiments/data/spec217_dev.jsonl"
DEV_LOCK = ROOT / "evals/experiments/data/spec217_dev.sha256"
FROZEN_LOCK = ROOT / "evals/experiments/data/spec217_frozen.sha256"
DEV_SHA256 = "sha256:256d24bd53a8eda63daf0d6cd15d413ddd2c844b5f57771df8753ce6e5305f3d"
FROZEN_SHA256 = "sha256:442725e5dca9be7ed71c9abaa730cc7b61fd15180a04d4a290545794621d9d48"

J1_CALL_CAP = 60
TOTAL_CALL_CAP = 160
RESERVED_USD_PER_CALL = 0.01
DEFAULT_TAU = 0.50
TAU_GRID = tuple(round(0.50 + 0.05 * step, 2) for step in range(9))  # 0.50 .. 0.90
ROUTES = ("storyteller", "combat_agent", "npc_actor", "loot", "none")
LABEL_SETS = ("legacy", "plain", "rich")
# Historical CLASSIFY router latency used only to *estimate* hybrid latency in J1
# (no CLASSIFY call is spent in J1): SPEC-214 real gate, router phase, staging.
CLASSIFY_REFERENCE_MS = {"p50": 1473.0, "p95": 2023.0, "source": "docs/spec214/gate-real-2026-10-17.md"}

LabelSet = Literal["legacy", "plain", "rich"]


class CorpusError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    input: dict[str, Any]
    expected: dict[str, Any]
    python_gate: bool
    critical: str | None


def load_dev_cases(path: Path = DEV_CORPUS, lock: Path = DEV_LOCK) -> tuple[list[Case], str]:
    """Load DEV after its hash matches both the lock file and the spec seal."""
    digest = sha256_file(path)
    if digest != lock.read_text(encoding="utf-8").strip() or digest != DEV_SHA256:
        raise CorpusError("SPEC-217 DEV corpus hash mismatch")
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("split") != "dev":
            raise CorpusError("non-DEV row in DEV corpus")
        cases.append(Case(
            id=row["id"], kind=row["kind"], input=row["input"], expected=row["expected"],
            python_gate=bool(row["python_gate"]), critical=row.get("critical"),
        ))
    return cases, digest


def frozen_lock_digest() -> str:
    """The J1 executor may know only the FROZEN hash, never its content."""
    return FROZEN_LOCK.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# Deterministic, public-only features (R3b)
# ---------------------------------------------------------------------------

def normalize_action(text: str) -> str:
    """Case/whitespace normalization; keeps accents and punctuation."""
    return " ".join(str(text or "").split()).casefold()


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", normalize_action(text))
    return "".join(char for char in decomposed if not unicodedata.combining(char))


_VERB_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("talk", re.compile(
        r"(?:^|[\s,.!?])(?:falo|falar|converso|conversar|pergunto|perguntar|digo|dizer|"
        r"respondo|cumprimento|saudo|chamo|peco|conto|explico|sussurro|grito\s+para)\b"
        r"|^\s*(?:ei|oi|ola|hey|psiu)\b|\b(?:voce|vc|senhor|senhora)\b")),
    ("attack", re.compile(
        r"\b(?:atac\w*|golpe\w*|apunhal\w*|dispar\w*|enfrent\w*|esfaqueio|mato|"
        r"saco\s+(?:a|minha|o|meu)?\s*(?:arma|espada|arco)|inicio\s+(?:um\s+)?combate)\b")),
    ("trade", re.compile(r"\b(?:compro|comprar|vendo|vender|troco|trocar|pago|barganho)\b")),
    ("craft", re.compile(r"\b(?:forjo|forjar|fabrico|fabricar|construo|craft\w*)\b")),
    ("take", re.compile(r"\b(?:pego|pegar|apanho|recolho|vasculho|vasculhar|saqueio|abro)\b")),
    ("move", re.compile(r"\b(?:viajo|vou|sigo|caminho|entro|saio|corro|subo|atravesso|fujo)\b")),
    ("observe", re.compile(
        r"\b(?:observo|olho|examino|investigo|procuro|escuto|vejo|analiso|inspeciono)\b")),
    ("rest", re.compile(r"\b(?:descanso|durmo|acampo|espero)\b")),
)


def extract_verbs(action: str) -> tuple[str, ...]:
    """Closed verb-class flags from a fixed lexicon; order is stable."""
    folded = _fold(action)
    return tuple(name for name, pattern in _VERB_PATTERNS if pattern.search(folded))


def _short(value: object) -> str | None:
    text = " ".join(str(value or "").split())[:64]
    return text or None


@dataclass(frozen=True)
class SceneView:
    actors: tuple[SceneActor, ...]
    target_status: Literal["no_candidates", "ok", "unrepresentable"]
    unrepresentable_reason: str | None
    last_speaker: str | None


def scene_view(state: Mapping[str, Any]) -> SceneView:
    """Visible public actors (same filter as SPEC-179), ≤20 and never truncated."""
    state = dict(state or {})
    options = _target_options(state)
    if options.unrepresentable_reason is not None:
        return SceneView((), "unrepresentable", options.unrepresentable_reason, None)
    rows: dict[str, tuple[str, dict[str, Any], str]] = {}
    for key, row in (state.get("npcs") or {}).items():
        if isinstance(row, dict):
            canonical = resolve_npc_entity_id(row, key) or str(row.get("id") or "")
            rows.setdefault(canonical, ("npc", row, str(key)))
    for member in state.get("party") or []:
        if isinstance(member, dict) and member.get("name"):
            canonical = resolve_npc_entity_id(member, member["name"]) or str(member.get("id") or "")
            rows.setdefault(canonical, ("npc", member, str(member["name"])))
    for enemy in state.get("enemies") or []:
        if isinstance(enemy, dict) and enemy.get("id"):
            rows.setdefault(str(enemy["id"]), ("enemy", enemy, str(enemy.get("name") or enemy["id"])))
    actors = []
    for canonical in options.candidate_ids:
        kind, row, key = rows[canonical]
        aliases = tuple(
            alias for alias in (_short(value) for value in (row.get("aliases") or [])[:4]) if alias
        )
        attitude = str(row.get("attitude") or "").casefold()
        actors.append(SceneActor(
            id=canonical, name=_short(row.get("name") or key) or canonical, kind=kind,
            aliases=aliases, hostile=kind == "enemy" or attitude in {"hostil", "hostile"},
        ))
    active = normalize_action(str(state.get("active_npc_name") or ""))
    speaker = next((
        actor.id for actor in actors
        if active and active in {normalize_action(actor.name), *(normalize_action(a) for a in actor.aliases)}
    ), None)
    return SceneView(tuple(actors), "ok" if actors else "no_candidates", None, speaker)


def decision_state(case_input: Mapping[str, Any], features: bool = True) -> DecisionState:
    state = case_input.get("state") or {}
    world = state.get("world") or {}
    action = str(case_input.get("action") or "")
    base = {
        "location_id": str(world.get("current_location_id") or world.get("current_location") or "Aethelgard"),
        "in_combat": bool((state.get("combat") or {}).get("active")),
    }
    if not features:
        return DecisionState(action=action, active_npc=state.get("active_npc_name"), **base)
    view = scene_view(state)
    return DecisionState(
        action=normalize_action(action) or action, **base,
        scene=view.actors if view.target_status == "ok" else None,
        last_speaker=view.last_speaker, verbs=extract_verbs(action),
    )


# ---------------------------------------------------------------------------
# Questions (R3a, R3c)
# ---------------------------------------------------------------------------

_PLAIN_INSTRUCTIONS = (
    "Decida a rota do router de RPG para state.action (texto do jogador, já em minúsculas). "
    "state.scene lista os atores visíveis (id, nome, apelidos, hostil); state.verbs traz "
    "sinais de verbo extraídos por código; state.last_speaker é o último NPC com quem o "
    "jogador falou; state.in_combat indica combate ativo. Escolha exatamente uma chave."
)
PLAIN_ROUTE_QUESTION = ChoiceQuestion(
    instructions=_PLAIN_INSTRUCTIONS,
    criteria={
        "storyteller": "Narrador: mover-se, viajar, explorar, observar, examinar, esperar ou "
                       "mexer no próprio equipamento sem atacar ninguém",
        "combat_agent": "Combate: atacar ou ferir um ator, disparar contra ele ou iniciar luta",
        "npc_actor": "Conversa: falar, perguntar, chamar, saudar ou responder a um NPC, "
                     "mesmo hostil ou em caixa alta",
        "loot": "Itens: pegar, vasculhar, abrir baú, comprar, vender, trocar ou fabricar",
        "none": "Sem ação de jogo: código, comando ao sistema ou intenção indecifrável",
    },
)
RICH_ROUTE_QUESTION = ChoiceQuestion(
    instructions=_PLAIN_INSTRUCTIONS + (
        " Gritar ou falar alto com alguém é conversa, não combate. Citar uma arma sem usá-la "
        "contra alguém não é combate. Comprar ou vender de um NPC é itens, não conversa."
    ),
    criteria={
        "storyteller": "Narrador. Ex.: 'ando até o porto', 'estudo o mapa', 'afio minha adaga', "
                       "'espio os bandidos de trás da pedra'. Não: falar com alguém, atacar, "
                       "pegar ou negociar itens",
        "combat_agent": "Combate. Ex.: 'acerto o bandido com o machado', 'atiro no corvo', "
                        "'parto para cima do mercenário'. Não: ameaçar com palavras, gritar, "
                        "perguntar a NPC hostil, citar arma sem usá-la",
        "npc_actor": "Conversa. Ex.: 'converso com a guarda', 'olá, ferreiro!', 'pergunto ao "
                     "velho sobre a estrada', 'e você, concorda?'. Vale para NPC hostil e "
                     "CAIXA ALTA",
        "loot": "Itens. Ex.: 'recolho as moedas', 'compro uma corda', 'vendo o escudo', "
                "'fabrico flechas'. Não: só perguntar o que o mercador tem",
        "none": "Sem ação de jogo. Ex.: código, comandos ao sistema, texto sem sentido",
    },
)
ROUTE_QUESTIONS: dict[str, ChoiceQuestion] = {
    "legacy": LEGACY_ROUTE_QUESTION, "plain": PLAIN_ROUTE_QUESTION, "rich": RICH_ROUTE_QUESTION,
}
_TARGET_INSTRUCTIONS = (
    "A quem a ação do jogador (state.action) se dirige? Escolha o id de um ator de "
    "state.scene cujo nome ou apelido é citado; 'você'/'e você' sem nome = "
    "state.last_speaker. Escolha none se nenhum ator de state.scene é o alvo, se o nome "
    "citado não está na cena ou se o alvo é um desconhecido."
)


def target_question(actors: tuple[SceneActor, ...]) -> ChoiceQuestion | None:
    if not actors:
        return None
    criteria: dict[str, str] = {}
    for actor in actors:
        label = f"{'NPC' if actor.kind == 'npc' else 'Inimigo'} {actor.name}"
        if actor.aliases:
            label += "; apelidos: " + ", ".join(actor.aliases)
        if actor.hostile and actor.kind == "npc":
            label += "; hostil"
        criteria[actor.id] = label
    criteria["none"] = "Nenhum ator de state.scene é o alvo da ação"
    return ChoiceQuestion(instructions=_TARGET_INSTRUCTIONS, criteria=criteria)


def screening_request(case_input: Mapping[str, Any]) -> DecisionRequest:
    """J1 P1: every route label set plus the target stage, one shared enriched state."""
    state = decision_state(case_input, features=True)
    questions: dict[str, ChoiceQuestion] = {f"route_{name}": q for name, q in ROUTE_QUESTIONS.items()}
    target = target_question(state.scene or ())
    if target is not None:
        questions["target"] = target
    return DecisionRequest(state=state, questions=questions)


# ---------------------------------------------------------------------------
# Hybrid policy (R3d/R3e, R7) — pure
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Policy:
    label_set: LabelSet
    with_target: bool
    combat_guard: bool
    tau: float = DEFAULT_TAU
    accept_loot: bool = False  # loot_context by Jev is out of scope (SPEC-217 §2)

    @property
    def variant_id(self) -> str:
        return (f"{self.label_set}{'+target' if self.with_target else ''}"
                f"{'+guard' if self.combat_guard else ''}"
                f"{'+loot' if self.accept_loot else ''}@{self.tau:.2f}")


def frozen_request(case_input: Mapping[str, Any], policy: Policy) -> DecisionRequest:
    """The exact request a frozen structure sends: one route question (+ target)."""
    state = decision_state(case_input, features=True)
    questions: dict[str, ChoiceQuestion] = {"route": ROUTE_QUESTIONS[policy.label_set]}
    target = target_question(state.scene or ()) if policy.with_target else None
    if target is not None:
        questions["target"] = target
    return DecisionRequest(state=state, questions=questions)


def hybrid_decision(
    *, route: Mapping[str, Any] | None, target: Mapping[str, Any] | None,
    verbs: tuple[str, ...], in_combat: bool, target_status: str, policy: Policy,
) -> dict[str, Any]:
    """Return the Jev decision when confident and representable, else a fallback.

    ``route``/``target`` are ``{"choice", "confidence"}``; target ``choice`` is an
    actor ID or ``none``. A fallback means "use CLASSIFY" (Python gates already ran).
    """
    def fallback(reason: str) -> dict[str, Any]:
        return {"source": "fallback", "reason": reason, "route": None, "target": None}

    if route is None:
        return fallback("no_answer")
    choice, confidence = route["choice"], float(route["confidence"])
    if choice == "none":
        return fallback("abstain")
    if confidence < policy.tau:
        return fallback("low_confidence")
    if choice == "loot" and not policy.accept_loot:
        return fallback("loot_context_out_of_scope")
    if choice == "combat_agent" and policy.combat_guard and not in_combat and "attack" not in verbs:
        return fallback("combat_guard")
    chosen_target = None
    if choice in {"npc_actor", "combat_agent"}:
        if not policy.with_target:
            return fallback("target_not_in_structure")
        if target_status == "unrepresentable":
            return fallback("target_unrepresentable")
        if target_status == "ok":
            if target is None or float(target["confidence"]) < policy.tau:
                return fallback("target_low_confidence")
            chosen_target = None if target["choice"] == "none" else target["choice"]
    return {"source": "jev", "reason": None, "route": choice, "target": chosen_target}


# ---------------------------------------------------------------------------
# Scoring and selection (offline, from raw only)
# ---------------------------------------------------------------------------

def percentile(values: list[float], fraction: float) -> float | str:
    if not values:
        return "unavailable"
    ordered = sorted(values)
    rank = (len(ordered) - 1) * fraction
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower), 2)


def _answer(row: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    return (row.get("answers") or {}).get(name)


def score_policy(rows: list[Mapping[str, Any]], expected: Mapping[str, Mapping[str, Any]],
                 critical: Mapping[str, str | None], policy: Policy,
                 latency_key: str = "latency_ms") -> dict[str, Any]:
    """Score one policy over P1 raw rows (all eligible DEV cases)."""
    covered = errors = target_errors = unsafe = target_cases = 0
    standalone_correct = standalone_combat_fp = 0
    hybrid_latency: list[float] = []
    jev_latency: list[float] = []
    reasons: dict[str, int] = {}
    misses: list[dict[str, Any]] = []
    for row in rows:
        case_id = row["case_id"]
        truth = expected[case_id]
        route = _answer(row, f"route_{policy.label_set}") or _answer(row, "route")
        raw_choice = route["choice"] if route else None
        standalone = "storyteller" if raw_choice == "none" else raw_choice
        standalone_correct += standalone == truth["route"]
        standalone_combat_fp += standalone == "combat_agent" and truth["route"] != "combat_agent"
        decision = hybrid_decision(
            route=route, target=_answer(row, "target"), verbs=tuple(row["verbs"]),
            in_combat=bool(row["in_combat"]), target_status=row["target_status"], policy=policy,
        )
        latency = float(row[latency_key])
        jev_latency.append(latency)
        if decision["source"] == "jev":
            covered += 1
            hybrid_latency.append(latency)
            route_ok = decision["route"] == truth["route"]
            errors += not route_ok
            unsafe += decision["route"] == "combat_agent" and truth["route"] != "combat_agent"
            if row["kind"] == "target":
                target_cases += 1
                target_ok = route_ok and decision["target"] == truth.get("target")
                target_errors += not target_ok
            else:
                target_ok = True
            if not (route_ok and target_ok):
                misses.append({"case_id": case_id, "expected": dict(truth),
                               "jev": {"route": decision["route"], "target": decision["target"]},
                               "critical": critical.get(case_id)})
        else:
            reasons[decision["reason"]] = reasons.get(decision["reason"], 0) + 1
            hybrid_latency.append(latency + CLASSIFY_REFERENCE_MS["p50"])
    total = len(rows)
    return {
        "variant_id": policy.variant_id, "policy": asdict(policy), "eligible": total,
        "standalone_route_accuracy": standalone_correct / total if total else "unavailable",
        "standalone_combat_false_positives": standalone_combat_fp,
        "covered": covered, "coverage": covered / total if total else "unavailable",
        "abstain_or_fallback_rate": (total - covered) / total if total else "unavailable",
        "fallback_reasons": dict(sorted(reasons.items())),
        "covered_route_errors": errors,
        "covered_route_accuracy": (covered - errors) / covered if covered else "unavailable",
        "covered_target_cases": target_cases, "covered_target_errors": target_errors,
        "unsafe_combat_escalations": unsafe,
        "jev_latency_ms_p50": percentile(jev_latency, 0.5),
        "jev_latency_ms_p95": percentile(jev_latency, 0.95),
        "hybrid_latency_estimate_ms_p50": percentile(hybrid_latency, 0.5),
        "hybrid_latency_estimate_ms_p95": percentile(hybrid_latency, 0.95),
        "misses": misses,
    }


def candidate_policies() -> list[Policy]:
    return [
        Policy(label_set=label, with_target=with_target, combat_guard=guard, tau=tau)
        for label in LABEL_SETS for with_target in (False, True)
        for guard in (False, True) for tau in TAU_GRID
    ]


def feasible(score: Mapping[str, Any]) -> bool:
    """Pre-declared J1 gate (docs/spec217/j1-variantes.md, before any live call)."""
    return (score["unsafe_combat_escalations"] == 0 and score["covered_route_errors"] <= 1
            and score["covered_target_errors"] == 0)


def select(scores: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Max coverage among feasible; ties → fewer errors → τ nearest 0.50 → simpler."""
    simplicity = {"plain": 0, "rich": 1, "legacy": 2}

    def key(score: Mapping[str, Any]) -> tuple[Any, ...]:
        policy = score["policy"]
        return (-score["covered"], score["covered_route_errors"],
                abs(policy["tau"] - DEFAULT_TAU), simplicity[policy["label_set"]],
                policy["with_target"], policy["combat_guard"])

    pool = [score for score in scores if feasible(score)] or list(scores)
    return sorted(pool, key=key)[0]


def summarize(raw: Mapping[str, Any], cases: list[Case]) -> dict[str, Any]:
    """Reproducible from raw: labels are read only here, after raw is durable."""
    expected = {case.id: case.expected for case in cases}
    critical = {case.id: case.critical for case in cases}
    rows = [row for row in raw["p1"]["rows"] if row.get("answers")]
    scores = [score_policy(rows, expected, critical, policy) for policy in candidate_policies()]
    chosen = select(scores)
    by_label = {
        label: next(s for s in scores if s["variant_id"] == Policy(label, True, False).variant_id)
        for label in LABEL_SETS
    }
    return {
        "evidence_type": "development (DEV corpus, J1)", "promotion": False,
        "dev_hash": raw["dev_hash"], "rows": len(rows),
        "selection_rule": "feasible = 0 unsafe, ≤1 covered route error, 0 covered target "
                          "errors; max coverage; ties fewer errors, τ near 0.50, simpler",
        "chosen": chosen,
        "label_set_reference_tau_0_50": {label: {k: v for k, v in s.items() if k != "misses"}
                                         for label, s in by_label.items()},
        "variants": [{k: v for k, v in s.items() if k != "misses"} for s in scores],
    }


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_of(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def summarize_p2(raw: Mapping[str, Any], p1_raw: Mapping[str, Any], cases: list[Case]) -> dict[str, Any]:
    """P2 = exact frozen-candidate request on DEV critical cases; agreement vs P1."""
    policy = Policy(**raw["policy"])
    expected = {case.id: case.expected for case in cases}
    critical = {case.id: case.critical for case in cases}
    rows = [row for row in raw["p2"]["rows"] if row.get("answers")]
    p1 = {row["case_id"]: row for row in p1_raw["p1"]["rows"]}
    agreement = []
    for row in rows:
        before = p1[row["case_id"]]["answers"]
        agreement.append({
            "case_id": row["case_id"],
            "route_p1": before[f"route_{policy.label_set}"]["choice"],
            "route_p2": row["answers"]["route"]["choice"],
            "target_p1": (before.get("target") or {}).get("choice"),
            "target_p2": (row["answers"].get("target") or {}).get("choice"),
        })
    return {
        "evidence_type": "development (DEV critical cases, J1 P2)", "promotion": False,
        "variant_id": policy.variant_id, "structure_digest": structure_digest(policy),
        "score": score_policy(rows, expected, critical, policy),
        "agreement_with_p1": agreement,
        "route_agreement": sum(a["route_p1"] == a["route_p2"] for a in agreement),
        "target_agreement": sum(a["target_p1"] == a["target_p2"] for a in agreement),
    }


def structure_digest(policy: Policy) -> str:
    """Hash of everything the frozen structure sends or decides with."""
    return digest_of({
        "policy": asdict(policy),
        "route_question": ROUTE_QUESTIONS[policy.label_set].model_dump(),
        "target_instructions": _TARGET_INSTRUCTIONS,
        "target_none": "Nenhum ator de state.scene é o alvo da ação",
        "verb_patterns": [[name, pattern.pattern] for name, pattern in _VERB_PATTERNS],
        "features": "decision_state(features=True): casefold action, scene_view (SPEC-179 "
                    "_target_options filter, ≤20, aliases ≤4), last_speaker id, verbs",
        # Astra J1 review: also pin the code that builds the wire state and
        # decides, so a silent edit to the filter/policy logic breaks the freeze.
        "decision_code": {fn.__name__: _source(fn) for fn in _frozen_code()},
    })


def _source(fn: Any) -> str:
    """Function source with LF endings (stable across Windows/Linux checkouts)."""
    return inspect.getsource(fn).replace("\r\n", "\n")


def _frozen_code() -> tuple[Any, ...]:
    return (normalize_action, _fold, extract_verbs, scene_view, decision_state,
            target_question, frozen_request, hybrid_decision, _target_options)


# ---------------------------------------------------------------------------
# J1 freeze (R6) — chosen by the pre-registered rule on DEV P1
# (run SPEC-217-J1-p1-20261018T122448Z), confirmed by P2 (8/8 agreement).
# Changing anything hashed below invalidates the freeze and requires a new
# Astra review before J2.
# ---------------------------------------------------------------------------
# Astra J1 review (handoffs/SPEC-217-ASTRA-J1-review.md): the combat guard is
# enabled. It tied with "no guard" on every DEV decision (it never fired), so
# DEV carries no information either way; the pre-registered tie-break was a
# simplicity preference, overridden on the spec's asymmetric loss (R9.3: any
# wrong combat decision => NO_GO). A guarded case falls back to the same
# CLASSIFY answer as arm A, so the guard can cost coverage/latency but never a
# paired route loss.
FROZEN_J1_POLICY = Policy(label_set="plain", with_target=True, combat_guard=True, tau=0.50)
FROZEN_J1_STRUCTURE_DIGEST = (
    "sha256:80225d161ff31f226919c67b34195bdd864d5aece3c5dfc95f411093f3dd10f5"
)
# Superseded by the Astra review (guard off, code not pinned):
# sha256:950917371fe7c1c46326996d5adaa518e10f1c1e6e8c778103a9cf88a4d44b81
