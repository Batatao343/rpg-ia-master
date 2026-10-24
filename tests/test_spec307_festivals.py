"""SPEC-307 Etapa 2: festas em mes+dia (R9-R11)."""

from __future__ import annotations

import pytest

from services import world_calendar as wc
from tests.spec303_helpers import cal_state, step, zero_cal

# R10: estacao e dia/14 de cada festa na SPEC-303 (tabela congelada)
V1_TABLE = {
    "dia_da_fundacao": ("verao", 7),
    "noite_do_silencio": ("inverno", 1),
    "procissao_de_vaelorn": ("outono", 5),
    "noite_dos_nomes": ("outono", 1),
    "fim_do_ceu_vermelho": ("primavera", 3),
    "dia_da_estaca": ("outono", 2),
    "rito_da_memoria": ("verao", 8),
    "colheita_do_po_de_sonho": ("outono", 8),
    "dia_da_simbiose": ("primavera", 6),
    "vigilia_dos_afogados": ("inverno", 6),
    "noite_das_cores_erradas": ("verao", 10),
    "colheita_das_carcacas": ("outono", 9),
    "dia_do_levante": ("primavera", 9),
    "cancoes_de_pedra": ("inverno", 4),
}
DEVIATIONS = {"vigilia_dos_afogados"}  # D5: 6o de Thessrak (tematico)


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")


def _pos(f: dict) -> tuple[str, int]:
    """(estacao, dia na estacao) da festa no calendario novo."""
    ms = wc.months()
    idx = next(i for i, m in enumerate(ms) if m["id"] == f["month"])
    season = ms[idx]["season"]
    first = next(i for i, m in enumerate(ms) if m["season"] == season)
    return season, (idx - first) * 20 + int(f["day_of_month"])


def test_catalog_month_day_valid():
    ids = {m["id"] for m in wc.months()}
    for f in wc.festivals_catalog():
        assert f["month"] in ids and 1 <= f["day_of_month"] <= 20 and f["duration_days"] >= 1
        assert "season" not in f and "day_in_season" not in f
        assert f["review"] == "dono"


def test_each_festival_keeps_303_season():
    assert {f["id"] for f in wc.festivals_catalog()} == set(V1_TABLE)
    for f in wc.festivals_catalog():
        assert _pos(f)[0] == V1_TABLE[f["id"]][0], f["id"]


def test_winter_festivals_in_cold_months():
    cold = {m["id"] for m in wc.months() if m["climate"] == "frio"}
    for f in wc.festivals_catalog():
        if V1_TABLE[f["id"]][0] == "inverno":
            assert f["month"] in cold, f["id"]


def test_proportional_rule_matches_table_except_listed_deviations():
    lens = {"primavera": 20, "verao": 40, "outono": 40, "inverno": 40}
    for f in wc.festivals_catalog():
        season, d = V1_TABLE[f["id"]]
        expected = ((d - 1) * lens[season]) // 14 + 1
        got = _pos(f)[1]
        if f["id"] in DEVIATIONS:
            assert got != expected
        else:
            assert got == expected, f["id"]
    thess = next(f for f in wc.festivals_catalog() if f["id"] == "vigilia_dos_afogados")
    assert (thess["month"], thess["day_of_month"]) == ("thessrak", 6)


def test_no_location_two_festivals_same_day():
    taken: dict[tuple[str, int], str] = {}
    ms = {m["id"]: i for i, m in enumerate(wc.months())}
    for f in wc.festivals_catalog():
        start = ms[f["month"]] * 20 + f["day_of_month"]
        for off in range(int(f["duration_days"])):
            for lid in f["location_ids"]:
                key = (lid, start + off)
                assert key not in taken, (key, f["id"], taken.get(key))
                taken[key] = f["id"]


def test_schedule_two_years_once_or_cancel():
    st = cal_state(zero_cal())
    seen: dict[tuple[str, int], str] = {}
    counts: dict[tuple[str, int], int] = {}
    for d in range(2, 2 * 140 + 1):
        step(st, d)
        for rec in st["world_sim"]["festivals"]:
            if rec["status"] in ("ativa", "encerrada", "cancelada"):
                k = (rec["festival_id"], rec["year"])
                seen[k] = rec["status"]
                counts[k] = counts.get(k, 0)
    for fest in wc.festivals_catalog():
        for year in (1, 2):
            assert (fest["id"], year) in seen, (fest["id"], year)
    ids = [r["festa_id"] for r in st["world_sim"]["festivals"]]
    assert len(ids) == len(set(ids))


def test_schedule_start_days_match_month_day():
    cal = zero_cal()
    plan = {p["festival_id"]: p for p in wc.festival_schedule(cal, "g", 1)}
    assert plan["dia_da_fundacao"]["start_day"] == 38 and plan["dia_da_fundacao"]["end_day"] == 40
    assert plan["noite_do_silencio"]["start_day"] == 101
    assert plan["vigilia_dos_afogados"]["start_day"] == 126
    nxt = {p["festival_id"]: p for p in wc.festival_schedule(cal, "g", 2)}
    assert nxt["noite_do_silencio"]["start_day"] == 101 + 140
    shifted = {**cal, "year_offset": 1}  # ano interno 2 comeca no dia 1 (migracao)
    assert wc.festival_schedule(shifted, "g", 2)[0]["start_day"] == 38
