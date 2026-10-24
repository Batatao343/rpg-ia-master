"""SPEC-303 Etapa 5: festas da lore via location_state_changed (R15-R19)."""

from __future__ import annotations

import json
import pathlib
import re

import pytest

import gamedata
from services import location_states as ls
from services import world_calendar as wc
from services.world_validators import validate_proposal
from tests.spec303_helpers import cal_state, run, step, zero_cal

# calendario zero (SPEC-307): Vaelith 18 = dia 38 (dia_da_fundacao, 2 dias); Solveth 1 = dia 61
FUND = ("nova_arcadia", "na_anel_dourado", "na_anel_ferro", "na_anel_lama")


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")


def _rows(st: dict) -> dict:
    return st["world_projection"].get("location_states") or {}


def _fresh(day: int = 1, **kw) -> dict:
    return cal_state(zero_cal(), day=day, **kw)


def test_catalog_valid():
    cat = wc.festivals_catalog()
    ids = [f["id"] for f in cat]
    assert len(ids) == len(set(ids)) and len(cat) >= 14
    locs = {loc["id"]: loc for loc in gamedata.WORLD_MAP["locations"]}
    lore = pathlib.Path("lore_nova")
    covered = set()
    for f in cat:
        assert f["review"] == "dono" and f["month"] in {m["id"] for m in wc.months()}
        assert 1 <= f["day_of_month"] <= 20 and f["duration_days"] >= 1
        assert f["label"] and f["lore_refs"]
        for lid in f["location_ids"]:
            assert lid in locs and locs[lid].get("kind") != "interior"
            covered.add(locs[lid]["region_id"])
        for ref in f["lore_refs"]:  # arquivo:linha existe na lore
            name, line = ref.rsplit(":", 1)
            n = sum(1 for _ in (lore / name).open(encoding="utf-8"))
            assert 1 <= int(line) <= n, ref
    assert covered == {loc["region_id"] for loc in locs.values()}  # 12 regioes


def test_festa_starts_and_ends_via_location_state_changed():
    st = _fresh()
    res = run(st, 2, 39)
    started = [
        e
        for r in res
        for e in r.pending_events
        if e["payload"].get("festival_id") == "dia_da_fundacao"
    ]
    assert {e["target_id"] for e in started} == set(FUND)
    for e in started:
        assert e["source"] == "engine" and e["payload"]["cause"] == "calendario"
        assert e["payload"]["festival_id"] == "dia_da_fundacao"
        assert e["payload"]["previous"] == "" and e["payload"]["severity"] == 1
    assert {lid for lid in FUND if _rows(st).get(lid, {}).get("state") == "festa"} == set(FUND)
    assert _rows(st)["nova_arcadia"]["festival_id"] == "dia_da_fundacao"
    ended = [
        e
        for r in run(st, 40, 40)
        for e in r.pending_events
        if e["payload"].get("festival_id") == "dia_da_fundacao"
    ]
    assert {e["target_id"] for e in ended} == set(FUND)
    assert all(e["payload"]["state"] == "" for e in ended)
    assert not [lid for lid in FUND if _rows(st).get(lid, {}).get("state") == "festa"]


def test_festa_id_deterministic_per_year():
    a = wc.festa_id("g", "dia_da_fundacao", 1)
    assert a == wc.festa_id("g", "dia_da_fundacao", 1) and len(a) == 16
    assert a != wc.festa_id("g", "dia_da_fundacao", 2) != wc.festa_id("h", "dia_da_fundacao", 2)
    st = _fresh()
    run(st, 2, 38)
    assert _rows(st)["nova_arcadia"]["crisis_id"] == wc.festa_id(
        st["game_id"], "dia_da_fundacao", 1
    )


def test_interior_inherits_festa():
    st = _fresh(day=1)
    run(st, 2, 61)  # noite_dos_nomes: skallgard, 1o de Solveth = dia 61
    row = ls.location_state(st, "sk_salao_do_jarl")
    assert row and row["state"] == "festa" and row["festival_id"] == "noite_dos_nomes"


def test_festa_cancelled_when_location_has_crisis_state():
    st = _fresh()
    st["world_projection"] = {
        "location_states": {"nova_arcadia": {"state": "cerco", "severity": 1, "crisis_id": "c"}}
    }
    res = run(st, 2, 38)
    assert _rows(st)["nova_arcadia"]["state"] == "cerco"  # nao sobrescrito
    assert all(_rows(st)[lid]["state"] == "festa" for lid in FUND[1:])
    cancelled = [i for r in res for i in r.digest if i["kind"] == "festa_cancelada"]
    assert [i["location_id"] for i in cancelled] == ["nova_arcadia"]
    assert cancelled[0]["template_id"] == "festa.cancelada"


