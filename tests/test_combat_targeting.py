"""SPEC-205: alvos válidos, motivo de indisponibilidade e rejeição de borda."""

from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import HTTPException

import api
from services import combat_targeting as ct
from tests.test_combat_simulator import _request

ATK = "san_corte_troca"  # dano, livre, 0E
ATK_TURN = "san_sil_exato"  # dano, turno, 1E
SUPPORT = "san_transfusao_hostil"  # cura, cena, 2E


def _state(quantity: int = 2) -> dict:
    state = api._build_combat_simulator_state(_request(quantity=quantity))
    player = state["player"]
    for cid in (ATK, ATK_TURN, SUPPORT):
        if cid not in player["known_cards"]:
            player["known_cards"].append(cid)
        if cid not in player["prepared_cards"]:
            player["prepared_cards"].append(cid)
    player["entropy"] = 10
    return state


def _enemy_ids(state):
    return [e["id"] for e in state["enemies"]]


def _req(**kw) -> api.ActionRequest:
    return api.ActionRequest(game_id="g", input_text="x", **kw)


def test_attack_card_lists_alive_enemies_only():
    state = _state()
    ids = _enemy_ids(state)
    res = ct.valid_targets_for_card(state, ATK)
    assert res.valid_targets == ids and res.invalid_reason is None
    state["enemies"][0].update(dead=True, status="morto")
    assert ct.valid_targets_for_card(state, ATK).valid_targets == [ids[1]]


def test_dead_target_excluded_and_reason_when_none_alive():
    state = _state(1)
    state["enemies"][0].update(dead=True, status="morto")
    res = ct.valid_targets_for_card(state, ATK)
    assert res.valid_targets == [] and res.invalid_reason == "target_dead"


def test_hidden_target_reason():
    state = _state(1)
    eid = _enemy_ids(state)[0]
    scene = state["combat"]["scene"]
    scene["positions"][eid]["hidden_from"] = ["player"]
    res = ct.valid_targets_for_card(state, ATK)
    assert res.valid_targets == [] and res.invalid_reason == "target_hidden"
    # posição aproximada devolve a mira (Desvantagem), como o motor.
    scene["positions"][eid]["approx_from"] = ["player"]
    assert ct.valid_targets_for_card(state, ATK).valid_targets == [eid]


def test_no_entropy_reason():
    state = _state()
    state["player"]["entropy"] = 0
    res = ct.valid_targets_for_card(state, SUPPORT)
    assert res.valid_targets == [] and res.invalid_reason == "no_entropy"


def test_spent_frequency_reason():
    state = _state()
    state["player"]["card_usage"] = {
        ATK_TURN: {"used_this_turn": 1},
        SUPPORT: {"used_this_scene": 1},
    }
    for cid in (ATK_TURN, SUPPORT):
        res = ct.valid_targets_for_card(state, cid)
        assert res.invalid_reason == "spent_frequency" and res.valid_targets == []


def test_not_prepared_reason():
    state = _state()
    state["player"]["prepared_cards"].remove(ATK)
    assert ct.valid_targets_for_card(state, ATK).invalid_reason == "not_prepared"


def test_silence_maps_to_cooldown():
    state = _state()
    state["player"]["active_conditions"] = [
        {"name": "Silêncio", "control": "silence", "duration": 2}
    ]
    assert ct.valid_targets_for_card(state, ATK).invalid_reason == "cooldown"


def test_combat_inactive_and_not_your_turn():
    state = _state()
    state["death_pending"] = True
    assert ct.valid_targets_for_card(state, ATK).invalid_reason == "not_your_turn"
    state["death_pending"] = False
    state["combat"]["active"] = False
    assert ct.valid_targets_for_card(state, ATK).invalid_reason == "combat_inactive"
    assert ct.basic_action_targeting(state, "attack").invalid_reason == "combat_inactive"


def test_support_card_targets_player_and_allies_never_enemies():
    state = _state()
    res = ct.valid_targets_for_card(state, SUPPORT)
    assert res.valid_targets[0] == "player"
    assert not set(res.valid_targets) & set(_enemy_ids(state))
    state["party"] = [
        {"id": "comp_bruna", "name": "Bruna", "active": True, "hp": 5, "vitalidade": 5}
    ]
    assert "comp_bruna" in ct.valid_targets_for_card(state, SUPPORT).valid_targets


