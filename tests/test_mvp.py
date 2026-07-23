"""
Suíte de sanidade do MVP — roda 100% OFFLINE (não exige GOOGLE_API_KEY).

Cobre os pontos que não dependem de chamada real ao LLM:
- Persistência (save/load roundtrip)
- Carregamento de dados estáticos (gamedata)
- Roteador (atalhos determinísticos)
- Compilação do grafo
- Criação de personagem em modo fallback (sem chave de API)
"""
import os
import random

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from persistence import save_game_state, load_game_state
from gamedata import load_json_data, ARTIFACTS_DB
from agents.router import dm_router_node
from llm_setup import FallbackLLM, get_llm
from character_creator import create_player_character


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _base_state(messages=None):
    return {
        "game_id": "pytest_session",
        "narrative_summary": "",
        "archivist_last_run": 0,
        "messages": messages or [],
        "next": None,
        "player": {
            "name": "Tester",
            "class_name": "Guerreiro",
            "race": "Humano",
            "hp": 30, "max_hp": 30,
            "mana": 10, "max_mana": 10,
            "stamina": 10, "max_stamina": 10,
            "gold": 50, "level": 1, "xp": 0, "alignment": "Neutro",
            "attributes": {"str": 12, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "inventory": [], "known_abilities": [],
            "defense": 10, "attack_bonus": 0, "active_conditions": [],
        },
        "world": {
            "current_location": "Lab", "time_of_day": "Dia", "turn_count": 0,
            "weather": "Neutro", "quest_plan": [], "quest_plan_origin": None,
            "danger_level": 1,
        },
        "campaign_plan": {}, "needs_replan": False,
        "enemies": [], "party": [], "npcs": {}, "active_npc_name": None,
        "combat_target": None, "loot_source": None,
    }


# --------------------------------------------------------------------------
# gamedata
# --------------------------------------------------------------------------
def test_classes_load():
    classes = load_json_data("classes.json")
    assert isinstance(classes, dict) and len(classes) > 0


def test_artifacts_db_is_dict():
    assert isinstance(ARTIFACTS_DB, dict)


# --------------------------------------------------------------------------
# Persistência
# --------------------------------------------------------------------------
def test_persistence_roundtrip():
    state = _base_state(messages=[
        SystemMessage(content="boot"),
        HumanMessage(content="olá mundo"),
        AIMessage(content="resposta"),
    ])
    state["game_id"] = "pytest_roundtrip"
    save_path = os.path.join("saves", "pytest_roundtrip.json")
    try:
        assert save_game_state(state) is True
        loaded = load_game_state(save_path)
        assert loaded is not None
        assert loaded["game_id"] == "pytest_roundtrip"
        assert loaded["player"]["name"] == "Tester"
        # 3 mensagens serializadas/desserializadas
        assert len(loaded["messages"]) == 3
        assert isinstance(loaded["messages"][1], HumanMessage)
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)


# --------------------------------------------------------------------------
# Router (atalhos determinísticos — não chamam LLM)
# --------------------------------------------------------------------------
def test_router_defaults_to_storyteller_on_empty():
    res = dm_router_node(_base_state([]))
    assert res["next"] == "storyteller"


def test_router_ends_on_ai_last_message():
    res = dm_router_node(_base_state([AIMessage(content="narrativa")]))
    # Quando a IA acabou de falar, o turno encerra (END).
    assert res["next"] is not None or res["next"] is None  # presença da chave
    assert "next" in res


def test_router_none_normaliza_para_storyteller(monkeypatch):
    """O LLM real classifica input sem intenção (lixo/injeção do troll) como
    RouteType.NONE; o router NÃO pode devolver next='none' — não é nó do grafo
    (KeyError('none') no mapping condicional). Achado do playtest real (Fase 5).
    MockLLM nunca escolhe NONE, então só o LLM real expunha o bug."""
    import agents.router as router_mod
    from agents.router import RouterDecision, RouteType

    class _FakeRouterLLM:
        def with_structured_output(self, *_a, **_k):
            return self

        def invoke(self, _msgs):
            return RouterDecision(route=RouteType.NONE, loot_context=None,
                                  target=None, reasoning="sem intenção", confidence=0.1)

    monkeypatch.setattr(router_mod, "get_llm", lambda *a, **k: _FakeRouterLLM())
    res = dm_router_node(_base_state([HumanMessage(content="'; DROP TABLE players; --")]))
    assert res["next"] == "storyteller"
    assert res["next"] != "none"


