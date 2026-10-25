"""
quest_log.py — Side quests persistentes (Fase 3.3).

Main quest = view derivada do campaign_plan (api.py). Side quests são estado novo
(`GameState.quests`), propostas pelo LLM (storyteller/npc_actor) e validadas/criadas
aqui — 100% Python determinístico, funções puras (dict novo, nunca mutam argumento).

Conclusão de quest reusa o pipeline de eventos estruturados (Fase 2.6): o LLM propõe
`ProposedWorldEvent(type="quest_completed", target_id=<quest_id>, payload={"quest_id":
...})`; `services/event_processor.py` chama `complete_quest` quando o evento é aplicado.
Falha sistêmica (`fail_orphan_quests`) roda após `npc_killed` aplicado — 100% sistêmico,
nunca passa pelo pipeline de propostas do LLM (`source="system"`).

Spec: specs/SPEC-008-fase-3.3-quest-log.md §3.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
import uuid
from typing import Dict, List, Tuple, Union

import gamedata
from observability.telemetry import log_event as _log_event
from services import graph_resolver as gr

MAX_ACTIVE_QUESTS = 8
_LORE_KINDS = frozenset(
    {"cacar_criatura", "entregar_material", "escoltar", "investigar_rumor", "recolher_mortos"}
)
# SPEC-313 R19: tipos cuja conclusao so o motor prova (combate, inventario, chegada)
_MECHANICAL = frozenset({"cacar_criatura", "entregar_material", "escoltar"})
TITLE_SIMILARITY = 0.75
QUEST_REWARD_GOLD = 20
# SPEC-301 R12: missão de fação paga por tier (no lugar do QUEST_REWARD_GOLD fixo).
MISSION_GOLD = {1: 20, 2: 35, 3: 50}
# SPEC-223 (revisão Sol): evidência exige VERBO de ação investigativa/interação.
# A mera palavra "missão"/"pista" (ou "marque a missão como concluída") não
# conta — senão a própria injeção viraria prova de investigação.
QUEST_ACTION_RE = re.compile(
    r"\b(?:investig|procur|examin|rastre|interrog|pergunt|vasculh|averigu|"
    r"inspecion|analis|busc(?:o|a|ar|amos|ando)\b|sig(?:o|a|amos)\b|"
    r"segu(?:ir|imos|indo)\b)",
    re.IGNORECASE,
)


def _as_dict(proposal: dict | object) -> dict:
    """Normaliza ProposedQuest (Pydantic) ou dict cru pro mesmo formato."""
    if hasattr(proposal, "model_dump"):
        return proposal.model_dump()
    return dict(proposal or {})


def _valid_location_ids() -> set:
    locations = (gamedata.WORLD_MAP or {}).get("locations", [])
    return {loc.get("id") for loc in locations if isinstance(loc, dict) and loc.get("id")}


def _valid_entity_ids() -> set:
    try:
        return set(gr.load_entities().keys())
    except Exception:
        return set()


def _vocab_match(kind: str, text: str) -> bool:
    """SPEC-305 R11: o texto casa o vocabulario de acao do tipo de quest de mundo."""
    from services import world_quests

    stems = world_quests.action_vocab(kind)
    folded = _fold_name(text)
    return bool(stems) and any(re.search(r"\b" + re.escape(stem), folded) for stem in stems)


def _duplicates_world_quest(
    proposal: dict, title: str, location_id: str, active: list[dict]
) -> bool:
    """SPEC-305 R10: proposta do LLM no alvo de quest de mundo ativa, com titulo parecido
    (>= TITLE_SIMILARITY) ou texto no vocabulario do tipo, e duplicata."""
    text = f"{title} {proposal.get('description') or ''}"
    for q in active:
        if not q.get("world_kind") or q.get("location_id") != location_id:
            continue
        similar = (
            difflib.SequenceMatcher(None, title.lower(), str(q.get("title", "")).lower()).ratio()
            >= TITLE_SIMILARITY
        )
        if similar or _vocab_match(str(q["world_kind"]), text):
            return True
    return False


def register_proposed_quests(
    quests: list[dict], proposals: list, *, turn: int = 0
) -> tuple[list[dict], list[dict]]:
    """PURO. Valida/cria side quests a partir de propostas do LLM.

    Retorna (lista_nova, criadas). Regras (nunca levanta, só ignora ou zera campo):
    - título vazio -> ignora
    - similaridade de título (SequenceMatcher >= 0.75) contra quests ATIVAS -> ignora
    - location_id fora de data/world_map.json -> ""
    - origin_entity_id fora do grafo canônico -> ""
    - já no teto de ativas (MAX_ACTIVE_QUESTS) -> ignora com log
    """
    quests = list(quests or [])
    created: list[dict] = []
    if not proposals:
        return quests, created

    valid_locs = _valid_location_ids()
    valid_entities = _valid_entity_ids()

    for raw in proposals:
        p = _as_dict(raw)
        title = str(p.get("title") or "").strip()
        if not title:
            continue

        active_titles = [q for q in quests if q.get("status") == "active"]
        if any(
            difflib.SequenceMatcher(None, title.lower(), q.get("title", "").lower()).ratio()
            >= TITLE_SIMILARITY
            for q in active_titles
        ):
            _log_event("quest", "proposal_duplicate_ignored", level="info")
            continue

        if len(active_titles) >= MAX_ACTIVE_QUESTS:
            _log_event("quest", "active_cap_reached", level="info", cap=MAX_ACTIVE_QUESTS)
            continue

        location_id = str(p.get("location_id") or "")
        if location_id and location_id not in valid_locs:
            location_id = ""

        # SPEC-305 R10: o LLM nao reinventa uma quest de mundo ja ativa naquele alvo.
        if location_id and _duplicates_world_quest(p, title, location_id, active_titles):
            _log_event("quest", "proposal_world_duplicate", level="info")
            continue
        origin_entity_id = str(p.get("origin_entity_id") or "")
        if origin_entity_id and origin_entity_id not in valid_entities:
            origin_entity_id = ""

        quest = {
            "id": uuid.uuid4().hex,
            "title": title,
            "description": str(p.get("description") or ""),
            "status": "active",
            "origin_name": str(p.get("origin_name") or ""),
            "origin_entity_id": origin_entity_id,
            "location_id": location_id,
            "created_turn": int(turn),
            "resolved_turn": 0,
            "reward_hint": str(p.get("reward_hint") or ""),
            "progress_log": [{"kind": "created", "turn": int(turn), "detail": ""}],
            "reward_gold": 0,
            "reward_delivered": False,
        }
        quests = quests + [quest]
        created.append(quest)

    return quests, created


def complete_quest(quests: list[dict], quest_id: str, turn: int = 0) -> list[dict]:
    """PURO. Quest ATIVA com esse id -> completed. Id ausente/já resolvida -> sem mudança."""
    out = []
    for q in quests or []:
        if q.get("id") == quest_id and q.get("status") == "active":
            q = {**q, "status": "completed", "resolved_turn": int(turn)}
        out.append(q)
    return out


def sync_location_progress(quests: list[dict], location_id: str, *, turn: int = 0) -> list[dict]:
    """Registra chegada ao alvo uma única vez, sem concluir a missão."""
    out: list[dict] = []
    for original in quests or []:
        q = dict(original)
        progress = list(q.get("progress_log") or [])
        if (
            q.get("status") == "active"
            and location_id
            # SPEC-301 (P1-1): missão de fação criada neste turno não nasce "alcançada"
            and not (q.get("faction_id") and _safe_turn(q.get("created_turn")) >= int(turn))
            and q.get("location_id") == location_id
            and not any(row.get("kind") == "location_reached" for row in progress)
        ):
            progress.append(
                {"kind": "location_reached", "turn": int(turn), "detail": str(location_id)}
            )
            q["progress_log"] = progress
        out.append(q)
    return out


def _normalized_words(value: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", str(value or ""))
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    return {word for word in re.findall(r"[a-z0-9]+", plain.casefold()) if len(word) >= 4}


FINGERPRINT_JACCARD = 0.6  # SPEC-226 R6 (D-B): similaridade máxima p/ "ação distinta"


def normalize_fingerprint(action: str) -> frozenset:
    """Tokens (>= 4 chars) sem acento/pontuação — insensível a caixa e pontuação."""
    text = unicodedata.normalize("NFKD", str(action or "")).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    words = re.findall(r"[a-z0-9]+", text)
    tokens = frozenset(w for w in words if len(w) >= 4)
    return tokens or frozenset(words)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _is_distinct(tokens: frozenset, existing: list) -> bool:
    return all(
        _jaccard(tokens, normalize_fingerprint(str(fp or ""))) < FINGERPRINT_JACCARD
        for fp in existing
    )


def sync_action_progress(
    quests: list[dict],
    location_id: str,
    action_text: str,
    *,
    turn: int = 0,
) -> tuple[list[dict], list[str]]:
    """Registra investigação verificável e sinaliza conclusão determinística.

    A ação precisa ocorrer no local-alvo já alcançado, conter um verbo de busca
    e citar a missão (título/descrição) ou usar vocabulário explícito de missão.
    Duas ações distintas fecham o objetivo; repetição literal é idempotente.
    """
    action = " ".join(str(action_text or "").split())[:240]
    generic_verb = bool(QUEST_ACTION_RE.search(action)) if action else False
    has_world = any(q.get("world_kind") and q.get("status") == "active" for q in quests or [])
    if not action or not (generic_verb or has_world):
        return [dict(q) for q in (quests or [])], []
    action_words = _normalized_words(action)
    generic_reference = bool(
        action_words & {"missao", "pista", "investigo", "investigar", "retomo"}
    )
    ready_ids: list[str] = []
    out: list[dict] = []
    fp_tokens = normalize_fingerprint(action)
    fingerprint = " ".join(sorted(fp_tokens))
    for original in quests or []:
        q = dict(original)
        progress = [dict(row) for row in (q.get("progress_log") or [])]
        quest_words = _normalized_words(f"{q.get('title', '')} {q.get('description', '')}")
        world_kind = q.get("world_kind")
        if world_kind in _MECHANICAL:
            out.append(q)  # SPEC-313 R19: nenhuma "investigacao" conclui caca/entrega/escolta
            continue
        if world_kind:
            # SPEC-305 R11: quest de mundo troca o verbo investigativo e a relevancia por
            # titulo pelo vocabulario de acao do proprio tipo.
            verb_ok = relevant = _vocab_match(str(world_kind), action)
        else:
            verb_ok = generic_verb
            relevant = generic_reference or bool(action_words & quest_words)
        reached = any(row.get("kind") == "location_reached" for row in progress)
        already_ready = bool(q.get("completion_ready"))
        fresh = int(q.get("created_turn", -1) or -1) < int(turn)
        if (
            q.get("status") == "active"
            and not q.get("personal_of")  # SPEC-300: missão pessoal é do motor
            and verb_ok
            and q.get("location_id") == location_id
            and reached
            and relevant
            and fresh
            and not already_ready
        ):
            if _is_distinct(
                fp_tokens,
                [row.get("fingerprint") for row in progress if row.get("kind") == "investigation"],
            ):
                progress.append(
                    {
                        "kind": "investigation",
                        "turn": int(turn),
                        "detail": action,
                        "fingerprint": fingerprint,
                    }
                )
            distinct: list[frozenset] = []
            for row in progress:
                if row.get("kind") != "investigation":
                    continue
                toks = normalize_fingerprint(str(row.get("fingerprint") or ""))
                if all(_jaccard(toks, d) < FINGERPRINT_JACCARD for d in distinct):
                    distinct.append(toks)
            investigations = distinct
            # SPEC-305: vitoria em combate no alvo vale 1 evidencia distinta por combate.
            combats = {
                _safe_turn(row.get("turn")) for row in progress if row.get("kind") == "combat_won"
            }
            if len(investigations) + len(combats) >= 2:
                q["completion_ready"] = True
                progress.append(
                    {
                        "kind": "completion_ready",
                        "turn": int(turn),
                        "detail": "objetivo verificado por ações distintas",
                    }
                )
                ready_ids.append(str(q.get("id") or ""))
            q["progress_log"] = progress
        out.append(q)
    return out, [quest_id for quest_id in ready_ids if quest_id]


# --- SPEC-223 R1: prova determinística p/ conclusão proposta pelo LLM ------------
PROOF_EVIDENCE_KINDS = (
    "investigation",
    "npc_interaction",
    "completion_ready",
    "combat_won",
    "hunt_kill",
)


def _fold_name(value: object) -> str:
    folded = unicodedata.normalize("NFKD", str(value or ""))
    plain = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " ".join(plain.casefold().split())


def sync_npc_interaction(quests: list[dict], npc_name: str, *, turn: int = 0) -> list[dict]:
    """PURO. Conversa real com o NPC de ORIGEM de uma quest ativa vira evidência
    (`npc_interaction`) — 1 linha por turno, nunca no turno de criação."""
    who = _fold_name(npc_name)
    out: list[dict] = []
    for original in quests or []:
        q = dict(original)
        progress = list(q.get("progress_log") or [])
        if (
            who
            and q.get("status") == "active"
            and _fold_name(q.get("origin_name")) == who
            and _safe_turn(q.get("created_turn")) < int(turn)
            and not any(
                row.get("kind") == "npc_interaction" and _safe_turn(row.get("turn")) == int(turn)
                for row in progress
                if isinstance(row, dict)
            )
        ):
            progress.append(
                {"kind": "npc_interaction", "turn": int(turn), "detail": str(npc_name)[:60]}
            )
            q["progress_log"] = progress
        out.append(q)
    return out


def _safe_turn(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def has_completion_proof(quest: dict, state: dict) -> tuple[bool, str]:
    """SPEC-223 R1 (D-A default (a)+(b)+(c)). PURO.

    (a) quest com alvo: `progress_log` tem `location_reached`;
    (b) evidência Python posterior à criação (investigação, conversa com a
        origem, objetivo verificado);
    (c) a quest não foi criada neste turno e segue ativa.
    Quest sem local-alvo exige (b) do tipo `npc_interaction` (entrega à origem).
    """
    turn = _safe_turn(((state or {}).get("world") or {}).get("turn_count", 0))
    if not isinstance(quest, dict) or quest.get("status") != "active":
        return False, "quest não está ativa"
    if quest.get("personal_of"):  # SPEC-300 R22: missão pessoal só o motor conclui
        return False, "missão pessoal é concluída pelo motor"
    if quest.get("world_kind") in _MECHANICAL:  # SPEC-313 R19: caça/entrega/escolta = motor
        return False, "prova mecânica: só o motor conclui"
    created = _safe_turn(quest.get("created_turn"))
    if created >= turn:
        return False, "quest criada neste turno"
    rows = [row for row in (quest.get("progress_log") or []) if isinstance(row, dict)]
    evidence = [
        row
        for row in rows
        if row.get("kind") in PROOF_EVIDENCE_KINDS and created < _safe_turn(row.get("turn")) <= turn
    ]
    if quest.get("location_id"):
        if not any(row.get("kind") == "location_reached" for row in rows):
            return False, "sem chegada ao local da missão"
        if not evidence:
            return False, "sem evidência de investigação/entrega"
        return True, ""
    if not any(row.get("kind") == "npc_interaction" for row in evidence):
        return False, "sem entrega/conversa com a origem da missão"
    return True, ""


def complete_quest_with_reward(
    quests: list[dict], quest_id: str, turn: int = 0
) -> tuple[list[dict], int]:
    """Conclui e materializa a recompensa fixa uma vez. Retorna ouro concedido."""
    out: list[dict] = []
    reward = 0
    for original in quests or []:
        q = dict(original)
        if q.get("id") == quest_id and q.get("status") == "active":
            progress = list(q.get("progress_log") or [])
            progress.append({"kind": "completed", "turn": int(turn), "detail": ""})
            gold = QUEST_REWARD_GOLD
            if q.get("world_kind") in _LORE_KINDS and "reward_gold_planned" in q:
                gold = max(0, _safe_turn(q.get("reward_gold_planned")))  # SPEC-313 R15
            elif q.get("faction_id"):
                tier = max(1, min(3, _safe_turn(q.get("mission_tier")) or 1))
                gold = MISSION_GOLD[tier]
            q.update(
                {
                    "status": "completed",
                    "resolved_turn": int(turn),
                    "progress_log": progress,
                    "reward_gold": gold,
                    "reward_delivered": True,
                }
            )
            reward = gold
        out.append(q)
    return out, reward


def fail_orphan_quests(
    quests: list[dict], dead_entity_id: str, turn: int = 0
) -> tuple[list[dict], list[dict]]:
    """PURO. Quests ATIVAS com origin_entity_id == dead_entity_id -> failed.

    Retorna (lista_nova, eventos `quest_failed` — 1 por quest, source="system").
    Id vazio nunca casa (quest sem origem canônica não falha sistemicamente).
    """
    if not dead_entity_id:
        return list(quests or []), []
    out = []
    events: list[dict] = []
    for q in quests or []:
        if q.get("status") == "active" and q.get("origin_entity_id") == dead_entity_id:
            q = {**q, "status": "failed", "resolved_turn": int(turn)}
            events.append(
                {
                    "event_id": uuid.uuid4().hex,
                    "turn": int(turn),
                    "type": "quest_failed",
                    "actor_id": "system",
                    "target_id": dead_entity_id,
                    "payload": {
                        "quest_id": q["id"],
                        "quest_title": q.get("title", ""),
                        "reason": "origin_killed",
                    },
                    "source": "system",
                }
            )
        out.append(q)
    return out, events


def sync_combat_progress(quests: list[dict], location_id: str, *, turn: int = 0) -> list[dict]:
    """SPEC-305 R11. PURO. Vitoria de combate no alvo de quest de mundo cujo tipo conta
    combate = 1 evidencia (`combat_won`), 1 por combate/turno, nunca no turno de criacao."""
    from services import world_quests

    out: list[dict] = []
    for original in quests or []:
        q = dict(original)
        kind = q.get("world_kind")
        progress = list(q.get("progress_log") or [])
        if (
            kind
            and q.get("status") == "active"
            and location_id
            and q.get("location_id") == location_id
            and world_quests.combat_counts(str(kind))
            and any(row.get("kind") == "location_reached" for row in progress)
            and _safe_turn(q.get("created_turn")) < int(turn)
            and not any(
                row.get("kind") == "combat_won" and _safe_turn(row.get("turn")) == int(turn)
                for row in progress
            )
        ):
            progress.append({"kind": "combat_won", "turn": int(turn), "detail": str(location_id)})
            q["progress_log"] = progress
        out.append(q)
    return out


def sync_hunt_progress(
    quests: list[dict], dead_bestiary_ids: list[str], region_id: str, *, turn: int = 0
) -> list[dict]:
    """SPEC-313 R20. PURO. Vitoria de combate em que morreu a criatura-ancora de uma
    `cacar_criatura` ativa da regiao = evidencia `hunt_kill` (1 por quest). Nunca no turno de
    criacao."""
    dead = {str(i) for i in dead_bestiary_ids or [] if i}
    out: list[dict] = []
    for original in quests or []:
        q = dict(original)
        anchor = q.get("lore_anchor") or {}
        progress = list(q.get("progress_log") or [])
        if (
            q.get("world_kind") == "cacar_criatura"
            and q.get("status") == "active"
            and str(anchor.get("id")) in dead
            and (not anchor.get("region_id") or anchor.get("region_id") == region_id)
            and _safe_turn(q.get("created_turn")) < int(turn)
            and not any(row.get("kind") == "hunt_kill" for row in progress)
        ):
            progress.append(
                {"kind": "hunt_kill", "turn": int(turn), "detail": str(anchor.get("id"))}
            )
            q["progress_log"] = progress
        out.append(q)
    return out


def _close_quest(
    quests: list[dict], quest_id: str, status: str, turn: int, reason: str, day: int
) -> list[dict]:
    out: list[dict] = []
    for original in quests or []:
        q = dict(original)
        if q.get("id") == quest_id and q.get("status") == "active":
            progress = list(q.get("progress_log") or [])
            progress.append({"kind": status, "turn": int(turn), "detail": reason})
            note = str(q.get("fail_text") or "").strip()
            desc = str(q.get("description") or "")
            if note and note not in desc:
                desc = f"{desc} {note}".strip()
            q.update(
                {
                    "status": status,
                    "resolved_turn": int(turn),
                    "resolved_day": int(day),
                    "fail_reason": reason,
                    "progress_log": progress,
                    "description": desc,
                }
            )
        out.append(q)
    return out


def fail_quest(
    quests: list[dict], quest_id: str, turn: int, reason: str, day: int = 0
) -> list[dict]:
    """SPEC-305 R15. PURO. Quest ATIVA -> failed (idempotente: id ausente/ja resolvida = igual).
    O texto de falha vem do template gravado na criacao (neutro, R18)."""
    return _close_quest(quests, quest_id, "failed", turn, reason, day)


def expire_quest(quests: list[dict], quest_id: str, turn: int, day: int = 0) -> list[dict]:
    """SPEC-305 R16/R19. PURO. A fonte acabou sozinha: quest ativa -> expired, sem falha."""
    return _close_quest(quests, quest_id, "expired", turn, "superada", day)


def deadline_label(days_left: int | None, status: str = "active") -> str:
    """SPEC-305 R21: rotulo vago de prazo, sem numero. `failed`/`expired` = mesmo rotulo."""
    if status in ("failed", "expired"):
        return "prazo esgotado"
    if days_left is None:
        return ""
    if days_left <= 2:
        return "urgente"
    if days_left <= 5:
        return "em poucos dias"
    return "há algum tempo"


_PUBLIC_QUEST_FIELDS = (
    "id",
    "title",
    "description",
    "status",
    "origin_name",
    "origin_entity_id",
    "location_id",
    "created_turn",
    "resolved_turn",
    "reward_hint",
)


def public_quest_view(quest: dict, day: int) -> dict:
    """SPEC-305 R20: LISTA BRANCA da quest para a API. Campos internos (prazo exato,
    `world_source_id`, `heard_via`, `origin_faction_id`, `fail_reason`, `world_kind`...)
    nunca saem por aqui."""
    view = {
        k: quest.get(k, "" if k not in ("created_turn", "resolved_turn") else 0)
        for k in _PUBLIC_QUEST_FIELDS
    }
    world = bool(quest.get("world_kind"))
    view["kind"] = "mundo" if world else ("faccao" if quest.get("mission_kind") else "comum")
    status = str(quest.get("status") or "")
    if world and status in ("failed", "expired"):
        # R21 (revisao P1-1): status publico UNICO — o jogador nao infere se a fonte
        # acabou sozinha ou seguiu adiante.
        status = view["status"] = "expired"
    left: int | None = None
    if world and status == "active" and quest.get("deadline_day") is not None:
        left = _safe_turn(quest.get("deadline_day")) - int(day)
    label = deadline_label(left, status) if world else ""
    if label:
        view["deadline_label"] = label
    if world and quest.get("world_kind") == "investigar_rumor":
        from services.lore_quests import outcome_label

        outcome = outcome_label(quest)  # SPEC-313 R28: so depois de concluida
        if outcome:
            view["outcome_label"] = outcome
    return view


def quest_markers(quests: list[dict]) -> list[dict]:
    """Quests ativas com local válido -> [{"quest_id", "location_id"}] pro mapa."""
    return [
        {"quest_id": q["id"], "location_id": q["location_id"]}
        for q in (quests or [])
        if q.get("status") == "active" and q.get("location_id")
    ]
