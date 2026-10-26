"""SPEC-203 — manifesto do encontro, elenco fixo e state machine do combate.

Funções PURAS (sem LLM, sem I/O). O dono da escrita é `agents/combat.combat_node`;
router/storyteller só propõem referências one-shot (`combat_target_ref`,
`combat_encounter_hint`); API/frontend só leem.

- O manifesto é congelado no spawn e lido a cada rodada (nunca reclassificado).
- Um participante só entra/sai da luta com `EncounterCompositionEvent`.
- `combat.phase ∈ {entering, active, resolving, ended}` com transições explícitas.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from copy import deepcopy
from typing import Any, Dict, List, Literal, Optional
from collections.abc import Iterable

from pydantic import BaseModel, Field

log = logging.getLogger("rpg.encounter")

Role = Literal["hostile", "ally", "neutral", "hazard"]
Presence = Literal["present", "arrived", "departed"]
Status = Literal["ativo", "morto", "fugiu", "rendido", "capturado", "ausente", "incapacitado"]
EventKind = Literal[
    "joined", "cut", "dead", "fled", "surrendered", "captured", "departed", "incapacitated"
]
Source = Literal[
    "systemic", "npc_in_scene", "threat", "scanner", "fallback", "legacy_migrated", "simulation"
]

PHASES = ("entering", "active", "resolving", "ended")
OUTCOMES = ("victory", "fled", "surrendered_enemy", "defeat", "death", "expired")
_ALLOWED = {
    None: {"entering"},
    "entering": {"active", "ended"},
    "active": {"resolving"},
    "resolving": {"ended"},
    "ended": set(),
}
_ENTERING_TO_ENDED_OUTCOMES = {"expired", "defeat"}
_STATUS_EVENT = {
    "morto": "dead",
    "fugiu": "fled",
    "rendido": "surrendered",
    "capturado": "captured",
    "ausente": "departed",
    "incapacitado": "incapacitated",  # SPEC-325 R9
}


class EncounterParticipant(BaseModel):
    participant_id: str
    bestiary_id: str = ""
    species_label: str
    faction_id: str = ""
    categoria: str = "padrao"
    role: Role = "hostile"
    presence: Presence = "present"
    zone_id: str = "z0"
    status: Status = "ativo"


class EncounterCompositionEvent(BaseModel):
    kind: EventKind
    participant_id: str
    cause: str
    round: int = 0
    event_id: str = ""


class EncounterManifest(BaseModel):
    encounter_id: str
    origin: str = "unknown"
    source: Source = "fallback"
    target_ref: str = ""
    participants: list[EncounterParticipant] = Field(default_factory=list)
    events: list[EncounterCompositionEvent] = Field(default_factory=list)
    frozen: bool = False
    schema_: int = Field(default=1, alias="schema")

    model_config = {"populate_by_name": True}


class InvalidEncounterTransition(ValueError):
    """Transição de fase não permitida pela state machine (R5)."""


# ---------------------------------------------------------------------------
# Normalização de nomes (determinística, sem LLM)
# ---------------------------------------------------------------------------
_STOP = {
    "o",
    "a",
    "os",
    "as",
    "um",
    "uma",
    "uns",
    "umas",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "e",
    "com",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "the",
    "of",
    "enemy",
    "mon",
    "inimigo",
    "inimigos",
    "grupo",
    "bando",
    "hostil",
    "hostis",
    "criatura",
    "criaturas",
    "alguns",
    "algumas",
    "par",
    "dois",
    "duas",
    "tres",
    "quatro",
    "horda",
    "matilha",
    "turba",
    "multidao",
    "ameaca",
    "inimiga",
    "inimigas",
    "agressor",
    "agressores",
    "atacante",
    "atacantes",
    "vulto",
    "vultos",
    "cinco",
    "seis",
}
_NUMBER_WORDS = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "par": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _singular(token: str) -> str:
    if len(token) <= 3:
        return token
    for plural, singular in (
        ("oes", "ao"),
        ("aes", "ao"),
        ("ais", "al"),
        ("eis", "el"),
        ("ois", "ol"),
        ("ns", "m"),
        ("res", "r"),
        ("zes", "z"),
    ):
        if token.endswith(plural):
            return token[: -len(plural)] + singular
    if token.endswith("s"):
        return token[:-1]
    return token


def name_tokens(text: str) -> list[str]:
    """Tokens de conteúdo normalizados (sem acento/caixa, singularizados)."""
    return [
        _singular(t)
        for t in re.split(r"[^a-z0-9]+", _fold(text))
        if t and t not in _STOP and not t.isdigit()
    ]


def _is_plural(text: str) -> bool:
    raw = [t for t in re.split(r"[^a-z0-9]+", _fold(text)) if t and t not in _STOP]
    return bool(raw) and raw[-1].endswith("s") and len(raw[-1]) > 3


def hint_count(text: str, *, maximum: int = 12) -> int:
    """Quantidade explícita na dica ('3 bandidos', 'dois lobos'); plural sem
    número → 2; singular → 1. Sempre limitada por `maximum`."""
    folded = _fold(text)
    digits = re.search(r"\b(\d{1,2})\b", folded)
    if digits:
        return max(1, min(maximum, int(digits.group(1))))
    for word in re.split(r"[^a-z0-9]+", folded):
        if word in _NUMBER_WORDS and word not in ("um", "uma"):
            return min(maximum, _NUMBER_WORDS[word])
    return 2 if _is_plural(text) else 1


def _bestiary() -> dict[str, dict]:
    import gamedata

    return dict(gamedata.BESTIARY or {})


def resolve_bestiary_name(text: str, bestiary: dict[str, dict] | None = None) -> str | None:
    """Nome livre → id do bestiário quando os tokens de conteúdo batem EXATAMENTE
    com o nome (ou o id) de uma entrada. Ambíguo → menor id (estável)."""
    wanted = tuple(sorted(set(name_tokens(text))))
    if not wanted:
        return None
    hits = []
    for bid, entry in (bestiary if bestiary is not None else _bestiary()).items():
        for label in (entry.get("name", ""), bid):
            if tuple(sorted(set(name_tokens(label)))) == wanted:
                hits.append(str(bid))
                break
    return sorted(hits)[0] if hits else None


def shares_identity(requested: str, resolved: str) -> bool:
    """Nome resolvido mantém a identidade pedida (≥1 token de conteúdo comum)."""
    return bool(set(name_tokens(requested)) & set(name_tokens(resolved)))


def is_generic_hint(text: str) -> bool:
    return not name_tokens(text)


# ---------------------------------------------------------------------------
# Fonte canônica (R3)
# ---------------------------------------------------------------------------
def resolve_canonical_source(
    state: dict[str, Any], combat_target: str | None, encounter_hint: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Ordem: (a) `enemy_id` do encontro sistêmico; (b) NPC em cena casado com
    o alvo do router; (c) alvo/ameaça já resolvida (alert/facção ou nome exato do
    bestiário). None → o chamador cai no scanner (d)."""
    bestiary = _bestiary()
    hint = dict(encounter_hint or {})
    enemy_id = str(hint.get("enemy_id") or "")
    if enemy_id and enemy_id in bestiary:
        reason = str(hint.get("reason") or "")
        source = "threat" if reason in {"reinforcements", "controlled"} else "systemic"
        return {
            "source": source,
            "kind": "bestiary",
            "target_ref": enemy_id,
            "groups": [(enemy_id, 1)],
        }

    target = str(combat_target or "").strip()
    ref = str(state.get("combat_target_ref") or "")
    if ref.startswith("npc:") or target:
        from services import npc_layers

        npcs = state.get("npcs") or {}
        in_scene = [name for name in npc_layers.npcs_in_scene(state) if name in npcs]
        wanted = ref[4:] if ref.startswith("npc:") else ""
        chosen = next((n for n in in_scene if wanted and n == wanted), None)
        if chosen is None and target:
            folded = _fold(target)
            chosen = next(
                (n for n in in_scene if _fold(n) in folded or (folded and folded in _fold(n))), None
            )
        if chosen:
            return {
                "source": "npc_in_scene",
                "kind": "npc",
                "target_ref": chosen,
                "npc_name": chosen,
            }

    if target and not is_generic_hint(target):
        bid = resolve_bestiary_name(target, bestiary)
        if bid:
            return {
                "source": "threat",
                "kind": "bestiary",
                "target_ref": bid,
                "groups": [(bid, hint_count(target))],
            }
    return None


