from playtest.invariants import check_campaign_grounding


def _state(*, active: bool, needs_replan: bool) -> dict:
    return {
        "world": {
            "turn_count": 23,
            "current_location": "Ophidia",
            "current_location_id": "ophidia",
        },
        "campaign_plan": {"location": "Brekmar", "beats": [{"status": "pending"}]},
        "combat": {"active": active},
        "needs_replan": needs_replan,
    }


def test_grounding_tolera_replan_diferido_durante_combate() -> None:
    state = _state(active=True, needs_replan=True)
    previous = _state(active=True, needs_replan=True)
    assert check_campaign_grounding(state, previous, 23) == []


def test_grounding_tolera_somente_turno_que_encerra_combate() -> None:
    state = _state(active=False, needs_replan=True)
    previous = _state(active=True, needs_replan=True)
    assert check_campaign_grounding(state, previous, 23) == []

    orphan_previous = _state(active=False, needs_replan=True)
    violations = check_campaign_grounding(state, orphan_previous, 24)
    assert [row.check_id for row in violations] == ["campaign.region_grounding"]


def test_grounding_stale_sem_replan_continua_erro() -> None:
    state = _state(active=True, needs_replan=False)
    previous = _state(active=True, needs_replan=False)
    violations = check_campaign_grounding(state, previous, 23)
    assert [row.check_id for row in violations] == ["campaign.region_grounding"]


def test_grounding_viagem_sem_flag_de_replan_e_erro_imediato() -> None:
    state = _state(active=False, needs_replan=False)
    previous = _state(active=False, needs_replan=False)
    previous["world"] = {
        **previous["world"],
        "current_location": "Brekmar",
        "current_location_id": "brekmar",
    }

    violations = check_campaign_grounding(state, previous, 23)

    assert [row.check_id for row in violations] == ["campaign.region_grounding"]
