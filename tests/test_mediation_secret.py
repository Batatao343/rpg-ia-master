"""SPEC-202 Etapa 3 — mediação do narrador sem vazar segredo (R11)."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

import agents.storyteller as stt


class _CaptureLLM:
    def __init__(self, narrative: str):
        self.narrative = narrative
        self.prompts: list[str] = []
        self._schema = None

    def with_structured_output(self, schema, *_a, **_k):
        self._schema = schema
        return self

    def invoke(self, messages, *_a, **_k):
        self.prompts.append(str(getattr(messages[0], "content", "")))
        if self._schema is stt.StoryUpdate:
            return stt.StoryUpdate(narrative=self.narrative)
        from mock_llm import MockLLM

        return MockLLM().with_structured_output(self._schema).invoke(messages)


def _state(**extra) -> dict:
    st = {
        "game_id": "pytest-spec202-med",
        "narrative_summary": "",
        "archivist_last_run": 0,
        "messages": [HumanMessage(content="Pergunto ao narrador o que a Velha Magda sente")],
        "npcs": {
            "Velha Magda": {
                "name": "Velha Magda",
                "role": "Vidente",
                "in_scene": True,
                "home_location_id": "nova_arcadia",
                "relationship": 6,
                "hidden_traits": ["supersticioso", "ganancioso"],
                "revealed_traits": [],
                "memory": ["Leu as cartas para o herói."],
                "persona": "Guarda o pacto com Daruun em segredo.",
            }
        },
        "party": [],
        "factions": [],
        "faction_intel": {},
        "campaign_plan": {},
        "player": {
            "name": "T",
            "class_name": "Devoto do Abismo",
            "level": 1,
            "vitalidade": 20,
            "max_vitalidade": 20,
        },
        "world": {
            "current_location": "Nova Arcádia",
            "current_location_id": "nova_arcadia",
            "turn_count": 5,
            "time_of_day": "Dia",
            "danger_level": 1,
            "world_clock": {"day": 1, "period": "Manhã"},
            "quest_plan": [],
        },
        "next": "storyteller",
        "interlocutor_reason": "meta_to_narrator",
        "mediated_subject_id": "npc_velha_magda",
    }
    st.update(extra)
    return st


def test_mediacao_usa_visible_npc_view(monkeypatch):
    llm = _CaptureLLM("Magda observa as cartas em silêncio.")
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: llm)
    stt.storyteller_node(_state())
    prompt = next(p for p in llm.prompts if "PERGUNTA AO NARRADOR" in p)
    assert "nome=Velha Magda" in prompt and "papel=Vidente" in prompt
    for hidden in (
        "supersticioso",
        "Supersticioso",
        "ganancioso",
        "Ganancioso",
        "pacto com Daruun",
    ):
        assert hidden not in prompt


def test_mediacao_clause_vazia_fora_de_mediacao():
    assert stt._mediation_clause({"interlocutor_reason": "direct_address"}) == ""
    assert stt._mediation_clause({}) == ""


def test_mediacao_com_assinatura_nao_revelada_substitui_paragrafo(monkeypatch):
    leak = (
        "Magda desvia o olhar.\n\nEla carrega o peso do pacto com Daruun, "
        "feito em troca de imortalidade.\n\n— Pergunte outra coisa."
    )
    llm = _CaptureLLM(leak)
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: llm)
    out = stt.storyteller_node(_state())
    text = out["messages"][-1].content
    assert "pacto com daruun" not in text.lower()
    assert "Magda desvia o olhar." in text
    assert "não deixa transparecer" in text
    assert any(
        r.startswith("mediation_secret:pacto_valerius")
        for r in out.get("narrative_rejections") or []
    )


def test_mediacao_segredo_ja_revelado_passa(monkeypatch):
    leak = "Ela carrega o peso do pacto com Daruun."
    llm = _CaptureLLM(leak)
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: llm)
    st = _state(
        player={
            "name": "T",
            "class_name": "Devoto do Abismo",
            "level": 1,
            "vitalidade": 20,
            "max_vitalidade": 20,
            "known_secrets": ["O pacto com Daruun"],
        }
    )
    out = stt.storyteller_node(st)
    assert "pacto com Daruun" in out["messages"][-1].content
    assert not any(
        str(r).startswith("mediation_secret") for r in out.get("narrative_rejections") or []
    )


def test_mediacao_multipla_lista_presentes():
    st = _state(interlocutor_reason="ambiguous_multi_mediated", mediated_subject_id=None)
    st["npcs"]["Brunna Ponte-Alta"] = {
        "name": "Brunna Ponte-Alta",
        "in_scene": True,
        "home_location_id": "nova_arcadia",
    }
    clause = stt._mediation_clause(st)
    assert "Velha Magda" in clause and "Brunna Ponte-Alta" in clause
