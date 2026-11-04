"""SPEC-387 R1-R4: Carta de cena nao depende de cache de processo."""

from __future__ import annotations

import json

import pytest

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
    events: list = []
    monkeypatch.setattr(card_piles, "log_event", lambda *a, **k: events.append((a, k)))
    view = card_piles.public_view(state["combat"]["pilhas"], state["player"])
    assert all(r["id"] != cid for r in view["mao"])
    assert [e[0] for e in events] == [("combat", "scene_card_orphan")]  # Sol P3-1
    assert cid not in str(events)  # sem id no evento


def test_old_save_without_scene_loads(monkeypatch):
    state, _ = _cold_state(monkeypatch)
    state["combat"].pop("scene", None)
    assert sc.rehydrate(state) == 0
    state["combat"] = None
    assert sc.rehydrate(state) == 0


def _api_seed(tmp):
    """Save legacy com a Carta de cena NA MÃO (objeto da cena), pronto para o POST /game/action."""
    import persistence
    from tests.fixtures import spec368_seed as sd

    gid = sd.seed_save(12, saves_dir=tmp)
    with sd._legacy(tmp):
        st = persistence.load_game_state(persistence.save_path(gid))
        st["enemies"][0]["vitalidade"] = st["enemies"][0]["max_vitalidade"] = 40
        st["enemies"][0]["esquiva_penalidade"] = 30
        st["combat"]["scene"]["objects"] = [dict(OBJ)]
        sc.sync_hand(st["combat"]["scene"], st["combat"]["pilhas"], "player")
        cid = next(c for c in st["combat"]["pilhas"]["mao"] if str(c).startswith("cena_"))
        assert persistence.save_game_state(st)
    return gid, cid, st["enemies"][0]["id"], sd


def _post_cold(tmp, flood):
    from fastapi.testclient import TestClient

    import api

    gid, cid, foe, sd = _api_seed(tmp)
    cards._TEMP_CARDS.clear()
    for i in range(flood):  # LRU cheio: 63 Cartas de outras partidas no meio
        cards.register_temp_card({"id": f"cena_outra_{i}", "name": "x"})
    with sd._legacy(tmp):
        r = TestClient(api.app).post(
            "/game/action",
            json={
                "game_id": gid,
                "input_text": "Encerro a rodada.",
                "jogadas": [{"card_id": cid, "target_id": foe}],
            },
        )
        after = sd.view(gid, tmp)
    return r, after, foe


@pytest.mark.parametrize("flood", [0, 63])
def test_cold_instance_play_via_api(tmp_path, flood):
    """Sol P2-1 / R3: POST com o catálogo vazio (ou o LRU cheio) responde 200, tem a linha da Carta e o efeito."""
    r, after, foe = _post_cold(str(tmp_path), flood)
    assert r.status_code == 200, r.text
    body = r.json()
    text = body.get("narration") or body.get("message") or json.dumps(body, ensure_ascii=False)
    assert "Empurrar (Poço Negro)" in text, text[:400]
    hp = [e for e in after["combat"]["enemies"] if e["id"] == foe]
    assert not hp or hp[0]["vitalidade"] < 40
