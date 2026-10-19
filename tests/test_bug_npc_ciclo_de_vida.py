"""SPEC-230 — NPC: guard de geração, ciclo de vida e relação em Python."""

import logging

from langchain_core.messages import AIMessage, HumanMessage

import agents.npc as npc_mod
from agents.npc import clamp_relationship_change, npc_actor_node
from services import npc_layers


class _AILLM:
    def with_structured_output(self, schema):
        return self

    def invoke(self, *_a, **_k):
        return AIMessage(content="erro: todos os providers falharam")


def _patch_gen(monkeypatch, llm, saved):
    monkeypatch.setattr(npc_mod, "load_npc_db", lambda: {})
    monkeypatch.setattr(npc_mod, "find_existing_entity", lambda *a, **k: None)
    monkeypatch.setattr(npc_mod, "query_rag", lambda *a, **k: "")
    monkeypatch.setattr(npc_mod, "get_llm", lambda *a, **k: llm)
    monkeypatch.setattr(npc_mod, "save_npc_template", lambda d: saved.append(d))


def test_generate_new_npc_aimessage_not_persisted(monkeypatch):
    saved = []
    _patch_gen(monkeypatch, _AILLM(), saved)
    data = npc_mod.generate_new_npc("Borin", "Local: Praça")
    assert data["role"] == "Desconhecido" and data["persona"]
    assert saved == []


def test_generate_new_npc_valid_llm_still_saves(monkeypatch):
    saved = []

    class _OK:
        def with_structured_output(self, s):
            return self

        def invoke(self, *_a, **_k):
            return npc_mod.NPCSchema(
                **{
                    "name": "Borin",
                    "role": "Ferreiro",
                    "persona": "Taciturno",
                    "location": "Praça",
                    "appearance": "Robusto",
                    "attributes": {
                        "str": 12,
                        "dex": 10,
                        "con": 12,
                        "int": 10,
                        "wis": 10,
                        "cha": 10,
                    },
                }
            )

    _patch_gen(monkeypatch, _OK(), saved)
    data = npc_mod.generate_new_npc("Borin", "Local: Praça")
    assert data["role"] == "Ferreiro"
    assert len(saved) == 1


def test_dead_npc_not_in_scene_or_context():
    grum = {"status": "morto", "in_scene": False, "home_location_id": "nova_arcadia"}
    st = {"npcs": {"Grum": grum}, "party": [], "world": {"current_location_id": "nova_arcadia"}}
    assert npc_layers.npcs_for_context(st) == []
    st2 = {
        "npcs": {"Grum": {**grum, "in_scene": True}},
        "party": [],
        "world": {"current_location_id": "nova_arcadia"},
    }
    assert npc_layers.npcs_in_scene(st2) == []
    assert not npc_layers.npc_alive({"dead": True})
    view = npc_layers.visible_npc_view({"Grum": {**grum, "name": "Grum"}})
    assert view[0]["status"] == "morto"


def test_npc_actor_dead_target_says_dead():
    st = {
        "messages": [HumanMessage(content="Falo com Grum")],
        "active_npc_name": "Grum",
        "game_id": "g",
        "npcs": {"Grum": {"name": "Grum", "status": "morto", "in_scene": True}},
        "party": [],
        "world": {"current_location": "Praça", "current_location_id": "praca"},
    }
    out = npc_actor_node(st)
    assert "morto" in out["messages"][0].content


def test_npc_killed_syncs_state_npcs_and_party():
    npcs, party = npc_layers.apply_npc_death(
        {"Valerius": {"name": "Valerius", "id": "npc_valerius", "in_scene": True}},
        [{"name": "Valerius", "active": True}, {"name": "Gorim", "active": True}],
        "npc_valerius",
        7,
    )
    assert npcs["Valerius"]["status"] == "morto" and npcs["Valerius"]["in_scene"] is False
    assert npcs["Valerius"]["died_turn"] == 7
    assert [c["name"] for c in party] == ["Gorim"]


def test_process_pending_events_npc_killed_syncs(monkeypatch):
    from services import event_processor as ep
    from services.world_validators import ValidationResult

    monkeypatch.setattr(ep, "validate_proposal", lambda *a, **k: ValidationResult(True))
    state = {
        "pending_world_events": [
            {"type": "npc_killed", "actor_id": "player", "target_id": "npc_valerius"}
        ],
        "npcs": {"Valerius": {"name": "Valerius", "id": "npc_valerius", "in_scene": True}},
        "party": [{"name": "Valerius", "active": True}],
        "world": {"turn_count": 3},
        "event_log": [],
        "world_projection": {},
    }
    out = ep.process_pending_events(state)
    assert out["npcs"]["Valerius"]["status"] == "morto"
    assert out["party"] == []


def test_waiting_companion_only_talks_at_waiting_location():
    st = {
        "messages": [HumanMessage(content="Oi Lyra")],
        "active_npc_name": "Lyra",
        "game_id": "g",
        "npcs": {},
        "party": [{"name": "Lyra", "active": False, "waiting_at": "Brekmar"}],
        "world": {"current_location": "Pântano", "current_location_id": "pantano"},
    }
    out = npc_actor_node(st)
    assert "não está aqui" in out["messages"][0].content


def test_relationship_zero_is_zero():
    import party

    npc = {"name": "Ark", "relationship": 0, "traits": []}
    st = {"npcs": {"Ark": npc}, "party": [], "factions": []}
    d = party.recruitment_decision(st, "Ark")
    assert d["relationship"] == 0 and d["ok"] is False
    assert party._relationship({"relationship": 0}) == 0
    assert party._relationship({}) == 5


def test_relationship_change_clamped(caplog):
    with caplog.at_level(logging.INFO):
        assert clamp_relationship_change(5, "X") == 1
        assert clamp_relationship_change(-4, "X") == -1
        assert clamp_relationship_change(0) == 0
    assert any("relationship_clamped" in r.name for r in caplog.records)


def test_npc_fallback_hint_cleared():
    from agents.router import RouteType, _base_route_payload

    p = _base_route_payload(RouteType.STORY, {})
    assert "npc_fallback_hint" in p and p["npc_fallback_hint"] is None


def test_load_npc_db_discards_broken_entries(monkeypatch, caplog):
    good = {"id": "npc_a", "name": "A", "role": "Ferreiro", "persona": "x"}
    raw = {
        "A": good,
        "B": {"id": "npc_b", "name": "B", "role": None, "persona": None},
        "C": {"id": "fallback", "name": "C", "role": "Desconhecido", "persona": "Genérico"},
    }
    monkeypatch.setattr(npc_mod, "_load_npc_db_raw", lambda: raw)
    with caplog.at_level(logging.WARNING):
        db = npc_mod.load_npc_db()
    assert db == {"A": good}
    assert any("descartada" in r.getMessage() for r in caplog.records)


def test_smoke_invalid_structured_output_leaves_cache_clean(monkeypatch, tmp_path):
    import json

    f = tmp_path / "npc.json"
    f.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(npc_mod, "NPC_DB_FILE", str(f))
    monkeypatch.setattr(npc_mod, "find_existing_entity", lambda *a, **k: None)
    monkeypatch.setattr(npc_mod, "query_rag", lambda *a, **k: "")
    monkeypatch.setattr(npc_mod, "get_llm", lambda *a, **k: _AILLM())
    data = npc_mod.generate_new_npc("Borin", "Local: x")
    assert data["role"] == "Desconhecido"
    assert json.loads(f.read_text(encoding="utf-8")) == {}
