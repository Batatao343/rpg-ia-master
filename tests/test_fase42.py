"""
Fase 4.2 — Buffs, passivas e condições mecânicas de verdade.
Spec: specs/fase-4.2-buffs-mecanicos.md. 100% offline, motor puro.
"""
import copy

import pytest

import combat_mechanics as cm
from gamedata import ABILITIES


def make_player(**over):
    p = {
        "name": "Testo", "class_name": "", "race": "Humano",
        "level": 3, "xp": 0,
        "hp": 30, "max_hp": 30, "mana": 20, "max_mana": 20,
        "stamina": 20, "max_stamina": 20,
        "gold": 0, "attributes": {"str": 14, "dex": 12, "con": 14,
                                  "int": 12, "wis": 12, "cha": 12},
        "inventory": [], "known_abilities": ["ataque_basico"],
        "defense": 12, "attack_bonus": 0,
        "active_conditions": [], "ability_cooldowns": {},
        "pending_choices": [],
    }
    p.update(over)
    return p


def make_enemy(**over):
    e = {
        "id": "enemy_x_1", "name": "Capanga", "type": "Minion",
        "hp": 30, "max_hp": 30, "defense": 5, "status": "ativo",
        "attributes": {"str": 10, "dex": 10, "con": 10},
        "active_conditions": [],
        "attacks": [{"name": "Golpe", "type": "melee", "bonus": 20, "damage": "1d1"}],
        "stamina": 0, "mana": 0, "attack_mod": 0,
        "behavior": {"profile": "feroz"},
    }
    e.update(over)
    return e


def buff_cond(stat, delta, dur=3, name="Buff"):
    return {"name": name, "dot": 0, "duration": dur, "source": "t",
            "stat": stat, "delta": delta}


def control_cond(kind, dur=2):
    return {"name": kind, "dot": 0, "duration": dur, "source": "t", "control": kind}


# ---------------------------------------------------------------------------
# Etapa 1 — condition_modifiers lidos em dano/AC/acerto/save
# ---------------------------------------------------------------------------

def test_condition_modifiers_soma():
    e = {"active_conditions": [buff_cond("damage", 5), buff_cond("damage", 2),
                               buff_cond("ac", -3), control_cond("fear")]}
    mods = cm.condition_modifiers(e)
    assert mods["damage"] == 7
    assert mods["ac"] == -3
    assert mods["attack"] == -2  # fear embutido


def test_condicao_legada_so_dot_segue_ok():
    e = {"active_conditions": [{"name": "Sangramento", "dot": 3, "duration": 2, "source": "x"}]}
    assert cm.condition_modifiers(e) == {"damage": 0, "ac": 0, "attack": 0, "save": 0}
    logs = cm.tick_conditions(dict(e, hp=10, name="Alvo", status="ativo"))
    assert any("Sangramento" in l for l in logs)


def test_buff_dano_aplica_no_numero(monkeypatch):
    """'+5 Dano' muda o dano observável (spec: critério da fase)."""
    monkeypatch.setattr(cm.random, "randint", lambda a, b: b if b == 20 else 1)
    player = make_player(active_conditions=[buff_cond("damage", 5)])
    base = make_player()
    enemy1, enemy2 = make_enemy(), make_enemy()
    act = {"ability_id": "ataque_basico", "target": "Capanga", "is_allowed": True}
    cm.resolve_player_action(base, [enemy1], dict(act), ABILITIES)
    cm.resolve_player_action(player, [enemy2], dict(act), ABILITIES)
    dano_sem = enemy1["max_hp"] - enemy1["hp"]
    dano_com = enemy2["max_hp"] - enemy2["hp"]
    assert dano_com == dano_sem + 5


def test_debuff_ac_no_inimigo_facilita_acerto():
    e = make_enemy(defense=15, active_conditions=[buff_cond("ac", -4)])
    # AC efetiva = 15 - 4 = 11 (validada via condition_modifiers no ataque)
    assert cm.condition_modifiers(e)["ac"] == -4


def test_ac_do_player_soma_buff():
    p = make_player(active_conditions=[buff_cond("ac", 3)])
    assert cm.compute_player_combat_stats(p)["ac"] == \
        cm.compute_player_combat_stats(make_player())["ac"] + 3


def test_save_do_alvo_soma_condicao(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 10)
    db = {"golpe_com_save": {"name": "Golpe", "cost": 0, "resource_type": "Nenhum",
                             "damage_formula": "2d6", "damage_type": "Físico",
                             "conditions": [], "save_stat": "con", "effects": []}}
    p = make_player()
    # save buff +10 garante resistir (dc = 10+attack; roll 10+0+10 >= dc)
    e = make_enemy(active_conditions=[buff_cond("save", 10)])
    act = {"ability_id": "golpe_com_save", "target": "Capanga", "is_allowed": True}
    logs = cm.resolve_player_action(p, [e], act, db)
    assert any("resiste" in l for l in logs)


# ---------------------------------------------------------------------------
# Etapa 2 — effects tipado -> condição (precedência sobre texto)
# ---------------------------------------------------------------------------

