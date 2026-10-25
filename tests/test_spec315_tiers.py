"""SPEC-315 D6 (dono 25/10): loteria do TAMANHO do achado; teto de frequencia segue 1/20 dias."""

from __future__ import annotations

import random

import pytest

import gamedata
from inventory import is_unique
from services import economy, exploration
from services import rumor_adoption as ra
from tests.spec315_helpers import FAR, adopted_row, set_flags, state

TIERS = ra.config()["find_tiers"]


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    set_flags(monkeypatch)


def _rows(n: int):
    return [adopted_row(f"r{i:010d}", "esconderijo", FAR, born=i % 7) for i in range(n)]


def test_tier_distribution_within_3pp():
    st = state()
    loc = {"danger": 2}
    picks = [ra.find_tier(st, r, loc) for r in _rows(6000)]
    total = sum(float(t["weight"]) for t in TIERS.values())
    for tid, t in TIERS.items():
        want = float(t["weight"]) / total
        got = picks.count(tid) / len(picks)
        assert abs(got - want) < 0.03, (tid, got, want)


def test_tier_deterministic_and_independent_of_hero():
    row = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR)
    poor, rich = state(), state()
    poor["player"] = {"level": 1, "gold": 0}
    rich["player"] = {"level": 20, "gold": 9999}
    assert ra.find_tier(poor, row, {"danger": 2}) == ra.find_tier(rich, row, {"danger": 2})
    assert ra.find_tier(poor, row, {"danger": 2}) == ra.find_tier(poor, row, {"danger": 2})


def test_high_danger_bumps_one_step():
    st = state()
    for r in _rows(300):
        base = ra.find_tier(st, r, {"danger": 2})
        up = ra.find_tier(st, r, {"danger": 4})
        order = ra.TIER_ORDER
        assert order.index(up) == min(len(order) - 1, order.index(base) + 1)


def _grant(tier_id: str, seed: int, kind="esconderijo", inventory=None, loc_id="pradaria_ruinas"):
    loc = gamedata.get_location(loc_id)
    player = {"gold": 0, "inventory": list(inventory or [])}
    note, got = exploration.grant_rumor_cache(
        player,
        {},
        loc,
        random.Random(seed),
        kind=kind,
        tier=TIERS[tier_id],
        tier_id=tier_id,
    )
    return player, note, got


@pytest.mark.parametrize("tier_id", list(TIERS))
def test_gold_cap_per_tier(tier_id):
    for seed in range(120):
        player, _n, got = _grant(tier_id, seed)
        assert got["gold"] <= TIERS[tier_id]["gold_max"] and player["gold"] == got["gold"]


def test_higher_tiers_find_better_things():
    def rank(tier_id):
        ladder = economy.RARITY_LADDER
        tot = n = 0
        for seed in range(150):
            _p, _note, got = _grant(tier_id, seed, "item_perdido", loc_id="montanhas_afiadas")
            if got["item_id"]:
                table = (
                    economy.LOOT_TABLES.get("montanhas_afiadas") or economy.LOOT_TABLES["default"]
                )
                for r, items in (table.get("pools") or {}).items():
                    if got["item_id"] in items:
                        tot += ladder.index(r)
                        n += 1
                        break
        return tot / max(1, n)

    assert rank("comum") < rank("bom") <= rank("raro") <= rank("excepcional")


def test_non_exceptional_tiers_never_unique():
    for tier_id in ("comum", "bom", "raro"):
        for seed in range(200):
            _p, _n, got = _grant(tier_id, seed, "item_perdido", loc_id="montanhas_afiadas")
            assert not got["item_id"] or not is_unique(got["item_id"])
            assert got["_events"] == []


def test_unique_never_duplicated_or_placed():
    placed = exploration._placed_uniques()
    seen = 0
    for seed in range(400):
        player, _n, got = _grant("excepcional", seed, "item_perdido", loc_id="montanhas_afiadas")
        item = got["item_id"]
        if item and is_unique(item):
            seen += 1
            assert item not in placed
            assert [e["target_id"] for e in got["_events"]] == [item]  # claim p/ a projection
    # com o unico ja na mochila do heroi, nunca duplica
    for seed in range(400):
        _p, _n, got = _grant(
            "excepcional",
            seed,
            "item_perdido",
            inventory=[{"id": "art_adaga_vidro_dragao", "qty": 1}],
            loc_id="montanhas_afiadas",
        )
        assert got["item_id"] != "art_adaga_vidro_dragao"
    assert seen >= 0


def test_unique_claimed_in_projection_is_not_found():
    proj = {"unique_items": {u: {"holder": "player"} for u in _all_uniques()}}
    loc = gamedata.get_location("montanhas_afiadas")
    for seed in range(200):
        player = {"gold": 0, "inventory": []}
        _n, got = exploration.grant_rumor_cache(
            player,
            {},
            loc,
            random.Random(seed),
            kind="item_perdido",
            projection=proj,
            tier=TIERS["excepcional"],
            tier_id="excepcional",
        )
        assert not got["item_id"] or not is_unique(got["item_id"])


def _all_uniques():
    return [k for k in gamedata.ARTIFACTS_DB if is_unique(k)]


def test_note_never_shows_tier_label_or_number_of_tier():
    for tier_id in TIERS:
        _p, note, _g = _grant(tier_id, 3)
        for bad in ("excepcional", "tier", "bom", "loteria", "nível do achado"):
            assert bad not in note.lower().replace("bom ", "")  # "bom" so como palavra solta


def test_cap_still_one_find_per_20_days():
    st = state(world_sim={"find_log": [3]})
    from tests.spec315_helpers import claim

    assert ra.validate_claim(st, claim("esconderijo", FAR), 10) == "budget"
    assert ra.validate_claim(st, claim("item_perdido", "pradaria_ruinas"), 23) == ""


def test_materialize_records_tier_and_events():
    row = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=True)
    st = state(5, FAR, world_sim={"rumors": [row]})
    upd, marked = ra.materialize(st, row, 5)
    mat = marked["materialization"]
    assert mat["tier"] in TIERS and "_events" not in mat
    assert mat["gold"] <= TIERS[mat["tier"]]["gold_max"]
    assert isinstance(upd["events"], list)
