"""SPEC-289 — criatura do encontro `looming_threat` ligada ao tema da ameaça (determinístico)."""

import gamedata
import world_utils as wu
from encounter_budget import is_boss

CORVANE = next(
    f["ascension"]["threat"] for f in gamedata.seed_factions() if f["id"] == "cultistas_destilacao"
)
CHAMA = next(
    f["ascension"]["threat"] for f in gamedata.seed_factions() if f["id"] == "filhos_chama_azul"
)


def _enc(loc, threat, level=1, override=None, faction_id=None, turn=10):
    world = {"current_location_id": loc, "looming_threat": threat}
    if override:
        world["danger_overrides"] = {loc: override}
    if faction_id:
        world["looming_threat_faction"] = faction_id
    return wu.check_encounter(world, gamedata.seed_factions(), {}, turn=turn, player_level=level)


def _tier(entry):
    return "elite" if "elite" in str(entry.get("type", "")).lower() else "minion"


def test_invocar_entidade_stamps_faction():
    facs = gamedata.seed_factions()
    f = next(x for x in facs if x["id"] == "cultistas_destilacao")
    _, world, _ = wu.resolve_faction_completions(facs, {}, [{"id": f["id"]}], {})
    assert world["looming_threat"] == CORVANE
    assert world["looming_threat_faction"] == "cultistas_destilacao"


def test_threat_faction_legacy_text_match():
    world = {"looming_threat": CORVANE}  # save antigo: sem o campo da fação
    assert wu.threat_faction(world, [])["id"] == "cultistas_destilacao"
    assert wu.threat_faction({"looming_threat": "algo qualquer"}, []) is None
    assert wu.threat_faction({}, gamedata.seed_factions()) is None


def test_threat_sphere_uses_target_and_home_region():
    facs = {f["id"]: f for f in gamedata.seed_factions()}
    assert wu.threat_sphere(facs["cultistas_destilacao"]) == {"aethelgard"}
    assert wu.threat_sphere(facs["filhos_chama_azul"]) == {"nova_arcadia"}


def test_corvane_in_sphere_picks_themed_creature():
    for level, want_tier in ((1, "minion"), (9, "elite")):
        enc = _enc("ae_ruinas_submersas", CORVANE, level=level)
        assert enc["reason"] == "looming_threat"
        entry = gamedata.BESTIARY[enc["enemy_id"]]
        assert enc["hint"] == entry["name"]
        assert "aethelgard" in entry["regions"] and not is_boss(entry)
        assert _tier(entry) == want_tier
        theme = wu.threat_theme_match(wu.threat_faction({"looming_threat": CORVANE}, []), CORVANE)
        assert theme(entry) > 0, entry["name"]
    # porte Minion: única temática é a Faísca da Destilação
    assert _enc("ae_ruinas_submersas", CORVANE, level=1)["enemy_id"] == "mon_faisca_destilacao"
    # porte Elite: fação (Cultista) + nome (Afogado, Quimera de Cristal Destilado), por turno
    seen = {_enc("ae_ruinas_submersas", CORVANE, level=9, turn=t)["enemy_id"] for t in range(6)}
    assert seen == {
        "enemy_cultista_destilacao",
        "mon_afogado_de_aethelgard",
        "mon_quimera_cristal",
    }


def test_chama_azul_in_sphere_prefers_faction_creature():
    enc = _enc("nova_arcadia", CHAMA, level=1, override=3)
    assert enc["enemy_id"] == "enemy_iniciado_chama_azul"
    assert enc["flavor"] == CHAMA


def test_porte_strict_falls_back_when_no_themed_elite():
    # porte Elite (nível 9, perigo 4) e a única temática é Minion → sorteio regional de antes
    with_theme = _enc("na_anel_dourado", CHAMA, level=9, override=4)
    legacy = _enc("na_anel_dourado", "texto sem dono", level=9, override=4)
    assert with_theme["enemy_id"] == legacy["enemy_id"]
    assert _tier(gamedata.BESTIARY[with_theme["enemy_id"]]) == "elite"
    # revisão P2-1: fallback na esfera emoldura o flavor (não cola o tema na fera)
    assert "Palácio de Obsidiana" in with_theme["flavor"]
    assert with_theme["flavor"] != CHAMA and "outra coisa" in with_theme["flavor"]


def test_out_of_sphere_keeps_regional_and_frames_flavor():
    enc = _enc("floresta_sussurros", CORVANE)
    legacy = _enc("floresta_sussurros", "texto sem dono")
    assert enc["enemy_id"] == legacy["enemy_id"]
    assert "Corvane" in enc["flavor"] and enc["flavor"] != CORVANE
    assert "distante" in enc["flavor"].lower()
    # mesmo tema em outra região com radical "afogad": fora da esfera, não puxa Afogado
    swamp = _enc("pantano_melancolia", CORVANE, level=9)
    assert swamp["enemy_id"] == _enc("pantano_melancolia", "texto sem dono", level=9)["enemy_id"]


def test_unknown_threat_text_is_legacy_behavior():
    a = _enc("ae_ruinas_submersas", "Algo desperta sob o lago.", level=9)
    pick = wu.pick_encounter_enemy(gamedata.get_location("ae_ruinas_submersas"), 4, 10)
    assert a["enemy_id"] == pick["id"]
    assert a["flavor"] == "Algo desperta sob o lago."


def test_stamped_faction_wins_over_text():
    # fação gravada (R1) vale mesmo com texto editado
    enc = _enc("ae_ruinas_submersas", "texto reescrito", level=1, faction_id="cultistas_destilacao")
    assert enc["enemy_id"] == "mon_faisca_destilacao"


def test_themed_pick_deterministic_and_systemic_manifest():
    from services import encounter_manifest as em

    a = _enc("ae_ruinas_submersas", CORVANE, level=9)
    b = _enc("ae_ruinas_submersas", CORVANE, level=9)
    assert a == b
    src = em.resolve_canonical_source({}, a["hint"], a)
    assert src["source"] == "systemic"
    assert src["target_ref"] == a["enemy_id"]


def test_pick_encounter_enemy_without_theme_unchanged():
    loc = gamedata.get_location("ae_ruinas_submersas")
    for danger in (1, 2, 3, 4):
        for turn in range(6):
            assert wu.pick_encounter_enemy(loc, danger, turn) == wu.pick_encounter_enemy(
                loc, danger, turn, theme=None
            )


def test_themed_pick_skips_boss_and_respects_weighted_path():
    import random

    loc = gamedata.get_location("ae_ruinas_submersas")
    fac = wu.threat_faction({"looming_threat": CORVANE}, [])
    theme = wu.threat_theme_match(fac, CORVANE)
    for seed in range(20):
        e = wu.pick_encounter_enemy(
            loc, 4, seed, bestiary_knowledge={}, projection={}, rng=random.Random(seed), theme=theme
        )
        assert theme(e) > 0 and not is_boss(e) and _tier(e) == "elite"
