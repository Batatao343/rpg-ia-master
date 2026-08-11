"""
Fase 6.4 — Encontros sistêmicos: detecção, surpresa e variedade.
Spec: specs/fase-6.4-encontros-sistemicos.md. 100% offline, zero LLM novo.
"""
import random

import pytest

import combat_mechanics as cm
import world_utils as wu
from gamedata import get_location


def make_player(**over):
    p = {"name": "T", "class_name": "", "level": 3, "hp": 30, "max_hp": 30,
         "mana": 5, "max_mana": 5, "stamina": 20, "max_stamina": 20, "xp": 0,
         "attributes": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 14, "cha": 10},
         "inventory": [], "equipment": {"weapon": None, "armor": None, "accessory": None},
         "known_abilities": ["ataque_basico"], "defense": 12, "attack_bonus": 0,
         "active_conditions": [], "ability_cooldowns": {}, "pending_choices": []}
    p.update(over)
    return p


class _FixedRng:
    """rng com d20 fixo (randint) e escolha determinística."""

    def __init__(self, roll):
        self.roll = roll

    def randint(self, a, b):
        return min(b, max(a, self.roll))

    def choices(self, seq, weights=None, k=1):
        return [seq[0]]


# ---------------------------------------------------------------------------
# Etapa 1 — detecção e tipo
# ---------------------------------------------------------------------------

def test_detection_check_faixas():
    p = make_player()  # wis 14 -> +2
    ok = wu.detection_check(p, 1, _FixedRng(10))   # 12 vs DC 10
    assert ok["perceived"] and ok["dc"] == 10
    bad = wu.detection_check(p, 4, _FixedRng(10))  # 12 vs DC 16
    assert not bad["perceived"] and bad["dc"] == 16


def test_detection_usa_bonus_racial_wis():
    p = make_player(racial_save_bonus={"wis": 4})
    r = wu.detection_check(p, 4, _FixedRng(10))  # 10+2+4=16 vs 16
    assert r["perceived"]


def test_roll_encounter_type_distribuicao():
    rng = random.Random(3)
    low = {wu.roll_encounter_type(1, rng) for _ in range(300)}
    assert low <= {"combat", "track", "social"}
    assert "trap" not in low  # armadilha só em danger alto
    high = {wu.roll_encounter_type(4, rng) for _ in range(300)}
    assert "trap" in high


# ---------------------------------------------------------------------------
# Etapa 2 — armadilha 100% Python
# ---------------------------------------------------------------------------

def test_armadilha_falha_dano_e_condicao():
    loc = get_location("pantano_melancolia")
    p = make_player(attributes={"str": 10, "dex": 6, "con": 10, "int": 10,
                                "wis": 10, "cha": 10})
    out, logs, info = wu.resolve_trap(p, loc, 3, _FixedRng(2))
    assert not info["dodged"]
    assert out["hp"] < 30
    # pântano: veneno tipado da tabela
    assert any(c.get("dot") for c in out.get("active_conditions", []))
    assert any("falha" in l for l in logs)


def test_armadilha_esquiva_da_xp():
    loc = get_location("pantano_melancolia")
    p = make_player(attributes={"str": 10, "dex": 18, "con": 10, "int": 10,
                                "wis": 10, "cha": 10})
    out, logs, info = wu.resolve_trap(p, loc, 1, _FixedRng(19))
    assert info["dodged"]
    assert out["xp"] == wu.TRAP_DODGE_XP
    assert out["hp"] == 30


def test_armadilha_regiao_sem_tabela_usa_default():
    loc = {"id": "x", "region_id": "regiao_fantasma"}
    _, logs, info = wu.resolve_trap(make_player(), loc, 2, _FixedRng(1))
    assert info and logs


