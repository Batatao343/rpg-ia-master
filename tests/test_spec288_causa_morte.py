"""SPEC-288 — causa da morte = espécie canônica, nunca o texto do gancho."""

import gamedata
import world_utils as wu
from agents.combat import _killer_identity
from playtest.runner import _death_cause


def test_looming_threat_hint_is_species_not_hook_text():
    world = {
        "current_location_id": "floresta_sussurros",
        "looming_threat": "Corvane reativou uma câmara de Destilação parcial.",
    }
    enc = wu.check_encounter(world, gamedata.seed_factions(), {}, turn=10)
    assert enc and enc["reason"] == "looming_threat"
    assert "criatura ligada" not in enc["hint"]
    assert "Corvane" not in enc["hint"]
    assert "Corvane" in enc["flavor"]
    if enc.get("enemy_id"):
        assert enc["enemy_id"] in gamedata.BESTIARY


def test_killer_identity_strips_instance_suffix_and_gives_bestiary_id():
    bid = next(iter(gamedata.BESTIARY))
    name = gamedata.BESTIARY[bid]["name"]
    label, killer_id = _killer_identity([{"id": f"{bid}_2", "name": f"{name} 2"}])
    assert label == name
    assert killer_id == bid


def test_death_cause_prefers_killer_then_category():
    assert _death_cause({"killer": "Lobo", "cause": "x"}) == "Lobo"
    assert _death_cause({"cause": "armadilha"}) == "armadilha"
    assert _death_cause({}) == "desconhecida"
