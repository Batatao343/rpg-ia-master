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


def test_two_flanking_enemies_hide_from_hero_by_rule_r5():
    """SPEC-398 R5: arquétipos de flanco (`batedor`; `covarde_oportunista` e `agil` têm `sempre: flank`, SPEC-285): no 1o round os dois
    se escondem do herói (relativo, `hide(observers=[alvo])`). Regra legítima, não bug: o ataque
    por Carta fica sem mira (`target_hidden`) até um `procurar`; passar e Cartas de aliado seguem."""
    import random

    from services import combat_targeting as ct
    from services import conflict_orchestrator as orch
    from tests.test_tactical_archetypes_runtime import _actor, _pass, _player, _scene

    player = _player()
    foes = [_actor(f"e{i}", "batedor", category="padrao", agility=4) for i in (1, 2)]
    scene = _scene("player", "e1", "e2")
    actors = {"player": player, **{f["id"]: f for f in foes}}
    orch.run_round(
        scene,
        actors,
        {"hero": ["player"], "enemy": ["e1", "e2"]},
        declarations={"player": _pass("player")},
        initiator="enemy",
        rng=random.Random(3),
    )
    state = {"combat": {"active": True, "scene": scene}, "enemies": foes, "player": player}
    res = ct.hand_card_targeting(state, ATK)
    assert res["valid_targets"] == [] and res["invalid_reason"] == "target_hidden"
    assert all(scene["positions"][f["id"]]["hidden_from"] == ["player"] for f in foes)
    # Procurar é a saída: mira justamente quem está escondido, e o 409 não o recusa.
    seek = ct.basic_action_targeting(state, "maneuver", "procurar")
    assert seek.invalid_reason is None and seek.valid_targets == ["e1", "e2"]
    assert (
        ct.check_declared_target(
            state, card_id=None, action_kind="maneuver", maneuver="procurar", target_id="e1"
        )
        is None
    )
    # Atacar escondido continua recusado (R5 não afrouxa a regra de ocultação).
    assert ct.basic_action_targeting(state, "attack").invalid_reason == "target_hidden"


def test_status_curse_card_in_hand_keeps_fardo_contract(monkeypatch):
    """Review P1-1: Carta de status/maldição (Fardo) não recebe `not_playable_from_hand`."""
    client, saved, gid = hp.api_client(monkeypatch)
    st = hp.open_combat(client, saved, gid)
    st["combat"]["pilhas"]["mao"] = ["sts_dor_surda", REACT]
    hand = _hand(client, gid)
    assert hand["sts_dor_surda"]["jogavel"] is False
    assert hand["sts_dor_surda"].get("invalid_reason") != "not_playable_from_hand"
    assert hand[REACT]["invalid_reason"] == "not_playable_from_hand"


def test_hidden_plus_visible_enemy_suggestions_never_409(monkeypatch):
    """Review P3-2/P3-3: 1 escondido + 1 visível. Atacar mira só o visível; Procurar só o escondido
    (Procurar no visível dá 409 `no_valid_target`: a Ação não é gasta à toa)."""
    from services import combat_targeting as ct

    client, saved, gid = hp.api_client(monkeypatch)
    st = hp.open_combat(client, saved, gid)
    second = hp.add_second_enemy(st)
    first = next(e["id"] for e in st["enemies"] if e["id"] != second)
    hp.hide_enemy(st, first)
    st["combat"]["pilhas"]["mao"] = [ATK]
    row = _hand(client, gid)[ATK]
    assert row["valid_targets"] == [second]
    cases = [(ATK, None, None), (None, "attack", None), (None, "maneuver", "procurar")]
    for card_id, kind, man in cases:
        res = (
            ct.hand_card_targeting(st, card_id)
            if card_id
            else ct.basic_action_targeting(st, kind, man).as_dict()
        )
        assert res["valid_targets"]
        for tid in res["valid_targets"]:
            assert (
                ct.check_declared_target(
                    st, card_id=card_id, action_kind=kind, maneuver=man, target_id=tid
                )
                is None
            )
    assert ct.basic_action_targeting(st, "maneuver", "procurar").valid_targets == [first]
    assert (
        ct.check_declared_target(
            st, card_id=None, action_kind="maneuver", maneuver="procurar", target_id=second
        )
        == "no_valid_target"
    )
    assert (
        ct.check_declared_target(
            st, card_id=None, action_kind="attack", maneuver=None, target_id=first
        )
        == "no_valid_target"
    )
