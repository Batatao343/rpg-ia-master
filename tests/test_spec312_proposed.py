"""SPEC-312 Etapa 6: `ProposedRumor` (a LLM propoe, o Python valida; aceito = falso)."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from agents import storyteller as stt
from services import rumors
from services.structured_outputs import ProposedRumor
from tests.spec312_helpers import base_state, make_rumor

TEXT = "Dizem nas docas que alguém anda comprando o silêncio dos estivadores"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_RUMORS", "on")
    monkeypatch.setenv("RPG_RUMORS_PROPOSED", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def _state(**extra):
    st = base_state(5, "brekmar", player={"name": "Aldric"}, world_sim={}, **extra)
    return st


def _prop(**kw):
    data = {"text": TEXT, "entity_ids": ["brekmar"], "location_id": ""}
    data.update(kw)
    return ProposedRumor(**data)


def _accept(st, props, *, quarantined=False):
    return rumors.accept_proposed(st, props, turn=5, day=5, quarantined=quarantined)


def test_invalid_items_dropped_not_whole_response():
    upd = stt.StoryUpdate(
        narrative="x",
        proposed_rumors=[
            {"text": TEXT, "entity_ids": ["brekmar"]},
            "lixo",
            {"foo": 1},
            {"text": ""},
        ],
    )
    assert len(upd.proposed_rumors) == 1 and upd.proposed_rumors[0].text == TEXT
    assert stt.StoryUpdate(narrative="x").proposed_rumors == []


def test_accepted_is_false_not_quest_eligible_and_perceived():
    sim, world, why = _accept(_state(), [_prop()])
    assert why == [] and sim and world
    inst = sim["rumors"][-1]
    assert inst["family"] == "narrador" and inst["truth"] is False
    assert inst["quest_eligible"] is False and inst["perceived_day"] == 5
    assert inst["born_turn"] == 5 and inst["expires_day"] == 15
    assert sim["rumor_last_perceived_day"] == 5 and inst["rumor_id"] in sim["perceived_ids"]
    entry = world["news"][-1]
    assert entry["kind"] == "rumor" and entry["text"] == TEXT[: len(entry["text"])]
    assert entry["rumor_id"] == inst["rumor_id"] and entry["expires_day"] == 15
    # nunca investigavel pela 313
    assert rumors.investigable({"world_sim": sim}, 6) == []
    # nunca vira fato: so mexeu em world_sim/world
    assert set(sim) >= {"rumors"}


@pytest.mark.parametrize(
    "kw,reason",
    [
        ({"entity_ids": []}, "entity"),
        ({"entity_ids": ["entidade_que_nao_existe"]}, "entity"),
        ({"location_id": "local_inexistente"}, "location"),
        ({"text": "curto demais"}, "length"),
        ({"text": TEXT + " cobrando 50 moedas de cada um"}, "digits"),
        ({"text": TEXT + " e ninguém viu Aldric por perto"}, "player_name"),
    ],
)
def test_rejects_invalid(kw, reason):
    sim, world, why = _accept(_state(), [_prop(**kw)])
    assert sim is None and world is None and why == [reason]


def test_rejects_unknown_or_hidden_entity(monkeypatch):
    from services import graph_resolver as gr

    ents = dict(gr.load_entities())
    ents["brekmar_oculto"] = {
        "id": "brekmar_oculto",
        "type": "location",
        "visibility": "hidden",
        "name": "Oculto",
    }
    monkeypatch.setattr(gr, "load_entities", lambda: ents)
    assert _accept(_state(), [_prop(entity_ids=["brekmar_oculto"])])[2] == ["entity"]


def test_rejects_secret_and_catalog_name(monkeypatch):
    assert _accept(_state(), [_prop(text=TEXT + " segundo Durrak, o anão")])[2] == ["name"]
    import services.memory_provenance as mp

    monkeypatch.setattr(mp, "find_strict_unrevealed", lambda text, state: "sec")
    assert _accept(_state(), [_prop()])[2] == ["secret"]


def test_rejects_duplicate_of_active_seed_or_news():
    st = _state()
    sim: dict = {}
    make_rumor(sim, "rumor_os_navios_de_durrak_atraem_o_fundo", region="brekmar", loc="brekmar")
    st["world_sim"] = sim
    dup_text = (
        "Dizem que os navios do estaleiro são feitos de osso de leviatã e o fundo do mar vem buscar"
    )
    assert _accept(st, [_prop(text=dup_text)])[2] == ["duplicate"]
    # semente da regiao (mesmo sem instancia ativa)
    st2 = _state()
    assert _accept(st2, [_prop(text=dup_text)])[2] == ["duplicate"]
    # notícia ja ouvida
    st3 = _state()
    st3["world"]["news"] = [{"text": TEXT, "location_id": "brekmar"}]
    assert _accept(st3, [_prop()])[2] == ["duplicate"]


def test_rejects_when_quarantined():
    sim, world, why = _accept(_state(), [_prop()], quarantined=True)
    assert sim is None and world is None and why[0] == "quarantine"


def test_rejects_over_daily_cap():
    st = _state()
    st["world_sim"] = {"rumor_last_perceived_day": 5}
    assert _accept(st, [_prop()])[2] == ["daily_cap"]


def test_only_one_per_turn():
    sim, _w, _why = _accept(_state(), [_prop(), _prop(text=TEXT + " e também nas docas velhas")])
    assert len([r for r in sim["rumors"] if r["family"] == "narrador"]) == 1


def test_proposed_mode_off_ignores_field(monkeypatch):
    monkeypatch.setenv("RPG_RUMORS_PROPOSED", "off")
    assert _accept(_state(), [_prop()]) == (None, None, ["mode"])
    updates: dict = {}
    stt._apply_proposed_rumors(
        _state(), updates, stt.StoryUpdate(narrative="x", proposed_rumors=[_prop()]), 5, False
    )
    assert updates == {}


def test_apply_helper_merges_into_updates():
    st = _state()
    updates = {"world": st["world"]}
    stt._apply_proposed_rumors(
        st, updates, stt.StoryUpdate(narrative="x", proposed_rumors=[_prop()]), 5, False
    )
    assert updates["world_sim"]["rumors"][-1]["family"] == "narrador"
    assert updates["world"]["news"][-1]["kind"] == "rumor"


def test_fallbackllm_story_update_without_field_is_safe():
    st = _state()
    updates: dict = {}
    stt._apply_proposed_rumors(
        st, updates, AIMessage(content="erro"), 5, False
    )  # guard de FallbackLLM
    stt._apply_proposed_rumors(st, updates, None, 5, False)
    assert updates == {}