# ---------------------------------------------------------------------------
# Manifesto
# ---------------------------------------------------------------------------
def _base_id(enemy_id: str) -> str:
    return re.sub(r"_\d+$", "", str(enemy_id or ""))


def species_label_for(enemy: dict[str, Any]) -> str:
    """Rótulo de espécie estável: nome do template (sem sufixo numérico)."""
    import gamedata

    base = _base_id(enemy.get("id", ""))
    entry = (gamedata.BESTIARY or {}).get(base) or {}
    if entry.get("name"):
        return str(entry["name"])
    return re.sub(r"\s+\d+$", "", str(enemy.get("name") or base or "Inimigo")).strip()


def _participant(
    enemy: dict[str, Any], *, presence: str = "present", zone_id: str = "z0", role: str = "hostile"
) -> dict[str, Any]:
    import gamedata

    base = _base_id(enemy.get("id", ""))
    bestiary_id = base if base in (gamedata.BESTIARY or {}) else str(enemy.get("bestiary_id") or "")
    status = str(enemy.get("status") or "ativo")
    if enemy.get("dead"):
        status = "morto"
    if status not in _STATUS_EVENT and status != "ativo":
        status = "ativo"
    return EncounterParticipant(
        participant_id=str(enemy.get("id") or enemy.get("name") or "enemy"),
        bestiary_id=bestiary_id,
        species_label=species_label_for(enemy),
        faction_id=str(enemy.get("faction_id") or enemy.get("faction") or ""),
        categoria=str(enemy.get("categoria") or "padrao"),
        role=role if role in ("hostile", "ally", "neutral", "hazard") else "hostile",
        presence=presence,
        zone_id=str(zone_id or "z0"),
        status=status,
    ).model_dump()