def test_festa_cancelled_when_region_has_announced_crisis():
    st = _fresh()
    run(st, 2, 36)
    st["world_sim"]["pressures"]["nova_arcadia"]["fome"] = 90  # aviso nao expira por queda
    st["world_sim"]["crises"].append(
        {
            "crisis_id": "x",
            "kind": "fome",
            "region_id": "nova_arcadia",
            "warned_day": 36,
            "start_day": None,
            "end_day": None,
            "severity": 0,
            "loc_state": "escassez",
        }
    )
    res = run(st, 37, 39)
    assert not [lid for lid in FUND if _rows(st).get(lid, {}).get("state") == "festa"]
    assert not [
        e
        for r in res
        for e in r.pending_events
        if e["payload"].get("festival_id") == "dia_da_fundacao"
    ]
    rec = next(r for r in st["world_sim"]["festivals"] if r["festival_id"] == "dia_da_fundacao")
    assert rec["status"] == "cancelada"
    assert (
        len(
            [
                i
                for r in res
                for i in r.digest
                if i["kind"] == "festa_cancelada" and i["location_id"] in FUND
            ]
        )
        == 4
    )


def test_crisis_during_festa_overwrites_and_end_is_noop():
    st = _fresh()
    run(st, 2, 38)
    st["world_projection"]["location_states"]["nova_arcadia"] = {
        "state": "escassez",
        "severity": 1,
        "crisis_id": "crise-x",
        "cause": "fome",
    }
    res = run(st, 39, 40)
    ends = [e for r in res for e in r.pending_events if e["payload"].get("state") == ""]
    assert "nova_arcadia" not in {e["target_id"] for e in ends}
    assert set(FUND[1:]) <= {e["target_id"] for e in ends}
    assert _rows(st)["nova_arcadia"]["state"] == "escassez"


def test_director_can_target_a_festa_location():
    rows = {lid: {"state": "festa"} for lid in FUND}
    import random

    target = ls.pick_crisis_target(
        "nova_arcadia", "guerra", {"location_states": rows}, random.Random(1)
    )
    assert target in FUND  # crise vence festa: local em festa segue elegivel


def test_validator_accepts_calendario_cause_only_for_festa():
    st = _fresh()

    def ev(**payload):
        base = {
            "state": "festa",
            "previous": "",
            "severity": 1,
            "cause": "calendario",
            "festival_id": "dia_da_fundacao",
            "crisis_id": "abc",
        }
        return {
            "type": "location_state_changed",
            "target_id": "nova_arcadia",
            "source": "engine",
            "payload": {**base, **payload},
        }

    assert validate_proposal(ev(), st).ok
    assert validate_proposal(ev(state="", severity=0), st).ok
    assert not validate_proposal(ev(state="cerco"), st).ok
    assert not validate_proposal(ev(festival_id="nao_existe"), st).ok
    assert not validate_proposal(ev(festival_id=""), st).ok


def test_llm_proposal_of_festa_rejected():
    st = _fresh()
    prop = {
        "type": "location_state_changed",
        "target_id": "nova_arcadia",
        "source": "storyteller",
        "payload": {
            "state": "festa",
            "severity": 1,
            "cause": "calendario",
            "festival_id": "dia_da_fundacao",
        },
    }
    assert not validate_proposal(prop, st).ok
    assert not validate_proposal({k: v for k, v in prop.items() if k != "source"}, st).ok


def test_noite_do_silencio_closes_merchants():
    st = _fresh()
    run(st, 2, 101)  # 1o de Vorrnak = dia 101
    eff = ls.location_effects(st, "nova_arcadia")
    assert eff["merchant_closed"] is True and eff["restock_mult"] == 0.0
    assert eff["price_mult"] == 1.0 and eff["danger_delta"] == 0
    assert ls.public_label(ls.location_state(st, "nova_arcadia")) == "em silêncio"


def test_festa_label_in_public_label():
    st = _fresh()
    run(st, 2, 38)
    row = ls.location_state(st, "nova_arcadia")
    assert ls.public_label(row) == "em festa"
    eff = ls.location_effects(st, "nova_arcadia")
    assert eff["price_mult"] == 1.1 and eff["restock_mult"] == 1.2 and not eff["merchant_closed"]
    assert eff["danger_delta"] == 0


def test_herald_two_days_before():
    st = _fresh()
    seen: dict[int, list] = {}
    for d in range(2, 39):
        seen[d] = [
            i
            for i in step(st, d).digest
            if i["kind"] == "festa_proxima" and i["params"]["festa"] == "Dia da Fundação"
        ]
    days = [d for d, items in seen.items() if items]
    assert days == [36]  # inicio 38 - FESTIVAL_HERALD_DAYS
    assert {i["region_id"] for i in seen[36]} == {"nova_arcadia"}
    assert seen[36][0]["template_id"] == "festa.proxima"


def test_one_occurrence_or_cancel_per_year():
    st = _fresh()
    seen: dict[tuple[str, int], str] = {}
    for d in range(2, 3 * 140 + 1):
        step(st, d)
        for rec in st["world_sim"]["festivals"]:
            if rec["status"] in ("ativa", "encerrada", "cancelada"):
                seen[(rec["festival_id"], rec["year"])] = rec["status"]
    for fest in wc.festivals_catalog():
        for year in (1, 2):
            assert (fest["id"], year) in seen, (fest["id"], year)
    # JSON do catalogo continua parseavel e sem duplicatas de chave
    json.loads(pathlib.Path("data/world/festivals.json").read_text(encoding="utf-8"))
    assert re.fullmatch(r"[0-9a-f]{16}", wc.festa_id("g", "x", 1))
