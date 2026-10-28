"""SPEC-355 R5: com os CLASSIFY esgotados, o alvo hostil precisa estar em cena (narrado)."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.router as router
from llm_setup import FallbackLLM


def _state(text, *ai_texts, enemies=None):
    msgs = [AIMessage(content=t) for t in ai_texts] + [HumanMessage(content=text)]
    st = {"messages": msgs, "world": {}}
    if enemies:
        st["enemies"] = enemies
    return st


@pytest.fixture(autouse=True)
def _exhausted(monkeypatch):
    monkeypatch.setattr(router, "get_llm", lambda **k: FallbackLLM("esgotado"))


@pytest.mark.parametrize(
    ("text", "ai", "enemies"),
    [
        ("sem pensar ataco o saqueador", ["Um saqueador surge da poeira."], None),
        ("ataco o guarda para abrir caminho", ["O guarda bloqueia o portão."], None),
        ("golpeio o bandido", ["A noite cai."], [{"name": "Bandido"}]),
        ("ataco o goblin", ["Um goblin rosna.", "Você recua um passo."], None),
    ],
)
def test_present_target_opens_combat(text, ai, enemies):
    payload = router.dm_router_node(_state(text, *ai, enemies=enemies))
    assert payload["next"] == "combat_agent", text


@pytest.mark.parametrize(
    ("text", "ai"),
    [
        ("ataco o lobo", ["A trilha segue em silêncio.", "Folhas se mexem."]),
        ("ataco o lobo", ["Um lobo rosna.", "Você recua.", "O vento sopra."]),  # 3ª fala atrás
        ("golpeio a porta para abrir caminho", ["Dois guardas vigiam a porta, ameaçadores."]),
        ("não ataco o guarda", ["O guarda bloqueia o portão."]),
        ("fui atacado pelo guarda", ["O guarda bloqueia o portão."]),
        ("numa partida de dados ataco o rei", ["O rei sorri, ameaçador."]),
        ("ataco o meu medo", ["Um saqueador surge."]),
        ("enfrento a subida", ["Um saqueador surge."]),
        ("ataco o guarda", ["A praça está vazia."]),
    ],
)
def test_absent_or_nonhostile_stays_story(text, ai):
    payload = router.dm_router_node(_state(text, *ai))
    assert payload["next"] == "storyteller", text
