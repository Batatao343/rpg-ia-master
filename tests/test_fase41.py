"""
Fase 4.1 — Progressão: XP, level up e árvore de habilidades.
Suíte offline (MockLLM forçado pelo conftest). Núcleo 100% Python: progression.py.
"""
import copy

import pytest

import progression as pg
from gamedata import XP_TABLE


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_player(**over):
    p = {
        "name": "Testo", "class_name": "Cavaleiro da Vigília", "race": "Humano",
        "level": 1, "xp": 0,
        "hp": 30, "max_hp": 30, "mana": 5, "max_mana": 5,
        "stamina": 20, "max_stamina": 20,
        "gold": 0, "attributes": {"str": 16, "dex": 10, "con": 16,
                                  "int": 8, "wis": 12, "cha": 12},
        "inventory": [], "known_abilities": ["ataque_basico"],
        "defense": 17, "attack_bonus": 0,
        "active_conditions": [], "ability_cooldowns": {},
        "pending_choices": [],
    }
    p.update(over)
    return p


# Árvore sintética p/ testes de elegibilidade (independente da 4.1b)
FAKE_ABILITIES = {
    "ataque_basico": {"name": "Ataque Básico", "classes": ["all"],
                      "branch": None, "tier": 1, "level_req": 1, "requires": []},
    "improvisado": {"name": "Improvisado", "classes": ["all"],
                    "branch": None, "tier": 1, "level_req": 1, "requires": []},
    "tronco_1": {"name": "Tronco 1", "classes": ["Cavaleiro da Vigília"],
                 "branch": None, "tier": 1, "level_req": 1, "requires": []},
    "tronco_alto": {"name": "Tronco Alto", "classes": ["Cavaleiro da Vigília"],
                    "branch": None, "tier": 1, "level_req": 4, "requires": []},
    "ramo_a_1": {"name": "Ramo A 1", "classes": ["Cavaleiro da Vigília"],
                 "branch": "muralha", "tier": 2, "level_req": 2, "requires": []},
    "ramo_a_2": {"name": "Ramo A 2", "classes": ["Cavaleiro da Vigília"],
                 "branch": "muralha", "tier": 3, "level_req": 3,
                 "requires": ["ramo_a_1"]},
    "ramo_b_1": {"name": "Ramo B 1", "classes": ["Cavaleiro da Vigília"],
                 "branch": "lanca", "tier": 2, "level_req": 2, "requires": []},
    "outra_classe": {"name": "Alheia", "classes": ["Arcanista Cinzento"],
                     "branch": None, "tier": 1, "level_req": 1, "requires": []},
}

FAKE_CLASSES = {
    "Cavaleiro da Vigília": {
        "level_gains": {"hp": 7, "mana": 0, "stamina": 3},
    },
}


# ---------------------------------------------------------------------------
# Etapa 1 — XP e level up
# ---------------------------------------------------------------------------

def test_xp_for_kills_por_tier():
    dead = [
        {"type": "Minion"}, {"type": "Elite"}, {"type": "BOSS"},
        {"type": "boss"}, {},  # sem type -> minion
    ]
    assert pg.xp_for_kills(dead) == 50 + 200 + 1000 + 1000 + 50


def test_xp_to_next():
    assert pg.xp_to_next(1) == XP_TABLE[2] == 300
    assert pg.xp_to_next(19) == XP_TABLE[20]
    assert pg.xp_to_next(20) is None


def test_grant_xp_sem_level():
    p = make_player()
    out, events = pg.grant_xp(p, 100, classes_db=FAKE_CLASSES)
    assert out["xp"] == 100
    assert out["level"] == 1
    assert out["pending_choices"] == []
    assert events == []


def test_grant_xp_level_up():
    p = make_player(hp=20)  # ferido: cura só o delta
    out, events = pg.grant_xp(p, 300, classes_db=FAKE_CLASSES)
    assert out["level"] == 2
    assert out["max_hp"] == 37          # 30 + 7
    assert out["hp"] == 27              # 20 + 7 (delta, não full heal)
    assert out["max_stamina"] == 23
    assert out["max_mana"] == 5
    kinds = [(c["level"], c["kind"]) for c in out["pending_choices"]]
    assert (2, "ability") in kinds
    assert (2, "attribute") in kinds    # nível par
    assert len(events) == 1
    assert events[0]["type"] == "level_up"
    assert events[0]["payload"]["new_level"] == 2


