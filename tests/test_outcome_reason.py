"""SPEC-398 R3: `outcome_reason` aditivo; `outcome` segue `defeat`."""

from __future__ import annotations

from services import encounter_manifest as em
from services import outcome_reason as orr


def test_mark_objective_failed_with_hero_standing():
    meta: dict = {}
    orr.mark(meta, "defeat", {"objetivo_resultado": "falhou"}, {"conscious": True})
    assert meta["outcome_reason"] == "objective_failed"


def test_mark_clears_when_not_failed_objective():
    meta = {"outcome_reason": "objective_failed"}
    orr.mark(meta, "defeat", {"objetivo_resultado": "falhou"}, {"conscious": False})
    assert "outcome_reason" not in meta
    meta = {}
    orr.mark(meta, "victory", {"objetivo_resultado": "cumprido"}, {"conscious": True})
    assert "outcome_reason" not in meta
    orr.mark(meta, "defeat", None, {})
    assert "outcome_reason" not in meta


def test_result_view_carries_reason_and_old_save_loads():
    combat = {
        "phase": "ended",
        "outcome": "defeat",
        "outcome_reason": "objective_failed",
        "result": {"outcome": "defeat", "xp_event_ref": "r1"},
    }
    got = em.result_view(combat, {"receipt_id": "r1"})
    assert got["outcome"] == "defeat" and got["outcome_reason"] == "objective_failed"
    del combat["outcome_reason"]
    old = em.result_view(combat, {"receipt_id": "r1"})
    assert old["outcome"] == "defeat" and "outcome_reason" not in old


def test_objective_failed_end_to_end_keeps_outcome_defeat(monkeypatch):
    from tests import spec364_board_helpers as hp

    client, saved, gid = hp.api_client(monkeypatch)
    st = hp.open_combat(client, saved, gid)
    foe = next(e["id"] for e in st["enemies"] if not e.get("dead"))
    st["combat"]["scene"]["objetivo"] = {"tipo": "interromper_ritual", "alvo": foe, "n": 1}
    r = client.post(
        "/game/action", json={"game_id": gid, "input_text": "Passo", "action_kind": "pass"}
    )
    assert r.status_code == 200, r.text
    res = r.json().get("combat_result") or {}
    assert res.get("outcome") == "defeat"
    assert res.get("outcome_reason") == "objective_failed"
