"""SPEC-215 §4 passo 2 — campos aditivos do ledger (SEM bump de schema).

Regra da onda: SCHEMA_VERSION fica em 8; o ledger é aditivo com default no load.
Save v8 real carrega com ledger vazio + `legacy_knowledge=True`; round-trip
preserva os links; save adulterado normaliza sem crash; nenhuma distribuição
retroativa.
"""
from __future__ import annotations

import copy
import json
import os

import persistence
from services import npc_knowledge as nk

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "save_v8_pre_spec202.json")


def _fixture() -> dict:
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def test_schema_version_not_bumped():
    assert persistence.SCHEMA_VERSION == 8


def test_v8_save_loads_with_empty_ledger_and_legacy_flag():
    state = persistence._raw_to_state(_fixture())
    assert state["knowledge_links"] == []
    assert state["knowledge_queue"] == []
    assert state["location_heard"] == {}
    assert state["legacy_knowledge"] is True


def test_v8_save_with_past_events_is_not_distributed(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    raw = _fixture()
    raw["event_log"] = [{"event_id": "ev_old", "turn": 1, "type": "npc_killed",
                         "actor_id": "player", "target_id": "npc_valerius",
                         "payload": {}, "source": "combat"}]
    state = persistence._raw_to_state(raw)
    out = nk.turn_updates(state)
    assert not out.get("knowledge_links") and not out.get("knowledge_queue")


def test_roundtrip_preserves_links_byte_for_byte():
    state = persistence._raw_to_state(_fixture())
    state["legacy_knowledge"] = False
    state["knowledge_links"] = [{
        "link_id": "abc", "holder_id": "npc:npc_mv_brunna_ponte_alta",
        "subject_kind": "event", "subject_id": "ev1", "relation": "observed_by",
        "source": "world", "channel": "witness", "hops": 0,
        "acquired_clock": 12, "acquired_turn": 3, "location_id": "brekmar"}]
    state["knowledge_queue"] = [{
        "delivery_id": "d1", "subject_kind": "event", "subject_id": "ev1",
        "from_location_id": "brekmar", "to_location_id": "ophidia", "hop": 1,
        "due_clock": 17, "created_turn": 3, "origin_location_id": "brekmar",
        "origin_clock": 12}]
    state["location_heard"] = {"brekmar": ["ev1"]}
    first = json.dumps(persistence._state_to_save_data(state, state["game_id"]),
                       sort_keys=True, ensure_ascii=False, default=str)
    loaded = persistence._raw_to_state(json.loads(first))
    second = json.dumps(persistence._state_to_save_data(loaded, loaded["game_id"]),
                        sort_keys=True, ensure_ascii=False, default=str)
    assert first == second
    assert loaded["knowledge_links"] == state["knowledge_links"]
    assert loaded["legacy_knowledge"] is False
    assert json.loads(first)["schema_version"] == 8


def test_tampered_save_normalizes_without_crash():
    raw = _fixture()
    raw["knowledge_links"] = [
        "lixo", 42, None,
        {"holder_id": "npc:x", "subject_kind": "event", "subject_id": "e",
         "relation": "sabe_tudo", "channel": "witness", "hops": 0, "acquired_clock": 1},
        {"holder_id": "npc:x", "subject_kind": "event", "subject_id": "e",
         "relation": "told_to", "channel": "messenger", "hops": 9, "acquired_clock": 1},
        {"holder_id": "npc:x", "subject_kind": "event", "subject_id": "e",
         "relation": "told_to", "channel": "messenger", "hops": "1",
         "acquired_clock": "7", "source": "loc:brekmar"},
    ]
    raw["knowledge_queue"] = {"nao": "lista"}
    raw["location_heard"] = ["errado"]
    raw["legacy_knowledge"] = "sim"
    state = persistence._raw_to_state(copy.deepcopy(raw))
    assert len(state["knowledge_links"]) == 1
    link = state["knowledge_links"][0]
    assert link["hops"] == 1 and link["acquired_clock"] == 7 and link["link_id"]
    assert state["knowledge_queue"] == [] and state["location_heard"] == {}
    assert isinstance(state["legacy_knowledge"], bool)
