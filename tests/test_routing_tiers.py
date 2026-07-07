"""Spec roteamento-multi-provider — Etapa 2: cada nó pede o tier certo.

Blinda regressão de tier: um `get_llm(tier=...)` trocado por engano (ex.: narração
voltar a SMART, ou o router subir de CLASSIFY) quebra aqui. Barato e offline —
monkeypatch em `<módulo>.get_llm` (os nós importam o nome por valor) capturando o
tier; o delegate devolve o MockLLM da suíte para o nó completar.

Tabela (spec §Etapa 2):
  CLASSIFY: router, combat(parse/spawn), loot(TradeIntent), librarian
  FAST:     storyteller, combat(narração), npc, loot(narração), world_simulator
  SMART:    campaign_manager, archivist, character_creator
"""
from langchain_core.messages import HumanMessage

import world_utils as wu
from llm_setup import ModelTier


def _recorder(monkeypatch, module):
    """Patch <module>.get_llm; devolve a lista de tiers pedidos."""
    import llm_setup
    seen = []
    real = llm_setup.get_llm

    def rec(temperature=0.1, tier=ModelTier.FAST):
        seen.append(tier)
        return real(temperature=temperature, tier=tier)

    monkeypatch.setattr(module, "get_llm", rec)
    return seen


def _state(**ov):
    s = {
        "game_id": "tier_test",
        "narrative_summary": "O herói chegou a Nova Arcádia.",
        "archivist_last_run": 0,
        "chronicle": [],
        "messages": [HumanMessage(content="exploro o mercado")],
        "next": None,
        "player": {
            "name": "Aldric", "class_name": "Guerreiro", "race": "Humano",
            "hp": 30, "max_hp": 30, "mana": 5, "max_mana": 5,
            "stamina": 15, "max_stamina": 15, "gold": 50, "level": 1, "xp": 0,
            "attributes": {"str": 14, "dex": 10, "con": 12, "int": 8, "wis": 10, "cha": 10},
            "inventory": [{"id": "espada_curta", "qty": 1}],
            "known_abilities": ["ataque_basico"], "defense": 12, "attack_bonus": 3,
            "active_conditions": [], "ability_cooldowns": {},
        },
        "world": wu.starting_world("Nova Arcádia", 1),
        "campaign_plan": None, "needs_replan": True,
        "enemies": [], "party": [], "npcs": {},
        "active_npc_name": None, "combat_target": None, "loot_source": None, "combat": None,
    }
    s.update(ov)
    return s


_GOBLIN = {
    "id": "goblin_1", "name": "Goblin", "hp": 12, "max_hp": 12,
    "stamina": 5, "mana": 0, "defense": 11, "attack_mod": 2,
    "attributes": {"str": 8, "dex": 14, "con": 10, "int": 6, "wis": 8, "cha": 6},
    "abilities": [], "status": "ativo", "active_conditions": [],
    "attacks": [{"name": "Adaga", "bonus": 2, "damage": "1d4"}],
}


# ---------------------------------------------------------------------------
# CLASSIFY
# ---------------------------------------------------------------------------
def test_router_usa_classify(monkeypatch):
    import agents.router as router
    seen = _recorder(monkeypatch, router)
    router.dm_router_node(_state())
    assert seen == [ModelTier.CLASSIFY]


def test_librarian_usa_classify(monkeypatch):
    import agents.librarian as lib
    seen = _recorder(monkeypatch, lib)
    lib.find_existing_entity("Varg", "npc", ["npc_varg_acougueiro"])
    assert seen == [ModelTier.CLASSIFY]


# ---------------------------------------------------------------------------
# CLASSIFY + FAST (parse barato + narração)
# ---------------------------------------------------------------------------
def test_combat_usa_classify_e_fast_sem_smart(monkeypatch):
    import agents.combat as combat
    seen = _recorder(monkeypatch, combat)
    combat.combat_node(_state(
        messages=[HumanMessage(content="ataco o goblin com a espada")],
        enemies=[dict(_GOBLIN)]))
    assert ModelTier.CLASSIFY in seen, seen
    assert ModelTier.FAST in seen, seen
    assert ModelTier.SMART not in seen, seen


def test_loot_usa_classify_e_fast_sem_smart(monkeypatch):
    import agents.loot as loot
    seen = _recorder(monkeypatch, loot)
    loot.loot_node(_state(
        loot_source="SHOP",
        messages=[HumanMessage(content="compro uma poção de cura")]))
    assert ModelTier.CLASSIFY in seen, seen
    assert ModelTier.FAST in seen, seen
    assert ModelTier.SMART not in seen, seen


# ---------------------------------------------------------------------------
# FAST (narração / roleplay)
# ---------------------------------------------------------------------------
def test_storyteller_usa_fast(monkeypatch):
    import agents.storyteller as stt
    seen = _recorder(monkeypatch, stt)
    stt.storyteller_node(_state(
        campaign_plan={"beats": [{"description": "Explorar", "status": "pending"}],
                       "current_step": 0}))
    assert seen == [ModelTier.FAST], seen


def test_npc_usa_fast(monkeypatch):
    import agents.npc as npc
    seen = _recorder(monkeypatch, npc)
    vend = {
        "id": "npc_vendedor", "name": "Vendedor", "role": "Comerciante",
        "persona": "Enigmático", "location": "Nova Arcádia",
        "relationship": 5, "memory": [], "in_scene": True,
        "attributes": {"str": 8, "dex": 12, "con": 10, "int": 16, "wis": 14, "cha": 18},
        "combat_stats": {"hp": 8, "ac": 10, "attacks": []},
    }
    npc.npc_actor_node(_state(
        npcs={"Vendedor": vend}, active_npc_name="Vendedor",
        messages=[HumanMessage(content='falo com o Vendedor: "o que vende?"')]))
    assert seen, "npc_actor não chamou get_llm"
    assert all(t == ModelTier.FAST for t in seen), seen


def test_world_simulator_usa_fast(monkeypatch):
    import agents.world_simulator as ws
    seen = _recorder(monkeypatch, ws)
    st = _state()
    ws.simulate_world(st, st["world"], [], {}, periods=1)
    assert ModelTier.FAST in seen, seen
    assert ModelTier.SMART not in seen, seen


# ---------------------------------------------------------------------------
# SMART (coerência)
# ---------------------------------------------------------------------------
def test_campaign_manager_usa_smart(monkeypatch):
    import agents.campaign_manager as cm
    seen = _recorder(monkeypatch, cm)
    cm.campaign_manager_node(_state())
    assert ModelTier.SMART in seen, seen


def test_archivist_usa_smart(monkeypatch):
    import agents.archivist as arch
    seen = _recorder(monkeypatch, arch)
    arch.archive_node(_state(archive_due=True))
    assert ModelTier.SMART in seen, seen


def test_character_creator_usa_smart(monkeypatch):
    import character_creator as cc
    seen = _recorder(monkeypatch, cc)
    cc.create_player_character({
        "name": "Aldric", "class_name": "Guerreiro",
        "race": "Humano", "region": "Nova Arcádia"})
    assert ModelTier.SMART in seen, seen
