"""
world_validators.py — Valida propostas de evento contra o grafo e o estado (Fase 2.6).

Uma proposta (`dict`, vinda de `pending_world_events`) só vira `GameEvent` se
`validate_proposal` devolver `ok=True`. Rejeição NÃO quebra o turno — o processor
descarta com log. Revalida do zero via Pydantic (defesa em profundidade: o LLM pode
ter inventado id/tipo mesmo com o bloco <ENTIDADES_CANONICAS> no prompt).

Spec: specs/SPEC-003-fase-2.6-structured-events.md §3.
"""

from __future__ import annotations

from typing import NamedTuple

from services import graph_resolver as gr
from services.structured_outputs import ProposedWorldEvent


class ValidationResult(NamedTuple):
    ok: bool
    reason: str = ""


# --- validadores por tipo ---------------------------------------------------
# Cada um recebe (ev: ProposedWorldEvent, state: dict, projection: dict) e devolve
# ValidationResult. A checagem comum (Pydantic, entidade-alvo, duplicata) roda antes.


def _v_npc_killed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    ent = gr.get_entity(ev.target_id)
    if not ent:
        return ValidationResult(False, f"id desconhecido em entities.json: {ev.target_id}")
    if ent.get("type") != "npc":
        return ValidationResult(False, f"{ev.target_id} não é do type npc (é {ent.get('type')})")
    if not gr.is_alive(ev.target_id, proj):
        return ValidationResult(False, f"{ev.target_id} já está morto")
    return ValidationResult(True)


def _v_secret_revealed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    if not gr.get_entity(ev.target_id):
        return ValidationResult(False, f"id desconhecido em entities.json: {ev.target_id}")
    # existe edge hidden/secret ligada ao alvo? (o segredo tem de EXISTIR no grafo)
    edges = gr.resolve_edges(proj, entity_id=ev.target_id, include_hidden=True)
    if not any(e.get("visibility") in ("hidden", "secret") for e in edges):
        return ValidationResult(
            False, f"nenhum segredo (edge hidden/secret) ligado a {ev.target_id}"
        )
    # fato ainda não revelado?
    revealed = proj.get("revealed_facts", {}) or {}
    if any(rf.get("entity_id") == ev.target_id for rf in revealed.values()):
        return ValidationResult(False, f"segredo de {ev.target_id} já revelado")
    return ValidationResult(True)


def _v_location_control_changed(
    ev: ProposedWorldEvent, state: dict, proj: dict
) -> ValidationResult:
    ent = gr.get_entity(ev.target_id)
    if not ent:
        return ValidationResult(False, f"id desconhecido em entities.json: {ev.target_id}")
    if ent.get("type") != "location":
        return ValidationResult(False, f"{ev.target_id} não é do type location")
    ncid = ev.payload.get("new_controller_id")
    if not ncid:
        return ValidationResult(False, "payload.new_controller_id ausente")
    nc = gr.get_entity(ncid)
    if not nc or nc.get("type") != "faction":
        return ValidationResult(False, f"new_controller_id {ncid} não é uma facção conhecida")
    if not gr.is_alive(ncid, proj):
        return ValidationResult(False, f"facção {ncid} está derrotada")
    return ValidationResult(True)


def _v_quest_completed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    # Fase 3.3: side quest — payload.quest_id aponta pra GameState.quests (não pro grafo).
    qid = ev.payload.get("quest_id")
    if qid:
        ativas = {q.get("id") for q in state.get("quests", []) or [] if q.get("status") == "active"}
        if qid in ativas:
            return ValidationResult(True)
        return ValidationResult(False, f"quest_id {qid} não é uma quest ativa")
    # Modo beat (Fase 2.6, comportamento original — sem quest_id no payload).
    plan = state.get("campaign_plan") or {}
    beats = plan.get("beats") or []
    if not beats:
        return ValidationResult(False, "sem campaign_plan/beats para concluir")
    idx = ev.payload.get("beat_index")
    if idx is not None and not (0 <= int(idx) < len(beats)):
        return ValidationResult(False, f"beat_index {idx} fora do plano (0..{len(beats) - 1})")
    return ValidationResult(True)


