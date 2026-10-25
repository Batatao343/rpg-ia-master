"""SPEC-316: entrega antecipada da narracao no SSE (funcoes puras, sem I/O).

O texto sai assim que o no narrador termina (antes de arquivista/finalizador/commit),
ja passado pelo guard de evidencia. Quem decide o *quando* e o `api.py`; aqui so se
decide *se* a update de um no carrega a narracao final do turno e *qual* e o texto.
"""

from __future__ import annotations

import os
from typing import Any, Literal

NARRATING_NODES = frozenset({"storyteller", "combat_agent", "npc_actor", "loot_agent"})
# Valores de `next` que significam "outro no narrador vem depois" (o router grafa
# `loot`, o no se chama `loot_agent`).
_NEXT_ALIASES = {"loot": "loot_agent"}

EarlyMode = Literal["off", "shadow", "on"]


def early_mode() -> EarlyMode:
    """`RPG_EARLY_NARRATIVE=off|shadow|on` (default `shadow`; valor invalido = `off`)."""
    raw = os.getenv("RPG_EARLY_NARRATIVE", "shadow").strip().lower()
    if raw in ("off", "shadow", "on"):
        return raw  # type: ignore[return-value]
    return "off"


def narrative_chunks(text: str, size: int = 80) -> list[str]:
    size = max(1, int(size))
    return [text[i : i + size] for i in range(0, len(text), size)]


def _merged_messages(state_before: dict, update: dict) -> list | None:
    """Aplica o reducer de `messages` (append, ou `Overwrite`) sem mutar nada."""
    if "messages" not in update:
        return None
    raw = update["messages"]
    before = list(state_before.get("messages") or [])
    if hasattr(raw, "value") and not isinstance(raw, list):  # langgraph Overwrite
        return list(raw.value or [])
    return before + list(raw or [])


def early_narrative(state_before: dict, update: dict, node: str = "") -> str | None:
    """Texto que o jogador veria se o turno terminasse na update do no `node`.

    `None` quando a update nao narra (so `SystemMessage`, sem mensagem) ou quando outro
    no narrador ainda vai rodar (R4: encontro, vitoria, delegacao do NPC)."""
    if not isinstance(update, dict):
        return None
    nxt = _NEXT_ALIASES.get(str(update.get("next") or ""), str(update.get("next") or ""))
    if nxt in NARRATING_NODES and nxt != node:
        return None
    messages = _merged_messages(state_before, update)
    if not messages or getattr(messages[-1], "type", "") != "ai":
        return None

    from services.faction_display import conceal_text, concealed_name_map
    from services.narrative_evidence import guard_current_messages
    from services.turn_outcome import player_facing_message

    merged: dict[str, Any] = {**state_before, **update, "messages": messages}
    # `last_turn_outcome` do turno anterior ainda esta no estado: o recibo deste turno
    # so nasce no finalizador; o texto antecipado vem da ultima mensagem guardada.
    merged.pop("last_turn_outcome", None)
    guarded, _audit = guard_current_messages(merged)
    merged["messages"] = guarded
    text = player_facing_message(merged)
    # Mesmo veu de exibicao do `format_response` (SPEC-293): nada de nome oculto.
    text = conceal_text(text, concealed_name_map(merged))
    return text if text and text.strip() else None
