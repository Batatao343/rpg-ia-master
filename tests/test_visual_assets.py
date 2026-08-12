from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage


def _state(*, npcs: dict | None = None, location_id: str = "nova_arcadia") -> dict:
    return {
        "game_id": "00000000-0000-0000-0000-000000000001",
        "world": {"current_location_id": location_id, "current_location": "Nova Arcádia"},
        "npcs": npcs or {},
        "visual_seen_entity_ids": [],
        "visual_cue_ledger": [],
        "messages": [AIMessage(content="A cena muda.")],
    }


def test_catalog_has_all_creation_art_and_only_canonical_public_assets():
    from services.visual_catalog import load_visual_catalog

    catalog = load_visual_catalog()
    assert set(catalog["creation"]["races"]) == {
        "race_humanos", "race_elfos", "race_anoes_fuligem",
        "race_vrel", "race_cinzeus", "race_osshari",
    }
    assert set(catalog["creation"]["classes"]) == {
        "Devoto do Abismo", "Sangromante", "Corruptor",
        "Arcanista Cinzento", "Médico de Campo",
    }
    assert all(a["visibility"] == "public" for a in catalog["assets"])
    assert all(str(a["variants"]["display"]["url"]).startswith("/art/v1/")
               for a in catalog["assets"])


def test_catalog_files_exist_match_hash_and_respect_budget():
    from services.visual_catalog import WEB_PUBLIC, load_visual_catalog, sha256_file

    catalog = load_visual_catalog()
    for asset in catalog["assets"]:
        for role, variant in asset["variants"].items():
            path = WEB_PUBLIC / variant["url"].removeprefix("/")
            assert path.is_file(), (asset["asset_id"], role)
            assert sha256_file(path) == variant["sha256"]
            assert path.stat().st_size == variant["bytes"]
            ceiling = 120_000 if role == "thumbnail" else (
                400_000 if asset["subject_type"] == "location" else 300_000
            )
            assert variant["bytes"] <= ceiling, (asset["asset_id"], role)


def test_visual_catalog_passes_integrated_content_lint():
    from services.content_validator import validate_visual_assets

    assert validate_visual_assets() == []


def test_scene_uses_exact_then_explicit_regional_fallback():
    from services.visual_catalog import scene_visual

    exact = scene_visual({"current_location_id": "nova_arcadia"})
    assert exact["scope"] == "exact"
    assert exact["asset"]["subject_id"] == "nova_arcadia"

    fallback = scene_visual({"current_location_id": "pm_profundezas"})
    assert fallback["scope"] == "regional"
    assert fallback["location_id"] == "pm_profundezas"
    assert fallback["asset"]["subject_id"] == "pantano_melancolia"


def test_npc_cue_uses_structured_state_not_narrative_text():
    from services.visual_catalog import resolve_turn_visual_state, visual_response

    previous = _state()
    current = _state(npcs={
        "Grum": {"id": "npc_grum", "name": "Grum", "known_by_player": True,
                  "in_scene": True, "role": "Taverneiro"},
    })
    update = resolve_turn_visual_state(previous, current, action_key="turn:1")
    current.update(update)
    response = visual_response(current, cue_action_key="turn:1")
    assert response["cue"]["subject_id"] == "npc_grum"
    assert response["cue"]["asset"]["asset_id"] == "VAL-P2-NPC-GRUM-001"

    only_text = _state()
    only_text["messages"] = [AIMessage(content="Grum talvez exista em algum rumor.")]
    no_cue = resolve_turn_visual_state(previous, only_text, action_key="turn:2")
    assert no_cue["visual_cue_ledger"][-1]["cue"] is None


def test_npc_cue_is_once_and_retry_safe():
    from services.visual_catalog import resolve_turn_visual_state, visual_response

    previous = _state()
    current = _state(npcs={
        "Grum": {"id": "npc_grum", "name": "Grum", "known_by_player": True,
                  "in_scene": True},
    })
    current.update(resolve_turn_visual_state(previous, current, action_key="same"))
    first = visual_response(current, cue_action_key="same")
    retry = visual_response(current, cue_action_key="same")
    assert first["cue"] == retry["cue"]

    later = dict(current)
    later.update(resolve_turn_visual_state(current, later, action_key="later"))
    assert visual_response(later, cue_action_key="later")["cue"] is None
    assert visual_response(later, cue_action_key=None)["cue"] is None


def test_active_npc_has_priority_and_runtime_npc_gets_honest_fallback():
    from services.visual_catalog import resolve_turn_visual_state

    previous = _state()
    current = _state(npcs={
        "Pessoa Nova": {"name": "Pessoa Nova", "known_by_player": True,
                        "in_scene": True, "role": "Viajante"},
        "Grum": {"id": "npc_grum", "name": "Grum", "known_by_player": True,
                  "in_scene": True},
    })
    current["active_npc_name"] = "Pessoa Nova"
    update = resolve_turn_visual_state(previous, current, action_key="a")
    cue = update["visual_cue_ledger"][-1]["cue"]
    assert cue["subject_name"] == "Pessoa Nova"
    assert cue["asset_id"] is None
    assert cue["fallback"] is True
    assert len(update["visual_seen_entity_ids"]) == 1


def test_entity_identity_handles_accents_punctuation_and_explicit_id():
    from services.entity_identity import resolve_npc_entity_id

    assert resolve_npc_entity_id({"id": "npc_grum", "name": "Outro"}) == "npc_grum"
    assert resolve_npc_entity_id({}, "Aelwin o ultimo conselheiro") == (
        "npc_aelwin_o_ultimo_conselheiro"
    )
    assert resolve_npc_entity_id({}, "Khatarn Olhos de Obsidiana") == (
        "npc_khatarn_olhos_de_obsidiana"
    )


def test_save_v5_migrates_visual_fields_and_roundtrips(tmp_path, monkeypatch):
    import persistence

    raw = {"schema_version": 5, "game_id": "00000000-0000-0000-0000-000000000001",
           "player": {}, "party": [], "enemies": []}
    migrated = persistence.migrate_state(raw)
    assert migrated["schema_version"] == 6
    assert migrated["visual_seen_entity_ids"] == []
    assert migrated["visual_cue_ledger"] == []

    state = _state()
    state.update({"player": {}, "party": [], "enemies": [],
                  "visual_seen_entity_ids": ["npc:npc_grum"],
                  "visual_cue_ledger": [{"action_key": "a", "cue": None}]})
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(str(tmp_path / f"{state['game_id']}.json"))
    assert loaded["visual_seen_entity_ids"] == ["npc:npc_grum"]
    assert loaded["visual_cue_ledger"] == [{"action_key": "a", "cue": None}]


def test_importer_rejects_hash_mismatch_before_writing(tmp_path):
    from scripts.import_visual_assets import verify_source_entry

    source = tmp_path / "source.png"
    source.write_bytes(b"not the expected bytes")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_source_entry(source, "0" * 64)


def test_frontend_contract_contains_visual_flow():
    root = Path(__file__).resolve().parents[1] / "web" / "src"
    app = (root / "App.tsx").read_text(encoding="utf-8")
    create = (root / "components" / "CreateScreen.tsx").read_text(encoding="utf-8")
    story = (root / "components" / "StoryLog.tsx").read_text(encoding="utf-8")
    play = (root / "components" / "PlayScreen.tsx").read_text(encoding="utf-8")
    assert "visual: r.visual?.cue" in app
    assert "visuals?.races" in create and "visuals?.classes" in create
    assert "VisualArtwork" in story
    assert "SceneArtwork" in play