def test_basic_attack_single_target_and_actions_shape():
    state = _state(1)
    actions = {(a["kind"], a.get("maneuver")): a for a in ct.basic_actions(state)}
    assert actions[("attack", None)]["valid_targets"] == _enemy_ids(state)
    assert actions[("flee", None)]["valid_targets"] == []
    assert actions[("maneuver", "engajar")]["valid_targets"] == _enemy_ids(state)
    assert actions[("maneuver", "guardar")]["invalid_reason"] is None


def test_unknown_reason_never_emitted():
    state = _state()
    variants = [state]
    s = deepcopy(state)
    s["player"]["entropy"] = 0
    variants.append(s)
    s = deepcopy(state)
    s["combat"]["active"] = False
    variants.append(s)
    s = deepcopy(state)
    s["enemies"][0].update(dead=True, status="morto")
    s["enemies"][1].update(dead=True, status="morto")
    variants.append(s)
    for variant in variants:
        for cid in variant["player"]["known_cards"]:
            assert ct.card_targeting(variant, cid)["invalid_reason"] in (None, *ct.INVALID_REASONS)
        for action in ct.basic_actions(variant):
            assert action["invalid_reason"] in (None, *ct.INVALID_REASONS)


def test_combat_block_exposes_additive_fields():
    state = _state()
    block = api._combat_block(state)
    assert "basic_actions" in block
    rows = {c["id"]: c for c in block["cards"]}
    assert rows[ATK]["valid_targets"] == _enemy_ids(state)
    assert "invalid_reason" in rows[ATK]
    # ids = participant_id do manifesto SPEC-203
    manifest_ids = {p["participant_id"] for p in block["encounter_view"].get("participants", [])}
    assert set(rows[ATK]["valid_targets"]) <= manifest_ids or not manifest_ids


# ---- paridade com o motor / borda ------------------------------------------
def test_targeting_matches_server_revalidation():
    from services.conflict_turn import TurnStep, _invalid_target_reason

    state = _state()
    scene = state["combat"]["scene"]
    actors = {"player": state["player"], **{e["id"]: e for e in state["enemies"]}}
    sides = {"hero": ["player"], "ally": [], "enemy": _enemy_ids(state)}
    for cid in (ATK, SUPPORT):
        support = cid == SUPPORT
        res = ct.valid_targets_for_card(state, cid)
        for tid in res.valid_targets:
            assert (
                _invalid_target_reason(
                    scene,
                    state["player"],
                    "player",
                    actors,
                    TurnStep(kind="card", card_id=cid, target_id=tid),
                    support=support,
                    sides=sides,
                )
                is None
            )
    # fora da lista: o motor também recusa (inimigo como alvo de suporte)
    bad = _invalid_target_reason(
        scene,
        state["player"],
        "player",
        actors,
        TurnStep(kind="card", card_id=SUPPORT, target_id=_enemy_ids(state)[0]),
        support=True,
        sides=sides,
    )
    assert bad


def test_invalid_target_rejected_without_spending():
    state = _state()
    before = deepcopy(state)
    state["enemies"][0].update(dead=True, status="morto")
    dead_id = state["enemies"][0]["id"]
    snapshot = deepcopy(state)
    with pytest.raises(HTTPException) as exc:
        api._apply_action_options(state, _req(card_id=ATK_TURN, target_id=dead_id))
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "invalid_target"
    assert exc.value.detail["invalid_reason"] == "no_valid_target"
    assert state == snapshot  # nada consumido/declarado
    assert state["player"]["entropy"] == before["player"]["entropy"]
    assert "combat_declaration" not in state


def test_attack_with_stale_target_rejected():
    state = _state()
    state["enemies"][0].update(dead=True, status="morto")
    with pytest.raises(HTTPException) as exc:
        api._apply_action_options(
            state, _req(action_kind="attack", target_id=state["enemies"][0]["id"])
        )
    assert exc.value.detail["code"] == "invalid_target"


