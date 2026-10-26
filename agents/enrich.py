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
from services.entity_identity import _NPC_DYNAMIC_FIELDS
from state import GameState

MAX_SHEETS_PER_TURN = 2
MAX_SHEET_ATTEMPTS = 3

# O que o stub já viveu e a ficha completa NÃO pode apagar (estado dinâmico). O papel e a
# relação inicial NÃO entram: o papel provisório é só uma inferência do texto e a ficha
# completa pode corrigi-lo; a relação só é preservada se já houve interação.
_KEEP_FROM_STUB = (
    set(_NPC_DYNAMIC_FIELDS)
    | {
        "created_turn",
        "memory",
        "revealed_traits",
        "hidden_traits",
        "recent_changes",
        "favors",
        "heard_deeds",
        "_rel_budget",
    }
) - {"relationship", "relationship_basis"}


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


def _touched(stub: dict) -> bool:
    return bool(
        stub.get("interaction_count")
        or stub.get("memory")
        or stub.get("recent_changes")
        or stub.get("favors")
        or stub.get("heard_deeds")
    )


def _merge_full(stub: dict, full: dict) -> dict:
    merged = dict(full)
    for field in _KEEP_FROM_STUB:
        if field in stub:
            merged[field] = stub[field]
    merged["name"] = stub.get("name", merged.get("name"))
    if _touched(stub):
        # já houve interação com o stub: a relação vivida vence a inicial da ficha
        for field in ("relationship", "relationship_basis"):
            if field in stub:
                merged[field] = stub[field]
    merged["sheet_status"] = "full"
    merged.pop("sheet_attempts", None)
    return merged


def _npc_id(key: str, npc: dict) -> str:
    return str(npc.get("id") or f"npc_{str(npc.get('name') or key).lower().replace(' ', '_')}")


def _remap_memory(rows, old_id: str, new_id: str):
    if not old_id or old_id == new_id:
        return None
    changed = False
    out = []
    for row in rows or []:
        if isinstance(row, dict) and row.get("npc_id") == old_id:
            row = {**row, "npc_id": new_id}
            changed = True
        out.append(row)
    return out if changed else None


def _merge_into_canonical(stub: dict, canon: dict, turn: int) -> dict:
    """Stub e NPC já existente são a mesma pessoa (dedupe do librarian): o stub se funde no
    canônico, que fica em cena e herda o que o stub viveu."""
    merged = dict(canon)
    merged["in_scene"] = True
    merged["last_seen_turn"] = max(
        int(canon.get("last_seen_turn", 0) or 0), int(stub.get("last_seen_turn", 0) or 0), turn
    )
    merged["memory"] = [*(canon.get("memory") or []), *(stub.get("memory") or [])][-20:]
    merged["interaction_count"] = int(canon.get("interaction_count", 0) or 0) + int(
        stub.get("interaction_count", 0) or 0
    )
    return merged


def _complete_sheet(state: GameState, npcs: dict, key: str) -> tuple[dict, bool, dict]:
    """Tenta a ficha completa de `npcs[key]`. Devolve (npcs, resolvido, extra_updates)."""
    from agents.storyteller import _with_new_npc

    stub = dict(npcs[key])
    world = state.get("world") or {}
    turn = _turn(state)
    created = int(stub.get("created_turn", -1) if stub.get("created_turn") is not None else -1)
    scene = _last_narration(state) if created == turn else ""
    note = (
        f"(Ficha provisória já mostrada ao jogador: nome {stub.get('name', key)}, "
        f"papel provisório {stub.get('role', 'Desconhecido')}. Respeite o nome; o papel "
        "provisório é só uma inferência e pode ser corrigido pela ficha.)"
    )
    others = {k: v for k, v in npcs.items() if k != key}
    recent_inputs = tuple(
        str(m.content)
        for m in [m for m in (state.get("messages") or []) if isinstance(m, HumanMessage)][-3:]
    )
    outcome: dict = {}
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
        outcome_out=outcome,
    )
    stub_id = _npc_id(key, stub)
    canon_key = outcome.get("merged_into")
    if canon_key and canon_key in result:
        # dedupe: o stub vira o NPC já existente (nada de duplicata viva em cena)
        canon = _merge_into_canonical(stub, result[canon_key], turn)
        rebuilt = {k: v for k, v in others.items()}
        rebuilt[canon_key] = canon
        extra: dict = {}
        remapped = _remap_memory(
            state.get("pending_npc_memory"), stub_id, _npc_id(canon_key, canon)
        )
        if remapped is not None:
            extra["pending_npc_memory"] = remapped
        if state.get("active_npc_name") == key:
            extra["active_npc_name"] = canon_key
        return rebuilt, True, extra
    if outcome.get("blocked"):
        # morto/ausente no grafo: como no legado, o NPC simplesmente não entra em cena
        return others, True, {}
    new_keys = [k for k in result if k not in others]
    full = result.get(new_keys[0]) if len(new_keys) == 1 else None
    if not isinstance(full, dict) or full.get("id") == "fallback":
        retry = dict(npcs)
        retry[key] = {**stub, "sheet_attempts": int(stub.get("sheet_attempts", 0) or 0) + 1}
        return retry, False, {}
    merged = _merge_full(stub, full)
    extra = {}
    remapped = _remap_memory(state.get("pending_npc_memory"), stub_id, _npc_id(key, merged))
    if remapped is not None:
        extra["pending_npc_memory"] = remapped
    return {k: (merged if k == key else v) for k, v in npcs.items()}, True, extra


def _enrich_npcs(state: GameState) -> dict:
    keys = pending_stubs(state)
    if not keys:
        return {}
    from observability import latency

    npcs = dict(state.get("npcs") or {})
    out: dict = {}
    for key in keys:
        if key not in npcs:
            continue
        npcs, ok, extra = _complete_sheet({**state, **out}, npcs, key)
        out.update(extra)
        if ok:
            _log_event("enrich", "npc_sheet_completed", level="info")
        else:
            _log_event("enrich", "npc_sheet_failed", level="warning")
    latency.bump("npc_sheets_deferred", len(keys))
    out["npcs"] = npcs
    return out


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
