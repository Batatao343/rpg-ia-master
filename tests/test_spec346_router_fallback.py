"""SPEC-346 R26: CLASSIFY esgotado + hostilidade explicita + sinal de alvo abre combate."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.router as router
from llm_setup import FallbackLLM

NARRACAO = AIMessage(
    content="Tres vultos armados saem da sombra e bloqueiam a estrada, rosnando ameacas."
)


def _state(text, ai=NARRACAO):
    msgs = ([ai] if ai else []) + [HumanMessage(content=text)]
    return {"messages": msgs, "world": {}}


@pytest.fixture(autouse=True)
def _exhausted(monkeypatch):
    monkeypatch.setattr(router, "get_llm", lambda **k: FallbackLLM("esgotado"))


def test_exhausted_classify_explicit_attack_opens_combat():
    payload = router.dm_router_node(_state("Saco a espada e ataco o bandido mais próximo"))
    assert payload["next"] == "combat_agent"
    assert payload["combat_target"] == "bandido"
    assert payload["interlocutor_reason"] == "classify_fallback"
    dec = router.last_decision()
    assert dec["route_source"] == "hostility_fallback"
    assert dec["route_fallback_reason"] == "not_router_decision"


def test_generic_target_becomes_inimigos():
    payload = router.dm_router_node(
        _state("ataco a primeira criatura hostil que surgir na galeria")
    )
    assert payload["next"] == "combat_agent"
    assert payload["combat_target"] == "Inimigos"


def test_exhausted_classify_without_threat_stays_story():
    payload = router.dm_router_node(
        _state("ataco o ar", ai=AIMessage(content="A estrada é calma."))
    )
    assert payload["next"] == "storyteller"
    assert router.last_decision()["route_source"] == "classify_fallback"


def test_negated_attack_stays_story():
    payload = router.dm_router_node(_state("não ataco ninguém"))
    assert payload["next"] == "storyteller"


def test_invoke_exception_branch_same_rule(monkeypatch):
    class Boom:
        def with_structured_output(self, *_a, **_k):
            raise RuntimeError("falhou")

    monkeypatch.setattr(router, "get_llm", lambda **k: Boom())
    payload = router.dm_router_node(_state("ataco o bandido"))
    assert payload["next"] == "combat_agent"
    assert router.last_decision()["route_fallback_reason"] == "invoke_exception"


def test_bestiary_name_in_text_is_a_signal():
    payload = router.dm_router_node(
        _state("ataco o goblin", ai=AIMessage(content="O vento sopra."))
    )
    assert payload["next"] == "combat_agent"


def test_off_path_unchanged():
    payload = router.dm_router_node(_state("ando pela estrada vazia"))
    assert payload["next"] == "storyteller"
    dec = router.last_decision()
    assert dec["route_source"] == "classify_fallback"
    assert dec["route_fallback_reason"] in {"not_router_decision", "invoke_exception"}
