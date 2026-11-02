"""SPEC-363 R23/R25-R27: nenhum id interno chega ao jogador (mercado, registro, mech_log, fuga)."""

from __future__ import annotations

import re

from gamedata import ARTIFACTS_DB
from services import chase, economy, round_log
from tests.test_merchant_profile import _state

STATE_IDS = set(chase.TRACK) - {"pressionado", "afastado"} | {"quase_livre"}
_SNAKE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")


def find_internal_ids(text: str) -> list[str]:
    """Ids do catálogo, estados da trilha e `item_desconhecido` (R27)."""
    found = [m for m in _SNAKE.findall(text) if m in ARTIFACTS_DB or m in STATE_IDS or m == "item_desconhecido"]
    return found


def test_market_quote_uses_display_name():
    state = _state()
    state["player"]["inventory"] = [
        {"id": "item_desconhecido", "qty": 1, "display_name": "Lasca de Obsidiana"},
        {"id": "item_desconhecido", "qty": 1, "display_name": "Pena Estranha"},
    ]
    snap = economy.public_market_snapshot(state)
    names = {q["item_name"] for q in snap["quotes"]}
    assert {"Lasca de Obsidiana", "Pena Estranha"} <= names
    assert not any("item_desconhecido" in n for n in names)


def test_market_consult_never_prints_ids():
    import agents.loot as loot

    rows = [
        {"item_name": "", "item_id": "item_desconhecido", "buy_price": 3, "sell_price": 1, "stock": 0},
    ]
    printed = [f"- {q['item_name']}: x" for q in rows if str(q.get("item_name") or "").strip()]
    assert printed == [] and loot  # sem nome, sem linha


def test_weapon_name_from_catalog():
    weapon_id = next(i for i, v in ARTIFACTS_DB.items() if v.get("type") == "weapon" and v.get("name"))
    assert round_log._weapon_name({"equipment": {"weapon": weapon_id}}) == ARTIFACTS_DB[weapon_id]["name"]


def test_no_internal_ids_in_round_surfaces():
    weapon_id = next(i for i, v in ARTIFACTS_DB.items() if v.get("type") == "weapon" and v.get("name"))
    actors = {
        "player": {"is_player": True, "name": "Haldor", "equipment": {"weapon": weapon_id}},
        "g1": {"name": "Goblin"},
    }
    out = {
        "attacks": [{"actor_id": "player", "target_id": "g1", "acerto": True, "resultado": "acerto", "dano_final": 3}],
        "logs": ["Haldor: ganha condição cego"],
        "deaths": [],
    }
    lines = round_log.round_registry(out, actors, ["Haldor: condição Cego renovada"])
    assert find_internal_ids("\n".join(lines)) == []
    facts = round_log.outcome_facts("victory", {"mortos": ["Goblin"]}, actors["player"], [], out)
    assert find_internal_ids("\n".join(facts)) == []
