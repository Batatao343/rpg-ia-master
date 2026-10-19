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


def test_looming_threat_picks_regional_bestiary_creature_deterministically():
    world = {
        "current_location_id": "floresta_sussurros",
        "looming_threat": "Corvane reativou uma câmara de Destilação parcial.",
    }
    a = wu.check_encounter(dict(world), gamedata.seed_factions(), {}, turn=10)
    b = wu.check_encounter(dict(world), gamedata.seed_factions(), {}, turn=10)
    assert a == b
    entry = gamedata.BESTIARY[a["enemy_id"]]
    assert a["hint"] == entry["name"]
    assert "floresta_sussurros" in (entry.get("regions") or [])
    assert "BOSS" not in str(entry.get("type", "")).upper()


def test_looming_threat_feeds_canonical_systemic_manifest_source():
    from services import encounter_manifest as em

    world = {
        "current_location_id": "floresta_sussurros",
        "looming_threat": "Corvane reativou uma câmara de Destilação parcial.",
    }
    enc = wu.check_encounter(world, gamedata.seed_factions(), {}, turn=10)
    src = em.resolve_canonical_source({}, enc["hint"], enc)
    assert src["source"] == "systemic"
    assert src["target_ref"] == enc["enemy_id"]


def test_killer_identity_legacy_hook_name_does_not_crash():
    legacy = {"id": "criatura_ligada_a_corvane", "name": "criatura ligada a: Corvane 2"}
    label, killer_id = _killer_identity([None, legacy])
    assert label == "criatura ligada a: Corvane"
    assert killer_id == ""
    assert _killer_identity([]) == ("", "")
