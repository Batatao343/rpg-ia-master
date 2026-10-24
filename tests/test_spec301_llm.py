"""SPEC-301 Etapa 7 — fiação do LLM: intenção proposta, prompt, crônica, guard (R20/R21)."""

from __future__ import annotations

import re

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.npc as npc
import agents.storyteller as st_mod
import gamedata
import mock_llm
import world_utils as wu
from services import faction_membership as fm
from services.chronicle import render_milestone
from tests.spec301_support import add_npc, at, joined, make_state, merge, mission_quest


class _FakeLLM:
    def __init__(self, result):
        self._result = result

    def with_structured_output(self, *_a, **_k):
        return self

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, _msgs):
        return self._result


def _story_state(text: str, *, location: str = "na_anel_ferro", **over) -> dict:
    st = make_state()
    st["messages"] = [HumanMessage(content=text)]
    st["world"] = {**wu.starting_world("Nova Arcádia", 3), "current_location_id": location}
    st["world"]["turn_count"] = 5
    st["factions"] = gamedata.seed_factions()
    st["faction_intel"] = {"legiao_ferro": {"known": True, "knows_goal": False}}
    st.update({"campaign_plan": {}, "needs_replan": False, "enemies": [], "party": []})
    st.update(over)
    return st


def _run_story(monkeypatch, update, state):
    monkeypatch.setattr(st_mod, "get_llm", lambda *a, **k: _FakeLLM(update))
    return st_mod.storyteller_node(state)


def test_membership_action_ausente_nao_quebra(monkeypatch):
    # FallbackLLM devolve AIMessage, não StoryUpdate: o guard ignora o campo todo.
    out = _run_story(
        monkeypatch, AIMessage(content="erro"), _story_state("Quero me alistar na Legião.")
    )
    assert "faction_membership" not in out
    assert out["messages"]


def test_story_join_via_membership_action(monkeypatch):
    update = st_mod.StoryUpdate(
        narrative="Thrace estuda você.",
        membership_action=st_mod.MembershipAction(action="join", faction_id="legiao_ferro"),
    )
    out = _run_story(monkeypatch, update, _story_state("Quero me alistar na Legião de Ferro."))
    rec = out["faction_membership"]["legiao_ferro"]
    assert rec["status"] == "ativo"
    assert any(e["type"] == "faction_membership_changed" for e in out["pending_world_events"])
    text = out["messages"][0].content
    assert "Recruta" in text and "Thrace estuda você." in text
    assert out["faction_intel"]["legiao_ferro"]["knows_goal"] is True


def test_id_invalido_vira_nota_de_recusa_sem_estado(monkeypatch):
    update = st_mod.StoryUpdate(
        narrative="x",
        membership_action=st_mod.MembershipAction(action="join", faction_id="osshari_brekmar"),
    )
    out = _run_story(monkeypatch, update, _story_state("Quero entrar nos Osshari."))
    assert "faction_membership" not in out
    assert (
        "osshari" not in out["messages"][0].content.lower()
        or "[FAÇÃO]" in out["messages"][0].content
    )
    # fação fechada: recusa narrável, sem número
    update = st_mod.StoryUpdate(
        narrative="x",
        membership_action=st_mod.MembershipAction(
            action="join", faction_id="mercadores_escravos_pradaria"
        ),
    )
    out = _run_story(monkeypatch, update, _story_state("Quero entrar."))
    assert "faction_membership" not in out
    assert not re.search(r"\d", out["messages"][0].content.split("\n\n", 1)[-1])
    # id que nem existe: nada muda
    upd, ev, note = fm.apply_intent(make_state(), "join", "faccao_inventada")
    assert (upd, ev) == ({}, []) and note


def test_acao_invalida_e_ignorada():
    assert fm.apply_intent(make_state(), "voar", "legiao_ferro") == ({}, [], "")
    assert fm.apply_intent(make_state(), "", "") == ({}, [], "")


