"""Serialização canônica compartilhada pelos stores File e Postgres."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping


def serialize_game_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Usa a única serialização mecânica existente sem duplicar defaults.

    O import tardio evita ciclo durante a transição de ``persistence.py`` para a
    fachada de stores. A extração física das funções pode ocorrer sem alterar o
    contrato deste módulo.
    """
    from persistence import _state_to_save_data

    value = deepcopy(dict(state))
    return _state_to_save_data(value, str(value["game_id"]))


def deserialize_game_state(document: Mapping[str, Any]) -> dict[str, Any]:
    from persistence import _raw_to_state

    return _raw_to_state(deepcopy(dict(document)))


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def document_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def game_projection(document: Mapping[str, Any]) -> dict[str, Any]:
    player = document.get("player") if isinstance(document.get("player"), dict) else {}
    world = document.get("world") if isinstance(document.get("world"), dict) else {}
    clock = world.get("world_clock") if isinstance(world.get("world_clock"), dict) else {}
    if document.get("archived"):
        status = "archived"
    elif document.get("game_over"):
        status = "memorial"
    elif document.get("death_pending"):
        status = "death_pending"
    elif document.get("combat_simulation"):
        status = "simulation"
    else:
        status = "active"
    return {
        "status": status,
        "player_name": str(player.get("name") or "Sem nome")[:200],
        "class_name": str(player.get("class_name") or "desconhecida")[:200],
        "player_level": max(1, int(player.get("level", 1) or 1)),
        "location_name": str(world.get("current_location") or "Desconhecido")[:300],
        "world_day": max(1, int(clock.get("day", 1) or 1)),
        "game_over": bool(document.get("game_over")),
        "combat_simulation": bool(document.get("combat_simulation")),
    }


def event_document(event: Mapping[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    return {
        "event_id": str(event.get("event_id") or ""),
        "turn": max(0, int(event.get("turn", 0) or 0)),
        "event_type": str(event.get("type") or "unknown"),
        "payload": deepcopy(payload),
        "source": str(event.get("source") or "unknown"),
    }
