"""SPEC-307 Etapa 4: exibicao, narrador e API (R13, R15-R18, R22)."""

from __future__ import annotations

import copy
import json

import pytest

import world_utils as wu
from agents import storyteller
from services import world_calendar as wc
from tests.spec303_helpers import cal_for, cal_state, step, v1_cal, zero_cal


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def _world(day: int = 5, period: str = "Manhã", **extra) -> dict:
    return {"world_clock": {"day": day, "period": period}, **extra}


@pytest.mark.parametrize("env", ["off", "shadow"])
def test_clock_label_legacy_byte_identical_off_shadow_none(monkeypatch, env):
    monkeypatch.setenv("RPG_CALENDAR", env)
    w = _world(date=wc.date_view(zero_cal(), 5))
    assert wu.clock_label(w, zero_cal()) == "Dia 5 · Manhã"
    assert wu.clock_label(w) == "Dia 5 · Manhã"


def test_clock_label_legacy_without_calendar():
    assert wu.clock_label(_world()) == "Dia 5 · Manhã"
    assert wu.clock_label(_world(), None) == "Dia 5 · Manhã"
    assert wu.clock_label({}) == "Dia 1 · Amanhecer"


def test_clock_label_with_calendar_on():
    cal = zero_cal()
    out = wu.clock_label(_world(), cal)
    assert out == "5º dia de Morrakh, Sino Mudo — Ano 112 da Era 7 · Manhã"
    # calendario v1 (ainda nao migrado) tambem rotula, convertido em memoria
    assert "Ano 112 da Era 7" in wu.clock_label(_world(), v1_cal("verao", 3))


def test_clock_label_stale_view_falls_back():
    cal = zero_cal()
    fresh = _world(date=wc.date_view(cal, 5))
    assert wu.clock_label(fresh) == "5º dia de Morrakh, Sino Mudo — Ano 112 da Era 7 · Manhã"
    stale = _world(date=wc.date_view(cal, 4))
    assert wu.clock_label(stale) == "Dia 5 · Manhã"


def test_world_date_written_by_hook_and_init_only_on(monkeypatch):
    st = cal_state(cal_for("primavera", 1))
    step(st, 2)
    assert st["world"]["date"]["day"] == 2
    assert st["world"]["date"]["label"] == wc.date_label(st["world_sim"]["calendar"], 2)
    for env in ("shadow", "off"):
        monkeypatch.setenv("RPG_CALENDAR", env)
        s2 = cal_state(cal_for("primavera", 1))
        s2["world_sim"].pop("calendar")
        step(s2, 2)
        assert "date" not in s2["world"] and "season" not in s2["world"]
    monkeypatch.setenv("RPG_CALENDAR", "on")
    new = {"game_id": "g-new", "factions": [], "world": wu.starting_world("Nova Arcádia", 1)}
    wc.init_new_game(new)
    assert new["world"]["date"]["day"] == 1 and new["world"]["date"]["label"]
    monkeypatch.setenv("RPG_CALENDAR", "off")
    other = {"game_id": "g-off", "factions": [], "world": wu.starting_world("Nova Arcádia", 1)}
    wc.init_new_game(other)
    assert "date" not in other["world"]


def _sim(cal: dict) -> dict:
    return {"calendar": cal, "festivals": [{"festa_id": "x", "closed_in": ["inverno"]}]}


def test_api_world_block_date_and_news_date_label():
    import api

    cal = zero_cal()
    w = {
        "current_location_id": "nova_arcadia",
        "world_clock": {"day": 3, "period": "Manhã"},
        "news": [{"day": 2, "period": "Noite", "location_name": "X", "text": "t", "turn": 1}],
    }
    block = api._world_block(w, {}, [], {}, _sim(cal))
    assert block["date"]["label"] == "3º dia de Morrakh, Sino de Cobre — Ano 112 da Era 7"
    assert block["date"]["month"] == "Morrakh" and block["date"]["weekday"] == "Sino de Cobre"
    assert block["date"]["climate"] == "transicao" and block["date"]["day_of_month"] == 3
    assert block["news"][0]["date_label"].startswith("2º dia de Morrakh")
    assert api._world_block(w, {}, [], {})["date"] is None  # sem calendario
    assert api._world_block(w, {}, [], {})["news"][0]["date_label"] == ""


def test_api_date_none_when_not_on(monkeypatch):
    import api

    monkeypatch.setenv("RPG_CALENDAR", "shadow")
    w = {"current_location_id": "nova_arcadia", "world_clock": {"day": 3, "period": "Manhã"}}
    assert api._world_block(w, {}, [], {}, _sim(zero_cal()))["date"] is None


