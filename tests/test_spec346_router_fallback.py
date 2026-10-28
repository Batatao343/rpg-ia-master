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


_AMEACA = AIMessage(
    content="Dois bandidos armados bloqueiam a ponte e o guarda Brunna rosna uma ameaça."
)

HOSTILE = [
    "Ataco o bandido mais próximo",
    "Saco a espada e ataco o bandido da esquerda",
    "Golpeio o bandido com o punho",
    "Apunhalo o bandido pelas costas",
    "Enfrento os bandidos na ponte",
    "Atiro contra o bandido",
]
NOT_HOSTILE = [
    "Enfrento meu medo e atravesso a ponte",
    "Disparo pela porta rumo à praça",
    "Golpeio a mesa com o punho e exijo o preço justo",
    "Conto ao capitão que fui atacado na estrada",
    "Enfrento a subida da montanha",
    "Ataco o problema com calma e penso num plano",
    "Não ataco o bandido, só observo",
    "Fui atacado ontem, mas hoje descanso",
    "Golpeio a madeira para acender a fogueira",
]


@pytest.mark.parametrize("text", HOSTILE)
def test_hostile_battery_opens_combat(text):
    payload = router.dm_router_node(_state(text, ai=_AMEACA))
    assert payload["next"] == "combat_agent", text
    assert router.last_decision()["route_source"] == "hostility_fallback"


@pytest.mark.parametrize("text", NOT_HOSTILE)
def test_non_hostile_battery_stays_story(text):
    payload = router.dm_router_node(_state(text, ai=_AMEACA))
    assert payload["next"] == "storyteller", text


def test_danger_or_armed_words_alone_are_not_a_signal():
    ai = AIMessage(content="Um homem armado e perigoso passa ao longe.")
    payload = router.dm_router_node(_state("Golpeio a mesa", ai=ai))
    assert payload["next"] == "storyteller"


@pytest.mark.parametrize("text", ["Ataco a criatura hostil que surgir", "Ataco os vultos"])
def test_generic_target_needs_creature_and_threat_in_narration(text):
    ai = AIMessage(content="Vultos hostis rosnam entre as sombras, uma criatura ameaça avançar.")
    assert router.dm_router_node(_state(text, ai=ai))["next"] == "combat_agent"
    calm = AIMessage(content="A estrada está calma.")
    assert router.dm_router_node(_state(text, ai=calm))["next"] == "storyteller"