def test_quarentena_ignora_campo(monkeypatch):
    from services.structured_outputs import ProposedWorldEvent

    update = st_mod.StoryUpdate(
        narrative="x",
        membership_action=st_mod.MembershipAction(action="join", faction_id="legiao_ferro"),
        proposed_events=[ProposedWorldEvent(type="npc_killed", target_id="npc_que_nao_existe")],
    )
    out = _run_story(monkeypatch, update, _story_state("Quero me alistar na Legião."))
    assert "faction_membership" not in out
    assert any("event_rejected" in r for r in out.get("narrative_rejections", []))


def test_ask_mission_cria_quest_de_template(monkeypatch):
    st = joined(_story_state("Peço uma missão à Legião."), "legiao_ferro")
    update = st_mod.StoryUpdate(
        narrative="x",
        membership_action=st_mod.MembershipAction(action="ask_mission", faction_id="legiao_ferro"),
    )
    out = _run_story(monkeypatch, update, st)
    quest = next(q for q in out["quests"] if q.get("faction_id") == "legiao_ferro")
    titles = {t["title"] for t in fm.load_catalog()["legiao_ferro"]["mission_templates"]}
    assert quest["title"] in titles
    assert quest["title"] in out["messages"][0].content


def test_bloco_faccao_sem_numeros():
    st = joined(make_state(), "legiao_ferro", rank_index=2, merit=9)
    st["quests"] = [mission_quest("legiao_ferro", qid="m1")]
    block = fm.prompt_block(st)
    assert block.startswith("<FAÇÃO_DO_JOGADOR>") and "Sargento" in block
    assert "Missao de teste" in block
    assert not re.search(r"\d", block)
    assert fm.prompt_block(make_state()) == ""  # sem vínculo: nenhum bloco
    st["faction_membership"]["legiao_ferro"]["status"] = "suspeito"
    assert "suspeito" in fm.prompt_block(st)


def test_bloco_entra_no_prompt_do_storyteller(monkeypatch):
    captured = {}

    class _Spy(_FakeLLM):
        def invoke(self, msgs):
            captured["prompt"] = str(msgs[0].content)
            return super().invoke(msgs)

    monkeypatch.setattr(st_mod, "get_llm", lambda *a, **k: _Spy(st_mod.StoryUpdate(narrative="ok")))
    st = joined(_story_state("Observo o pátio."), "legiao_ferro")
    st_mod.storyteller_node(st)
    assert "<FAÇÃO_DO_JOGADOR>" in captured["prompt"] and "Recruta" in captured["prompt"]
    st_mod.storyteller_node(_story_state("Observo o pátio."))
    assert "<FAÇÃO_DO_JOGADOR>" not in captured["prompt"]
    assert "membership_action" in captured["prompt"]  # instrução curta, sempre presente


def _npc_state(location="na_anel_dourado", **over):
    st = at(make_state(), location)
    st["npcs"]["Comandante Thrace"] = {
        "id": "npc_comandante_thrace",
        "name": "Comandante Thrace",
        "role": "Comandante",
        "persona": "Seco.",
        "location": "Anel de Ferro",
        "in_scene": True,
        "relationship": 5,
        "memory": [],
        "home_location_id": location,
    }
    st["messages"] = [HumanMessage(content="Quero me alistar na Legião de Ferro.")]
    st["active_npc_name"] = "Comandante Thrace"
    st.update(over)
    return st


def _run_npc(monkeypatch, response, state):
    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: _FakeLLM(response))
    monkeypatch.setattr(npc, "RAG_AVAILABLE", False)
    return npc.npc_actor_node(state)


def _npc_response(**kw):
    return npc.NPCResponse(
        dialogue="Apresente-se amanhã.",
        action_description="Assente.",
        memory_update="x",
        relationship_change=0,
        **kw,
    )


