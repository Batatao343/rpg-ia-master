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
    if state.get("game_over") or state.get("death_pending"):
        return False
    t = _turn(state)
    if t > 0 and t % CHECKPOINT_EVERY == 0:
        return True
    return entered_safe_zone(state, prev)


def snapshot(state: dict) -> dict:
    """Cópia profunda restaurável (usada in-memory pelo harness)."""
    return copy.deepcopy(state)


def maybe_write(state: dict, prev: Optional[dict] = None) -> bool:
    """Grava o checkpoint em disco se a cadência (D1) mandar. Retorna se gravou."""
    if should_checkpoint(state, prev):
        return persistence.save_checkpoint(state)
    return False


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
        return new

    restored: Optional[dict] = None
    if checkpoint is not None:
        restored = copy.deepcopy(checkpoint)
    elif state.get("game_id"):
        restored = persistence.load_checkpoint(state["game_id"])
    if restored is None:  # D7: sem checkpoint → início da sessão
        restored = copy.deepcopy(initial_state) if initial_state is not None else copy.deepcopy(state)
    restored["death_pending"] = False
    restored["game_over"] = False
    return restored