def test_grant_xp_nivel_impar_sem_attr():
    p = make_player(level=2, xp=300)
    out, _ = pg.grant_xp(p, 600, classes_db=FAKE_CLASSES)  # 900 = nível 3
    assert out["level"] == 3
    kinds = [(c["level"], c["kind"]) for c in out["pending_choices"]]
    assert (3, "ability") in kinds
    assert (3, "attribute") not in kinds


def test_grant_xp_multi_level():
    p = make_player()
    out, events = pg.grant_xp(p, 1000, classes_db=FAKE_CLASSES)  # cruza 300 e 900
    assert out["level"] == 3
    assert out["max_hp"] == 30 + 7 + 7
    assert [e["payload"]["new_level"] for e in events] == [2, 3]
    # 2 escolhas de habilidade + 1 de atributo (só o nível 2 é par)
    kinds = [c["kind"] for c in out["pending_choices"]]
    assert kinds.count("ability") == 2
    assert kinds.count("attribute") == 1


def test_grant_xp_nivel_20_cap():
    p = make_player(level=20, xp=XP_TABLE[20])
    out, events = pg.grant_xp(p, 99999, classes_db=FAKE_CLASSES)
    assert out["level"] == 20
    assert out["xp"] == XP_TABLE[20] + 99999
    assert events == []


def test_grant_xp_classe_sem_gains_usa_default():
    p = make_player(class_name="Classe Fantasma")
    out, _ = pg.grant_xp(p, 300, classes_db=FAKE_CLASSES)
    assert out["level"] == 2
    assert out["max_hp"] > 30  # default aplicado, não crash


def test_grant_xp_nao_muta_original():
    p = make_player()
    snapshot = copy.deepcopy(p)
    pg.grant_xp(p, 300, classes_db=FAKE_CLASSES)
    assert p == snapshot


# ---------------------------------------------------------------------------
# Etapa 3 — Árvore: elegibilidade, ramo (subclasse), escolha
# ---------------------------------------------------------------------------

def test_player_branch_derivada():
    p = make_player()
    assert pg.player_branch(p, abilities_db=FAKE_ABILITIES) is None
    p2 = make_player(known_abilities=["ataque_basico", "ramo_a_1"])
    assert pg.player_branch(p2, abilities_db=FAKE_ABILITIES) == "muralha"


def test_eligible_filtra_classe_nivel_prereq():
    p = make_player(level=1)
    elig = pg.eligible_abilities(p, abilities_db=FAKE_ABILITIES)
    assert "tronco_1" in elig
    assert "improvisado" in elig            # universal, não conhecida
    assert "ataque_basico" not in elig      # já conhecida
    assert "outra_classe" not in elig       # classe errada
    assert "tronco_alto" not in elig        # level_req 4
    assert "ramo_a_2" not in elig           # requires não satisfeito
    assert "ramo_a_1" not in elig           # level_req 2


def test_lock_de_ramo():
    p = make_player(level=3, known_abilities=["ataque_basico", "ramo_a_1"])
    elig = pg.eligible_abilities(p, abilities_db=FAKE_ABILITIES)
    assert "ramo_a_2" in elig               # aprofunda o próprio ramo
    assert "ramo_b_1" not in elig           # ramo rival trancado
    assert "tronco_1" in elig               # tronco segue livre


def test_apply_choice_ability():
    p = make_player(level=2, pending_choices=[
        {"id": "lvl2-ability", "level": 2, "kind": "ability"}])
    out, err = pg.apply_choice(p, "lvl2-ability", ability_id="ramo_a_1",
                               abilities_db=FAKE_ABILITIES)
    assert err is None
    assert "ramo_a_1" in out["known_abilities"]
    assert out["pending_choices"] == []


def test_apply_choice_attr():
    p = make_player(pending_choices=[
        {"id": "lvl2-attr", "level": 2, "kind": "attribute"}])
    out, err = pg.apply_choice(p, "lvl2-attr", attr="Força",
                               abilities_db=FAKE_ABILITIES)
    assert err is None
    assert out["attributes"]["str"] == 17   # normalize_attr + 1
    assert out["pending_choices"] == []


