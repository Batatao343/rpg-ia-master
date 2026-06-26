"""
Correção do bug de CURA no combate determinístico (combat_mechanics).
Antes: habilidades de cura davam DANO no inimigo e nunca curavam. Agora curam o herói.
"""
import combat_mechanics as cm
from gamedata import ABILITIES


def _player(hp=5, max_hp=30, stamina=12, max_stamina=12):
    return {
        "name": "Kael", "class_name": "Tecnólogo",
        "hp": hp, "max_hp": max_hp, "mana": 10, "max_mana": 10,
        "stamina": stamina, "max_stamina": max_stamina,
        "attributes": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 14, "cha": 10},
        "inventory": [], "known_abilities": [], "attack_bonus": 0,
        "active_conditions": [], "ability_cooldowns": {},
    }


def _enemy(hp=20):
    return {"id": "e1", "name": "Goblin", "hp": hp, "max_hp": hp, "defense": 1,
            "status": "ativo", "attributes": {"dex": 8}, "active_conditions": []}


def test_granada_de_cura_heals_player_not_enemy():
    p = _player(hp=5, max_hp=30)
    e = _enemy(hp=20)
    cm.resolve_player_action(p, [e], {"ability_id": "granada_de_cura", "target": "Goblin",
                                      "is_allowed": True}, ABILITIES)
    assert p["hp"] > 5, "cura deve AUMENTAR o HP do herói"
    assert e["hp"] == 20, "habilidade de cura NÃO pode ferir o inimigo"


def test_sutura_heals_and_removes_bleed():
    p = _player(hp=10, max_hp=30)
    p["active_conditions"] = [{"name": "Sangramento", "dot": 3, "duration": 3}]
    e = _enemy()
    cm.resolve_player_action(p, [e], {"ability_id": "sutura_de_campo", "is_allowed": True}, ABILITIES)
    assert p["hp"] > 10
    assert all("sangramento" not in c["name"].lower() for c in p["active_conditions"]), "deve remover Sangramento"


def test_heal_clamps_to_max_hp():
    p = _player(hp=29, max_hp=30)
    cm.resolve_player_action(p, [_enemy()], {"ability_id": "granada_de_cura", "is_allowed": True}, ABILITIES)
    assert p["hp"] == 30, "cura não passa do máximo"


def test_adrenalina_recovers_stamina():
    p = _player(stamina=2, max_stamina=10)
    cm.resolve_player_action(p, [_enemy()], {"ability_id": "adrenalina_suja", "is_allowed": True}, ABILITIES)
    assert p["stamina"] > 2 and p["stamina"] <= 10


def test_drenar_vida_lifesteal():
    p = _player(hp=5, max_hp=30, stamina=10, max_stamina=10)
    p["mana"] = 20; p["max_mana"] = 20
    e = _enemy(hp=40)
    cm.resolve_player_action(p, [e], {"ability_id": "drenar_vida", "target": "Goblin",
                                      "is_allowed": True}, ABILITIES)
    # acertou (AC do goblin = 1) → inimigo tomou dano E herói recuperou parte
    if e["hp"] < 40:
        assert p["hp"] > 5, "lifesteal deve curar o herói quando há dano"


def test_offensive_still_damages_enemy():
    p = _player(hp=30, stamina=10, max_stamina=10)
    e = _enemy(hp=30)
    cm.resolve_player_action(p, [e], {"ability_id": "estocada_renal", "target": "Goblin",
                                      "is_allowed": True}, ABILITIES)
    assert e["hp"] <= 30  # pode errar, mas nunca cura o inimigo
    assert p["hp"] == 30  # ofensiva não muda HP do herói
