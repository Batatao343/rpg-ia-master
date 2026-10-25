"""SPEC-309 Etapa 4 (R13-R17): bloco <MUNDO_PERCEBIDO>."""

from __future__ import annotations

import copy
import re

import pytest

from services import perceived_world as pw
from services import world_director as wd
from tests.spec309_helpers import world_state_two_regions


def _state(loc="skallgard", states=None, ledger=None, events=None, festivals=None, season=None):
    world = {
        "current_location_id": loc,
        "world_clock": {"day": 5, "period": "Manhã"},
        "turn_count": 11,
    }
    if season:
        world["season"] = {"id": season}
    return {
        "game_id": "g",
        "event_log": list(events or []),
        "world_projection": {"location_states": states or {}},
        "world_sim": {"perceived_ids": list(ledger or []), "festivals": festivals or []},
        "world": world,
    }


def _st(state="cerco", **kw):
    return {"state": state, "severity": 2, "since_day": 4, "crisis_id": "c", **kw}


def _sc(loc, state, day=5, crisis="c1", previous="", cause="guerra", **extra):
    ev = wd._ev(
        "g",
        day,
        "location_state_changed",
        loc,
        {
            "state": state,
            "previous": previous,
            "severity": 2,
            "crisis_id": crisis,
            "cause": cause,
            "day": day,
            **extra,
        },
        f"{state}{day}{loc}",
    )
    ev["turn"] = day
    return ev


def _warn(region="skallgard", crisis="c1", day=4):
    ev = wd._ev(
        "g",
        day,
        "world_crisis_warning",
        "skallgard",
        {"kind": "guerra", "region_id": region, "crisis_id": crisis, "earliest_day": day + 3},
        f"w{day}",
    )
    ev["turn"] = day
    return ev


def _fest(start=6, fid="noite_dos_nomes"):
    return {
        "festa_id": "f1",
        "festival_id": fid,
        "start_day": start,
        "end_day": start + 1,
        "status": "anunciada",
    }


def test_local_state_line_uses_public_label():
    """R14.1"""
    st = _state("brekmar", {"brekmar": _st()})
    assert pw.perceived_world_lines(st, audience="story") == ["Brekmar está sitiada."]


def test_interior_inherits_parent_state():
    st = _state("sk_salao_do_jarl", {"skallgard": _st()})
    assert pw.perceived_world_lines(st, audience="story") == ["Skallgard está sitiada."]


def test_festival_today_and_upcoming():
    """R14.1 (festa hoje) e R14.2 (anunciada)."""
    today = _state(
        "skallgard",
        {"skallgard": {"state": "festa", "severity": 1, "festival_id": "noite_dos_nomes"}},
    )
    assert pw.perceived_world_lines(today, audience="story") == [
        "Hoje: Noite dos Nomes — Skallgard está em luto."
    ]
    soon = _state(festivals=[_fest(6)])
    assert pw.perceived_world_lines(soon, audience="story") == [
        "Nos próximos dias: Noite dos Nomes."
    ]
    far = copy.deepcopy(soon)
    far["world_sim"]["festivals"][0]["start_day"] = 20
    assert pw.perceived_world_lines(far, audience="story") == []


def test_remote_crisis_only_if_perceived():
    ev = _sc("sk_fortaleza_vorr", "cerco")
    assert pw.perceived_world_lines(_state(events=[ev]), audience="story") == []
    seen = _state(events=[ev], ledger=[ev["event_id"]])
    assert pw.perceived_world_lines(seen, audience="story") == [
        "Pelo que o herói soube, Fortaleza de Vorr está sitiada."
    ]


def test_last_perceived_event_wins():
    w = _warn()
    o = _sc("sk_fortaleza_vorr", "cerco", day=5)
    e = _sc("sk_fortaleza_vorr", "", day=6, previous="cerco")
    ids = [w["event_id"], o["event_id"], e["event_id"]]
    only_warn = pw.perceived_world_lines(_state(events=[w], ledger=ids), audience="story")
    assert "Há sinais de guerra" in only_warn[0]
    opened = pw.perceived_world_lines(_state(events=[w, o], ledger=ids), audience="story")
    assert "Fortaleza de Vorr está sitiada" in opened[0]
    ended = _state(events=[w, o, e], ledger=ids)
    assert pw.perceived_world_lines(ended, audience="story") == []