def event_id_for(encounter_id: str, kind: str, participant_id: str, round_: int) -> str:
    raw = f"{encounter_id}|{kind}|{participant_id}|{int(round_)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def build_manifest(
    enemies: Iterable[dict[str, Any]],
    *,
    source: str,
    origin: str,
    encounter_id: str,
    target_ref: str = "",
    scene: dict | None = None,
    joined_ids: Iterable[str] = (),
    cut_ids: Iterable[str] = (),
    cause_joined: str = "budget_fill",
    cause_cut: str = "budget_clamp",
) -> dict:
    """Congela o elenco do spawn. `joined_ids` (reforço regional) entram como
    `arrived` + evento `joined`; `cut_ids` só geram evento `cut`."""
    positions = (scene or {}).get("positions") or {}
    joined = set(joined_ids)
    participants = []
    for enemy in enemies:
        pid = str(enemy.get("id") or enemy.get("name") or "enemy")
        zone = (positions.get(pid) or {}).get("zone_id") or "z0"
        participants.append(
            _participant(enemy, presence="arrived" if pid in joined else "present", zone_id=zone)
        )
    manifest = EncounterManifest(
        encounter_id=str(encounter_id),
        origin=str(origin or "unknown"),
        source=source if source in Source.__args__ else "fallback",  # type: ignore[attr-defined]
        target_ref=str(target_ref or ""),
        participants=participants,
        events=[],
        frozen=True,
    ).model_dump(by_alias=True)
    for pid in sorted(joined):
        manifest = apply_composition(manifest, "joined", pid, cause_joined, 0)
    for pid in cut_ids:
        manifest = apply_composition(manifest, "cut", str(pid), cause_cut, 0)
    return manifest


