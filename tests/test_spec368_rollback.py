"""SPEC-368 R1-R3 - rollback `RPG_CARD_DECK on -> off` fora de combate."""

from __future__ import annotations

import copy
from uuid import uuid4

import api
import persistence
from services import card_piles, cards


def _player() -> dict:
    pool = [
        c["id"]
        for c in cards.cards_for_class("Sangromante")
        if not c.get("subclasse") and c.get("tipo") == "ativa" and c.get("level_req", 1) == 1
    ]
    known = pool[:6]
    return {
        "class_name": "Sangromante",
        "level": 1,
        "known_cards": known,
        "prepared_cards": known[:4],
        "entropy": 6,
        "max_entropy": 10,
    }


def test_off_outside_combat_restores_pre_deck(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    p = _player()
    original = list(p["prepared_cards"])
    card_piles.activate_deck(p)
    assert p["prepared_cards"] != original
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    rows = api._cards_block(p)
    assert {r["id"] for r in rows if r["prepared"]} == set(original)
    assert p["prepared_cards"] != original  # a view nao muta o chamador
    probe = {"player": p, "world": {"danger_level": 0}, "combat": {}}
    cards.set_prepared(probe, original[:2])
    assert p["prepared_cards"] == original[:2] and "prepared_cards_pre_deck" not in p


def test_round_trip_off_on_off_with_save(monkeypatch, tmp_path):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    p = _player()
    original = list(p["prepared_cards"])
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    card_piles.activate_deck(p)
    state = {"game_id": str(uuid4()), "messages": [], "player": p, "world": {}}
    assert persistence.save_game_state(state)
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    loaded = persistence.load_game_state(persistence.save_path(state["game_id"]))
    assert loaded["player"]["prepared_cards"] == original
    assert "prepared_cards_pre_deck" not in loaded["player"]
    assert loaded["player"]["deck"]  # o baralho fica guardado
    # volta a `on`, salva, desliga de novo: exato
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    card_piles.activate_deck(loaded["player"])
    assert persistence.save_game_state(loaded)
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    again = persistence.load_game_state(persistence.save_path(state["game_id"]))
    assert again["player"]["prepared_cards"] == original


def test_on_path_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    p = _player()
    card_piles.activate_deck(p)
    snap = copy.deepcopy(p)
    assert card_piles.sync_deck_mode(p) is False and p == snap
    state = {"game_id": str(uuid4()), "messages": [], "player": p, "world": {}}
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(persistence.save_path(state["game_id"]))
    assert loaded["player"]["prepared_cards"] == snap["prepared_cards"]
    assert "prepared_cards_pre_deck" in loaded["player"]