def _v_quest_failed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """SPEC-305 R15: falha validada (so o motor chega aqui). A quest precisa estar ATIVA:
    uma quest nunca recebe duas falhas."""
    qid = ev.payload.get("quest_id") or ev.target_id
    quest = next(
        (q for q in state.get("quests", []) or [] if isinstance(q, dict) and q.get("id") == qid),
        None,
    )
    if quest is None or quest.get("status") != "active":
        return ValidationResult(False, f"quest_id {qid} não é uma quest ativa")
    return ValidationResult(True)


def _v_world_quest_relief(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    # SPEC-305 R13: derivado do event_processor; nunca uma proposta validavel.
    return ValidationResult(False, "alívio de quest é um fato gerado pelo motor, não proposto")


def _v_faction_relation_changed(
    ev: ProposedWorldEvent, state: dict, proj: dict
) -> ValidationResult:
    other = ev.payload.get("other_faction_id") or ev.actor_id
    a, b = gr.get_entity(ev.target_id), gr.get_entity(other)
    if not a or a.get("type") != "faction":
        return ValidationResult(False, f"{ev.target_id} não é facção")
    if not b or b.get("type") != "faction":
        return ValidationResult(False, f"{other} não é facção")
    relation = ev.payload.get("relation") or ev.detail
    if relation not in gr.load_relation_types():
        return ValidationResult(False, f"relação desconhecida: {relation!r}")
    return ValidationResult(True)


def _v_reputation_changed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """Fase 3.4: evento enfileirado pelo Python (storyteller), não pelo LLM — a
    validação aqui é sanidade (fação existe/viva), não gate de alucinação."""
    f = gr.get_entity(ev.target_id)
    if not f or f.get("type") != "faction":
        return ValidationResult(False, f"{ev.target_id} não é facção")
    if not gr.is_alive(ev.target_id, proj):
        return ValidationResult(False, f"facção {ev.target_id} está derrotada")
    return ValidationResult(True)


def _v_faction_deed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """SPEC-298 R11: a fação existe, está viva e está *em cena* (controla o local
    atual, tem NPC presente ou quest ativa de origem). Direção/magnitude fechadas."""
    f = gr.get_entity(ev.target_id)
    if not f or f.get("type") != "faction":
        return ValidationResult(False, f"{ev.target_id} não é facção")
    if not gr.is_alive(ev.target_id, proj):
        return ValidationResult(False, f"facção {ev.target_id} está derrotada")
    if ev.payload.get("direction") not in ("ajudou", "prejudicou"):
        return ValidationResult(False, "payload.direction inválido (use ajudou|prejudicou)")
    if ev.payload.get("magnitude", "menor") not in ("menor", "maior"):
        return ValidationResult(False, "payload.magnitude inválido (use menor|maior)")
    from services import reputation

    if not reputation.faction_in_scene(state, ev.target_id, proj):
        return ValidationResult(False, f"facção {ev.target_id} não está em cena")
    return ValidationResult(True)


def _v_faction_membership_changed(
    ev: ProposedWorldEvent, state: dict, proj: dict
) -> ValidationResult:
    """SPEC-301: evento do motor. Sanidade: fação do catálogo e ação do enum fechado."""
    from services import faction_membership as fm

    if ev.target_id not in fm.load_catalog():
        return ValidationResult(False, f"{ev.target_id} não é fação com vínculo")
    if ev.payload.get("action") not in fm.ACTIONS:
        return ValidationResult(False, "payload.action inválido")
    return ValidationResult(True)


def _v_level_up(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """Fase 4.1: evento do motor (grant_xp). O gate anti-LLM (source='progression')
    fica em validate_proposal; aqui só sanidade do payload."""
    if ev.target_id != "player" or ev.actor_id != "player":
        return ValidationResult(False, "level_up é sempre do player")
    if not isinstance(ev.payload.get("new_level"), int):
        return ValidationResult(False, "payload.new_level ausente/inválido")
    return ValidationResult(True)


def _v_progression_choice(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    del state, proj
    if ev.actor_id != "player":
        return ValidationResult(False, "evento de progressão exige actor player")
    return ValidationResult(bool(ev.target_id), "target de progressão ausente")


def _route_pair_blocked(proj: dict, a: str, b: str) -> bool:
    pair = frozenset((a, b))
    return any(
        frozenset((r.get("a"), r.get("b"))) == pair
        for r in (proj or {}).get("blocked_routes", []) or []
    )


def _v_route_blocked(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """Fase 6.1: rota só existe entre locais DIRETAMENTE conectados no mapa."""
    from gamedata import get_location

    a = ev.target_id
    b = str(ev.payload.get("other_location_id") or "")
    if not get_location(a):
        return ValidationResult(False, f"{a} não é local do mapa")
    if not b or not get_location(b):
        return ValidationResult(False, f"{b!r} não é local do mapa")
    if b not in (get_location(a).get("connections") or []):
        return ValidationResult(False, f"{a} e {b} não têm conexão direta")
    if _route_pair_blocked(proj, a, b):
        return ValidationResult(False, f"rota {a}↔{b} já está bloqueada")
    return ValidationResult(True)


def _v_route_cleared(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    a = ev.target_id
    b = str(ev.payload.get("other_location_id") or "")
    if not _route_pair_blocked(proj, a, b):
        return ValidationResult(False, f"rota {a}↔{b} não está bloqueada")
    return ValidationResult(True)


def _v_unique_item(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """Fase 6.2: gate de source fica em validate_proposal; aqui sanidade do item."""
    from gamedata import ARTIFACTS_DB

    item = ARTIFACTS_DB.get(ev.target_id)
    if not item:
        return ValidationResult(False, f"{ev.target_id} não existe no ARTIFACTS_DB")
    if not item.get("unique"):
        return ValidationResult(False, f"{ev.target_id} não é item único")
    return ValidationResult(True)


def _v_companion_event(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """SPEC-300: gate de source fica em validate_proposal; o alvo precisa ter alma."""
    if ev.target_id not in (state.get("companion_souls") or {}):
        return ValidationResult(
            False, f"id desconhecido: {ev.target_id} não é um companheiro com alma"
        )
    return ValidationResult(True)


def _v_player_died(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """Fase 4.6: evento do motor (combate) — gate anti-LLM em validate_proposal."""
    if ev.target_id != "player":
        return ValidationResult(False, "player_died é sempre do player")
    return ValidationResult(True)


def _v_player_downed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """spec balanceamento-early-game (R3): O Saque é 1x por campanha e só do motor."""
    if ev.target_id != "player":
        return ValidationResult(False, "player_downed é sempre do player")
    for e in state.get("event_log") or []:
        if isinstance(e, dict) and e.get("type") == "player_downed":
            return ValidationResult(False, "player_downed já ocorreu nesta campanha (1x)")
    return ValidationResult(True)


# --- SPEC-223: prova determinística p/ eventos propostos pelo LLM ---------------
# Fontes do MOTOR (Python) — tudo o mais (sem `source`, ou "storyteller") é
# proposta do LLM e precisa de prova no estado antes de virar fato.
ENGINE_SOURCES = frozenset(
    {
        "system",
        "combat",
        "rule_engine",
        "engine",
        "progression",
        "trap",
    }
)
PROOF_REQUIRED_TYPES = frozenset({"quest_completed", "secret_revealed", "npc_killed"})
UNPROVEN_PREFIX = "sem prova determinística"
LIMIT_PREFIX = "limite de conclusões"
QUEST_COMPLETION_COOLDOWN = 3  # turnos entre conclusões propostas pelo LLM


def is_engine_proposal(proposal: dict) -> bool:
    return str((proposal or {}).get("source") or "") in ENGINE_SOURCES


def _turn_of(state: dict) -> int:
    try:
        return int((state.get("world") or {}).get("turn_count", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _fold(value: object) -> str:
    import unicodedata

    folded = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(c for c in folded if not unicodedata.combining(c)).casefold().split())


def scene_anchor_ids(state: dict) -> set:
    """Ids canônicos ANCORADOS na cena atual: local atual + NPCs `in_scene`."""
    from services.entity_identity import resolve_npc_entity_id

    world = state.get("world") or {}
    ids = {str(world.get("current_location_id") or "")}
    for key, npc in (state.get("npcs") or {}).items():
        if not isinstance(npc, dict) or not npc.get("in_scene"):
            continue
        eid = resolve_npc_entity_id(npc, str(key))
        if eid:
            ids.add(eid)
    ids.discard("")
    return ids


def _hidden_edges(target_id: str, proj: dict) -> list:
    return [
        e
        for e in gr.resolve_edges(proj, entity_id=target_id, include_hidden=True)
        if e.get("visibility") in ("hidden", "secret")
    ]


def canonical_secret_detail(target_id: str, proj: dict, anchors: set | None = None) -> str:
    """Texto do segredo vem do GRAFO (edges hidden/secret), nunca do LLM.

    Com ``anchors`` e alvo FORA da cena, só entram as edges ancoradas na cena
    (a revelação que a prova autorizou) — nunca os demais segredos do alvo."""

    def name(eid: str) -> str:
        return str((gr.get_entity(eid) or {}).get("name") or eid)

    edges = _hidden_edges(target_id, proj)
    if anchors is not None and target_id not in anchors:
        edges = [e for e in edges if e.get("source") in anchors or e.get("target") in anchors]
    parts = [f"{name(e.get('source'))} —{e.get('type')}→ {name(e.get('target'))}" for e in edges]
    return "; ".join(parts)


def _quest_proof(ev: ProposedWorldEvent, state: dict) -> ValidationResult:
    from services.quest_log import has_completion_proof

    qid = ev.payload.get("quest_id")
    if not qid:
        # Modo beat: conclusão de beat é decidida por beat_completed (SPEC-142),
        # não por evento proposto — o LLM não fecha beat por quest_completed.
        return ValidationResult(False, f"{UNPROVEN_PREFIX}: quest_completed sem quest_id")
    quest = next(
        (q for q in state.get("quests", []) or [] if isinstance(q, dict) and q.get("id") == qid),
        None,
    )
    if quest is None:
        return ValidationResult(False, f"quest_id {qid} não é uma quest ativa")
    ok, why = has_completion_proof(quest, state)
    if not ok:
        return ValidationResult(False, f"{UNPROVEN_PREFIX}: quest_completed ({why})")
    turn = _turn_of(state)
    done_turns = [
        int(e.get("turn", 0) or 0)
        for e in state.get("event_log") or []
        if isinstance(e, dict) and e.get("type") == "quest_completed"
    ]
    if any(t == turn for t in done_turns):
        return ValidationResult(False, f"{LIMIT_PREFIX}: 1 quest_completed por turno")
    past = [t for t in done_turns if t < turn]
    if past and turn - max(past) < QUEST_COMPLETION_COOLDOWN:
        return ValidationResult(
            False, f"{LIMIT_PREFIX}: cooldown de {QUEST_COMPLETION_COOLDOWN} turnos"
        )
    return ValidationResult(True)


def _secret_proof(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    anchors = scene_anchor_ids(state)
    if ev.target_id in anchors:
        return ValidationResult(True)
    for edge in _hidden_edges(ev.target_id, proj):
        if edge.get("source") in anchors or edge.get("target") in anchors:
            return ValidationResult(True)
    return ValidationResult(
        False, f"{UNPROVEN_PREFIX}: secret_revealed sem âncora na cena ({ev.target_id})"
    )


def _killed_proof(ev: ProposedWorldEvent, state: dict) -> ValidationResult:
    summary = state.get("conflict_summary") or {}
    if isinstance(summary, dict):
        try:
            same_turn = int(summary.get("conflict_turn")) == _turn_of(state)
        except (TypeError, ValueError):
            same_turn = False
        if same_turn:
            ent = gr.get_entity(ev.target_id) or {}
            wanted = {_fold(ev.target_id), _fold(ent.get("name"))} - {""}
            for dead in summary.get("mortos") or []:
                if _fold(dead) in wanted:
                    return ValidationResult(True)
    return ValidationResult(
        False, f"{UNPROVEN_PREFIX}: npc_killed sem combate encerrado neste turno"
    )


def _proof_gate(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    if ev.type == "quest_completed":
        return _quest_proof(ev, state)
    if ev.type == "secret_revealed":
        return _secret_proof(ev, state, proj)
    if ev.type == "npc_killed":
        return _killed_proof(ev, state)
    return ValidationResult(True)


def reason_class(reason: str) -> str:
    """Classe FECHADA de rejeição p/ métrica (sem texto livre como label)."""
    text = str(reason or "")
    if text.startswith(UNPROVEN_PREFIX):
        return "unproven"
    if text.startswith(LIMIT_PREFIX):
        return "rate_limited"
    if "gerado pelo motor" in text or "registrada pelo motor" in text:
        return "engine_only"
    if text.startswith("duplicata"):
        return "duplicate"
    if text.startswith("proposta malformada"):
        return "malformed"
    return "invalid"


REASON_CODES = frozenset(
    {
        "unproven",
        "cooldown",
        "rate_limited",
        "engine_only",
        "duplicate",
        "malformed",
        "unknown_target",
        "wrong_type",
        "not_active",
        "already_done",
        "no_secret",
        "invalid_payload",
        "no_connection",
        "unique_claimed",
        "other",
    }
)


def reason_code(reason: str) -> str:
    """SPEC-252 R1: código FECHADO (enum `REASON_CODES`) derivado do motivo textual do
    validador. O texto livre nunca vai para log; motivo desconhecido => `other`."""
    text = str(reason or "")
    if text.startswith(UNPROVEN_PREFIX):
        return "unproven"
    if text.startswith(LIMIT_PREFIX):
        return "cooldown" if "cooldown" in text else "rate_limited"
    if "gerado pelo motor" in text or "registrada pelo motor" in text:
        return "engine_only"
    if text.startswith("duplicata"):
        return "duplicate"
    if text.startswith("proposta malformada"):
        return "malformed"
    if (
        "id desconhecido" in text
        or "não existe no ARTIFACTS_DB" in text
        or "não é local do mapa" in text
        or "relação desconhecida" in text
        or "jurisdição desconhecida" in text
    ):
        return "unknown_target"
    if (
        "não é do type" in text
        or "não é facção" in text
        or "não é fação com vínculo" in text
        or "não é item único" in text
        or "não é uma facção conhecida" in text
        or "sempre do player" in text
        or "é interior" in text
        or "exige actor player" in text
    ):
        return "wrong_type"
    if "não é uma quest ativa" in text or "não está em cena" in text:
        return "not_active"
    if "nenhum segredo" in text:
        return "no_secret"
    if (
        "já está morto" in text
        or "já revelado" in text
        or "já ocorreu" in text
        or "derrotada" in text
        or "bloqueada" in text
    ):
        return "already_done"
    if "sem conexão" in text or "não têm conexão" in text:
        return "no_connection"
    if (
        "ausente" in text
        or "inválido" in text
        or "fora do plano" in text
        or "sem campaign_plan" in text
    ):
        return "invalid_payload"
    return "other"


_ENGINE_SOURCES = frozenset({"engine", "combat", "progression", "system", "rule", "law"})


def rejection_source(proposal: dict) -> str:
    """SPEC-252 R1: `llm|rule|prevalidation` (conjunto fechado)."""
    if proposal.get("_prevalidation_rejected") is True:
        return "prevalidation"
    return "rule" if proposal.get("source") in _ENGINE_SOURCES else "llm"


def catalog_ref(target_id: object) -> str | None:
    """SPEC-252: `target_ref` só se for id de catálogo (entidade do grafo, local do mapa ou
    artefato). Qualquer outra coisa (nome livre vindo do LLM, id de quest) => None."""
    tid = str(target_id or "")
    if not tid or len(tid) > 80:
        return None
    try:
        from gamedata import ARTIFACTS_DB, get_location

        if gr.get_entity(tid) or get_location(tid) or tid in ARTIFACTS_DB:
            return tid
    except Exception:  # silent-ok: ref de catalogo e best-effort; sem ela o log omite o campo
        return None
    return None


def _v_location_state_changed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """SPEC-302 R28: estado de local do motor (gate de source em validate_proposal)."""
    from gamedata import get_location
    from services.location_states import STATES

    loc = get_location(ev.target_id)
    if not loc:
        return ValidationResult(False, f"{ev.target_id} não é local do mapa")
    if loc.get("kind") == "interior":
        return ValidationResult(False, f"{ev.target_id} é interior: o estado vive no local pai")
    new_state = ev.payload.get("state", "")
    if new_state and new_state not in STATES:
        return ValidationResult(False, f"estado de local inválido: {new_state!r}")
    sev = ev.payload.get("severity", 0)
    if not isinstance(sev, int) or not 0 <= sev <= 3:
        return ValidationResult(False, "payload.severity inválido")
    return ValidationResult(True)


def _v_world_crisis_warning(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    from gamedata import get_location
    from services.world_pressures import region_ids

    if not get_location(ev.target_id):
        return ValidationResult(False, f"{ev.target_id} não é local do mapa")
    if ev.payload.get("region_id") not in region_ids():
        return ValidationResult(False, "payload.region_id inválido")
    if not ev.payload.get("kind"):
        return ValidationResult(False, "payload.kind ausente")
    return ValidationResult(True)


def _v_crime_witnessed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """SPEC-299 R13: o crime existe no ``law_state`` e a jurisdição é conhecida."""
    from services import law_codes

    jid = str(ev.payload.get("jurisdiction_id") or "")
    if not law_codes.get_code(jid):
        return ValidationResult(False, f"jurisdição desconhecida: {jid!r}")
    crimes = (state.get("law_state") or {}).get("crimes") or []
    if not any(c.get("crime_id") == ev.target_id for c in crimes if isinstance(c, dict)):
        return ValidationResult(False, "crime_id ausente do law_state")
    return ValidationResult(True)


def _v_law_resolved(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    from services import law_codes

    if not law_codes.get_code(ev.target_id):
        return ValidationResult(False, f"jurisdição desconhecida: {ev.target_id!r}")
    if ev.payload.get("mode") not in ("fine", "sentence", "expulsao", "bribe"):
        return ValidationResult(False, "payload.mode inválido")
    return ValidationResult(True)


_ENGINE_ONLY_TYPES = frozenset({"location_state_changed", "world_crisis_warning"})

_VALIDATORS = {
    "location_state_changed": _v_location_state_changed,
    "world_crisis_warning": _v_world_crisis_warning,
    "crime_witnessed": _v_crime_witnessed,
    "law_resolved": _v_law_resolved,
    "npc_killed": _v_npc_killed,
    "secret_revealed": _v_secret_revealed,
    "location_control_changed": _v_location_control_changed,
    "quest_completed": _v_quest_completed,
    "quest_failed": _v_quest_failed,
    "world_quest_relief": _v_world_quest_relief,
    "faction_relation_changed": _v_faction_relation_changed,
    "reputation_changed": _v_reputation_changed,
    "faction_deed": _v_faction_deed,
    "faction_membership_changed": _v_faction_membership_changed,
    "level_up": _v_level_up,
    "subclass_chosen": _v_progression_choice,
    "class_apex_unlocked": _v_progression_choice,
    "player_died": _v_player_died,
    "player_downed": _v_player_downed,
    "route_blocked": _v_route_blocked,
    "route_cleared": _v_route_cleared,
    "unique_item_claimed": _v_unique_item,
    "unique_item_lost": _v_unique_item,
    "companion_left": _v_companion_event,
    "companion_betrayed": _v_companion_event,
    "companion_fate": _v_companion_event,
}


def validate_proposal(proposal: dict, state: dict) -> ValidationResult:
    """Valida UMA proposta contra grafo + estado. Nunca levanta."""
    # 1. Revalida do zero — dict malformado / tipo desconhecido = rejeitado sem exceção.
    try:
        ev = ProposedWorldEvent.model_validate(proposal)
    except Exception as exc:
        return ValidationResult(False, f"proposta malformada: {exc}")

    # Fase 4.1: level_up só nasce no motor (grant_xp) — proposta do LLM chega sem
    # `source` (o schema ProposedWorldEvent não tem o campo) e é rejeitada aqui.
    if (
        ev.type in ("level_up", "subclass_chosen", "class_apex_unlocked")
        and proposal.get("source") != "progression"
    ):
        return ValidationResult(False, "level_up é gerado pelo motor, não proposto")
    # Fase 4.6: player_died idem — só o combate emite.
    if ev.type == "player_died" and proposal.get("source") != "combat":
        return ValidationResult(False, "player_died é gerado pelo motor, não proposto")
    # spec balanceamento-early-game (R3): player_downed idem — só o combate emite.
    if ev.type == "player_downed" and proposal.get("source") != "combat":
        return ValidationResult(False, "player_downed é gerado pelo motor, não proposto")
    # SPEC-298: faction_deed nasce no storyteller (Python), nunca de proposta livre do LLM.
    if ev.type == "faction_deed" and proposal.get("source") != "storyteller":
        return ValidationResult(False, "faction_deed é gerado pelo motor, não proposto")
    # SPEC-300: partida/traição/destino de companheiro são do motor, nunca propostos.
    if (
        ev.type in ("companion_left", "companion_betrayed", "companion_fate")
        and proposal.get("source") != "engine"
    ):
        return ValidationResult(False, "evento de companheiro é gerado pelo motor, não proposto")
    # SPEC-299: crime/pena nascem na lei (Python), nunca de proposta do LLM.
    if ev.type in ("crime_witnessed", "law_resolved") and proposal.get("source") != "law":
        return ValidationResult(False, f"{ev.type} é gerado pelo motor, não proposto")
    # SPEC-301: vínculo com fação é decidido por Python (apply_intent), nunca pelo LLM.
    if ev.type == "faction_membership_changed" and proposal.get("source") != "engine":
        return ValidationResult(
            False, "faction_membership_changed é gerado pelo motor, não proposto"
        )
    # Fase 6.2: posse de item único é observada pelo motor, nunca proposta.
    if (
        ev.type in ("unique_item_claimed", "unique_item_lost")
        and proposal.get("source") != "engine"
    ):
        return ValidationResult(False, "posse de item único é registrada pelo motor, não proposta")

    # SPEC-305 R15: falha de quest e fato do motor (prazo), nunca proposta do LLM.
    if ev.type == "quest_failed" and proposal.get("source") not in ("system", "engine"):
        return ValidationResult(False, "falha de quest é um fato gerado pelo motor, não proposto")
    # SPEC-302 R28: estados de local e avisos de crise sao fatos do motor de mundo.
    if ev.type in _ENGINE_ONLY_TYPES and proposal.get("source") != "engine":
        return ValidationResult(False, "estado de mundo é gerado pelo motor, não proposto")
    # SPEC-302 (revisão P1-1): paz e aliança entre facções são cruzamentos do motor.
    if (
        ev.type == "faction_relation_changed"
        and (ev.payload.get("relation") or ev.detail) in ("neutral", "allied_with")
        and proposal.get("source") != "engine"
    ):
        return ValidationResult(
            False, "relação neutral/allied_with é um cruzamento gerado pelo motor, não proposto"
        )
    projection = state.get("world_projection") or {}
    turn = (state.get("world") or {}).get("turn_count", 0)

    # 2. Sem duplicata (mesmo type+target já no event_log DESTE turno).
    #    Exceção: multi-level no mesmo turno (boss XP) — level_up distingue por new_level.
    for e in state.get("event_log") or []:
        if (
            e.get("type") == ev.type
            and e.get("target_id") == ev.target_id
            and e.get("turn") == turn
        ):
            if ev.type == "level_up" and (e.get("payload") or {}).get(
                "new_level"
            ) != ev.payload.get("new_level"):
                continue
            # SPEC-302: o motor pode mudar o MESMO local mais de uma vez no turno
            # (varios dias numa acao): distingue por estado/severidade/crise/dia.
            if ev.type in _ENGINE_ONLY_TYPES and any(
                (e.get("payload") or {}).get(k) != ev.payload.get(k)
                for k in ("state", "severity", "crisis_id", "day", "kind")
            ):
                continue
            # Fase 6.1: mesmo local pode bloquear/limpar rotas para PARES diferentes
            if ev.type in ("route_blocked", "route_cleared") and (e.get("payload") or {}).get(
                "other_location_id"
            ) != ev.payload.get("other_location_id"):
                continue
            return ValidationResult(
                False, f"duplicata: {ev.type}/{ev.target_id} já no turno {turn}"
            )

    # 3. Regra específica do tipo.
    result = _VALIDATORS[ev.type](ev, state, projection)
    if not result.ok:
        return result
    # 4. SPEC-223: proposta do LLM (sem fonte do motor) exige prova no estado.
    if ev.type in PROOF_REQUIRED_TYPES and not is_engine_proposal(proposal):
        return _proof_gate(ev, state, projection)
    return result