def test_api_season_chip_only_in_regional_label_places():
    import api

    cal = cal_for("inverno", 3)
    sk = {
        "current_location_id": "skallgard",
        "world_clock": {"day": 3, "period": "Manhã"},
        "season": {"id": "inverno"},
    }
    br = {**sk, "current_location_id": "brekmar"}
    assert api._world_block(sk, {}, [], {}, _sim(cal))["date"]["season_chip"] == "Noite Longa"
    assert api._world_block(br, {}, [], {}, _sim(cal))["date"]["season_chip"] == ""


def test_api_never_leaks_epoch_year_offset_catalog():
    import api

    cal = {**zero_cal(), "year_offset": 3}
    w = {
        "current_location_id": "skallgard",
        "world_clock": {"day": 3, "period": "Manhã"},
        "season": {"id": "inverno"},
    }
    blob = json.dumps(api._world_block(w, {}, [], {}, _sim(cal)), default=str)
    for banned in (
        "epoch_offset",
        "year_offset",
        "festivals",
        "closed_in",
        "day_of_year",
        "calendar",
    ):
        assert banned not in blob


def test_api_v1_calendar_read_converted_without_write():
    import api

    sim = _sim(v1_cal("inverno", 1))
    before = copy.deepcopy(sim)
    w = {"current_location_id": "nova_arcadia", "world_clock": {"day": 4, "period": "Manhã"}}
    block = api._world_block(w, {}, [], {}, sim)
    assert block["date"] and "Ano 112 da Era 7" in block["date"]["label"]
    assert sim == before  # nada gravado


class _Recorder:
    """Envolve o LLM do storyteller registrando o SystemMessage do prompt."""

    prompts: list[str] = []

    def __init__(self, inner):
        self.inner = inner

    def with_structured_output(self, model):
        eng = self.inner.with_structured_output(model)
        outer = self

        class _I:
            def invoke(self, msgs):
                outer.prompts.append(str(msgs[0].content))
                return eng.invoke(msgs)

        return _I()


def _story_state(cal: dict | None) -> dict:
    from tests.test_fase2 import _state_for_graph

    st = _state_for_graph("olho em volta")
    st["world"]["world_clock"] = {"day": 5, "period": "Manhã"}
    if cal:
        st["world_sim"] = {"calendar": cal}
    return st


def test_storyteller_prompt_has_date_and_no_invent_rule(monkeypatch):
    real = storyteller.get_llm
    _Recorder.prompts = []
    monkeypatch.setattr(storyteller, "get_llm", lambda **kw: _Recorder(real(**kw)))
    storyteller.storyteller_node(_story_state(zero_cal()))
    prompt = _Recorder.prompts[-1]
    assert "Momento: 5º dia de Morrakh, Sino Mudo — Ano 112 da Era 7 · Manhã." in prompt
    assert "não invente datas nem meses de outro mundo" in prompt
    monkeypatch.setenv("RPG_CALENDAR", "off")
    storyteller.storyteller_node(_story_state(zero_cal()))
    off = _Recorder.prompts[-1]
    assert "Momento: Dia 5 · Manhã." in off and "não invente datas" not in off


def test_no_extra_llm_call_on_day_turn(monkeypatch):
    from agents import world_simulator as wsim
    from main import app
    from services import world_engine as we
    from tests.test_fase2 import _state_for_graph

    def run(on: bool) -> int:
        monkeypatch.setenv("RPG_CALENDAR", "on" if on else "off")
        calls = {"n": 0}

        class _C:
            def with_structured_output(self, model):
                class _I:
                    def invoke(self, _m):
                        calls["n"] += 1
                        return model(text="Ecos do mundo.")

                return _I()

        monkeypatch.setattr(wsim, "get_llm", lambda **kw: _C())
        st = _state_for_graph("vou descansar e acampar aqui")
        st["world"]["world_clock"] = {"day": 3, "period": "Noite"}
        sim = we.ensure_world_sim({**st, "world": st["world"]}, 3, st.get("factions"))
        sim["calm_until_day"] = 10_000
        sim["calendar"] = cal_for("primavera", 3)
        st["world_sim"] = copy.deepcopy(sim)
        app.invoke(st)
        return calls["n"]

    assert run(True) == run(False)


def test_season_digest_uses_month_label_not_generic_season():
    from services import world_perception as wperc

    st = cal_state(cal_for("verao", 5))
    res = step(st, 5)
    item = next(i for i in res.digest if i["kind"] == "estacao")
    assert item["params"] == {"mes": "Vaelith"}
    text = wperc.render({"world": {"current_location_id": "nova_arcadia"}}, item)
    assert text.startswith("Começa o mês de Vaelith. ")
    assert "verão" not in text.lower() and "outono" not in text.lower()
