"""SPEC-312 Etapa 5: a LLM so costura (BOATO), sem chamada nova e sem vazar nomes."""

from __future__ import annotations

import pytest

from agents import world_simulator as wsim
from services import rumors
from services import world_engine as we
from services import world_perception as wperc
from tests.spec312_helpers import base_state, make_rumor


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_RUMORS", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


class _Capture:
    calls = 0
    prompts: list = []

    def __init__(self, text="Dizem que a cama do Lorde Protetor fica intocada."):
        self.text = text

    def with_structured_output(self, model):
        outer = self

        class _Inv:
            def invoke(self, msgs):
                type(outer).calls += 1
                type(outer).prompts.append(" || ".join(str(m.content) for m in msgs))
                return model(text=outer.text)

        return _Inv()


def _reset():
    _Capture.calls = 0
    _Capture.prompts = []


def _signal(region="nova_arcadia"):
    from services.world_director import digest_item

    return digest_item("g312", 5, "sinal", region, region, "fome.sinal.preco", {"local": region})


def test_rumor_lines_are_boato_not_fato(monkeypatch):
    _reset()
    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _Capture())
    sim: dict = {}
    r = make_rumor(sim)
    st = base_state(5, "nova_arcadia")
    st["world_sim"] = sim
    wsim.narrate_day(st, [_signal(), r])
    prompt = _Capture.prompts[0]
    assert "FATO: " in prompt and "BOATO: " in prompt
    boato_line = next(ln for ln in prompt.split("\n") if ln.startswith("BOATO: "))
    assert boato_line == "BOATO: " + wperc.render(st, r)
    assert "FATO: " + wperc.render(st, r) not in prompt
    assert "Linhas BOATO" in prompt  # instrucao de costura
    # sem rumor, o prompt de sistema nao ganha a regra
    _reset()
    wsim.narrate_day(st, [_signal()])
    assert "Linhas BOATO" not in _Capture.prompts[0]


def test_rumor_only_day_makes_zero_llm_calls(monkeypatch):
    _reset()
    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _Capture())
    sim: dict = {}
    r = make_rumor(sim)
    st = base_state(5, "nova_arcadia")
    out = wsim.narrate_day(st, [r])
    assert _Capture.calls == 0 and out == wperc.render(st, r) != ""


def test_invoke_count_equals_302_baseline(monkeypatch):
    _reset()
    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _Capture())
    sim: dict = {}
    r = make_rumor(sim)
    st = base_state(5, "nova_arcadia")
    items_sets = [[_signal()], [_signal(), r], [r, _signal(), _signal("brekmar")]]
    for items in items_sets:
        _reset()
        wsim.narrate_day(st, items)
        assert _Capture.calls == 1
    _reset()
    wsim.narrate_day(st, [r])
    assert _Capture.calls == 0


def test_public_names_allowed_and_others_labeled(monkeypatch):
    # a prosa da LLM pode citar um public_name; um nome de catalogo fora da lista volta ao template
    sim: dict = {}
    r = make_rumor(sim, "rumor_as_leis_de_valerius_foram_escritas_em_uma_noite", day=5)
    st = base_state(5, "nova_arcadia")
    assert "Valerius" in wsim._allowed_names(st, [r])
    assert "Valerius" not in wsim._allowed_names(st, [])
    sig = _signal()
    monkeypatch.setattr(
        wsim, "get_llm", lambda **kw: _Capture("Dizem que Valerius escreveu as leis.")
    )
    assert "Valerius" in wsim.narrate_day(st, [sig, r])
    monkeypatch.setattr(
        wsim, "get_llm", lambda **kw: _Capture("Dizem que Durrak construiu navios.")
    )
    assert wsim.narrate_day(st, [sig, r]) == wsim._template_text(st, [sig, r])


def test_all_seed_templates_never_emit_unlisted_catalog_names():
    catalog = wsim._catalog_names()
    st = base_state(5, "nova_arcadia")
    for sid, seed in rumors.load_seeds().items():
        sim: dict = {}
        fam = seed["family"]
        item = make_rumor(
            sim,
            sid,
            region=seed["regions"][0],
            loc=seed.get("location_id") or seed["regions"][0],
            family=fam,
        )
        for opt_index in range(len(rumors.config()["templates"][f"rumor.{fam}"])):
            inst = rumors.from_item(item)
            tpl = rumors.config()["templates"][f"rumor.{fam}"][opt_index]
            text = (
                tpl.replace("{gist}", str(seed.get("gist") or ""))
                .replace("{fonte_label}", str(seed.get("fonte_label") or ""))
                .replace("{criatura}", str(seed.get("creature_label") or ""))
                .replace("{local}", "Local")
            )
            for name in catalog:
                if name.lower() in text.lower():
                    assert name in rumors.public_names(inst), (sid, name)
        rendered = wperc.render(st, item)
        assert rendered
        for name in catalog:
            if name.lower() in rendered.lower():
                assert name in rumors.public_names(rumors.from_item(item)), (sid, name)


def test_no_canonical_memory_contains_rumor_gist():
    from services.perceived_world import day_memory_facts

    sim: dict = {}
    r = make_rumor(sim)
    st = base_state(5, "nova_arcadia")
    assert day_memory_facts(st, [r]) == []
    facts = day_memory_facts(st, [_signal(), r])
    assert len(facts) == 1 and "cama" not in facts[0]


def test_integration_rumor_only_action_costs_no_llm_and_marks_news(monkeypatch):
    from main import app
    from tests.test_spec302_perception import _rest_state

    _reset()
    sim = we._new_sim("g312", 1, [], "on")
    item = make_rumor(sim, "rumor_valerius_nao_come_nem_dorme", day=3, turn=3)
    sim["pending_digest"] = [item]

    def fake(state, before, after, factions, intel):
        return we.WorldTickResult(after, list(factions), sim, [], [item], 1, "world_sim")

    monkeypatch.setattr(we, "advance_days", fake)
    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _Capture())
    st = _rest_state("Noite")
    st["world"]["current_location_id"] = "nova_arcadia"
    out = app.invoke(st)
    news = [n for n in out["world"].get("news", []) if n.get("kind") == "rumor"]
    assert news and news[0]["rumor_id"] == item["subject_id"]
    inst = rumors.instance({"world_sim": out["world_sim"]}, item["subject_id"])
    assert inst["perceived_day"] > 0
    # nenhuma narracao do dia foi pedida para o boato sozinho
    assert not any("BOATO:" in p for p in _Capture.prompts)
    # nenhum fato canonico com o gist
    blob = repr(out.get("memory_canonical_facts") or []) + repr(out.get("event_log") or [])
    assert "cama" not in blob
    assert "world_projection" not in repr(item)