def test_armadilha_que_preenche_ultimo_critico_dispara_fluxo_terminal(monkeypatch):
    from services import conflict_damage

    def lethal_damage(target, **_kwargs):
        target["vitalidade"] = 0
        target["ferimentos"]["critico"].append({"regiao": "torso"})
        return {"log": ["Ferimento crítico em torso"]}

    monkeypatch.setattr(conflict_damage, "resolve_damage_and_wounds", lethal_damage)
    loc = {"id": "x", "region_id": "regiao_fantasma"}
    player = make_player(
        is_player=True,
        virtudes={"forca": 0, "agilidade": 0, "corpo": 0, "mente": 0, "carisma": 0},
        vitalidade=0,
        max_vitalidade=6,
        hp=0,
        max_hp=6,
        ferimento_espacos={"leve": 1, "grave": 1, "critico": 1},
        ferimentos={"leve": [], "grave": [], "critico": []},
    )

    out, _logs, info = wu.resolve_trap(player, loc, 4, _FixedRng(1))

    assert info["terminal_triggered"] is True
    assert info["dead"] is True
    assert out["dead"] is True


# ---------------------------------------------------------------------------
# Etapa 3 — rastro
# ---------------------------------------------------------------------------

def test_rastro_alimenta_codex_e_pode_dar_pista():
    loc = get_location("na_anel_lama") or get_location("nova_arcadia")
    bk, note, hint = wu.resolve_track({}, loc, 1, turn=5, rng=_FixedRng(1))
    assert bk  # rumor registrado (grau 3.2)
    assert "rastro" in note.lower() or "Rastros" in note
    assert isinstance(hint, bool)


def test_boost_de_tesouro_forca_banda_alta():
    from services import economy as eco
    rng = random.Random(5)
    rarities = {eco.roll_loot("skallgard", 1, rng, boost=True)["rarity"]
                for _ in range(120)}
    assert rarities - {"comum", "incomum"}  # banda 3-4 tem raro/epico/lendario


# ---------------------------------------------------------------------------
# Etapa 4 — surpresa no combate
# ---------------------------------------------------------------------------

def _combat_state(surprise):
    from langchain_core.messages import HumanMessage, SystemMessage
    enemy = {"id": "e1", "name": "Orc", "type": "Minion", "hp": 30, "max_hp": 30,
             "defense": 30, "status": "ativo", "attributes": {"dex": 10},
             "active_conditions": [],
             "attacks": [{"name": "Golpe", "bonus": -20, "damage": "1d1"}],
             "stamina": 0, "mana": 0, "attack_mod": 0}
    return {"messages": [SystemMessage(content="COMBAT START. Emboscada!"),
                         HumanMessage(content="ataco o orc")],
            "player": make_player(), "enemies": [enemy],
            "combat": {}, "combat_target": "Orc",
            "world": {"turn_count": 3, "current_location": "X",
                      "encounter_surprise": surprise,
                      "world_clock": {"day": 1}},
            "bestiary_knowledge": {}, "pending_world_events": [], "party": []}


def test_surpresa_ajusta_iniciativa_e_consome_flag(monkeypatch):
    from agents import combat as cbt
    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "ok")
    st = _combat_state("enemy")
    st["combat_declaration"] = {
        "actor_id": "player", "acao": {"kind": "attack", "target_id": "e1"}}
    out = cbt.combat_node(st)
    assert out["combat"]["initiative"][0] == "enemy"
    # flag consumida
    assert "encounter_surprise" not in (out.get("world") or {})

    st2 = _combat_state("player")
    st2["combat_declaration"] = {
        "actor_id": "player", "acao": {"kind": "attack", "target_id": "e1"}}
    out2 = cbt.combat_node(st2)
    assert out2["combat"]["initiative"][0] == "heroes"


def test_sem_flag_comportamento_normal(monkeypatch):
    from agents import combat as cbt
    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "ok")
    st = _combat_state(None)
    del st["world"]["encounter_surprise"]
    st["combat_declaration"] = {
        "actor_id": "player", "acao": {"kind": "attack", "target_id": "e1"}}
    out = cbt.combat_node(st)
    assert out["combat"]["initiative"]