def test_apply_choice_invalida():
    p = make_player(level=2, known_abilities=["ataque_basico", "ramo_a_1"],
                    pending_choices=[
                        {"id": "lvl2-ability", "level": 2, "kind": "ability"}])
    snapshot = copy.deepcopy(p)

    # habilidade de ramo rival
    out, err = pg.apply_choice(p, "lvl2-ability", ability_id="ramo_b_1",
                               abilities_db=FAKE_ABILITIES)
    assert err is not None
    assert p == snapshot  # intocado

    # choice_id inexistente
    out, err = pg.apply_choice(p, "nao-existe", ability_id="tronco_1",
                               abilities_db=FAKE_ABILITIES)
    assert err is not None

    # atributo inválido
    p2 = make_player(pending_choices=[
        {"id": "lvl2-attr", "level": 2, "kind": "attribute"}])
    out, err = pg.apply_choice(p2, "lvl2-attr", attr="sorte",
                               abilities_db=FAKE_ABILITIES)
    assert err is not None
    assert p2["pending_choices"]  # não consumiu


def test_level_up_event_shape():
    p = make_player()
    _, events = pg.grant_xp(p, 300, classes_db=FAKE_CLASSES)
    ev = events[0]
    assert ev["actor_id"] == "player" and ev["target_id"] == "player"
    assert ev["source"] == "progression"
    assert "detail" in ev


# ---------------------------------------------------------------------------
# Etapa 2a — Schema da árvore nos DADOS REAIS (conteúdo: spec 4.1b)
# ---------------------------------------------------------------------------

from gamedata import ABILITIES, CLASSES  # noqa: E402

VALID_EFFECT_KINDS = {"buff", "debuff", "dot", "control", "heal"}
VALID_EFFECT_STATS = {"damage", "ac", "attack", "save", None}


def test_schema_arvore():
    class_names = set(CLASSES.keys()) | {"all"}
    for aid, a in ABILITIES.items():
        classes = a.get("classes")
        assert isinstance(classes, list) and classes, f"{aid}: classes ausente"
        for c in classes:
            assert c in class_names, f"{aid}: classe desconhecida {c!r}"
        assert isinstance(a.get("tier"), int) and 1 <= a["tier"] <= 3, f"{aid}: tier"
        assert isinstance(a.get("level_req"), int) and a["level_req"] >= 1, f"{aid}: level_req"
        reqs = a.get("requires")
        assert isinstance(reqs, list), f"{aid}: requires"
        for r in reqs:
            assert r in ABILITIES, f"{aid}: requires id inexistente {r!r}"
        br = a.get("branch")
        if br is not None:
            # branch declarado precisa existir em alguma classe da habilidade
            owners = [c for c in classes if c != "all"]
            assert any(br in ((CLASSES.get(c) or {}).get("branches") or {})
                       for c in owners), f"{aid}: branch {br!r} sem dono"


def test_sem_ciclo_em_requires():
    def deps(aid, seen):
        assert aid not in seen, f"ciclo de requires envolvendo {aid}"
        seen = seen | {aid}
        for r in ABILITIES.get(aid, {}).get("requires") or []:
            deps(r, seen)
    for aid in ABILITIES:
        deps(aid, frozenset())


def test_effects_tipado():
    for aid, a in ABILITIES.items():
        for eff in a.get("effects") or []:
            assert eff.get("kind") in VALID_EFFECT_KINDS, f"{aid}: kind {eff.get('kind')!r}"
            assert eff.get("stat") in VALID_EFFECT_STATS, f"{aid}: stat {eff.get('stat')!r}"
            assert isinstance(eff.get("duration", 1), int), f"{aid}: duration"


def test_level_gains_presentes():
    for cname, c in CLASSES.items():
        gains = c.get("level_gains")
        assert isinstance(gains, dict), f"{cname}: level_gains ausente"
        for k in ("hp", "mana", "stamina"):
            assert isinstance(gains.get(k), int), f"{cname}: level_gains.{k}"
        assert gains["hp"] >= 1, f"{cname}: hp por nível deve ser >= 1"


def test_starting_abilities_validas():
    for cname, c in CLASSES.items():
        start = c.get("starting_abilities")
        assert isinstance(start, list) and start, f"{cname}: starting_abilities"
        for aid in start:
            assert aid in ABILITIES, f"{cname}: starting {aid!r} não existe"
            a = ABILITIES[aid]
            assert a.get("level_req", 1) == 1, f"{cname}: starting {aid} exige nível > 1"
            assert a.get("branch") is None, f"{cname}: starting {aid} não pode ter ramo"
            classes = a.get("classes") or []
            assert "all" in classes or cname in classes, \
                f"{cname}: starting {aid} não pertence à classe"
