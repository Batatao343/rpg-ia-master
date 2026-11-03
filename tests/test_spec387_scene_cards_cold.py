"""SPEC-387 R1-R4: Carta de cena nao depende de cache de processo."""

from __future__ import annotations

from services import card_piles, cards, combat_targeting
from services import scene_cards as sc
from tests.test_encounter_lifecycle_reload import _decl, _reload
from tests.test_scene_cards_node import _start, _step, _tanky

OBJ = {
    "id": "poco_negra",
    "name": "Poço Negro",
    "uses_remaining": 1,
    "destroyed": False,
    "interactions": [
        {"label": "empurrar", "effect": {"kind": "damage", "params": {"amount": 3, "target": "x"}}}
    ],
}


def _cold_state(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    state = _tanky(_start(monkeypatch))
    _, state = _step(state)
    state["combat"]["scene"]["objects"] = [dict(OBJ)]
    _decl(state)
    out, state = _step(state)
    temp = [c for c in state["combat"]["pilhas"]["mao"] if str(c).startswith("cena_")]
    assert temp
    return state, temp[0]


def test_rehydrate_registers_scene_cards(monkeypatch):
    state, cid = _cold_state(monkeypatch)
    cards._TEMP_CARDS.clear()
    assert sc.rehydrate(state) == 1
    assert cards.get_card(cid)["name"] == "Empurrar (Poço Negro)"
    assert sc.rehydrate({"combat": {}}) == 0


def test_cold_instance_view_has_name_and_cost(monkeypatch):
    state, cid = _cold_state(monkeypatch)
    cards._TEMP_CARDS.clear()  # outra instancia: nada em memoria
    state = _reload(state)  # o load reidrata
    view = card_piles.public_view(state["combat"]["pilhas"], state["player"])
    row = next(r for r in view["mao"] if r["id"] == cid)
    assert row["name"] == "Empurrar (Poço Negro)"
    assert row["custo_folego"] == 1 and row["tipo"] == "ativa"
    assert all(r["name"] != r["id"] for r in view["mao"])
    hand = combat_targeting.hand_card_targeting(state, cid)
    assert hand["valid_targets"]


def test_cold_instance_play_accepted(monkeypatch):
    state, cid = _cold_state(monkeypatch)
    foe = state["enemies"][0]["id"]
    cards._TEMP_CARDS.clear()
    state = _reload(state)
    reason = combat_targeting.check_declared_target(
        state, card_id=cid, action_kind=None, maneuver=None, target_id=foe
    )
    assert reason is None
    assert cards._in_scene_hand(state, cid)


def test_lru_eviction_survives(monkeypatch):
    state, cid = _cold_state(monkeypatch)
    for i in range(70):
        cards.register_temp_card({"id": f"cena_outra_{i}", "name": "x"})
    assert cards.get_card(cid) is None  # descartada pelo LRU
    state = _reload(state)
    assert cards.get_card(cid)["name"] == "Empurrar (Poço Negro)"


def test_orphan_card_never_shown_raw(monkeypatch):
    state, cid = _cold_state(monkeypatch)
    state["combat"]["scene"]["objects"][0]["interactions"][0]["effect"]["params"]["amount"] = 9
    # catalogo mudou entre deploys: o id salvo nao e mais reconstruivel
    cards._TEMP_CARDS.clear()
    state = _reload(state)
    assert cards.get_card(cid) is None
    view = card_piles.public_view(state["combat"]["pilhas"], state["player"])
    assert all(r["id"] != cid for r in view["mao"])


def test_old_save_without_scene_loads(monkeypatch):
    state, _ = _cold_state(monkeypatch)
    state["combat"].pop("scene", None)
    assert sc.rehydrate(state) == 0
    state["combat"] = None
    assert sc.rehydrate(state) == 0
