"""services/checkpoints.py — checkpoints + restore na morte (spec checkpoints-morte).

Modelo (8 decisões de 2026-07-20):
- D1: grava a cada CHECKPOINT_EVERY turnos E ao entrar em zona segura.
- D2: a morte abre a escolha Continuar (restaura) / Aceitar (memorial) —
  `resolve_death_choice`.
- D3: sem custo extra além do progresso perdido desde o checkpoint.
- D5: 1 slot por save (em `persistence.save_checkpoint`, sobrescreve).
- D7: sem checkpoint ainda → restaura do estado INICIAL da sessão.
- D8: sem permadeath imposto — memorial só pela via voluntária "Aceitar".

Fundação determinística (sem LLM). O flip do fluxo de morte em `agents/combat.py`
(setar `death_pending`), o endpoint da API e a tela do frontend consomem isto.
"""
from __future__ import annotations

import copy
import os
import hashlib
from typing import Any, Dict, Optional

import persistence

CHECKPOINT_EVERY = 10   # D1: a cada N turnos
SAFE_DANGER = 1         # zona segura = danger_level <= isto


def _turn(state: dict) -> int:
    return int((state.get("world") or {}).get("turn_count", 0) or 0)


def _danger(state: dict) -> int:
    return int((state.get("world") or {}).get("danger_level", 1) or 1)


def entered_safe_zone(state: dict, prev: Optional[dict]) -> bool:
    """True se o jogador ACABOU de chegar numa zona segura (mudou de local E
    danger <= SAFE_DANGER). Sem `prev`, considera só o perigo atual."""
    if _danger(state) > SAFE_DANGER:
        return False
    cur = (state.get("world") or {}).get("current_location_id")
    old = ((prev or {}).get("world") or {}).get("current_location_id")
    return bool(cur) and cur != old


def should_checkpoint(state: dict, prev: Optional[dict] = None) -> bool:
    """D1: grava a cada CHECKPOINT_EVERY turnos OU ao entrar em zona segura.
    Nunca grava com o jogo encerrado (memorial) ou morte pendente."""
    from services.actor_lifecycle import transition_readiness
    if not transition_readiness(state)["ready"]:
        return False
    t = _turn(state)
    if t > 0 and t % CHECKPOINT_EVERY == 0:
        return True
    return entered_safe_zone(state, prev)


def snapshot(state: dict) -> Optional[dict]:
    """Cópia profunda do estado e da memória externa usada pelo harness."""
    from services.actor_lifecycle import transition_readiness
    if not transition_readiness(state)["ready"]:
        return None
    snap = copy.deepcopy(state)
    from services.continuity import mark_checkpoint
    snap["continuity"] = mark_checkpoint(
        snap.get("continuity"), canonical_turn=_turn(snap),
    )
    game_id = snap.get("game_id")
    if game_id:
        snap["_checkpoint_memory_snapshot"] = (
            persistence.capture_session_memory(str(game_id))
        )
    return snap


def maybe_write(state: dict, prev: Optional[dict] = None) -> bool:
    """Grava o checkpoint em disco se a cadência (D1) mandar. Retorna se gravou."""
    if should_checkpoint(state, prev):
        marked = copy.deepcopy(state)
        from services.continuity import mark_checkpoint
        marked["continuity"] = mark_checkpoint(
            marked.get("continuity"), canonical_turn=_turn(marked),
        )
        return persistence.save_checkpoint(marked)
    return False


def _sanitize_legacy_combat_checkpoint(restored: dict) -> dict:
    """Fecha cena/transições efêmeras capturadas por versões antigas."""
    from services.actor_lifecycle import transition_readiness, sanitize_interturn_state
    readiness = transition_readiness(restored)
    if readiness["ready"]:
        return restored
    clean = copy.deepcopy(restored)
    old = clean.get("combat") or {}
    if old.get("active"):
        clean["combat"] = {
            "active": False, "round": int(old.get("round", 0) or 0),
            "idle_turns": 0, "origin": old.get("origin", "unknown"), "scene": None,
        }
        clean["enemies"] = []
        clean["combat_target"] = None
    return sanitize_interturn_state(clean)


def resolve_death_choice(state: dict, choice: str, *,
                         checkpoint: Optional[dict] = None,
                         initial_state: Optional[dict] = None) -> dict:
    """Resolve a tela de morte (D2). Não muta o estado de entrada.

    - `choice == "accept"` → memorial: seta `game_over` (fluxo atual preservado),
      limpa `death_pending`.
    - senão ("continue") → restaura: usa o `checkpoint` in-memory (harness) se
      dado; senão o checkpoint em disco do `game_id`; senão o `initial_state`
      (D7, início da sessão); senão mantém o estado vivo. Limpa `death_pending`.
    """
    if choice == "accept":
        new = copy.deepcopy(state)
        new["death_pending"] = False
        new["game_over"] = True
        events = list(new.get("event_log") or [])
        if not any(
            isinstance(event, dict) and event.get("type") == "player_died"
            for event in events
        ):
            turn = _turn(new)
            epoch = int((new.get("continuity") or {}).get("timeline_epoch", 0) or 0)
            event_id = hashlib.sha256(
                f"{new.get('game_id', '')}:{epoch}:{turn}:player_died".encode("utf-8")
            ).hexdigest()[:32]
            event = {
                "event_id": event_id,
                "turn": turn,
                "type": "player_died",
                "actor_id": "player",
                "target_id": "player",
                "payload": {"detail": "o fim foi aceito e a campanha tornou-se memorial"},
                "source": "combat",
            }
            events.append(event)
            new["event_log"] = events
            from services.chronicle import append_entry, render_milestone
            milestone = render_milestone(event, new.get("world_projection") or {})
            if milestone:
                new["chronicle"] = append_entry(
                    new.get("chronicle") or [], text=milestone, turn=turn,
                    kind="milestone", event_id=event_id,
                )
        return new

    restored: Optional[dict] = None
    if checkpoint is not None:
        restored = copy.deepcopy(checkpoint)
        captured = restored.pop("_checkpoint_memory_snapshot", None)
        if state.get("game_id") and "_checkpoint_memory_snapshot" in checkpoint:
            persistence.restore_captured_session_memory(
                str(state["game_id"]), captured)
    elif state.get("game_id"):
        restored = persistence.load_checkpoint(state["game_id"])
        if restored is not None and os.getenv('RPG_RUNTIME_PROFILE', 'legacy') == 'legacy':
            restored_external = persistence.restore_checkpoint_memory(
                str(state["game_id"]))
            if not restored_external:
                # Slot anterior à spec: não há como distinguir fatos pré/pós
                # checkpoint. Falha fechado limpando o índice derivado; o ledger
                # `memory_facts` restaurado ainda sustenta a continuidade global.
                persistence.restore_captured_session_memory(
                    str(state["game_id"]), None)
    if restored is None:  # D7: sem checkpoint → início da sessão
        restored = copy.deepcopy(initial_state) if initial_state is not None else copy.deepcopy(state)
    restored = _sanitize_legacy_combat_checkpoint(restored)
    restored["death_pending"] = False
    restored["game_over"] = False
    from services.continuity import after_restore
    restored["continuity"] = after_restore(state, restored)
    return restored
