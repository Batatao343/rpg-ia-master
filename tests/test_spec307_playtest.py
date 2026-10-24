"""SPEC-307 Etapa 5: invariantes e telemetria do playtest (R24-R25)."""

from __future__ import annotations

from playtest import invariants as inv
from playtest import telemetry as tel
from services import world_calendar as wc
from tests.spec303_helpers import cal_for, v1_cal


def _st(cal=None, season="inverno", day=10, date=None, ticked=None):
    w = {"season": {"id": season}, "world_clock": {"day": day}}
    if date is not None:
        w["date"] = date
    return {
        "world_sim": {
            "calendar": cal or cal_for("inverno", 1),
            "last_ticked_day": day if ticked is None else ticked,
            "enabled_from_day": 1,
        },
        "world_projection": {"location_states": {}},
        "world": w,
    }


def _ids(vs):
    return {v.check_id for v in vs}


def test_params_changed_allows_single_v1_to_v2():
    v1 = v1_cal("inverno", 1)
    prev = _st(cal=v1)
    migrated = _st(cal=wc.migrate_calendar(v1, "g", 10))
    assert "calendar.params_changed" not in _ids(inv.check_calendar(migrated, prev, 3))
    # qualquer outra mudanca continua error (v2 -> v2 diferente, v1 -> v2 sem marca)
    assert "calendar.params_changed" in _ids(
        inv.check_calendar(_st(cal=cal_for("verao", 1)), _st(), 3)
    )
    unmarked = {k: v for k, v in wc.migrate_calendar(v1, "g", 10).items() if k != "migrated_from"}
    assert "calendar.params_changed" in _ids(inv.check_calendar(_st(cal=unmarked), prev, 3))


def test_season_regressed_uses_v2_lengths():
    prev = _st(season="verao", day=10)
    # estacao anda para tras em 15 dias (< 20, menor estacao v2): erro
    assert "calendar.season_regressed" in _ids(
        inv.check_calendar(_st(season="primavera", day=25), prev, 3)
    )
    # 21 dias depois ja pode ser a volta do ano: nao e regressao
    assert "calendar.season_regressed" not in _ids(
        inv.check_calendar(_st(season="primavera", day=31), prev, 3)
    )
    assert "calendar.season_regressed" not in _ids(
        inv.check_calendar(_st(season="outono", day=11), prev, 3)
    )


def test_date_regressed_and_stale():
    cal = cal_for("primavera", 1)
    d5, d4 = wc.date_view(cal, 5), wc.date_view(cal, 4)
    prev = _st(cal=cal, day=4, date=d4)
    good = _st(cal=cal, day=5, date=d5)
    assert not _ids(inv.check_calendar(good, prev, 2)) & {
        "calendar.date_regressed",
        "calendar.date_stale",
    }
    back = _st(cal=cal, day=6, date=d4)  # relogio avancou, data nao
    assert "calendar.date_stale" in _ids(inv.check_calendar(back, prev, 2))
    older = {**wc.date_view(cal, 3), "day": 6}
    regress = _st(cal=cal, day=6, date=older)
    assert "calendar.date_regressed" in _ids(inv.check_calendar(regress, prev, 2))


def test_report_has_months_seen():
    st = _st(cal=cal_for("primavera", 1), day=60)
    out = tel._world_summary(st)
    assert out["months_seen"] == 3  # dias 1..60 = Morrakh, Vaelith, Malagor
    assert tel._world_summary(_st(cal=v1_cal("inverno", 1)))["months_seen"] == 0
