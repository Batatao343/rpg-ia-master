"""Suíte da spec refatoracao-sistema-classes (Cinco Posturas diante do Abismo).

Etapa 1: recurso Entropia. Offline/determinístico.
Ver specs/refatoracao-sistema-classes.md.
"""
import combat_mechanics as cm
import world_utils as wu


# --- Etapa 1: recurso Entropia ----------------------------------------------

def test_entropy_resource_field():
    assert cm._resource_field("Entropia") == "entropy"
    assert cm._resource_field("entropy") == "entropy"
    # os antigos seguem funcionando (compat)
    assert cm._resource_field("Mana") == "mana"
    assert cm._resource_field("Estamina") == "stamina"


def test_pay_from_entropy():
    player = {"entropy": 10, "max_entropy": 14, "ability_cooldowns": {}}
    ability = {"name": "Provocação do Abismo", "cost": 4, "resource_type": "Entropia"}
    ok, _msg = cm.spend_resources(player, "provocacao_do_abismo", ability)
    assert ok is True
    assert player["entropy"] == 6


def test_pay_from_entropy_insuficiente():
    player = {"entropy": 2, "max_entropy": 14, "ability_cooldowns": {}}
    ability = {"name": "Golpe Caro", "cost": 8, "resource_type": "Entropia"}
    ok, _msg = cm.spend_resources(player, "golpe_caro", ability)
    assert ok is False
    assert player["entropy"] == 2  # não deduz se não pode pagar


def test_rest_refills_entropy_full():
    player = {"hp": 10, "max_hp": 40, "entropy": 3, "max_entropy": 16,
              "active_conditions": []}
    world = wu.ensure_world({"current_location_id": "nova_arcadia"})
    p2, _w = wu.apply_rest(player, world)
    assert p2["entropy"] == 16          # Entropia INTEGRAL
    assert p2["hp"] < p2["max_hp"]      # HP só ~metade (não integral)


def test_rest_nao_derruba_carga_do_abismo():
    player = {"hp": 10, "max_hp": 40, "entropy": 3, "max_entropy": 16,
              "abyss_charge": 5, "active_conditions": []}
    world = wu.ensure_world({})
    p2, _w = wu.apply_rest(player, world)
    assert p2["abyss_charge"] == 5      # Carga do Abismo NÃO cai no descanso
