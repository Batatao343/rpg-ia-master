"""tests/test_conflito_orquestrador.py — orquestrador de rodada do conflito v2 (conflito-13, cutover Stage 1).

Cobre a peça de COMPOSIÇÃO que sobe do turno (conflict_turn) para a rodada inteira:
adaptador de ficha v4, IA de inimigo por perfil, fim de combate, Estado Terminal/
estabilização (R6=A), DoT em Vitalidade, AoO, evento do Abismo e reprodutibilidade.
"""
import random

import pytest

from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct


def _player(**kw):
    p = {"id": "player", "name": "Herói", "is_player": True, "class_name": "Sangromante",
         "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
         "attack_formula": "2d6", "entropy": 10, "max_entropy": 10, "abyss_charge": 0}
    p.update(kw)
    return orch.ensure_combat_sheet(p, is_player=True)


def _legacy_enemy(eid="gob_1", **kw):
    e = {"id": eid, "name": "Goblin", "type": "Minion", "hp": 12, "max_hp": 12, "ac": 11,
         "attributes": {"str": 10, "dex": 12, "con": 10, "int": 8, "wis": 8, "cha": 6}}
    e.update(kw)
    return orch.ensure_combat_sheet(e)


def _scene(*ids):
    scene = cs.new_scene()
    for i in ids:
        cs.place(scene, i)
    cs.freeze(scene)
    return scene


def _attack(target_id):
    return ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="attack", target_id=target_id))


# ------------------------------------------------------------------ adaptador
def test_ensure_sheet_converte_inimigo_legado_para_v4():
    e = _legacy_enemy()
    assert isinstance(e["virtudes"], dict) and set(e["virtudes"]) >= {"forca", "agilidade", "corpo"}
    assert e["max_vitalidade"] >= 1 and e["vitalidade"] == e["max_vitalidade"]
    assert set(e["ferimentos"]) == {"leve", "grave", "critico"}
    assert e["esquiva"] >= 10
    assert e["categoria"] == "lacaio"          # type=Minion → lacaio


def test_ensure_sheet_respeita_v4_curado():
    e = {"id": "e", "name": "Elite", "categoria": "elite",
         "virtudes": {"forca": 3, "agilidade": 2, "corpo": 4, "mente": 2, "carisma": 1},
         "vitalidade": 9, "max_vitalidade": 14}
    orch.ensure_combat_sheet(e)
    assert e["categoria"] == "elite"           # não sobrescreve
    assert e["vitalidade"] == 9                # respeita atual


def test_ensure_sheet_tipo_desconhecido_vira_padrao():
    e = orch.ensure_combat_sheet({"id": "x", "name": "?", "virtudes": {"corpo": 2}})
    assert e["categoria"] == "padrao"


# --------------------------------------------------------------- IA de inimigo
def test_enemy_declaration_ataque_default():
    e = _legacy_enemy()
    scene = _scene("player", "gob_1")
    actors = {"player": _player(), "gob_1": e}
    decl = orch.enemy_declaration(scene, "gob_1", actors, {"hero": ["player"], "enemy": ["gob_1"]},
                                  rng=random.Random(1))
    assert decl.acao.kind in ("attack", "card")
    assert decl.acao.target_id == "player"


def test_enemy_declaration_rendicao_por_perfil():
    e = _legacy_enemy(tactical_profile={"priorities": [
        {"trigger": "sempre", "tipo": "obrigatorio", "action_hint": "Rende-se e implora pela vida."}]})
    scene = _scene("player", "gob_1")
    actors = {"player": _player(), "gob_1": e}
    decl = orch.enemy_declaration(scene, "gob_1", actors, {"hero": ["player"], "enemy": ["gob_1"]},
                                  rng=random.Random(1))
    assert e.get("surrendered") is True
    assert decl.acao.kind == "pass"


def test_enemy_declaration_fuga_por_perfil():
    e = _legacy_enemy(tactical_profile={"priorities": [
        {"trigger": "sempre", "tipo": "obrigatorio", "action_hint": "Foge do combate."}]})
    scene = _scene("player", "gob_1")
    actors = {"player": _player(), "gob_1": e}
    decl = orch.enemy_declaration(scene, "gob_1", actors, {"hero": ["player"], "enemy": ["gob_1"]},
                                  rng=random.Random(1))
    assert decl.acao.kind == "move" and decl.acao.direction == "afastar"


# --------------------------------------------------------------- rodada / fim
def test_lacaio_cai_com_ferimento_e_combate_encerra():
    player, e = _player(), _legacy_enemy()
    scene = _scene("player", "gob_1")
    actors = {"player": player, "gob_1": e}
    sides = {"hero": ["player"], "enemy": ["gob_1"]}
    rng = random.Random(7)
    ended = False
    for _ in range(12):
        out = orch.run_round(scene, actors, sides, {"player": player},
                             declarations={"player": _attack("gob_1")}, rng=rng)
        if out["ended"]:
            ended = True
            assert "gob_1" in out["deaths"] or e.get("status") == "morto"
            break
    assert ended


