"""SPEC-302 Etapa 2: pressoes regionais."""

from __future__ import annotations

import json

import pytest

from services import world_engine as we
from services import world_pressures as wp
from tests.spec302_helpers import make_state, quiet, tick


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")


def _rng(day=1, salt="t"):
    return we.day_rng("g", day, salt)


def test_drift_to_baseline():
    cfg = quiet()
    base = wp.baseline(cfg)
    cur = {r: {k: v + 20 for k, v in row.items()} for r, row in base.items()}
    out = wp.step_pressures(cur, rng=_rng(), cfg=cfg)
    for r in base:
        for k in wp.KINDS:
            assert out[r][k] == cur[r][k] - cfg["constants"]["drift_per_day"]


def test_cause_route_blocked_raises_fome_both_regions():
    ev = {
        "type": "route_blocked",
        "target_id": "nova_arcadia",
        "payload": {"other_location_id": "pantano_melancolia"},
    }
    d = wp.event_deltas([ev])
    assert d["nova_arcadia"]["fome"] == 8 and d["pantano_melancolia"]["fome"] == 8
    clear = {**ev, "type": "route_cleared"}
    assert wp.event_deltas([clear])["nova_arcadia"]["fome"] == -8


def test_cause_applied_once_per_event(monkeypatch):
    cfg = wp.get_config()
    monkeypatch.setitem(cfg["constants"], "noise", 0)
    monkeypatch.setitem(cfg["constants"], "surge_p", 0.0)
    st = make_state("once")
    tick(st, 1, 2)  # ancora last_event_seq ao log vazio
    base = st["world_sim"]["pressures"]["nova_arcadia"]["fome"]
    st["event_log"].append(
        {
            "type": "route_blocked",
            "target_id": "nova_arcadia",
            "payload": {"other_location_id": "pantano_melancolia"},
        }
    )
    tick(st, 2, 3)
    up = st["world_sim"]["pressures"]["nova_arcadia"]["fome"]
    assert up == base + 8 - cfg["constants"]["drift_per_day"]
    tick(st, 3, 4)
    assert st["world_sim"]["pressures"]["nova_arcadia"]["fome"] <= up  # nao reaplica


def test_plague_spreads_only_to_adjacent_regions():
    cfg = quiet()
    cfg["constants"]["spread_p"] = 1.0
    base = wp.baseline(cfg)
    cur = {r: dict(row) for r, row in base.items()}
    cur["pantano_melancolia"]["praga"] = 90
    out = wp.step_pressures(cur, rng=_rng(), cfg=cfg)
    adj = set(wp.region_adjacency()["pantano_melancolia"])
    for r in base:
        if r == "pantano_melancolia":
            continue
        if r in adj:
            assert out[r]["praga"] >= base[r]["praga"] + 5
        else:
            assert out[r]["praga"] <= base[r]["praga"]


def test_plague_does_not_cross_blocked_route():
    cfg = quiet()
    cfg["constants"]["spread_p"] = 1.0
    base = wp.baseline(cfg)
    cur = {r: dict(row) for r, row in base.items()}
    cur["pantano_melancolia"]["praga"] = 90
    blocked = set()
    for nb in wp.region_adjacency()["pantano_melancolia"]:
        blocked |= set(wp.region_link_pairs("pantano_melancolia", nb))
    out = wp.step_pressures(cur, rng=_rng(), cfg=cfg, blocked_pairs=blocked)
    for r in base:
        if r != "pantano_melancolia":
            assert out[r]["praga"] <= base[r]["praga"]


def test_hysteresis_no_repeat_events():
    bands = {"r": {k: "normal" for k in wp.KINDS}}
    ups = 0
    for v in (60, 69, 71, 69, 71, 68, 71, 66):
        pressures = {"r": {"guerra": v, "fome": 0, "praga": 0, "abismo": 0}}
        bands, up = wp.update_bands(bands, pressures)
        ups += sum(1 for x in up if x[2:] == ("sinal", "crise"))
    assert ups == 1


def test_signal_cap_per_region_and_global():
    regs = wp.region_ids()
    prev = {r: {k: 10 for k in wp.KINDS} for r in regs}
    cur = {r: {k: 60 for k in wp.KINDS} for r in regs}
    bands = {r: {k: "sinal" for k in wp.KINDS} for r in regs}
    sigs = wp.pick_signals(prev, cur, bands, day=3, rng=_rng())
    assert 0 < len(sigs) <= 4
    assert len({s["region_id"] for s in sigs}) == len(sigs)


def test_pressures_clamped():
    cfg = quiet()
    base = wp.baseline(cfg)
    hi = wp.step_pressures(base, rng=_rng(), cfg=cfg, deltas={"nova_arcadia": {"guerra": 900}})
    lo = wp.step_pressures(base, rng=_rng(), cfg=cfg, deltas={"nova_arcadia": {"guerra": -900}})
    assert hi["nova_arcadia"]["guerra"] == 100 and lo["nova_arcadia"]["guerra"] == 0
    st = make_state("clamp")
    for d in range(1, 120, 10):
        tick(st, d, d + 10)
    assert all(0 <= v <= 100 for row in st["world_sim"]["pressures"].values() for v in row.values())


def test_region_adjacency_derived_from_map():
    adj = wp.region_adjacency()
    assert len(adj) == 12 and len(wp.region_ids()) == 12
    for a, nbs in adj.items():
        assert a not in nbs and nbs
        for b in nbs:
            assert a in adj[b]


def test_independent_of_player():
    a = make_state("ind", player={"level": 1})
    b = make_state("ind", player={"level": 20, "gold": 10**6})
    tick(a, 1, 10), tick(b, 1, 10)
    assert json.dumps(a["world_sim"]["pressures"]) == json.dumps(b["world_sim"]["pressures"])
