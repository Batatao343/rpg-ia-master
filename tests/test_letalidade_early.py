"""Suíte da spec letalidade-early-game-v2 (Etapa 2) — 4 alavancas determinísticas.

Offline/mock. Ver specs/letalidade-early-game-v2.md. Baseline: run 20260720-093014
(combate/explorador morriam nível 1–3 por falta de laço de recuperação).
"""
import combat_mechanics as cm
import world_utils as wu
from gamedata import CLASSES


# --- helpers ----------------------------------------------------------------

def _player(level):
    return {
        "name": "Herói", "class_name": "Errante", "level": level,
        "hp": 30, "max_hp": 30, "attack_bonus": 0, "defense": 12,
        "attributes": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
        "known_abilities": [], "active_conditions": [],
    }


def _enemy(hp=100, level=1):
    return {"name": "Alvo", "hp": hp, "max_hp": hp, "defense": 1, "status": "ativo",
            "level": level, "attributes": {}, "active_conditions": []}


_ABILITY = {"golpe": {"name": "Golpe", "cost": 0, "resource_type": "Nenhum",
                      "damage_formula": "1d6", "conditions": [], "save_stat": None,
                      "damage_type": "Físico"}}
_ACTION = {"ability_id": "golpe", "target": "Alvo", "is_allowed": True}


# --- Alavanca 4: dano de early-game (runtime, só o herói) --------------------

def test_early_game_damage_bonus_por_nivel():
    assert cm.early_game_damage_bonus({"level": 1}) == 2
    assert cm.early_game_damage_bonus({"level": 2}) == 2
    assert cm.early_game_damage_bonus({"level": 3}) == 1
    assert cm.early_game_damage_bonus({"level": 4}) == 0
    assert cm.early_game_damage_bonus({"level": 7}) == 0
    assert cm.early_game_damage_bonus({}) == 2  # sem nível => trata como 1


def test_early_damage_bonus_soma_no_golpe_do_jogador(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 18)  # acerta, sem crit
    monkeypatch.setattr(cm, "resolve_damage_formula", lambda f, a: (5, "5"))
    e1 = _enemy(); cm.resolve_player_action(_player(1), [e1], _ACTION, _ABILITY)
    e4 = _enemy(); cm.resolve_player_action(_player(4), [e4], _ACTION, _ABILITY)
    assert (100 - e1["hp"]) - (100 - e4["hp"]) == 2  # +2 vigor inicial no nível 1


def test_early_damage_bonus_zera_nivel_4(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 18)
    monkeypatch.setattr(cm, "resolve_damage_formula", lambda f, a: (5, "5"))
    e = _enemy(); cm.resolve_player_action(_player(4), [e], _ACTION, _ABILITY)
    assert 100 - e["hp"] == 5  # sem bônus algum a partir do nível 4


def test_early_damage_bonus_nao_afeta_inimigo(monkeypatch):
    # o inimigo NUNCA passa por resolve_player_action; seu dano não escala com "level"
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 18)
    p1 = _player(5); p1["hp"] = 100
    p2 = _player(5); p2["hp"] = 100
    en = {"name": "Ogro", "attack_mod": 0, "status": "ativo", "hp": 10, "attributes": {},
          "active_conditions": [], "attacks": [{"name": "Soco", "bonus": 0, "damage": "5"}]}
    en1 = dict(en, level=1)
    en9 = dict(en, level=9)
    cm.resolve_enemy_turn(en1, p1)
    cm.resolve_enemy_turn(en9, p2)
    assert p1["hp"] == p2["hp"]  # dano do inimigo independe do nível dele


# --- Alavanca 1: recuperação no descanso/viagem -----------------------------

def test_recovery_rest_safe_early_game_zona_segura():
    assert wu.recovery_rest_safe(1, 3, {"tags": []}) is True
    assert wu.recovery_rest_safe(wu.EARLY_GAME_LEVEL, wu.RECOVERY_SAFE_DANGER, {}) is True


def test_recovery_rest_safe_nega_apex_perigo_ou_nivel_alto():
    assert wu.recovery_rest_safe(1, 3, {"tags": ["apex"]}) is False   # apex nunca suaviza
    assert wu.recovery_rest_safe(1, 4, {}) is False                    # perigo alto
    assert wu.recovery_rest_safe(wu.EARLY_GAME_LEVEL + 1, 1, {}) is False  # já cresceu


def test_cooldown_encontro_maior_no_early_game(monkeypatch):
    monkeypatch.setattr(wu, "_effective_danger", lambda w, l: 5)
    monkeypatch.setattr(wu, "pick_encounter_enemy", lambda *a, **k: {"name": "Fera", "id": "fera"})
    base = {"current_location_id": "zona", "current_location": "Zona",
            "last_encounter_turn": 0, "danger_level": 5}
    # early-game (nível 1): cooldown = 2 + 2 = 4. Turno 3 (< 4) => bloqueado.
    assert wu.check_encounter(dict(base), [], {}, turn=3, player_level=1) is None
    # turno 4 (>= 4) => não bloqueado => encontro dispara.
    assert wu.check_encounter(dict(base), [], {}, turn=4, player_level=1) is not None
    # nível alto: cooldown = 2. Turno 3 (>= 2) => dispara (sem bônus de early-game).
    assert wu.check_encounter(dict(base), [], {}, turn=3, player_level=9) is not None


# --- Alavancas 2/3: +poções e +HP base (gerador regenerado) -----------------

def test_hp_base_pisos_novos():
    assert CLASSES["Arcanista Cinzento"]["base_stats"]["hp"] == 26
    assert CLASSES["Sangromante"]["base_stats"]["hp"] == 30
    assert CLASSES["Corruptor"]["base_stats"]["hp"] == 30
    assert CLASSES["Médico de Campo"]["base_stats"]["hp"] == 30
    assert CLASSES["Devoto do Abismo"]["base_stats"]["hp"] == 40


def test_starting_equipment_pocoes():
    for name, cls in CLASSES.items():
        n = list(cls.get("starting_equipment", [])).count("pocao_cura")
        assert n >= 2, f"{name} deveria começar com >=2 poções, tem {n}"
    assert list(CLASSES["Médico de Campo"]["starting_equipment"]).count("pocao_cura") == 3
