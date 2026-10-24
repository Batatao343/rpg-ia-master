"""SPEC-303 Etapa 7: invariantes e relatorio do playtest (R27)."""

from __future__ import annotations

from playtest import invariants as inv
from playtest import telemetry as tel
from tests.spec303_helpers import cal_for


def _st(rows=None, season="inverno", day=10, cal=None):
    return {
        "world_sim": {
            "calendar": cal or cal_for("inverno", 1),
            "last_ticked_day": day,
            "enabled_from_day": 1,
        },
        "world_projection": {"location_states": rows or {}},
        "world": {"season": {"id": season}, "world_clock": {"day": day}},
    }


def _ids(vs):
    return {v.check_id for v in vs}


def test_invariants_festa_over_crisis_and_season_regressed():
    prev = _st({"nova_arcadia": {"state": "cerco"}})
    cur = _st({"nova_arcadia": {"state": "festa"}})
    assert "calendar.festa_over_crisis" in _ids(inv.check_calendar(cur, prev, 3))
    ok = _st({"nova_arcadia": {"state": "festa"}})
    assert not inv.check_calendar(ok, _st({}), 3)
    back = _st(season="outono")
    assert "calendar.season_regressed" in _ids(inv.check_calendar(back, _st(season="inverno"), 3))
    changed = _st(cal=cal_for("verao", 1))
    assert "calendar.params_changed" in _ids(inv.check_calendar(changed, _st(), 3))
    assert not inv.check_calendar(_st(), _st(), 3)


def test_report_world_section_has_seasons_and_festas():
    st = _st()
    st["world_sim"]["festivals"] = [{"status": "cancelada"}, {"status": "encerrada"}]
    st["world_sim"]["perceived_stats"] = {"festas": 2, "pass_crossings": 1}
    out = tel._world_summary(st)
    assert out["seasons_seen"] >= 1 and out["festas_perceived"] == 2
    assert out["festas_cancelled"] == 1 and out["pass_crossings"] == 1