def manifest_from_legacy(
    enemies: Iterable[dict[str, Any]], combat: dict[str, Any], *, game_id: str = "game"
) -> dict:
    """Save antigo/manifesto corrompido → manifesto `legacy_migrated` derivado de
    `enemies` (identidade = o que já estava persistido)."""
    encounter_id = str(combat.get("instance_id") or f"{game_id}:legacy")
    from services.combat_origin import normalize

    return build_manifest(
        list(enemies or []),
        source="legacy_migrated",
        origin=normalize(combat.get("origin")),
        encounter_id=encounter_id,
        scene=combat.get("scene"),
    )


def is_valid_manifest(manifest: Any) -> bool:
    if not isinstance(manifest, dict):
        return False
    try:
        EncounterManifest.model_validate(manifest)
    except Exception:
        return False
    return True


def apply_composition(
    manifest: dict, kind: str, participant_id: str, cause: str, round_: int
) -> dict:
    """Registra um evento de composição (idempotente por `event_id`)."""
    out = deepcopy(manifest)
    eid = event_id_for(out.get("encounter_id", ""), kind, participant_id, round_)
    if any(ev.get("event_id") == eid for ev in out.get("events") or []):
        return out
    out.setdefault("events", []).append(
        EncounterCompositionEvent(
            kind=kind,
            participant_id=str(participant_id),
            cause=str(cause),
            round=int(round_),
            event_id=eid,
        ).model_dump()
    )
    status = {
        "dead": "morto",
        "fled": "fugiu",
        "surrendered": "rendido",
        "captured": "capturado",
        "departed": "ausente",
        "incapacitated": "incapacitado",
    }.get(kind)
    for p in out.get("participants") or []:
        if p.get("participant_id") == participant_id:
            if status:
                p["status"] = status
            if kind == "departed":
                p["presence"] = "departed"
    return out


def assert_immutable(before: dict, after: dict) -> None:
    """R1: espécie/bestiário/facção/papel de participante existente não mudam."""
    old = {p["participant_id"]: p for p in before.get("participants") or []}
    for p in after.get("participants") or []:
        prev = old.get(p["participant_id"])
        if prev is None:
            continue
        for key in ("species_label", "bestiary_id", "faction_id", "role"):
            if prev.get(key) != p.get(key):
                raise ValueError(f"participante congelado mudou {key}: {p['participant_id']}")


def validate_roster(manifest: dict, enemies: Iterable[dict[str, Any]]) -> list[str]:
    """Violações do elenco da rodada contra o manifesto (vazio = ok)."""
    by_id = {p["participant_id"]: p for p in manifest.get("participants") or []}
    violations: list[str] = []
    for enemy in enemies or []:
        pid = str(enemy.get("id") or enemy.get("name") or "")
        part = by_id.get(pid)
        if part is None:
            violations.append(f"intruder:{pid}")
            continue
        if species_label_for(enemy) != part.get("species_label"):
            violations.append(f"species_drift:{pid}")
    return violations


def reconcile_roster(manifest: dict, enemies: list[dict[str, Any]], round_: int):
    """Produção: manifesto é a verdade. Intrusos saem com evento `cut`
    (`roster_violation`); participantes ativos sumidos ganham `departed`."""
    violations = validate_roster(manifest, enemies)
    if violations:
        log.warning("encounter.roster_violation %s", violations)
    intruders = {v.split(":", 1)[1] for v in violations if v.startswith("intruder:")}
    kept = [e for e in enemies if str(e.get("id") or e.get("name") or "") not in intruders]
    for pid in sorted(intruders):
        manifest = apply_composition(manifest, "cut", pid, "roster_violation", round_)
    present = {str(e.get("id") or e.get("name") or "") for e in kept}
    for p in manifest.get("participants") or []:
        if p.get("status") == "ativo" and p["participant_id"] not in present:
            manifest = apply_composition(
                manifest, "departed", p["participant_id"], "missing_from_roster", round_
            )
    return manifest, kept, violations


