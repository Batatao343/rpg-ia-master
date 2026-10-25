"""SPEC-302 Etapa 6: percepcao, noticias e narracao."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

import gamedata
from agents import world_simulator as wsim
from services import world_engine as we
from services import world_perception as wperc
from services import world_pressures as wp
from services.world_director import digest_item


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def _state(loc="nova_arcadia", **extra):
    return {
        "game_id": "g",
        "world": {
            "current_location_id": loc,
            "current_location": loc,
            "world_clock": {"day": 5, "period": "Manhã"},
            "turn_count": 5,
        },
        "factions": gamedata.seed_factions(),
        "faction_intel": {},
        "npcs": {},
        **extra,
    }


def _item(template, region="nova_arcadia", loc="nova_arcadia", **kw):
    return digest_item(
        "g",
        5,
        kw.pop("kind", "sinal"),
        region,
        loc,
        template,
        kw.pop("params", {"local": loc}),
        **kw,
    )


def test_local_witness_only_current_location():
    item = _item("praga.crise.inicio", region="pantano_melancolia", loc="pantano_melancolia")
    assert wperc.perceivable(_state("pantano_melancolia"), [item]) == [item]
    assert wperc.perceivable(_state("pradaria_ruinas"), [item]) == []
    # regiao igual mas local diferente: template `local` nao e testemunhado
    other = _item("praga.crise.inicio", region="pantano_melancolia", loc="pm_profundezas")
    assert wperc.perceivable(_state("pantano_melancolia"), [other]) == []


def test_regional_visibility_rule():
    item = _item("fome.sinal.preco", region="pradaria_ruinas", loc="pradaria_ruinas")
    assert wperc.perceivable(_state("pr_vaelorn"), [item]) == [item]  # mesma regiao
    assert wperc.perceivable(_state("nova_arcadia"), [item]) == []


def test_far_crisis_invisible_without_propagation():
    item = _item("guerra.crise.fim", region="skallgard", loc="skallgard", subject_id="ev1")
    st = _state("nova_arcadia", location_heard={"nova_arcadia": ["ev1"]})
    assert wperc.perceivable(st, [item]) == []  # SPEC-215 off: so (a) e (b)


def test_far_crisis_heard_via_location_heard(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    item = _item("guerra.crise.fim", region="skallgard", loc="skallgard", subject_id="ev1")
    st = _state("nova_arcadia", location_heard={"nova_arcadia": ["ev1"]})
    assert wperc.perceivable(st, [item]) == [item]
    assert wperc.perceivable(_state("nova_arcadia", location_heard={}), [item]) == []


def test_unknown_faction_never_named_in_any_template():
    names = {f["name"] for f in gamedata.seed_factions()}
    st = _state()
    templates = wperc._templates()["templates"]
    for tid in templates:
        for f in gamedata.seed_factions():
            item = _item(tid, params={"faccao": f["id"], "local": "nova_arcadia"})
            text = wperc.render(st, item)
            assert text, tid
            assert not any(n in text for n in names), (tid, f["id"], text)


def test_known_faction_is_named():
    st = _state(faction_intel={"legiao_ferro": {"known": True}})
    text = wperc.render(
        st, _item("guerra.aviso.cerco", params={"faccao": "legiao_ferro", "local": "nova_arcadia"})
    )
    assert "Legião de Ferro" in text


def test_news_ring_persists_template_text_not_llm():
    st = _state()
    items = [_item("fome.sinal.preco") for _ in range(1)]
    world = wperc.record_news(st["world"], st, items)
    assert world["news"][-1]["text"] == wperc.render(st, items[0])
    assert world["news"][-1]["source"] == "world_engine"
    many = [
        _item("praga.sinal.febre", loc="nova_arcadia"),
        _item("abismo.sinal.sombras"),
        _item("guerra.sinal.patrulha"),
    ]
    w = world
    for i in range(20):
        w = wperc.record_news(
            w, st, [_item("fome.sinal.celeiro", params={"local": f"x{i}"}), *many]
        )
    assert len(w["news"]) <= 12


class _CountingLLM:
    calls = 0

    def with_structured_output(self, model):
        outer = self

        class _Inv:
            def invoke(self, _msgs):
                type(outer).calls += 1
                return model(text="Os preços do pão subiram; ouvi falar de Marechal Inventado.")

        return _Inv()


def test_narrator_called_at_most_once_and_only_when_day_turned(monkeypatch):
    from agents import storyteller

    monkeypatch.setenv("RPG_DAY_DIGEST", "llm")  # SPEC-318: modo legado com a chamada FAST
    _CountingLLM.calls = 0
    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _CountingLLM())
    st = _state()
    assert storyteller._narrate_world(st, st["world"], st["factions"], {}, []) == ""
    assert _CountingLLM.calls == 0
    out = storyteller._narrate_world(
        st,
        st["world"],
        st["factions"],
        {},
        [_item("fome.sinal.preco"), _item("guerra.sinal.patrulha")],
    )
    assert _CountingLLM.calls == 1 and out.startswith("[ECOS DO MUNDO]")


def test_narrator_fallback_on_aimessage(monkeypatch):
    class _Fallback:
        def with_structured_output(self, _m):
            class _I:
                def invoke(self, _msgs):
                    return AIMessage(content="erro")

            return _I()

    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _Fallback())
    st = _state()
    items = [_item("fome.sinal.preco")]
    assert wsim.narrate_day(st, items) == wperc.render(st, items[0])


def test_narrator_rejects_unlisted_names(monkeypatch):
    class _Leaky(_CountingLLM):
        def with_structured_output(self, model):
            class _I:
                def invoke(self, _msgs):
                    return model(text="A Legião de Ferro marcha sobre a cidade.")

            return _I()

    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _Leaky())
    st = _state()
    items = [_item("fome.sinal.preco")]
    assert wsim.narrate_day(st, items) == wperc.render(
        st, items[0]
    )  # nome nao liberado -> templates
    st2 = _state(faction_intel={"legiao_ferro": {"known": True}})
    assert "Legião de Ferro" in wsim.narrate_day(st2, items)


def test_no_llm_field_mutates_state():
    assert "danger_shift" not in wsim.WorldDayNarration.model_fields
    assert list(wsim.WorldDayNarration.model_fields) == ["text"]


def _stub_tick(days_ticked, item):
    sim = we._new_sim("g", 1, [], "on")
    sim["pending_digest"] = [item] if item else []

    def fake(state, before, after, factions, intel):
        return we.WorldTickResult(
            after, list(factions), sim, [], [item] if item else [], days_ticked, "world_sim"
        )

    return fake


def _rest_state(period="Noite"):
    from tests.test_fase2 import _state_for_graph

    st = _state_for_graph("vou descansar e acampar aqui")
    st["world"]["world_clock"] = {"day": 3, "period": period}
    return st


def test_integration_rest_turning_day_narrates_once_and_records_news(monkeypatch):
    from main import app

    monkeypatch.setenv("RPG_DAY_DIGEST", "llm")  # SPEC-318: modo legado com a chamada FAST
    item = _item("fome.sinal.preco", region="nova_arcadia", loc="nova_arcadia")
    _CountingLLM.calls = 0
    monkeypatch.setattr(we, "advance_days", _stub_tick(1, item))
    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _CountingLLM())
    out = app.invoke(_rest_state("Noite"))
    assert _CountingLLM.calls == 1
    assert any(n["source"] == "world_engine" for n in out["world"].get("news", []))
    assert out["world_sim"]


def test_no_call_when_day_did_not_turn(monkeypatch):
    from main import app

    item = _item("fome.sinal.preco")
    _CountingLLM.calls = 0
    monkeypatch.setattr(we, "advance_days", _stub_tick(0, None))
    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _CountingLLM())
    app.invoke(_rest_state("Manhã"))
    assert _CountingLLM.calls == 0
    assert item


def test_api_world_block_has_label_and_news_only():
    import api

    w = {
        "current_location_id": "skallgard",
        "world_clock": {"day": 3, "period": "Manhã"},
        "news": [
            {
                "day": 2,
                "period": "Manhã",
                "location_name": "X",
                "text": "t",
                "source": "world_engine",
                "turn": 1,
            }
        ],
    }
    proj = {"location_states": {"skallgard": {"state": "cerco", "severity": 3}}}
    block = api._world_block(w, proj, [], {})
    assert block["location_state"] == "sitiada"
    assert block["news"][0]["text"] == "t"
    blob = repr(block)
    for banned in ("pressures", "world_sim", "faction_relations", "severity"):
        assert banned not in blob


def test_pressures_cfg_has_all_regions():
    assert set(wp.get_config()["regions"]) == set(wp.region_ids())
