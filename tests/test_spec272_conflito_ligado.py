"""SPEC-272 — capacidades do conflito que só os testes usavam, agora ligadas ao motor.

(a) Revelação de Cartas do inimigo + bestiário persistente (SPEC-069 R8) e
(b) Teste de Sorte dos companheiros na fuga (SPEC-070 R5).
"""
import random

from langchain_core.messages import HumanMessage

from agents import combat
from agents.combat import _attempt_flee
from services import bestiary_knowledge as bk
from services import conflict_orchestrator as orch


class _MaxRng:
    def randint(self, a, b):
        return b


def _player():
    return {"name": "Valen", "conscious": True, "virtudes": {"agilidade": 0}}


def _enemy():
    return {"id": "lobo", "name": "Lobo", "status": "ativo",
            "pursuit_policy": "persegue", "virtudes": {"agilidade": 0}}


# --- (b) Teste de Sorte na fuga ----------------------------------------------
def test_fuga_com_companheiro_rola_sorte_e_ganha_vantagem():
    _, _, state = _attempt_flee(
        {"positions": {"player": {"distance_state": "proximo"}}}, _player(),
        [_enemy()], {"hero": ["player"], "ally": ["bors"], "enemy": ["lobo"]},
        _MaxRng())
    assert state["_last"]["advantage"] == 1          # 1d10=10 → Ajuda → Vantagem


def test_fuga_sozinho_nao_rola_sorte():
    _, _, state = _attempt_flee(
        {"positions": {"player": {"distance_state": "proximo"}}}, _player(),
        [_enemy()], {"hero": ["player"], "ally": [], "enemy": ["lobo"]},
        _MaxRng())
    assert state["_last"]["advantage"] == 0


# --- (a) Revelação de Cartas do inimigo --------------------------------------
def test_carta_usada_pelo_inimigo_fica_revelada_e_persiste(monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    enemy = {"id": "lobo_1", "archetype_id": "lobo",
             "enemy_card_usage": {"bst_toque_gelido": {"turno": 1}}}
    combat._sync_enemy_knowledge([enemy])
    assert enemy["revealed_cards"] == ["bst_toque_gelido"]

    novo = {"id": "lobo_2", "archetype_id": "lobo"}
    combat._sync_enemy_knowledge([novo], load_persisted=True)
    assert novo["revealed_cards"] == ["bst_toque_gelido"]


def test_perfil_nao_legacy_revela_so_no_combate(monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")
    enemy = {"id": "lobo_1", "archetype_id": "lobo",
             "enemy_card_usage": {"bst_toque_gelido": {"turno": 1}}}
    combat._sync_enemy_knowledge([enemy])
    assert enemy["revealed_cards"] == ["bst_toque_gelido"]
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    assert bk._load_all() == {}                       # nada vazou p/ escopo compartilhado


def test_instancia_de_inimigo_carrega_id_do_arquetipo():
    tpl = {"id": "lobo", "name": "Lobo"}
    inst = combat._instances(tpl, 2, {})
    assert [i["archetype_id"] for i in inst] == ["lobo", "lobo"]


def test_combat_node_revela_carta_usada_na_rodada(monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    random.seed(3)
    player = {"name": "Kael", "level": 2, "inventory": [], "known_abilities": [],
              "vitalidade": 30, "max_vitalidade": 30, "hp": 30, "max_hp": 30,
              "virtudes": {"forca": 2, "agilidade": 2}, "conscious": True}
    enemy = {"id": "g1", "archetype_id": "goblin", "name": "Goblin 1", "hp": 400,
             "max_hp": 400, "defense": 5, "status": "ativo",
             "attributes": {"dex": 12, "con": 10},
             "attacks": [{"name": "Adaga", "bonus": 0, "damage": "1d2"}],
             "active_conditions": []}
    world = {"current_location": "P", "current_location_id": "pantano_melancolia",
             "turn_count": 3, "danger_level": 2, "visited": ["pantano_melancolia"]}
    state = {"game_id": "a", "messages": [HumanMessage(content="Ataco o Goblin 1")],
             "player": player, "enemies": [enemy], "combat": {"active": True},
             "world": world, "party": [], "npcs": {}}
    real = orch.run_round

    def using_card(scene, actors, *a, **k):
        res = real(scene, actors, *a, **k)
        actors["g1"].setdefault("enemy_card_usage", {})["bst_toque_gelido"] = {"turno": 1}
        return res

    monkeypatch.setattr(orch, "run_round", using_card)
    out = combat.combat_node(state)
    g1 = next(e for e in out["enemies"] if e["id"] == "g1")
    assert "bst_toque_gelido" in g1["revealed_cards"]
    assert "bst_toque_gelido" in bk._load_all()["goblin"]["revealed_cards"]


def test_instancia_sem_archetype_id_usa_id_base_no_overlay(monkeypatch):
    """Revisão: reforço do orçamento (`fill_encounter`) e saves antigos chegam sem
    `archetype_id`; a chave persistida é o id do bestiário, não o da instância."""
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    enemy = {"id": "goblin_3", "enemy_card_usage": {"bst_toque_gelido": {"turno": 1}}}
    combat._sync_enemy_knowledge([enemy])
    data = bk._load_all()
    assert "goblin" in data and "goblin_3" not in data
    assert enemy["archetype_id"] == "goblin"