def sync_statuses(manifest: dict, enemies: Iterable[dict[str, Any]], round_: int) -> dict:
    """Pós-rodada: cada saída (morte/fuga/rendição/captura) vira evento."""
    for enemy in enemies or []:
        pid = str(enemy.get("id") or enemy.get("name") or "")
        status = str(enemy.get("status") or "ativo")
        if enemy.get("dead"):
            status = "morto"
        elif enemy.get("fled"):
            status = "fugiu"
        elif enemy.get("surrendered"):
            status = "rendido"
        elif enemy.get("captured"):
            status = "capturado"
        elif enemy.get("incapacitated"):
            status = "incapacitado"
        kind = _STATUS_EVENT.get(status)
        if not kind or kind == "departed":
            continue
        current = next(
            (p for p in manifest.get("participants") or [] if p["participant_id"] == pid), None
        )
        if current is None or current.get("status") != "ativo":
            continue
        manifest = apply_composition(manifest, kind, pid, "combat_round", round_)
    return manifest


# ---------------------------------------------------------------------------
# State machine (R5)
# ---------------------------------------------------------------------------
def transition(combat: dict[str, Any], to_phase: str, outcome: str | None = None) -> dict:
    current = combat.get("phase") or None
    if to_phase not in PHASES:
        raise InvalidEncounterTransition(f"fase desconhecida: {to_phase}")
    if to_phase not in _ALLOWED.get(current, set()):
        raise InvalidEncounterTransition(f"{current}->{to_phase}")
    if to_phase == "ended":
        if outcome not in OUTCOMES:
            raise InvalidEncounterTransition(f"outcome inválido: {outcome}")
        if current == "entering" and outcome not in _ENTERING_TO_ENDED_OUTCOMES:
            raise InvalidEncounterTransition(f"entering->ended exige expired/defeat: {outcome}")
    elif outcome is not None:
        raise InvalidEncounterTransition("outcome só em ended")
    out = dict(combat)
    out["phase"] = to_phase
    out["outcome"] = outcome if to_phase == "ended" else None
    return out


def safe_transition(combat: dict[str, Any], to_phase: str, outcome: str | None = None) -> dict:
    """Produção: transição inválida é registrada (log + `phase_violations`),
    nunca silenciosa e nunca derruba o turno."""
    try:
        return transition(combat, to_phase, outcome)
    except InvalidEncounterTransition as exc:
        log.warning("encounter.invalid_transition %s", exc)
        out = dict(combat)
        out["phase_violations"] = [*(combat.get("phase_violations") or []), str(exc)][-8:]
        return out


def end_combat(combat: dict[str, Any], outcome: str) -> dict:
    """Leva a fase até `ended` pelo caminho permitido a partir da atual."""
    phase = combat.get("phase") or None
    out = dict(combat)
    if phase is None:
        out = safe_transition(out, "entering")
        phase = "entering"
    if phase == "entering" and outcome not in _ENTERING_TO_ENDED_OUTCOMES:
        out = safe_transition(out, "active")
        phase = "active"
    if phase == "active":
        out = safe_transition(out, "resolving")
    if out.get("phase") == "ended":
        return out
    return safe_transition(out, "ended", outcome)


def next_step(combat: dict[str, Any]) -> str:
    """Próximo passo causal de uma fase (R11): combate ou exploração."""
    phase = (combat or {}).get("phase")
    if phase in ("entering", "active", "resolving") and (combat or {}).get("active", True):
        return "combat_agent"
    return "explore"


