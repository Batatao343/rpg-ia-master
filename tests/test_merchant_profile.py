from __future__ import annotations

import copy
import random

import playtest.profiles as profile_module
from playtest.invariants import check_contextual
from playtest.profiles import Comerciante
from playtest.runner import TurnRecord, _merchant_action_family
from services import economy


def _state(location_id: str = "na_anel_dourado") -> dict:
    return {
        "player": {
            "name": "Iria",
            "class_name": "Sangromante",
            "gold": 500,
            "vitalidade": 18,
            "max_vitalidade": 18,
            "inventory": [{"id": "corda", "qty": 2}],
            "equipment": {},
        },
        "world": {
            "current_location_id": location_id,
            "visited": [location_id],
            "turn_count": 3,
            "world_clock": {"day": 1, "period": "manha"},
            "merchant_stocks": {},
            "merchant_restock_day": {},
            "danger_level": 1,
        },
        "world_projection": {},
        "factions": [],
        "npcs": {},
        "enemies": [],
    }


def test_public_market_snapshot_is_read_only_and_uses_canonical_prices():
    state = _state()
    before = copy.deepcopy(state)

    snapshot = economy.public_market_snapshot(state)

    assert state == before
    assert snapshot is not None
    assert snapshot["merchant_id"] == "mercado_anel_dourado"
    potion = next(q for q in snapshot["quotes"] if q["item_id"] == "pocao_cura")
    merchant = economy.MERCHANTS[snapshot["merchant_id"]]
    assert potion["buy_price"] == economy.price(
        "pocao_cura", mode="buy", state=state, merchant=merchant,
    )
    assert potion["sell_price"] < potion["buy_price"]


def test_public_market_snapshot_never_exposes_remote_market():
    snapshot = economy.public_market_snapshot(_state())
    assert snapshot is not None
    assert snapshot["location_id"] == "na_anel_dourado"
    assert snapshot["merchant_id"] != "ferreiro_skallgard"


def test_public_market_snapshot_quotes_player_item_without_making_it_buyable():
    state = _state()
    state["player"]["inventory"] = [{"id": "adaga_serrilhada", "qty": 1}]

    snapshot = economy.public_market_snapshot(state)

    quote = next(q for q in snapshot["quotes"] if q["item_id"] == "adaga_serrilhada")
    assert quote["stock"] == 0
    assert quote["sell_price"] > 0


def test_merchant_reset_clears_campaign_memory_and_is_deterministic():
    state = _state()
    profile = Comerciante()
    profile.reset()
    first = [profile.decide(state, random.Random(9)).text for _ in range(6)]
    assert profile.quote_book
    profile.acquisition_cost["corda"] = 20

    profile.reset()
    second = [profile.decide(state, random.Random(9)).text for _ in range(6)]

    assert first == second
    assert "corda" not in profile.acquisition_cost
    assert profile.resolve_progression is True


def test_transaction_conservation_detects_corrupt_gold_delta():
    outcome = {
        "ok": True,
        "mode": "buy",
        "item_id": "corda",
        "qty": 1,
        "gold_before": 100,
        "gold_after": 95,
        "gold_delta": -10,
        "inventory_before": [{"id": "corda", "qty": 1}],
        "inventory_after": [{"id": "corda", "qty": 2}],
        "stock_before": [{"item_id": "corda", "stock": 3}],
        "stock_after": [{"item_id": "corda", "stock": 2}],
    }
    violations = check_contextual(
        _state(), None, 4, {"economy_action": outcome, "net_worth_after": 110},
    )
    assert "economy.transaction_conservation" in {
        violation.check_id for violation in violations
    }