def test_valid_target_accepted_and_declared():
    state = _state()
    eid = _enemy_ids(state)[1]
    api._apply_action_options(state, _req(card_id=ATK, target_id=eid))
    assert state["combat_declaration"]["acao"]["target_id"] == eid


def test_support_card_from_ui_targets_player():
    """R10/R12: sem alvo ou com inimigo vindo da UI, suporte resolve no jogador."""
    for tid in (None, "mon_cao_rebite__sim_1"):
        state = _state()
        api._apply_action_options(state, _req(card_id=SUPPORT, target_id=tid))
        assert state["combat_declaration"]["acao"]["target_id"] == "player"


def test_old_client_payload_still_valid():
    state = _state()
    api._apply_action_options(state, _req(card_id=ATK))  # sem target_id
    assert state["combat_declaration"]["acao"]["card_id"] == ATK
    api._apply_action_options(state, _req(action_kind="flee"))
    assert state["combat_declaration"]["acao"]["kind"] == "flee"


def _client(monkeypatch):
    from fastapi.testclient import TestClient

    import agents.campaign_manager as campaign_manager
    import agents.combat as combat_agent
    import character_creator

    saved: dict = {}

    def save(state):
        saved[state["game_id"]] = deepcopy(state)
        return True

    def load(path=None):
        if not path:
            return None
        gid = path.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".json")
        return deepcopy(saved.get(gid))

    def forbidden(*_a, **_k):
        raise AssertionError("sem LLM/RAG")

    monkeypatch.setattr(api, "save_game_state", save)
    monkeypatch.setattr(api, "load_game_state", load)
    for mod, name in (
        (character_creator, "get_llm"),
        (character_creator, "query_rag"),
        (campaign_manager, "get_llm"),
        (combat_agent, "get_llm"),
        (combat_agent, "build_context_pack"),
    ):
        monkeypatch.setattr(mod, name, forbidden)
    monkeypatch.setattr("services.checkpoints.maybe_write", forbidden)
    return TestClient(api.app), saved


def test_action_retry_same_action_id_single_turn_card(monkeypatch):
    client, saved = _client(monkeypatch)
    first = client.post("/game/combat-simulator", json=_request(quantity=2).model_dump()).json()
    gid = first["game_id"]
    cards_view = {c["id"]: c for c in first["combat"]["cards"]}
    assert cards_view["san_finta"]["valid_targets"][0] == "player"
    assert first["combat"]["basic_actions"][0]["kind"] == "attack"
    target = first["combat"]["enemies"][0]["id"]
    body = {
        "game_id": gid,
        "input_text": "Uso Finta.",
        "card_id": "san_finta",
        "action_id": "11111111-1111-4111-8111-111111111111",
    }
    a = client.post("/game/action", json=body)
    b = client.post("/game/action", json=body)
    assert a.status_code == b.status_code == 200, (a.text, b.text)
    assert a.json()["combat"]["round"] == b.json()["combat"]["round"] == 1
    assert saved[gid]["combat"]["round"] == 1
    # Alvo velho: 409 estruturado, sem mudar o estado salvo.
    snap = deepcopy(saved[gid])
    stale = client.post(
        "/game/action",
        json={
            "game_id": gid,
            "input_text": "x",
            "action_kind": "attack",
            "target_id": "nao_existe",
            "action_id": "22222222-2222-4222-8222-222222222222",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "invalid_target"
    assert saved[gid]["combat"]["round"] == snap["combat"]["round"]
    assert target


def test_empty_scene_allies_recomputed_like_engine(monkeypatch):
    """Revisão Sol: `combat.scene_allies == []` recalcula como o motor (`or`)."""
    import party as party_mod

    state = _state()
    state["combat"]["scene_allies"] = []
    monkeypatch.setattr(
        party_mod,
        "scene_allies",
        lambda st, excluded=None: [
            {"id": "npc_brunna", "name": "Brunna", "hp": 5, "vitalidade": 5}
        ],
    )
    assert "npc_brunna" in ct.valid_targets_for_card(state, SUPPORT).valid_targets
