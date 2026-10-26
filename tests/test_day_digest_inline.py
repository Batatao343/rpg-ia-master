"""SPEC-318 R3: digest do dia sem chamada `narrate_day` (bloco factual no prompt do narrador)."""

from __future__ import annotations

import pytest

from agents import storyteller
from agents import world_simulator as wsim
from tests.test_spec302_perception import _item, _state


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


class _CountingLLM:
    calls = 0

    def with_structured_output(self, model):
        outer = self

        class _Inv:
            def invoke(self, _msgs):
                type(outer).calls += 1
                return model(text="Os preços do pão subiram.")

        return _Inv()


def _items():
    return [_item("fome.sinal.preco"), _item("guerra.sinal.patrulha")]


def test_inline_mode_makes_no_narrate_day_call(monkeypatch):
    _CountingLLM.calls = 0
    monkeypatch.setattr(wsim, "get_llm", lambda **_k: _CountingLLM())
    st = _state()
    note = storyteller._narrate_world(st, st["world"], st["factions"], {}, _items())
    assert _CountingLLM.calls == 0  # o dia que vira não custa FAST extra
    assert note.startswith("[ECOS DO MUNDO]")
    assert "teça estes fatos" in note and "FATO:" in note


def test_perceived_items_in_prompt_block():
    st = _state()
    items = _items()
    note = storyteller._narrate_world(st, st["world"], st["factions"], {}, items)
    from services import world_perception as wperc

    for it in items:
        assert wperc.render(st, it) in note  # só o texto de template já percebido


def test_no_items_means_no_note():
    st = _state()
    assert storyteller._narrate_world(st, st["world"], st["factions"], {}, []) == ""


def test_rumor_stays_labeled_as_rumor(monkeypatch):
    from services import rumors

    items = _items()
    monkeypatch.setattr(rumors, "is_rumor_item", lambda it: it is items[1])
    lines = wsim.digest_prompt_lines(_state(), items)
    assert any(line.startswith("BOATO:") for line in lines)
    assert any(line.startswith("FATO:") for line in lines)


def test_llm_mode_keeps_narrate_day(monkeypatch):
    monkeypatch.setenv("RPG_DAY_DIGEST", "llm")
    _CountingLLM.calls = 0
    monkeypatch.setattr(wsim, "get_llm", lambda **_k: _CountingLLM())
    st = _state()
    storyteller._narrate_world(st, st["world"], st["factions"], {}, _items())
    assert _CountingLLM.calls == 1


def test_day_turn_makes_single_fast_call(monkeypatch):
    """Um descanso que vira o dia: só o narrador chama o LLM (nenhum `narrate_day`)."""
    from main import app
    from services import world_engine as we
    from tests.test_spec302_perception import _rest_state, _stub_tick

    item = _item("fome.sinal.preco", region="nova_arcadia", loc="nova_arcadia")
    _CountingLLM.calls = 0
    monkeypatch.setattr(we, "advance_days", _stub_tick(1, item))
    monkeypatch.setattr(wsim, "get_llm", lambda **_k: _CountingLLM())
    out = app.invoke(_rest_state("Noite"))
    assert _CountingLLM.calls == 0
    assert any(n["source"] == "world_engine" for n in out["world"].get("news", []))
    assert out["world_sim"]


def test_digest_lines_are_capped(monkeypatch):
    from services.perceived_world import DAY_FACTS_MAX

    many = [_item("fome.sinal.preco", subject_id=f"s{i}") for i in range(DAY_FACTS_MAX + 5)]
    assert len(wsim.digest_prompt_lines(_state(), many)) <= DAY_FACTS_MAX
