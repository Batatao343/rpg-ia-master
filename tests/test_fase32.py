"""
Suíte da Fase 3.2 — Conhecimento revelável (Codex do jogador + bestiário progressivo).
Spec: specs/fase-3.2-conhecimento-revelavel.md. 100% offline, zero LLM.

Usa ids reais de data/bestiary.json e data/codex/ (evita fixtures inventadas que
mascarariam bug de id):
  criatura:  enemy_rato_peste_anel_lama (regions: [nova_arcadia])
  location:  nova_arcadia (codex público)
  npc:       npc_valerius (codex público)
  faction:   legiao_ferro (codex público)
  segredo:   secret_valerius_lich_mas_nao_forma_que_rumores_sugerem (codex secret)
"""

import copy
import os
import random

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

import gamedata
import world_utils as wu
from services import codex_loader as cl
from services import discovery as disc
from services import graph_resolver as gr

RATO = "enemy_rato_peste_anel_lama"


def _base_state(messages=None):
    return {
        "game_id": "pytest_fase32", "narrative_summary": "", "archivist_last_run": 0,
        "messages": messages or [], "next": None,
        "player": {
            "name": "Tester", "class_name": "Guerreiro", "race": "Humano",
            "hp": 30, "max_hp": 30, "mana": 10, "max_mana": 10,
            "stamina": 10, "max_stamina": 10, "gold": 50, "level": 1, "xp": 0,
            "attributes": {"str": 12, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "inventory": [], "known_abilities": [], "defense": 10, "attack_bonus": 0,
            "active_conditions": [], "ability_cooldowns": {},
        },
        "world": {"current_location": "Nova Arcádia", "current_location_id": "nova_arcadia",
                   "time_of_day": "Dia", "turn_count": 0, "weather": "Neutro",
                   "quest_plan": [], "danger_level": 1, "visited": []},
        "campaign_plan": {}, "needs_replan": False, "enemies": [], "party": [],
        "npcs": {}, "active_npc_name": None, "factions": [], "faction_intel": {},
        "bestiary_knowledge": {}, "combat_target": None, "loot_source": None, "combat": {},
    }


def _combat_player():
    return {"name": "Kael", "class_name": "Guerreiro", "hp": 30, "max_hp": 30,
            "stamina": 12, "max_stamina": 12, "mana": 0,
            "attributes": {"str": 16, "dex": 14, "con": 12},
            "inventory": [], "attack_bonus": 0,
            "active_conditions": [], "ability_cooldowns": {}}


@pytest.fixture(autouse=True)
def _fresh_caches():
    gr.clear_cache()
    cl.clear_codex_index_cache()
    yield
    gr.clear_cache()
    cl.clear_codex_index_cache()


# ---------------------------------------------------------------------------
# Etapa 1 — contadores + graus puros
# ---------------------------------------------------------------------------

def test_rato_existe_no_bestiario():
    assert RATO in gamedata.BESTIARY  # sanity: fixture real, não inventada


def test_normalize_id_instancia():
    assert disc.normalize_bestiary_id({"id": f"{RATO}_2"}) == RATO
    assert disc.normalize_bestiary_id({"id": f"{RATO}_10"}) == RATO
    assert disc.normalize_bestiary_id({"id": RATO}) == RATO


def test_normalize_id_desconhecido_vazio():
    assert disc.normalize_bestiary_id({"id": "enemy_nao_existe_123"}) == ""


def test_record_encounter_uma_vez_por_combate():
    enemies = [{"id": f"{RATO}_1"}, {"id": f"{RATO}_2"}, {"id": f"{RATO}_3"}]
    bk = disc.record_encounter({}, enemies, turn=5)
    assert bk[RATO]["seen"] == 1
    assert bk[RATO]["fought"] == 1
    assert bk[RATO]["first_seen_turn"] == 5


def test_record_kills_conta_instancias():
    dead = [{"id": f"{RATO}_1"}, {"id": f"{RATO}_2"}]
    bk = disc.record_kills({}, dead, turn=6)
    assert bk[RATO]["defeated"] == 2


def test_record_rumor_so_seen():
    bk = disc.record_rumor({}, RATO, turn=3)
    assert bk[RATO]["seen"] == 1
    assert bk[RATO].get("fought", 0) == 0


def test_tier_progressao():
    assert disc.knowledge_tier({"seen": 1}) == 1
    assert disc.knowledge_tier({"seen": 1, "fought": 1}) == 2
    assert disc.knowledge_tier({"seen": 1, "fought": 1, "defeated": 3}) == 3
    assert disc.knowledge_tier({"seen": 1, "fought": 1, "defeated": 7}) == 4
    assert disc.knowledge_tier({}) == 0


def test_funcoes_puras_nao_mutam_original():
    original = {}
    frozen = copy.deepcopy(original)
    disc.record_encounter(original, [{"id": RATO}], turn=1)
    assert original == frozen


# ---------------------------------------------------------------------------
# Etapa 2 — revelação por grau (bestiary_view)
# ---------------------------------------------------------------------------

def test_view_grau1_sem_stats():
    bk = {RATO: {"seen": 1}}
    view = disc.bestiary_view(bk)
    assert len(view) == 1
    entry = view[0]
    assert entry["tier"] == 1
    assert "max_hp" not in entry
    assert "attacks" not in entry
    assert "loot" not in entry


def test_view_grau3_ataques_sem_dano():
    bk = {RATO: {"seen": 1, "fought": 1, "defeated": 3}}
    entry = disc.bestiary_view(bk)[0]
    assert entry["tier"] == 3
    assert entry["attacks"] == ["Mordida Infecciosa"]
    assert "loot" not in entry


def test_view_grau4_completo():
    bk = {RATO: {"seen": 1, "fought": 1, "defeated": 7}}
    entry = disc.bestiary_view(bk)[0]
    assert entry["tier"] == 4
    assert entry["attacks"][0]["damage"]
    assert "behavior" in entry
    assert "loot" in entry


def test_criatura_desconhecida_fora_da_view():
    bk = {RATO: {"seen": 1}, "enemy_nao_existe": {"seen": 1}}
    view = disc.bestiary_view(bk)
    assert len(view) == 1
    assert view[0]["id"] == RATO


def test_grau_zero_nao_aparece():
    bk = {RATO: {}}
    assert disc.bestiary_view(bk) == []


# ---------------------------------------------------------------------------
# Etapa 4 — codex_index / codex_body (services/codex_loader.py)
# ---------------------------------------------------------------------------

def test_codex_index_acha_id_conhecido():
    idx = cl.codex_index()
    assert "nova_arcadia" in idx
    assert "npc_valerius" in idx


def test_codex_body_public_only():
    body = cl.codex_body("nova_arcadia")
    assert "Arcádia" in body or "cinzas" in body.lower() or len(body) > 0


def test_codex_body_hidden_vazio():
    secret_id = "secret_valerius_lich_mas_nao_forma_que_rumores_sugerem"
    assert cl.codex_body(secret_id) == ""


def test_codex_body_id_inexistente_vazio():
    assert cl.codex_body("id_que_nao_existe_em_lugar_nenhum") == ""


def test_codex_body_none_vazio():
    assert cl.codex_body(None) == ""


# ---------------------------------------------------------------------------
# Etapa 3 — hooks no combate + threat_alerts
# ---------------------------------------------------------------------------

def test_combate_registra_encounter(monkeypatch):
    import agents.combat as combat

    def fake_spawn(messages, target_hint, state=None):
        enemy = dict(gamedata.BESTIARY[RATO])
        enemy["id"] = f"{RATO}_1"
        enemy["status"] = "ativo"
        return [enemy], "Ratos surgem das sombras!"

    monkeypatch.setattr(combat, "_spawn_enemies_integrated", fake_spawn)
    random.seed(1)
    state = _base_state(messages=[
        HumanMessage(content="viajo para o beco"),
        SystemMessage(content="COMBAT START. Ratos surgem!"),
    ])
    state["player"] = _combat_player()
    state["enemies"] = []
    state["combat"] = {}
    state["combat_target"] = "Rato da Peste (Anel de Lama)"

    out = combat.combat_node(state)
    bk = out["bestiary_knowledge"]
    assert bk[RATO]["seen"] == 1
    assert bk[RATO]["fought"] == 1
    assert bk[RATO].get("defeated", 0) == 0


def test_morte_registra_defeated(monkeypatch):
    import agents.combat as combat

    def fake_kill(player, enemies, action, abilities):
        enemies[0]["status"] = "morto"
        enemies[0]["hp"] = 0
        return ["Golpe fatal derruba o inimigo."]

    monkeypatch.setattr(combat.cm, "resolve_player_action", fake_kill)
    random.seed(2)
    enemy = dict(gamedata.BESTIARY[RATO])
    enemy["id"] = f"{RATO}_1"
    enemy["status"] = "ativo"
    enemy["defense"] = enemy.get("ac", 10)
    state = _base_state(messages=[HumanMessage(content="ataco o rato")])
    state["player"] = _combat_player()
    state["enemies"] = [enemy]
    state["combat"] = {}

    out = combat.combat_node(state)
    bk = out["bestiary_knowledge"]
    assert bk[RATO]["defeated"] == 1


def test_alerta_com_enemy_id_gera_rumor_sem_fought():
    world = wu.ensure_world({"current_location_id": "nova_arcadia"})
    world = wu.register_flee_alert(world, "Rato da Peste (Anel de Lama)", turn=5, enemy_id=RATO)
    enc = wu.check_encounter(world, gamedata.seed_factions(), {}, turn=7)
    assert enc and enc["reason"] == "reinforcements"
    assert enc["enemy_id"] == RATO

    bk = disc.record_rumor({}, enc["enemy_id"], turn=7)
    assert bk[RATO]["seen"] == 1
    assert bk[RATO].get("fought", 0) == 0
    assert disc.knowledge_tier(bk[RATO]) == 1  # "Rumores" — não "Encontrada"


def test_register_flee_alert_sem_enemy_id_retrocompativel():
    # chamada antiga (sem enemy_id) continua funcionando — enemy_id vazio no alerta.
    world = wu.ensure_world({"current_location_id": "pradaria_ruinas"})
    world = wu.register_flee_alert(world, "Nômade Canibal 2", faction_id="bandos_nomades", turn=5)
    assert world["threat_alerts"][0]["enemy_id"] == ""


def test_pick_encounter_enemy_by_faction_carrega_enemy_id():
    world = {"current_location_id": ""}
    loc = {"region_id": "", "region": "brekmar"}
    entry = wu.pick_encounter_enemy(loc, danger=3, turn=0, faction_id="legiao_ferro")
    assert entry and entry["id"] == "enemy_soldado_legiao_ferro"


# ---------------------------------------------------------------------------
# Etapa 4 — codex agregado + endpoint
# ---------------------------------------------------------------------------

def test_codex_index_cacheia():
    idx1 = cl.codex_index()
    idx2 = cl.codex_index()
    assert idx1 is idx2  # mesmo objeto — não varreu o disco de novo


def test_player_codex_deriva_fontes():
    state = _base_state()
    state["world"]["visited"] = ["nova_arcadia"]
    state["factions"] = [{"id": "legiao_ferro", "name": "Legião de Ferro",
                          "goal": "Unificar Valoria sob a lei", "defeated": False}]
    state["faction_intel"] = {"legiao_ferro": {"known": True, "knows_goal": True}}
    state["npcs"] = {"Lorde Protetor Valerius": {"name": "Lorde Protetor Valerius",
                                                  "role": "governante", "location": "nova_arcadia"}}
    state["bestiary_knowledge"] = {RATO: {"seen": 1, "fought": 1}}
    state["world_projection"] = {"revealed_facts": {
        "e1": {"entity_id": "npc_valerius", "fact": "É um lich", "revealed_at_turn": 4},
    }}

    codex = disc.player_codex(state)
    assert {loc["id"] for loc in codex["locations"]} == {"nova_arcadia"}
    assert codex["locations"][0]["body"]  # doc público -> corpo não vazio
    assert {f["id"] for f in codex["factions"]} == {"legiao_ferro"}
    assert codex["factions"][0]["goal"] == "Unificar Valoria sob a lei"
    assert {c["name"] for c in codex["characters"]} == {"Lorde Protetor Valerius"}
    assert codex["characters"][0]["body"]  # match por nome achou npc_valerius.md (público)
    assert {c["id"] for c in codex["creatures"]} == {RATO}
    assert codex["secrets"][0]["fact"] == "É um lich"


def test_faction_goal_nao_vaza_sem_knows_goal():
    state = _base_state()
    state["factions"] = [{"id": "mao_sombria", "name": "Mão Sombria",
                          "goal": "Segredo não revelado", "defeated": False}]
    state["faction_intel"] = {"mao_sombria": {"known": True, "knows_goal": False}}
    codex = disc.player_codex(state)
    assert codex["factions"][0]["goal"] == ""
    assert codex["factions"][0]["knows_goal"] is False


def test_faccao_desconhecida_fora_do_codex():
    state = _base_state()
    state["factions"] = [{"id": "filhos_chama_azul", "name": "Filhos da Chama Azul",
                          "goal": "...", "defeated": False}]
    state["faction_intel"] = {}  # jogador nunca ouviu falar
    codex = disc.player_codex(state)
    assert codex["factions"] == []


def test_local_nao_visitado_fora_do_codex():
    state = _base_state()
    state["world"]["visited"] = []
    assert disc.player_codex(state)["locations"] == []


def test_endpoint_codex():
    # /game/codex monta o caminho como /game/state (f"saves/{game_id}.json", literal,
    # não via persistence.SAVES_DIR) — grava/limpa no saves/ real do projeto.
    from fastapi.testclient import TestClient

    import api
    import persistence

    import uuid
    game_id = str(uuid.uuid4())  # Fase 10: game_id da API precisa ser UUID
    save_path = os.path.join(persistence.SAVES_DIR, f"{game_id}.json")
    state = _base_state()
    state["game_id"] = game_id
    state["world"]["visited"] = ["nova_arcadia"]
    state["bestiary_knowledge"] = {RATO: {"seen": 1, "fought": 1, "defeated": 3}}
    assert persistence.save_game_state(state)
    try:
        client = TestClient(api.app)
        resp = client.get("/game/codex", params={"game_id": game_id})
        assert resp.status_code == 200
        body = resp.json()
        assert {loc["id"] for loc in body["locations"]} == {"nova_arcadia"}
        assert body["creatures"][0]["tier_name"] == "Estudada"
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)


def test_endpoint_codex_game_id_inexistente_404():
    import uuid
    from fastapi.testclient import TestClient

    import api
    client = TestClient(api.app)
    # UUID válido sem save no disco -> 404 (não-UUID vira 400 — Fase 10)
    resp = client.get("/game/codex", params={"game_id": str(uuid.uuid4())})
    assert resp.status_code == 404
