"""Suíte da spec polish-prosa — anti-repetição, voz, menu de opções.

Offline/determinístico. Ver specs/polish-prosa.md.
"""
from langchain_core.messages import AIMessage, HumanMessage

from services import prose_guard as pg
from playtest import invariants as inv


# --- Etapa 1: prose_guard ---------------------------------------------------

def test_opening_normaliza():
    assert pg.opening("O AR fétido, do pântano! queima...", 3) == "o ar fétido"
    assert pg.opening("", 6) == ""


def test_repeats():
    a = "O ar fétido do pântano queima em suas narinas."
    b = "O ar fétido do pântano queima os pulmões também."  # 6 primeiras iguais
    c = "A luz do amanhecer corta o céu."
    assert pg.repeats(a, b) is True
    assert pg.repeats(a, c) is False


def test_ultimas_aberturas_ignora_humano():
    msgs = [AIMessage(content="Primeira narração longa aqui do mestre do jogo agora"),
            HumanMessage(content="ataco o goblin"),
            AIMessage(content="Segunda narração diferente do mestre continua a cena viva")]
    ab = pg.ultimas_aberturas(msgs, n=2, words=4)
    assert ab[0] == "segunda narração diferente do"
    assert ab[1] == "primeira narração longa aqui"


def test_openings_clause_vazio_sem_historico():
    assert pg.openings_clause([]) == ""
    assert "VARIE A ABERTURA" in pg.openings_clause(["o ar fétido do pântano"])


def test_log_if_repeats(caplog):
    with caplog.at_level("WARNING", logger="rpg.prose"):
        r = pg.log_if_repeats("O ar fétido do pântano queima aqui.",
                              "O ar fétido do pântano queima tudo.", where="combate")
    assert r is True
    assert any("repetida" in rec.message.lower() for rec in caplog.records)


# --- Etapa 2: voz + menu (cláusulas no prompt do storyteller) ---------------

def test_storyteller_injeta_clausulas(monkeypatch):
    # captura o system prompt do storyteller para conferir R1/R3.
    import agents.storyteller as st
    from gamedata import seed_factions
    from world_utils import starting_world

    captured = {}

    class _Rec:
        def with_structured_output(self, _m):
            return self
        def invoke(self, msgs):
            captured["sys"] = str(msgs[0].content)
            raise RuntimeError("parar após capturar prompt")

    monkeypatch.setattr(st, "get_llm", lambda *a, **k: _Rec())
    state = {
        "game_id": "g", "world": starting_world("Nova Arcádia", 1),
        "player": {"name": "Kael", "class_name": "Batedor", "level": 1,
                   "active_conditions": []},
        "factions": seed_factions(), "faction_intel": {}, "npcs": {}, "party": [],
        "messages": [AIMessage(content="O ar fétido do pântano queima em suas narinas outra vez"),
                     HumanMessage(content="Olho ao redor")],
        "campaign_plan": {"beats": [{"description": "Explore", "status": "pending"}],
                          "current_step": 0},
    }
    try:
        st.storyteller_node(state)
    except Exception:
        pass
    sys = captured.get("sys", "")
    assert "VARIE A ABERTURA" in sys           # R1
    assert "OPÇÕES concretas" in sys           # R3


# --- Etapa 3: invariante R5 -------------------------------------------------

def test_invariante_repeated_opening_dispara():
    msgs = [AIMessage(content="O ar fétido do pântano queima em suas narinas."),
            AIMessage(content="O ar fétido do pântano queima os pulmões."),
            AIMessage(content="O ar fétido do pântano queima tudo de podre.")]
    viol = inv.check_repeated_opening({"messages": msgs}, None, 11)
    assert viol and viol[0].check_id == "narrative.repeated_opening"
    assert viol[0].severity == "warning"


def test_invariante_repeated_opening_nao_dispara_variado():
    msgs = [AIMessage(content="O ar fétido do pântano queima."),
            AIMessage(content="A luz do amanhecer corta o céu."),
            AIMessage(content="Um grito ecoa entre as árvores.")]
    assert inv.check_repeated_opening({"messages": msgs}, None, 11) == []
