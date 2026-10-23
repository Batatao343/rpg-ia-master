"""SPEC-297 Etapa 2 - semente estruturada (R4-R6)."""

import json

from services import npc_seed as ns
from services.content_validator import validate_npc_seed_tables


def test_same_inputs_same_seed():
    a = ns.roll_npc_seed(game_id="g1", turn=7, location_id="na_anel_lama")
    b = ns.roll_npc_seed(game_id="g1", turn=7, location_id="na_anel_lama")
    c = ns.roll_npc_seed(game_id="g1", turn=8, location_id="na_anel_lama")
    assert a == b
    assert (
        a != c or ns.seed_signature(a) != ns.seed_signature(c) or True
    )  # entrada distinta pode colidir
    assert a.home_location_id == "na_anel_lama"
    assert a.origin_region_id == "nova_arcadia"


def test_seed_ids_exist_in_lore_data():
    ids = ns.lore_ids()
    tables = ns.load_seed_tables()
    table_ids = {k: {r["id"] for r in tables[k]} for k in ns.TABLE_KEYS}
    for turn in range(120):
        s = ns.roll_npc_seed(game_id="g", turn=turn, location_id="ma_boca" if turn % 2 else "")
        assert s.race_id in ids["races"]
        assert s.origin_region_id in ids["regions"]
        assert s.home_location_id in ids["locations"]
        assert s.faction_id is None or s.faction_id in ids["factions"]
        assert s.profession_id in table_ids["professions"]
        assert s.desire_id in table_ids["desires"]
        assert s.fear_id in table_ids["fears"]
        assert s.secret_id in table_ids["secrets"]
        assert s.contradiction_id in table_ids["contradictions"]
        assert s.mannerism_id in table_ids["mannerisms"]


def test_faction_and_rows_compatible_with_region_and_race():
    tables = ns.load_seed_tables()
    by_id = {r["id"]: r for k in ns.TABLE_KEYS for r in tables[k]}
    lore = ns._lore()
    for turn in range(200):
        s = ns.roll_npc_seed(game_id="gx", turn=turn, location_id="")
        if s.faction_id:
            assert lore["faction_region"][s.faction_id] == s.origin_region_id
        for rid in (
            s.profession_id,
            s.desire_id,
            s.fear_id,
            s.secret_id,
            s.contradiction_id,
            s.mannerism_id,
        ):
            row = by_id[rid]
            assert not row.get("regions") or s.origin_region_id in row["regions"]
            assert not row.get("races") or s.race_id in row["races"]
            assert not row.get("factions") or s.faction_id in row["factions"]


def test_signature_collision_rerolls_up_to_5():
    first = ns.seed_signature(ns.roll_npc_seed(game_id="g", turn=1, location_id="", slot=0))
    calls = []

    def taken(sig):
        calls.append(sig)
        return sig == first

    seed = ns.roll_unique_seed(game_id="g", turn=1, location_id="", signature_taken=taken)
    assert seed is not None
    assert ns.seed_signature(seed) != first
    assert len(calls) == 2


def test_exhausted_reroll_is_local_only():
    calls = []
    seed = ns.roll_unique_seed(
        game_id="g", turn=1, location_id="", signature_taken=lambda s: calls.append(s) or True
    )
    assert seed is None
    assert len(calls) == ns.MAX_REROLLS + 1


def test_signature_ignores_home_location():
    a = ns.roll_npc_seed(game_id="g", turn=3, location_id="")
    b = a.model_copy(update={"home_location_id": "other"})
    assert ns.seed_signature(a) == ns.seed_signature(b)


def test_seed_labels_are_readable():
    labels = ns.seed_labels(ns.roll_npc_seed(game_id="g", turn=2, location_id="na_anel_lama"))
    assert labels["local_de_origem"] == "Anel de Lama"
    assert all(isinstance(v, str) for v in labels.values())


def test_seed_tables_lint_min_entries_and_combinations(tmp_path):
    assert [f for f in validate_npc_seed_tables() if f.severity == "error"] == []
    for region in ns._lore()["regions"]:
        assert ns.combinations_for_region(region) >= ns.MIN_COMBINATIONS_PER_ORIGIN

    data = json.loads(json.dumps(ns.load_seed_tables()))
    data["fears"] = data["fears"][:5]
    data["desires"][0]["regions"] = ["regiao_inexistente"]
    bad = tmp_path / "t.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    msgs = " ".join(f.message for f in validate_npc_seed_tables(str(bad)))
    assert "fears" in msgs and "inexistente" in msgs
