"""SPEC-215 §4 passo 1 — distância em períodos (Dijkstra sobre travel_times)."""

import gamedata
import world_utils
from services.world_distance import travel_periods


def test_adjacent_equals_travel_cost():
    for dest_id in ("brekmar", "deserto_zhur", "pantano_melancolia"):
        cost = world_utils.travel_cost(
            {"current_location_id": "nova_arcadia"}, gamedata.get_location(dest_id)
        )
        assert travel_periods("nova_arcadia", dest_id) == cost


def test_multi_hop_sums_shortest_path():
    # nova_arcadia -2-> brekmar -3-> ophidia
    assert travel_periods("nova_arcadia", "ophidia") == 5
    assert travel_periods("nova_arcadia", "nova_arcadia") == 0


def test_interior_zero():
    # anel_lama (0) -> taverna (interior, 0)
    assert travel_periods("nova_arcadia", "na_taverna_javali") == 0


def test_unreachable_none():
    assert travel_periods("nova_arcadia", "lugar_que_nao_existe") is None
    assert travel_periods("", "nova_arcadia") is None


def test_symmetric_fallback():
    # deserto_zhur define 2 p/ nova_arcadia; ida e volta coincidem.
    assert travel_periods("deserto_zhur", "nova_arcadia") == 2
    assert travel_periods("nova_arcadia", "deserto_zhur") == 2