def test_transaction_conservation_sums_duplicate_non_stackable_entries():
    outcome = {
        "ok": True,
        "mode": "buy",
        "item_id": "escudo_amassado",
        "qty": 1,
        "gold_before": 100,
        "gold_after": 90,
        "gold_delta": -10,
        "inventory_before": [{"id": "escudo_amassado", "qty": 1}],
        "inventory_after": [
            {"id": "escudo_amassado", "qty": 1},
            {"id": "escudo_amassado", "qty": 1},
        ],
        "stock_before": [{"item_id": "escudo_amassado", "stock": 2}],
        "stock_after": [{"item_id": "escudo_amassado", "stock": 1}],
    }

    violations = check_contextual(
        _state(), None, 4, {"economy_action": outcome, "net_worth_after": 110},
    )

    assert "economy.transaction_conservation" not in {
        violation.check_id for violation in violations
    }


def test_merchant_mix_contains_all_normal_play_families():
    profile = Comerciante()
    profile.reset()
    state = _state()
    rng = random.Random(12)
    for _ in range(55):
        profile.decide(state, rng)
    assert profile.action_counts["economy"] > 0
    assert profile.action_counts["exploration"] > 0
    assert profile.action_counts["social"] > 0
    assert profile.action_counts["quest"] > 0


def test_merchant_overexploration_switches_to_normal_social_or_quest_action(monkeypatch):
    profile = Comerciante()
    profile.reset()
    profile.action_counts.update({
        "economy": 35, "exploration": 40, "quest": 8, "social": 8, "survival": 9,
    })
    state = _state("rota_sem_mercado")
    monkeypatch.setattr(profile_module, "_connections", lambda _location: [])
    before_exploration = profile.action_counts["exploration"]

    decision = profile.decide(state, random.Random(13))

    assert profile.action_counts["exploration"] == before_exploration
    assert decision.text.startswith(("Pergunto", "Converso"))


def test_merchant_action_family_does_not_read_cura_inside_procurando():
    record = TurnRecord(
        turn=1,
        action="Viajo para Brekmar procurando novos mercados.",
        route="storyteller",
        latency_ms=1,
    )

    assert _merchant_action_family(record) == "exploration"

    record.action = "Uso uma poção de cura em mim."
    assert _merchant_action_family(record) == "survival"


def test_merchant_learns_to_avoid_observed_location_when_no_travel_was_planned(
    monkeypatch,
):
    profile = Comerciante()
    profile.reset()
    monkeypatch.setattr(profile_module, "_connections", lambda _location: [])
    state = _state("deserto_zhur")
    state["continuity"] = {"timeline_epoch": 0}
    profile.decide(state, random.Random(3))
    state["continuity"] = {"timeline_epoch": 1}
    state["world"]["current_location_id"] = "brekmar"

    profile.decide(state, random.Random(3))

    assert "deserto_zhur" in profile._avoided_locations


def test_merchant_avoids_fatal_travel_destination_not_rollback_source(monkeypatch):
    profile = Comerciante()
    profile.reset()
    monkeypatch.setattr(profile_module, "_connections", lambda _location: [
        {"id": "pradaria_ruinas", "name": "Pradaria das Ruínas", "danger": 3,
         "tags": []},
    ])
    departed = _state("nova_arcadia")
    departed["continuity"] = {"timeline_epoch": 0}
    profile.decide(departed, random.Random(3))
    assert profile._last_travel_destination_id == "pradaria_ruinas"

    rolled_back = _state("nova_arcadia")
    rolled_back["continuity"] = {"timeline_epoch": 1}
    profile.decide(rolled_back, random.Random(3))

    assert "pradaria_ruinas" in profile._avoided_locations
    assert "nova_arcadia" not in profile._avoided_locations


def test_merchant_prefers_low_risk_route_after_survival_pressure(monkeypatch):
    profile = Comerciante()
    profile.reset()
    profile.action_counts.update({
        "economy": 30, "exploration": 20, "social": 10, "quest": 10, "survival": 30,
    })
    monkeypatch.setattr(profile_module, "_connections", lambda _location: [
        {"id": "perigo", "name": "Desfiladeiro Mortal", "danger": 5, "tags": []},
        {"id": "seguro", "name": "Estrada Segura", "danger": 1, "tags": []},
    ])
    state = _state("origem")
    state["world"]["visited"] = ["origem", "perigo", "seguro"]

    action = profile._travel_action(state, random.Random(4))

    assert "Estrada Segura" in action
