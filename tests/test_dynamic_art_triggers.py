from services.art_triggers import ArtGenerationRequest, arc_instance_id, reserve_request


def _state(turn=0, arc="a"):
    return {
        "game_id": "game", "world": {"turn_count": turn},
        "campaign_plan": {"arc_title": "Arco", "last_planned_turn": 1,
                          "arc_instance_id": arc},
        "art_arc_budgets": {}, "art_generation_ledger": [],
    }


def _npc(index, arc="a"):
    return ArtGenerationRequest("npc_first_appearance", f"npc-{index}", "npc",
                                f"npc-{index}", arc, f"action-{index}")


def test_quatro_npcs_por_arco_cooldown_e_novo_arco_renova():
    state = _state()
    for index in range(4):
        state["world"]["turn_count"] = index * 15
        reserved = reserve_request(state, _npc(index))
        assert reserved
        state.update({key: reserved[key] for key in ("art_arc_budgets", "art_generation_ledger")})
    state["world"]["turn_count"] = 100
    assert reserve_request(state, _npc(5)) is None
    assert reserve_request(state, _npc(0)) is None
    renewed = reserve_request(state, _npc(0, arc="b"))
    assert renewed and renewed["art_arc_budgets"]["b"]["npc_generations_used"] == 1


def test_epico_unico_e_subclasse_nunca_reserva():
    state = _state()
    epic = ArtGenerationRequest("arc_epic_moment", "boss-1", "scene", "boss-1", "a", "x")
    first = reserve_request(state, epic)
    assert first
    state.update({key: first[key] for key in ("art_arc_budgets", "art_generation_ledger")})
    assert reserve_request(state, ArtGenerationRequest(
        "arc_epic_moment", "conclusion", "scene", "end", "a", "y")) is None
    assert reserve_request(state, ArtGenerationRequest(
        "subclass_chosen", "consagrado", "player", "player", "a", "z")) is None


def test_arc_instance_id_nao_depende_apenas_do_titulo():
    one = _state(); one["campaign_plan"].pop("arc_instance_id")
    two = _state(); two["campaign_plan"].pop("arc_instance_id"); two["campaign_plan"]["last_planned_turn"] = 50
    assert arc_instance_id(one) != arc_instance_id(two)