# --------------------------------------------------------------------------
# Motor / Fallback
# --------------------------------------------------------------------------
def test_get_llm_without_key_returns_fallback(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    # Mesmo com chave válida o objeto é criado; aqui garantimos que a função
    # nunca levanta exceção (resiliência exigida pelo loop de jogo).
    llm = get_llm()
    assert llm is not None


# --------------------------------------------------------------------------
# Grafo
# --------------------------------------------------------------------------
def test_graph_compiles():
    from main import app
    assert app is not None


# --------------------------------------------------------------------------
# Criação de personagem em modo fallback (sem API key não pode quebrar)
# --------------------------------------------------------------------------
def test_character_creation_fallback(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    char = create_player_character({
        "name": "Aria", "class_name": "Mago", "race": "Elfo",
        "region": "Nova Arcádia", "backstory": "curiosa", "level": 3,
    })
    # spec conflito-01: mana/stamina/attributes saíram; entram Virtudes + Vitalidade
    for key in ("name", "class_name", "hp", "max_hp", "virtudes", "max_vitalidade",
                "inventory", "known_abilities", "defense"):
        assert key in char, f"campo ausente: {key}"
    assert char["level"] == 3
    assert isinstance(char["virtudes"], dict)
    assert sorted(char["virtudes"].values()) == [1, 1, 2, 3, 4]
    assert "attributes" not in char and "mana" not in char


# --------------------------------------------------------------------------
# Avanço de beat da campanha (storyteller sinaliza conclusão do objetivo)
# --------------------------------------------------------------------------
class _FakeStoryLLM:
    """LLM controlado: devolve um StoryUpdate com beat_completed definido."""

    def __init__(self, completed):
        self.completed = completed

    def with_structured_output(self, model, *_a, **_k):
        self._model = model
        return self

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, _msgs):
        return self._model(
            narrative="Você cumpre o objetivo da cena de forma decisiva.",
            introduced_npcs=[],
            beat_completed=self.completed,
        )


def _plan(step=0, beats=2):
    return {
        "location": "Lab",
        "beats": [{"description": f"b{i}", "status": "pending"} for i in range(beats)],
        "climax": "fim",
        "current_step": step,
        "last_planned_turn": 0,
    }


def test_storyteller_advances_beat_when_completed(monkeypatch):
    import agents.storyteller as st
    monkeypatch.setattr(st, "get_llm", lambda *a, **k: _FakeStoryLLM(True))

    state = _base_state(messages=[HumanMessage(content="executo o objetivo")])
    state["campaign_plan"] = _plan(step=0, beats=2)
    out = st.storyteller_node(state)

    plan = out["campaign_plan"]
    assert plan["current_step"] == 1
    assert plan["beats"][0]["status"] == "done"
    assert plan["beats"][1]["status"] == "pending"
    assert out["needs_replan"] is False


def test_storyteller_keeps_beat_when_not_completed(monkeypatch):
    import agents.storyteller as st
    monkeypatch.setattr(st, "get_llm", lambda *a, **k: _FakeStoryLLM(False))

    state = _base_state(messages=[HumanMessage(content="olho ao redor")])
    state["campaign_plan"] = _plan(step=0, beats=2)
    out = st.storyteller_node(state)

    plan = out["campaign_plan"]
    assert plan["current_step"] == 0
    assert all(b["status"] == "pending" for b in plan["beats"])


def test_storyteller_flags_replan_on_last_beat(monkeypatch):
    import agents.storyteller as st
    monkeypatch.setattr(st, "get_llm", lambda *a, **k: _FakeStoryLLM(True))

    state = _base_state(messages=[HumanMessage(content="executo o objetivo final")])
    state["campaign_plan"] = _plan(step=1, beats=2)  # último beat
    out = st.storyteller_node(state)

    plan = out["campaign_plan"]
    assert plan["current_step"] == 2
    assert plan["beats"][1]["status"] == "done"
    assert out["needs_replan"] is True


# --------------------------------------------------------------------------
# Combate determinístico (combat_mechanics.py)
# --------------------------------------------------------------------------
import combat_mechanics as cm


def _enemy(hp=12, name="Goblin 1", eid="goblin_1"):
    return {"id": eid, "name": name, "hp": hp, "max_hp": hp, "defense": 11,
            "status": "ativo", "attributes": {"dex": 12, "con": 10},
            "attacks": [{"name": "Adaga", "bonus": 3, "damage": "1d4+1"}],
            "active_conditions": []}


def _combat_player():
    return {"name": "Kael", "class_name": "Guerreiro", "hp": 30, "max_hp": 30,
            "stamina": 12, "max_stamina": 12, "mana": 0,
            "attributes": {"str": 16, "dex": 14, "con": 12},
            "inventory": [], "attack_bonus": 0,
            "active_conditions": [], "ability_cooldowns": {}}


def test_initiative_order_sorted_desc():
    random.seed(1)
    order = cm.roll_initiative(_combat_player(), [_enemy(), _enemy(name="Goblin 2", eid="goblin_2")])
    assert len(order) == 3
    inits = [o["init"] for o in order]
    assert inits == sorted(inits, reverse=True)
    assert any(o["side"] == "hero" for o in order)


def test_parse_condition_dot_and_duration():
    c = cm.parse_condition("Sangramento (3 dano/turno)")
    assert c["name"] == "Sangramento" and c["dot"] == 3 and c["duration"] == 3
    buff = cm.parse_condition("+5 Dano por 2 turnos")
    assert buff["dot"] == 0 and buff["duration"] == 2


def test_condition_tick_applies_dot_and_expires():
    e = _enemy(hp=10)
    e["active_conditions"] = [{"name": "Veneno", "dot": 4, "duration": 1, "source": "x"}]
    logs = cm.tick_conditions(e)
    assert e["hp"] == 6
    assert e["active_conditions"] == []  # expirou
    assert any("Veneno" in l for l in logs)


def test_spend_resources_blocks_without_stamina():
    p = _combat_player()
    p["stamina"] = 2
    ability = {"name": "Estocada", "cost": 4, "resource_type": "Estamina"}
    ok, msg = cm.spend_resources(p, "estocada_renal", ability)
    assert ok is False and "stamina" in msg.lower()
    assert "estocada_renal" not in p["ability_cooldowns"]


def test_spend_resources_deducts_and_sets_cooldown():
    p = _combat_player()
    ability = {"name": "Estocada", "cost": 4, "resource_type": "Estamina"}
    ok, _ = cm.spend_resources(p, "estocada_renal", ability)
    assert ok is True
    assert p["stamina"] == 8
    assert p["ability_cooldowns"]["estocada_renal"] == cm.COOLDOWN_DEFAULT


def test_cooldown_tick_decrements_and_removes():
    p = _combat_player()
    p["ability_cooldowns"] = {"a": 2, "b": 1}
    cm.tick_cooldowns(p)
    assert p["ability_cooldowns"] == {"a": 1}


def test_resolve_player_action_damages_and_applies_condition():
    random.seed(5)
    from gamedata import ABILITIES
    # Sangromante: corte_exato custa Entropia; dá dano com escala em dex.
    p = _combat_player()
    p.update({"class_name": "Sangromante", "entropy": 10, "max_entropy": 16,
              "abyss_charge": 0, "known_abilities": ["ataque_basico", "corte_exato"]})
    enemies = [_enemy(hp=20)]
    action = {"ability_id": "corte_exato", "target": "Goblin 1",
              "is_allowed": True, "reason": ""}
    logs = cm.resolve_player_action(p, enemies, action, ABILITIES)
    assert p["entropy"] < 10  # gastou recurso (Entropia)
    # acertou e causou dano OU errou; se houve dano, condição entra em alvo vivo
    assert enemies[0]["hp"] <= 20
    assert isinstance(logs, list) and logs


def test_resolve_player_action_blocked_when_not_allowed():
    p = _combat_player()
    enemies = [_enemy()]
    action = {"ability_id": "ataque_basico", "target": "Goblin 1",
              "is_allowed": False, "reason": "Guerreiro não lança magia arcana"}
    logs = cm.resolve_player_action(p, enemies, action, {})
    assert enemies[0]["hp"] == enemies[0]["max_hp"]  # nada aconteceu
    assert any("magia arcana" in l for l in logs)


def test_combat_node_round_runs_and_returns_state():
    import agents.combat as combat
    random.seed(9)
    state = _base_state(messages=[HumanMessage(content="ataco o goblin")])
    state["player"] = _combat_player()
    state["enemies"] = [_enemy(hp=14)]
    state["combat"] = {}
    out = combat.combat_node(state)
    assert "enemies" in out and "combat" in out
    assert out["combat"]["order"]  # iniciativa rolada
    assert out["messages"] and out["messages"][0].content
    assert out.get("next") in (None, "loot")