def test_effects_buff_vira_condicao():
    db = {"pacto": {"name": "Pacto", "cost": 0, "resource_type": "Nenhum",
                    "damage_formula": "0", "damage_type": "Físico",
                    "conditions": ["Custa 5 HP"], "save_stat": None,
                    "effects": [{"kind": "buff", "stat": "damage", "delta": 3, "duration": 3},
                                {"kind": "buff", "stat": "attack", "delta": 2, "duration": 3}]}}
    p = make_player(hp=30)
    e = make_enemy()
    act = {"ability_id": "pacto", "target": "Capanga", "is_allowed": True}
    cm.resolve_player_action(p, [e], act, db)
    stats = [c.get("stat") for c in p["active_conditions"]]
    assert "damage" in stats and "attack" in stats
    assert p["hp"] == 25  # "Custa 5 HP"
    # precedência: as strings textuais NÃO viraram condições duplicadas
    assert len(p["active_conditions"]) == 2


def test_effects_control_vira_condicao(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 1)  # save falha
    db = {"chantagem": {"name": "Chantagem", "cost": 0, "resource_type": "Nenhum",
                        "damage_formula": "0", "damage_type": "Físico",
                        "conditions": [], "save_stat": "wis",
                        "effects": [{"kind": "debuff", "stat": "attack", "delta": -3, "duration": 2}]}}
    p = make_player()
    e = make_enemy()
    act = {"ability_id": "chantagem", "target": "Capanga", "is_allowed": True}
    logs = cm.resolve_player_action(p, [e], act, db)
    assert any(c.get("stat") == "attack" and c.get("delta") == -3
               for c in e["active_conditions"]), (logs, e["active_conditions"])


def test_effects_dot_sem_duplicar_texto(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: b if b == 20 else 1)
    db = {"flecha": {"name": "Flecha", "cost": 0, "resource_type": "Nenhum",
                     "damage_formula": "1d6", "damage_type": "Físico",
                     "conditions": ["Sangramento (2 dano/turno)"], "save_stat": None,
                     "effects": [{"kind": "dot", "delta": 2, "duration": 3}]}}
    p = make_player()
    e = make_enemy(hp=100, max_hp=100)
    act = {"ability_id": "flecha", "target": "Capanga", "is_allowed": True}
    cm.resolve_player_action(p, [e], act, db)
    dots = [c for c in e["active_conditions"] if c.get("dot")]
    assert len(dots) == 1  # effects aplicou; string não duplicou


def test_fallback_parser_string_legado():
    cond = cm.parse_condition("+5 Dano por 3 turnos", source="Juramento")
    assert cond["stat"] == "damage" and cond["delta"] == 5 and cond["duration"] == 3
    cond2 = cm.parse_condition("-2 de acerto por 2 turnos", source="x")
    assert cond2["stat"] == "attack" and cond2["delta"] == -2
    cond3 = cm.parse_condition("Atordoado (1 turno)", source="x")
    assert cond3["control"] == "stun"


# ---------------------------------------------------------------------------
# Etapa 3 — controle: stun / root / fear
# ---------------------------------------------------------------------------

def test_stun_inimigo_pula_turno():
    e = make_enemy(active_conditions=[control_cond("stun", 1)])
    p = make_player()
    logs = cm.resolve_enemy_turn(e, p)
    assert any("ATORDOADO" in l for l in logs)
    assert p["hp"] == 30  # não atacou


def test_root_bloqueia_fuga_do_inimigo():
    e = make_enemy(behavior={"profile": "covarde", "flee_below": 0.9},
                   hp=1, max_hp=30,
                   active_conditions=[control_cond("root", 2)])
    log = cm.check_morale(e)
    assert log and "ENREDADO" in log
    assert e["status"] == "ativo"  # não fugiu


def test_fear_penaliza_acerto_do_inimigo(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 10)
    p = make_player()  # AC = 10 + 1 (dex 12) = 11
    ok = make_enemy(attacks=[{"name": "G", "type": "melee", "bonus": 1, "damage": "1d1"}])
    feared = make_enemy(attacks=[{"name": "G", "type": "melee", "bonus": 1, "damage": "1d1"}],
                        active_conditions=[control_cond("fear")])
    hit_logs = cm.resolve_enemy_turn(ok, make_player())      # 10+1=11 vs 11: acerta
    miss_logs = cm.resolve_enemy_turn(feared, p)             # 10+1-2=9 vs 11: erra
    assert any("acerta" in l or "CRÍTICO" in l for l in hit_logs)
    assert any("erra" in l for l in miss_logs)


def test_resist_racial_anula_controle():
    e = make_enemy(condition_resists=["medo"])
    log = cm.apply_condition(e, control_cond("fear") | {"name": "Medo"})
    assert "resiste" in log
    assert not e["active_conditions"]


# ---------------------------------------------------------------------------
# Etapa 4 — passivas data-driven: as passivas por-classe da Fase 4.2 (Muralha
# Humana, hp_as_mana, Triagem, etc.) foram SUBSTITUÍDAS pelos gatilhos de
# Entropia + consequências de Carga das 5 Posturas (spec refatoracao-sistema-
# classes; cobertura em tests/test_classes_refactor.py). A máquina genérica de
# passive_effects segue no motor (inerte: classes novas têm passive_effects []).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Compat: saves antigos (condição sem campos novos)
# ---------------------------------------------------------------------------

def test_save_antigo_condicao_sem_campos_novos():
    e = {"name": "X", "hp": 10, "status": "ativo",
         "active_conditions": [{"name": "Veneno", "dot": 2, "duration": 1, "source": "y"}]}
    assert not cm.has_control(e, "stun")
    assert cm.condition_modifiers(e)["damage"] == 0
    logs = cm.tick_conditions(e)
    assert e["hp"] == 8 and any("Veneno" in l for l in logs)