def normalize_combat(
    combat: Any, enemies: Iterable[dict[str, Any]] = (), *, game_id: str = "game"
) -> dict:
    """Normalização ADITIVA e idempotente no load (sem bump de schema): combate
    ativo sem manifesto válido ganha manifesto `legacy_migrated` + fase `active`;
    sem combate ativo ganha `phase=ended`/`outcome` preservado (default None)."""
    combat = dict(combat or {})
    if combat.get("active"):
        if not is_valid_manifest(combat.get("encounter")):
            if combat.get("encounter") is not None:
                log.warning("encounter.manifest_rebuilt game=%s", game_id)
            combat["encounter"] = manifest_from_legacy(enemies, combat, game_id=game_id)
        if combat.get("phase") not in ("entering", "active", "resolving"):
            combat["phase"] = "active"
            combat["outcome"] = None
    else:
        if combat.get("phase") != "ended":
            combat["phase"] = "ended"
        combat.setdefault("outcome", None)
        if combat.get("encounter") is not None and not is_valid_manifest(combat["encounter"]):
            combat.pop("encounter", None)
    return combat


# ---------------------------------------------------------------------------
# Views públicas (R7)
# ---------------------------------------------------------------------------
def _hidden_ids(scene: dict | None) -> set:
    hidden = set()
    for pid, pos in ((scene or {}).get("positions") or {}).items():
        if isinstance(pos, dict) and "player" in (pos.get("hidden_from") or []):
            hidden.add(str(pid))
    return hidden


def public_view(manifest: dict | None, scene: dict | None = None) -> dict:
    """Só campos públicos e participantes percebidos pelo protagonista."""
    if not manifest:
        return {}
    hidden = _hidden_ids(scene)
    return {
        "encounter_id": manifest.get("encounter_id", ""),
        "origin": manifest.get("origin", "unknown"),
        "participants": [
            {
                "participant_id": p["participant_id"],
                "species_label": p["species_label"],
                "categoria": p.get("categoria", "padrao"),
                "role": p.get("role", "hostile"),
                "presence": p.get("presence", "present"),
                "status": p.get("status", "ativo"),
            }
            for p in manifest.get("participants") or []
            if p["participant_id"] not in hidden
        ],
    }


def build_result(manifest: dict, outcome: str, ended_round: int, *, loot: bool = False) -> dict:
    """Snapshot persistido do desfecho (R7). `xp_event_ref` é carimbado pelo
    turn_finalizer com o `receipt_id` do turno de término (SPEC-199)."""
    encounter_id = manifest.get("encounter_id", "")
    result_event_id = hashlib.sha256(
        f"{encounter_id}|result|{outcome}|{int(ended_round)}".encode()
    ).hexdigest()[:16]
    return {
        "encounter_id": encounter_id,
        "outcome": outcome,
        "participants": [
            {
                "participant_id": p["participant_id"],
                "species_label": p["species_label"],
                "final_status": p.get("status", "ativo"),
            }
            for p in manifest.get("participants") or []
        ],
        "xp_event_ref": None,
        "loot_ref": f"loot:{encounter_id}" if loot else None,
        "ended_round": int(ended_round),
        "result_event_id": result_event_id,
    }


def result_view(combat: dict | None, turn_outcome: dict | None) -> dict:
    """`combat_result` derivado de estado persistido: aparece no turno de término
    (o `receipt_id` do último turno é o `xp_event_ref` do resultado) e, por isso,
    sobrevive a reload antes de "Continuar"."""
    combat = combat or {}
    result = combat.get("result") or {}
    if combat.get("phase") != "ended" or not result:
        return {}
    receipt = str((turn_outcome or {}).get("receipt_id") or "")
    if not receipt or result.get("xp_event_ref") != receipt:
        return {}
    return dict(result)
