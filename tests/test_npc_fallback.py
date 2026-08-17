"""Suíte da spec npc-fallback-sem-alvo — fim do "Ninguém responde.".

Offline/determinístico. Ver specs/npc-fallback-sem-alvo.md.
"""
from langchain_core.messages import HumanMessage

from agents.npc import _mission_hint_block, npc_actor_node
from agents.storyteller import _npc_fallback_clause
from services.npc_layers import npcs_in_scene


# --- R1: resolução de alvo (npcs_in_scene) ----------------------------------

def test_npcs_in_scene_inclui_npc_e_party_exclui_waiting():
    state = {
        "npcs": {"Velho Tomás": {"in_scene": True}, "Bruxa": {"in_scene": False}},
        "party": [
            {"name": "Gorim", "active": True, "status": "ativo"},
            {"name": "Lyra", "active": False, "status": "ativo", "waiting_at": "Vila"},
        ],
    }
    got = npcs_in_scene(state)
    assert "Velho Tomás" in got          # in_scene
    assert "Bruxa" not in got            # fora de cena
    assert "Gorim" in got                # aliado presente
    assert "Lyra" not in got             # waiting


def test_sem_nome_escolhe_npc_em_cena():
    state = {"messages": [HumanMessage(content="Pergunto a quem estiver por perto")],
             "npcs": {"Velho Tomás": {"in_scene": True}}, "party": [],
             "world": {"current_location": "Praça"}, "game_id": "g"}
    # com NPC em cena, npcs_in_scene resolve o alvo (não cai no fallback)
    assert npcs_in_scene(state)[0] == "Velho Tomás"


def test_sem_nome_escolhe_party_gorim():
    # Cenário Gorim: nenhum NPC no dict, mas aliado presente → ele é o alvo.
    state = {"npcs": {}, "party": [{"name": "Gorim", "active": True, "status": "ativo"}]}
    assert npcs_in_scene(state) == ["Gorim"]


# --- R2: fallback para o storyteller (nunca "Ninguém responde") -------------

def test_sem_candidato_roteia_storyteller():
    state = {"messages": [HumanMessage(content="Chamo por ajuda no ermo vazio")],
             "npcs": {}, "party": [], "world": {"current_location": "Ermo"}, "game_id": "g"}
    out = npc_actor_node(state)
    assert out.get("next") == "storyteller"
    assert out.get("npc_fallback_hint")
    # nunca a string seca
    msgs = out.get("messages") or []
    assert not any("Ninguém responde" in str(getattr(m, "content", "")) for m in msgs)


def test_npc_fallback_clause_presente_com_hint():
    clause = _npc_fallback_clause({"npc_fallback_hint": "Falo com o taverneiro"})
    assert "SEM INTERLOCUTOR" in clause


def test_npc_fallback_clause_ausente_sem_hint():
    assert _npc_fallback_clause({}) == ""


def test_grafo_npc_actor_liga_no_storyteller():
    # A aresta condicional npc_actor→storyteller existe no grafo compilado.
    from main import build_game_graph
    g = build_game_graph()
    edges = g.get_graph().edges
    pares = {(e.source, e.target) for e in edges}
    assert ("npc_actor", "storyteller") in pares
    assert ("npc_actor", "archivist") in pares


# --- R4: pergunta de missão usa o beat --------------------------------------

def test_pergunta_de_missao_usa_objetivo_publico_sem_vazar_beat():
    state = {"campaign_plan": {"beats": [
        {"description": "Encontre o mercador desaparecido nas docas", "status": "pending"}],
        "current_step": 0}}
    block = _mission_hint_block(state, "o que a missão exige agora?")
    assert "Investigue os acontecimentos" in block
    assert "mercador desaparecido" not in block
    assert "OBJETIVO_ATUAL" in block


def test_pergunta_nao_missao_nao_injeta_beat():
    state = {"campaign_plan": {"beats": [{"description": "X", "status": "pending"}]}}
    assert _mission_hint_block(state, "que belo dia, não?") == ""