def test_unperceived_end_keeps_last_known_line():
    """Sem vazamento por ausencia: o fim nao percebido nao apaga a linha."""
    o = _sc("sk_fortaleza_vorr", "cerco", day=5)
    e = _sc("sk_fortaleza_vorr", "", day=6, previous="cerco")
    st = _state(events=[o, e], ledger=[o["event_id"]])
    assert pw.perceived_world_lines(st, audience="story") == [
        "Pelo que o herói soube, Fortaleza de Vorr está sitiada."
    ]


def test_other_region_never_listed():
    st = world_state_two_regions(perceive_siege=True)
    assert all("Brekmar" not in line for line in pw.perceived_world_lines(st, audience="story"))


def test_story_audience_omits_season():
    st = _state(season="inverno")
    assert pw.perceived_world_lines(st, audience="story") == []
    for aud in ("npc", "combat", "day"):
        lines = pw.perceived_world_lines(st, audience=aud)
        assert len(lines) == 1 and lines[0].startswith("Estação: ")


def test_npc_audience_local_and_season_only():
    st = _state(
        "brekmar",
        {"brekmar": _st()},
        season="inverno",
        events=[_warn(region="brekmar")],
        festivals=[_fest(6, "fim_do_ceu_vermelho")],
    )
    lines = pw.perceived_world_lines(st, audience="npc")
    assert lines[0] == "Brekmar está sitiada." and len(lines) == 2
    assert lines[1].startswith("Estação:")


@pytest.mark.parametrize("mode", ["off", "shadow"])
def test_engine_off_or_shadow_no_state_lines(monkeypatch, mode):
    monkeypatch.setenv("RPG_WORLD_ENGINE", mode)
    st = _state("brekmar", {"brekmar": _st()}, season="inverno")
    lines = pw.perceived_world_lines(st, audience="npc")
    assert all(not line.startswith("Brekmar") for line in lines)


def test_budget_max_lines_and_tokens(monkeypatch):
    st = _state("brekmar", {"brekmar": _st()}, season="inverno")
    assert len(pw.perceived_world_lines(st, audience="combat")) == 2
    monkeypatch.setattr(pw, "MAX_LINES", 1)
    assert pw.perceived_world_lines(st, audience="combat") == ["Brekmar está sitiada."]
    monkeypatch.setattr(pw, "MAX_LINES", 4)
    monkeypatch.setattr(pw, "MAX_TOKENS", 5)
    assert pw.perceived_world_block(st, audience="combat") == ""


def test_empty_returns_empty_string():
    assert pw.perceived_world_block(_state(), audience="story") == ""


def test_block_shape_and_default_budget():
    st = _state("brekmar", {"brekmar": _st()}, season="inverno")
    block = pw.perceived_world_block(st, audience="combat")
    assert block.startswith("<MUNDO_PERCEBIDO>\n" + pw.INSTRUCTION)
    assert block.endswith("</MUNDO_PERCEBIDO>")
    assert len([ln for ln in block.splitlines() if ln.startswith("- ")]) <= pw.MAX_LINES
    from services.context_builder import estimate_tokens

    assert estimate_tokens(block) <= pw.MAX_TOKENS


def test_deterministic_byte_equal():
    a = world_state_two_regions(season="inverno")
    b = {k: a[k] for k in reversed(list(a))}
    assert pw.perceived_world_block(a, audience="day") == pw.perceived_world_block(
        b, audience="day"
    )
    assert pw.perceived_world_block(a, audience="day") == pw.perceived_world_block(
        a, audience="day"
    )


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"world": "x"},
        {"world": {"current_location_id": 7}},
        {
            "world": {"current_location_id": "skallgard"},
            "event_log": "x",
            "world_projection": 3,
        },
    ],
)
def test_never_raises_returns_empty(bad):
    assert pw.perceived_world_block(bad, audience="story") == ""
    assert pw.day_memory_facts(bad, [{"template_id": None}]) == []


def test_no_forbidden_words_or_digits():
    warn = _warn(region="brekmar")
    st = _state(
        "brekmar",
        {"brekmar": _st(severity=3)},
        season="inverno",
        events=[warn],
        ledger=[warn["event_id"]],
    )
    for aud in ("story", "npc", "combat", "day"):
        block = pw.perceived_world_block(st, audience=aud)
        assert not re.search(r"\d|severidade|pressão|tensão|fase|banda|multa", block, re.I)
