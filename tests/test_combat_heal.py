"""
Cura no combate determinístico (combat_mechanics), agora com as 5 Posturas.
Habilidades de cura do Médico de Campo curam o herói (damage_type "Cura"),
nunca ferem o inimigo; lifesteal e limpeza de condição seguem funcionando.
"""
import combat_mechanics as cm
from gamedata import ABILITIES


def _player(hp=5, max_hp=30, entropy=16, max_entropy=16):
    return {
        "name": "Kael", "class_name": "Médico de Campo",
        "hp": hp, "max_hp": max_hp, "mana": 0, "max_mana": 0,
        "stamina": 0, "max_stamina": 0,
        "entropy": entropy, "max_entropy": max_entropy, "abyss_charge": 0,
        "attributes": {"str": 12, "dex": 12, "con": 12, "int": 14, "wis": 14, "cha": 10},
        "inventory": [], "known_abilities": ["ataque_basico", "sutura_de_campo",
                                             "intervencao_imediata"],
        "attack_bonus": 0, "equipment": {"weapon": None},
        "active_conditions": [], "ability_cooldowns": {},
    }


def _enemy(hp=20):
    return {"id": "e1", "name": "Goblin", "hp": hp, "max_hp": hp, "defense": 1,
            "status": "ativo", "attributes": {"dex": 8}, "active_conditions": []}


def test_cura_heals_player_not_enemy():
    p = _player(hp=5, max_hp=30)
    e = _enemy(hp=20)
    cm.resolve_player_action(p, [e], {"ability_id": "intervencao_imediata",
                                      "target": "Goblin", "is_allowed": True}, ABILITIES)
    assert p["hp"] > 5, "cura deve AUMENTAR o HP do herói"
    assert e["hp"] == 20, "habilidade de cura NÃO pode ferir o inimigo"


def test_sutura_heals_and_removes_bleed():
    p = _player(hp=10, max_hp=30)
    p["active_conditions"] = [{"name": "Sangramento", "dot": 3, "duration": 3}]
    e = _enemy()
    cm.resolve_player_action(p, [e], {"ability_id": "sutura_de_campo",
                                      "is_allowed": True}, ABILITIES)
    assert p["hp"] > 10
    assert all("sangramento" not in c["name"].lower() for c in p["active_conditions"]), \
        "deve remover Sangramento"


def test_heal_clamps_to_max_hp():
    p = _player(hp=29, max_hp=30)
    cm.resolve_player_action(p, [_enemy()], {"ability_id": "intervencao_imediata",
                                             "is_allowed": True}, ABILITIES)
    assert p["hp"] == 30, "cura não passa do máximo"


def test_estabilizar_cleanse():
    p = _player(hp=20, max_hp=30)
    p["active_conditions"] = [{"name": "Veneno", "dot": 2, "duration": 3}]
    cm.resolve_player_action(p, [_enemy()], {"ability_id": "estabilizar",
                                             "is_allowed": True}, ABILITIES)
    assert all("veneno" not in c["name"].lower() for c in p["active_conditions"])


def test_lifesteal_via_condicao_textual():
    """Lifesteal ('cura metade do dano') segue funcionando com ability inline."""
    p = _player(hp=5, max_hp=30)
    p["attributes"]["str"] = 16
    e = _enemy(hp=40)
    db = {"drenar_vida": {"name": "Drenar Vida", "cost": 0, "resource_type": "Nenhum",
                          "damage_formula": "3d6+str_mod", "damage_type": "Necrótico",
                          "conditions": ["Cura metade do dano causado"], "save_stat": None,
                          "effects": []}}
    cm.resolve_player_action(p, [e], {"ability_id": "drenar_vida", "target": "Goblin",
                                      "is_allowed": True}, db)
    if e["hp"] < 40:
        assert p["hp"] > 5, "lifesteal deve curar o herói quando há dano"


def test_offensive_still_damages_enemy():
    from gamedata import ABILITIES as AB
    p = _player(hp=30)
    p.update({"class_name": "Sangromante", "entropy": 10,
              "known_abilities": ["ataque_basico", "corte_exato"]})
    e = _enemy(hp=30)
    cm.resolve_player_action(p, [e], {"ability_id": "corte_exato", "target": "Goblin",
                                      "is_allowed": True}, AB)
    assert e["hp"] <= 30  # pode errar, mas nunca cura o inimigo
    assert p["hp"] == 30  # ofensiva não muda HP do herói
