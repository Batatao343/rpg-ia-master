"""SPEC-398 R1/R2: contrato da mão coerente com o motor (reação, alvo oculto)."""

from __future__ import annotations

from tests import spec364_board_helpers as hp

REACT = "med1_ini_pinca_no_tendao"
ATK = "bas_med_golpe"


def _hand(client, gid):
    st = client.get("/game/state", params={"game_id": gid}).json()
    return {m["id"]: m for m in (st.get("combat") or {}).get("pilhas", {}).get("mao") or []}


def test_reaction_in_hand_is_not_playable_and_not_enemy_target(monkeypatch):
    client, saved, gid = hp.api_client(monkeypatch)
    st = hp.open_combat(client, saved, gid)
    st["combat"]["pilhas"]["mao"] = [REACT, ATK]
    row = _hand(client, gid)[REACT]
    assert row["jogavel"] is False
    assert row["invalid_reason"] == "not_playable_from_hand"
    assert row["alvo"] != "inimigo"
    assert row["valid_targets"] == []


def test_enemy_card_without_visible_target_carries_reason(monkeypatch):
    client, saved, gid = hp.api_client(monkeypatch)
    st = hp.open_combat(client, saved, gid)
    st["combat"]["pilhas"]["mao"] = [ATK]
    for e in st["enemies"]:
        hp.hide_enemy(st, e["id"])
    row = _hand(client, gid)[ATK]
    assert row["valid_targets"] == []
    assert row["invalid_reason"] in ("target_hidden", "no_valid_target")
    assert row["jogavel"] is True  # blocked by target, not by contract


def test_every_suggested_target_is_accepted_by_engine(monkeypatch):
    from services import combat_targeting as ct

    client, saved, gid = hp.api_client(monkeypatch)
    st = hp.open_combat(client, saved, gid)
    st["combat"]["pilhas"]["mao"] = [REACT, ATK]
    for cid, row in _hand(client, gid).items():
        for tid in row.get("valid_targets") or []:
            assert (
                ct.check_declared_target(
                    st, card_id=cid, action_kind=None, maneuver=None, target_id=tid
                )
                is None
            )