def test_chefe_sem_aliado_morre_no_estado_terminal():
    # Corpo 0 = 1 espaço de Crítico; um golpe pesado (excedente alto) o preenche,
    # dispara Estado Terminal, e sem aliado capaz o Chefe morre (07 R6=A).
    player = _player(attack_formula="6d8")
    chefe = orch.ensure_combat_sheet({
        "id": "boss", "name": "Chefe", "categoria": "chefe",
        "virtudes": {"forca": 3, "agilidade": 1, "corpo": 0, "mente": 2, "carisma": 2},
        "vitalidade": 1, "max_vitalidade": 6})
    scene = _scene("player", "boss")
    actors = {"player": player, "boss": chefe}
    sides = {"hero": ["player"], "enemy": ["boss"]}
    rng = random.Random(3)
    for _ in range(10):
        orch.run_round(scene, actors, sides, {"player": player},
                       declarations={"player": _attack("boss")}, rng=rng)
        if chefe.get("dead"):
            break
    assert chefe.get("dead") is True           # sem aliado capaz → morre no Terminal


def test_jogador_morre_marca_player_dead():
    # Corpo 0 = 1 espaço de Crítico; um Ogro pesado o preenche → Terminal → sem
    # aliado → morte REAL → player_dead (o nó de combate abre a tela de morte).
    player = _player(virtudes={"forca": 4, "agilidade": 3, "corpo": 0, "mente": 1, "carisma": 1},
                     vitalidade=1, max_vitalidade=6)
    ogre = orch.ensure_combat_sheet({
        "id": "ogre", "name": "Ogro", "categoria": "elite",
        "virtudes": {"forca": 5, "agilidade": 2, "corpo": 4, "mente": 1, "carisma": 1},
        "attack_formula": "6d8"})
    scene = _scene("player", "ogre")
    actors = {"player": player, "ogre": ogre}
    sides = {"hero": ["player"], "enemy": ["ogre"]}
    rng = random.Random(11)
    dead = False
    for _ in range(15):
        out = orch.run_round(scene, actors, sides, {"player": player},
                             declarations={"player": ct.TurnDeclaration(
                                 actor_id="player", acao=ct.TurnStep(kind="pass"))}, rng=rng)
        if out.get("player_dead"):
            dead = True
            break
    assert dead and player.get("dead") is True


# ------------------------------------------------------------------- DoT / AoO
def test_dot_v4_reduz_vitalidade_e_gera_ferimento():
    e = _legacy_enemy(vitalidade=2, max_vitalidade=10)
    out = {"logs": []}
    e["active_conditions"] = [{"name": "Sangramento", "dot": 5, "duration": 2, "source": "cortante"}]
    orch._tick_conditions_v4(e, out)
    assert e["vitalidade"] == 0                # 2 - 5, piso 0
    assert orch._has_any_wound(e)              # excedente 3 → Ferimento


def test_aoo_ao_abandonar_engajamento():
    player = _player()
    e = _legacy_enemy(virtudes={"forca": 3, "agilidade": 2, "corpo": 3, "mente": 1, "carisma": 1})
    scene = _scene("player", "gob_1")
    cs.engage(scene, "player", "gob_1", spend=False)   # engajados
    actors = {"player": player, "gob_1": e}
    sides = {"hero": ["player"], "enemy": ["gob_1"]}
    out = {"logs": [], "deaths": [], "terminal": []}
    orch._resolve_opportunity_attacks(scene, "player", actors, sides, out, random.Random(2))
    assert any("Oportunidade" in l for l in out["logs"])


# ------------------------------------------------------------ reprodutibilidade
def _run_fixed(seed):
    random.seed(seed)   # dano usa `combat_mechanics.roll_dice_numeric` (random global);
    player, e = _player(), _legacy_enemy()   # reprodutibilidade = seed global (harness já faz)
    scene = _scene("player", "gob_1")
    actors = {"player": player, "gob_1": e}
    sides = {"hero": ["player"], "enemy": ["gob_1"]}
    rng = random.Random(seed)
    logs = []
    for _ in range(4):
        out = orch.run_round(scene, actors, sides, {"player": player},
                             declarations={"player": _attack("gob_1")}, rng=rng)
        logs += out["logs"]
        if out["ended"]:
            break
    return logs


def test_reprodutibilidade_mesma_seed_mesmo_resultado():
    assert _run_fixed(123) == _run_fixed(123)


# ------------------------------------------------------------------- Abismo
def test_abismo_carrega_com_cargas_suficientes():
    player = _player(abyss_charge=3)
    e = _legacy_enemy()
    scene = _scene("player", "gob_1")
    scene["objects"] = [{"id": "altar", "name": "Altar rachado"}]
    prepared = [{"id": "fissura", "gatilho": "sempre", "prioridade": 1,
                 "cargas_necessarias": 2, "usos_permitidos": 1, "base_na_cena": "altar",
                 "effect": {"kind": "apply_condition",
                            "params": {"target": "gob_1", "condition": "exposto", "duration": 1}}}]
    actors = {"player": player, "gob_1": e}
    sides = {"hero": ["player"], "enemy": ["gob_1"]}
    out = orch.run_round(scene, actors, sides, {"player": player},
                         declarations={"player": _attack("gob_1")},
                         prepared_abyss=prepared, rng=random.Random(5))
    assert any("ABISMO" in l for l in out["logs"])
    assert player["abyss_charge"] == 1         # 3 - 2 Cargas gastas
