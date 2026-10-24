"""SPEC-299 etapas 5-6 — notoriedade, decaimento, fama por local, sinais e não vazamento."""

from __future__ import annotations

import re

import pytest
from langchain_core.messages import HumanMessage

import api
from services import law
from tests.spec299_helpers import base_state, clock_where, commit, with_clock


@pytest.fixture(autouse=True)
def _law_on(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "on")
    monkeypatch.delenv("RPG_NPC_KNOWLEDGE", raising=False)


def _wanted(heat=0, *, capital=False, bounty=0, last=0, known=None, shown=None) -> dict:
    return {
        "jurisdiction_id": "codigo_de_ferro",
        "heat": heat,
        "bounty": bounty,
        "capital": capital,
        "last_crime_clock": last,
        "known_at": known if known is not None else {"nova_arcadia": 0},
        "signals_shown": shown or [],
        "hunters_last_clock": -1,
    }


def _state_with(wanted, *, clock=40, loc="nova_arcadia", **over):
    state = with_clock(base_state(loc), clock)
    state["law_state"] = {"wanted": {"codigo_de_ferro": wanted}}
    state.update(over)
    return state


# --------------------------- níveis e decaimento --------------------------- #
def test_heat_levels_thresholds():
    expect = {0: "limpo", 9: "limpo", 10: "suspeito", 34: "suspeito", 35: "procurado"}
    expect.update({64: "procurado", 65: "cacado", 100: "cacado"})
    for heat, name in expect.items():
        assert law.level(_wanted(heat, capital=True), 0) == name
    assert law.level(None, 0) == "limpo"


def test_lazy_decay_pure():
    w = _wanted(50, last=0)
    before = dict(w)
    day4 = 4 * 5
    assert law.effective_heat(w, day4) == 50 - 3 * 4  # decay_per_day = 3
    assert law.effective_heat(w, day4) == law.effective_heat(w, day4)  # pura
    assert w == before  # não muta
    assert law.effective_heat(w, 10_000) == 0


def test_capital_never_decays():
    w = _wanted(80, capital=True, last=0)
    assert law.effective_heat(w, 5 * 365) == 80


def test_victim_multiplier_legion():
    state = base_state()
    state["npcs"]["Mercador"]["faction_id"] = "legiao_ferro"
    _st, rec, _ = commit(state, "agressao", victim_ref="npc:npc_mercador")
    assert rec["severity"] == 60 and rec["victim_faction_id"] == "legiao_ferro"
    state["npcs"]["Mercador"]["faction_id"] = "mercadores_livres"
    _st, rec, _ = commit(state, "agressao", victim_ref="npc:npc_mercador")
    assert rec["severity"] == 30


# --------------------------------- fama (R15) ------------------------------ #
class _Fame:
    def __init__(self, value):
        self.value = value
        self.writes = []

    def read(self, state, loc):
        return self.value

    def write(self, state, loc, subject, ctype):
        self.writes.append((loc, subject, ctype))
        return {loc: {"renown": 0, "infamy": 6, "deeds": [subject]}}


def test_recognition_uses_fame_magnitude(monkeypatch):
    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: True)
    monkeypatch.setattr(law, "_unit", lambda *a: 0.9)
    state = _state_with(_wanted(40, last=40), clock=40)
    monkeypatch.setattr(law, "_fame_bridge", _Fame(0))
    assert law.recognition_check(state, "nova_arcadia", 40) is False  # 0.3 < 0.9
    monkeypatch.setattr(law, "_fame_bridge", _Fame(100))
    assert law.recognition_check(state, "nova_arcadia", 40) is True  # 0.3 + 1.0 -> teto 0.95
    # abaixo de `procurado` ou sem a notícia, nunca reconhece
    low = _state_with(_wanted(20, last=40), clock=40)
    assert law.recognition_check(low, "nova_arcadia", 40) is False
    late = _state_with(_wanted(40, last=40, known={"nova_arcadia": 99}), clock=40)
    assert law.recognition_check(late, "nova_arcadia", 40) is False


def test_fame_written_once_on_first_report(monkeypatch):
    fake = _Fame(0)
    monkeypatch.setattr(law, "_fame_bridge", fake)
    state = base_state()
    state["npcs"] = {}
    state = with_clock(state, clock_where(state, "nova_arcadia", patrol=True))
    st, rec, _ = commit(state, "furto")
    out = law.turn_updates(st)
    assert len(fake.writes) == 1 and fake.writes[0][1] == rec["crime_id"]
    law.turn_updates({**st, **out})  # reentrega: crime já `reported`
    assert len(fake.writes) == 1
    assert out["location_fame"]["nova_arcadia"]["infamy"] == 6


def test_fame_real_bridge_writes_infamy_idempotently():
    state = base_state()
    state["npcs"] = {}
    state = with_clock(state, clock_where(state, "nova_arcadia", patrol=True))
    st, _rec, _ = commit(state, "furto")
    out = law.turn_updates(st)
    assert out["location_fame"]["nova_arcadia"]["infamy"] == law.FAME_DELTA_INFAMY
    again = law.turn_updates({**st, **out})
    assert "location_fame" not in again


def test_fame_bridge_absent_returns_zero(monkeypatch):
    from services import reputation

    def boom(*a, **k):
        raise AttributeError("sem SPEC-298")

    monkeypatch.setattr(reputation, "fame_at", boom)
    monkeypatch.setattr(reputation, "add_location_fame", boom)
    assert law._fame_bridge.read({}, "nova_arcadia") == 0
    assert law._fame_bridge.write({}, "nova_arcadia", "c1", "furto") is None


