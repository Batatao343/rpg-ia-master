"""SPEC-318 R6: nó `enrich` — trabalho pós-narração, entre o narrador e o arquivista.

Roda DEPOIS que a update do nó narrador já saiu (SPEC-316 entrega o texto nela) e ainda
dentro do stream do turno. Hospeda (1) a ficha completa dos NPCs que o narrador só
esbocou (stub determinístico) e (2) o replan do arco para o PRÓXIMO turno. Falha aqui
nunca derruba o turno: registra e devolve o estado como estava.

A narração não é tocada: `enrich` nunca devolve `messages`. A regra de ouro vale porque o
stub só carrega o que o texto já mostrou e a ficha completa é gerada pelo mesmo caminho
(`_with_new_npc`) com o stub como contexto fixo de nome e papel.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from observability.telemetry import log_event as _log_event
from services import latency_flags
from state import GameState

MAX_SHEETS_PER_TURN = 2
MAX_SHEET_ATTEMPTS = 3

# O que o stub já viveu e a ficha completa NÃO pode apagar (identidade e estado dinâmico).
_KEEP_FROM_STUB = (
    "id",
    "in_scene",
    "last_seen_turn",
    "created_turn",
    "memory",
    "interaction_count",
    "revealed_traits",
    "hidden_traits",
    "known_by_player",
    "knowledge_source",
    "last_interaction",
    "recent_changes",
    "favors",
    "heard_deeds",
    "_rel_budget",
    "home_location_id",
    "location",
    "status",
    "active_conditions",
)


def _turn(state: GameState) -> int:
    return int((state.get("world") or {}).get("turn_count", 0) or 0)


def _last_narration(state: GameState) -> str:
    for message in reversed(state.get("messages") or []):
        if isinstance(message, AIMessage):
            return str(message.content or "")
        break
    return ""


def pending_stubs(state: GameState) -> list[str]:
    """Chaves de `npcs` com ficha provisória que ainda podem tentar a completa."""
    return [
        str(key)
        for key, npc in (state.get("npcs") or {}).items()
        if isinstance(npc, dict)
        and npc.get("sheet_status") == "stub"
        and int(npc.get("sheet_attempts", 0) or 0) < MAX_SHEET_ATTEMPTS
    ][:MAX_SHEETS_PER_TURN]


def _merge_full(stub: dict, full: dict) -> dict:
    merged = dict(full)
    for field in _KEEP_FROM_STUB:
        if field in stub:
            merged[field] = stub[field]
    merged["name"] = stub.get("name", merged.get("name"))
    if str(stub.get("role") or "Desconhecido") != "Desconhecido":
        merged["role"] = stub["role"]  # nome/papel ja mostrados ao jogador nao mudam
    if stub.get("interaction_count") or stub.get("memory"):
        # ja houve interacao com o stub: a relacao vivida vence a inicial da ficha
        for field in ("relationship", "relationship_basis"):
            if field in stub:
                merged[field] = stub[field]
    merged["sheet_status"] = "full"
    merged.pop("sheet_attempts", None)
    return merged


def _complete_sheet(state: GameState, npcs: dict, key: str) -> tuple[dict, bool]:
    """Tenta a ficha completa de `npcs[key]`. Devolve (npcs, completou)."""
    from agents.storyteller import _with_new_npc

    stub = dict(npcs[key])
    world = state.get("world") or {}
    turn = _turn(state)
    created = int(stub.get("created_turn", -1) if stub.get("created_turn") is not None else -1)
    scene = _last_narration(state) if created == turn else ""
    note = (
        f"(Ficha provisória já mostrada ao jogador: nome {stub.get('name', key)}, "
        f"papel {stub.get('role', 'Desconhecido')}. A ficha completa NÃO pode contradizê-los.)"
    )
    others = {k: v for k, v in npcs.items() if k != key}
    recent_inputs = tuple(
        str(m.content)
        for m in [m for m in (state.get("messages") or []) if isinstance(m, HumanMessage)][-3:]
    )
    result = _with_new_npc(
        others,
        str(stub.get("name") or key),
        str(world.get("current_location", "")),
        f"{scene}\n{note}".strip(),
        game_id=str(state.get("game_id") or ""),
        home_id=str(stub.get("home_location_id") or world.get("current_location_id", "")),
        turn=int(stub.get("created_turn", turn) or turn),
        player_inputs=recent_inputs,
        state=state,
        stub_only=False,
    )
    new_keys = [k for k in result if k not in others]
    full = result.get(new_keys[0]) if len(new_keys) == 1 else None
    if not isinstance(full, dict) or full.get("id") == "fallback":
        npcs = dict(npcs)
        npcs[key] = {**stub, "sheet_attempts": int(stub.get("sheet_attempts", 0) or 0) + 1}
        return npcs, False
    merged = _merge_full(stub, full)
    rebuilt = {k: (merged if k == key else v) for k, v in npcs.items()}
    return rebuilt, True


def _enrich_npcs(state: GameState) -> dict:
    keys = pending_stubs(state)
    if not keys:
        return {}
    from observability import latency

    npcs = dict(state.get("npcs") or {})
    for key in keys:
        npcs, ok = _complete_sheet(state, npcs, key)
        if ok:
            _log_event("enrich", "npc_sheet_completed", level="info")
        else:
            _log_event("enrich", "npc_sheet_failed", level="warning")
    latency.bump("npc_sheets_deferred", len(keys))
    return {"npcs": npcs}


def _enrich_plan(state: GameState) -> dict:
    from agents.campaign_manager import replan_after_delivery
    from observability import latency

    if state.get("game_over") or state.get("death_pending"):
        return {}
    out = replan_after_delivery(state)
    if out:
        latency.bump("replan_deferred")
    return out


def enrich_node(state: GameState) -> dict:
    from observability import latency
    from observability.telemetry import log_fallback

    if (state.get("combat_simulation") or {}).get("enabled"):
        return {}
    with latency.accumulate("enrich_ms"):
        out: dict = {}
        if latency_flags.two_phase_on():
            try:
                out.update(_enrich_npcs(state))
            except Exception as exc:
                log_fallback("enrich", "npc_sheets_failed", exc)
        if latency_flags.replan_after_on():
            try:
                out.update(_enrich_plan({**state, **out}))
            except Exception as exc:
                log_fallback("enrich", "replan_failed", exc)
        return out