def test_npc_recrutador_presente_habilita_join(monkeypatch):
    # fora do QG, mas Thrace (recrutador) está em cena
    resp = _npc_response(
        membership_action=npc.MembershipAction(action="join", faction_id="legiao_ferro")
    )
    out = _run_npc(monkeypatch, resp, _npc_state("na_anel_dourado"))
    assert out["faction_membership"]["legiao_ferro"]["status"] == "ativo"
    assert any(e["type"] == "faction_membership_changed" for e in out["pending_world_events"])
    assert "Recruta" in out["messages"][0].content
    # sem o recrutador em cena e fora do QG: recusa
    st = _npc_state("na_anel_dourado")
    st["npcs"] = {
        "Guarda": {**st["npcs"]["Comandante Thrace"], "id": "npc_guarda", "name": "Guarda"}
    }
    st["active_npc_name"] = "Guarda"
    out = _run_npc(monkeypatch, resp, st)
    assert "faction_membership" not in out


def test_npc_sem_campo_ou_fallback_nao_quebra(monkeypatch):
    out = _run_npc(monkeypatch, _npc_response(), _npc_state())
    assert "faction_membership" not in out and out["messages"]
    out = _run_npc(monkeypatch, AIMessage(content="erro"), _npc_state())
    assert out["messages"][0].content == "..."


def test_milestone_cronica_por_acao():
    def ev(action, fid="legiao_ferro", **payload):
        return {
            "type": "faction_membership_changed",
            "target_id": fid,
            "actor_id": "player",
            "event_id": "e",
            "turn": 3,
            "payload": {"action": action, **payload},
        }

    assert "Recruta" in render_milestone(ev("joined", rank_name="Recruta"), {})
    assert "Sargento" in render_milestone(ev("promoted", rank_name="Sargento"), {})
    assert "deixou" in render_milestone(ev("left"), {})
    assert "traiu" in render_milestone(ev("betrayed"), {})
    assert "destruída" in render_milestone(ev("dissolved"), {})
    assert "expulsou" in render_milestone(ev("expelled"), {})
    # o diário é do jogador: entrada secreta aparece na crônica...
    assert render_milestone(ev("joined", "mao_sombria", rank_name="Olheiro"), {})
    # ...mas não no contexto que os NPCs recebem
    from services.context_builder import render_event

    assert render_event(ev("joined", "mao_sombria"), {}) == ""
    assert "Legião" in render_event(ev("joined"), {})


def test_validator_rejeita_membership_vindo_do_llm():
    from services.event_processor import prevalidate_event_batch

    res = prevalidate_event_batch(
        [
            {
                "type": "faction_membership_changed",
                "actor_id": "player",
                "target_id": "legiao_ferro",
                "payload": {"action": "joined"},
                "source": "storyteller",
            }
        ],
        make_state(),
    )
    assert res and not res[0].ok


def test_mock_so_propoe_quando_o_jogador_pede():
    assert mock_llm._mock_membership("observo o pátio") is None
    assert mock_llm._mock_membership("quero me alistar na legião de ferro") == {
        "action": "join",
        "faction_id": "legiao_ferro",
    }
    assert mock_llm._mock_membership("deixo a legião")["action"] == "leave"
    assert mock_llm._mock_membership("peço uma missão à legião")["action"] == "ask_mission"
    assert mock_llm._mock_membership("quero me alistar") is None  # sem fação identificável


def test_mock_story_update_default_vazio():
    from pydantic import BaseModel  # noqa: F401

    msgs = [HumanMessage(content="Observo o pátio.")]
    obj = mock_llm._story_update(st_mod.StoryUpdate, msgs)
    assert obj.membership_action is None


@pytest.mark.parametrize("model", [st_mod.MembershipAction, npc.MembershipAction])
def test_schema_do_campo_defaults(model):
    m = model()
    assert m.action == "" and m.faction_id == ""
    assert add_npc and merge  # helpers usados em outros testes do arquivo