# ---------------------------------- sinais --------------------------------- #
def test_signals_only_where_news_arrived():
    wanted = _wanted(50, last=40, known={"nova_arcadia": 60, "na_anel_dourado": 30})
    early = _state_with(wanted, clock=40)
    assert law.signals_for(early) == []  # a notícia ainda não chegou aqui
    arrived = _state_with(wanted, clock=60)
    assert any("cartaz" in s for s in law.signals_for(arrived))
    elsewhere = _state_with(wanted, clock=60, loc="brekmar")
    assert law.signals_for(elsewhere) == []  # outra jurisdição / sem lei


def test_poster_text_has_no_number():
    state = _state_with(_wanted(50, bounty=999, last=40), clock=40)
    lines = law.signals_for(state)
    assert lines and not any(ch.isdigit() for line in lines for ch in line)
    assert "999" not in " ".join(lines)
    assert "modesta" in law._bounty_phrase(10) and "gorda" in law._bounty_phrase(150)


def test_npc_warning_needs_relationship():
    state = _state_with(_wanted(20, last=40), clock=40)  # suspeito
    state["npcs"]["Mercador"]["relationship"] = 7
    friendly = law.signals_for(state, for_npc="Mercador")
    assert any("sussurrar" in s for s in friendly)
    state["npcs"]["Mercador"]["relationship"] = 2
    assert not any("sussurrar" in s for s in law.signals_for(state, for_npc="Mercador"))


def test_signals_capped_per_scene(monkeypatch):
    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: True)
    state = _state_with(_wanted(90, bounty=500, last=40), clock=40)
    assert len(law.signals_for(state, for_npc="Mercador")) <= law.MAX_SIGNALS_PER_SCENE
    text, upd = law.scene_block(state)
    shown = upd["law_state"]["wanted"]["codigo_de_ferro"]["signals_shown"]
    assert 1 <= len(shown) <= law.MAX_SIGNALS_PER_SCENE
    # sinais já mostrados (cartaz) não se repetem
    again = law.signals_for({**state, **upd})
    assert not any("cartaz" in s for s in again)


def test_prompt_block_absent_when_clean(monkeypatch):
    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: False)
    assert law.scene_block(base_state()) == ("", {})
    assert law.scene_block(base_state("brekmar")) == ("", {})
    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: True)
    text, _ = law.scene_block(base_state())
    assert "<LEI_NA_CENA>" in text and "patrulham" in text  # só o fato de cena


def test_scene_block_never_has_heat_or_bounty(monkeypatch):
    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: True)
    state = _state_with(_wanted(95, bounty=777, capital=True, last=40), clock=40)
    state["law_state"]["crimes"] = [{"crime_id": "abc123", "crime_type": "homicidio"}]
    state["law_state"]["confrontation"] = {
        "jurisdiction_id": "codigo_de_ferro",
        "location_id": "nova_arcadia",
        "started_turn": 5,
        "talk_turns": 0,
        "reason": "patrol_witness",
    }
    text, _ = law.scene_block(state, for_npc="Mercador")
    low = text.lower()
    for forbidden in ("heat", "bounty", "777", "homicidio", "abc123", "cacado", "nível", "nivel"):
        assert forbidden not in low
    assert not re.search(r"\d", text)


def test_storyteller_prompt_never_contains_law_numbers(monkeypatch):
    """O prompt REAL do narrador (não só o bloco) não carrega heat/bounty/crimes."""
    from agents import storyteller
    from services.structured_outputs import ProposedWorldEvent  # noqa: F401

    captured: list = []

    class _Runner:
        def invoke(self, msgs):
            captured.extend(msgs)
            return storyteller.StoryUpdate(narrative="O guarda o encara.")

    class _LLM:
        def with_structured_output(self, model):
            return _Runner()

    monkeypatch.setattr(storyteller, "get_llm", lambda *a, **k: _LLM())
    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: True)
    state = _state_with(_wanted(95, bounty=777, capital=True, last=40), clock=40)
    state["law_state"]["crimes"] = [
        {"crime_id": "abc123zz", "crime_type": "homicidio", "status": "reported"}
    ]
    state["messages"] = [HumanMessage(content="olho em volta")]
    storyteller.storyteller_node(state)
    prompt = "\n".join(str(m.content) for m in captured)
    assert "<LEI_NA_CENA>" in prompt
    for forbidden in ("777", "abc123zz", "heat", "bounty", "last_crime_clock", "codigo_de_ferro"):
        assert forbidden not in prompt


# ------------------------------- não vazamento ----------------------------- #
def test_game_response_has_no_law_keys():
    state = _state_with(_wanted(90, bounty=500, capital=True, last=40), clock=40)
    state["law_state"]["confrontation"] = {"jurisdiction_id": "codigo_de_ferro"}
    payload = api.format_response(state).model_dump()
    dumped = repr(payload).lower()
    for key in ("law_state", "heat", "bounty", "wanted", "confrontation"):
        assert key not in payload
    assert "codigo_de_ferro" not in dumped and "'bounty'" not in dumped


def test_codex_and_dossiers_unchanged():
    from services import dossiers as dz

    clean = base_state()
    dirty = _state_with(_wanted(90, bounty=500, capital=True, last=40), clock=40)
    assert dz.build_dossiers(clean) == dz.build_dossiers({**clean, "law_state": dirty["law_state"]})
