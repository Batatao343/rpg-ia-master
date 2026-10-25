"""SPEC-312 Etapa 4: propagacao do boato pelo ledger da SPEC-215 (sempre `[BOATO]`)."""

from __future__ import annotations

import pytest

from services import npc_knowledge as nk
from services import rumors
from tests.spec312_helpers import base_state, make_rumor


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_RUMORS", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")


def _npc(name, home):
    return {
        name: {
            "name": name,
            "id": "npc_" + name.lower(),
            "home_location_id": home,
            "location": home,
            "in_scene": False,
            "memory": [],
            "relationship": 5,
        }
    }


def _state(day=5, loc="nova_arcadia", turn=5, **extra):
    st = base_state(day, loc, **extra)
    st["world"]["turn_count"] = turn
    return st


def _seeded(loc="na_anel_dourado", seed="rumor_valerius_nao_come_nem_dorme", **kw):
    sim: dict = {}
    item = make_rumor(sim, seed, loc=loc, day=5, turn=5, **kw)
    st = _state(npcs={**_npc("Mara", loc), **_npc("Tomas", "brekmar")}, world_sim=sim)
    return st, sim, item


def test_rumor_subject_kind_roundtrip_and_legacy_save():
    assert "rumor" in nk.SUBJECT_KINDS
    link = {
        "holder_id": "npc:mara",
        "subject_kind": "rumor",
        "subject_id": "abc",
        "relation": "told_to",
        "channel": "local_rumor",
        "hops": 0,
        "acquired_clock": 3,
    }
    out = nk.normalize_knowledge({"knowledge_links": [link]}, legacy_default=False)
    assert out["knowledge_links"][0]["subject_kind"] == "rumor"
    bad = nk.normalize_knowledge(
        {"knowledge_links": [dict(link, subject_kind="alien")]}, legacy_default=False
    )
    assert bad["knowledge_links"] == []
    assert nk.normalize_knowledge({}, legacy_default=False)["knowledge_links"] == []


def test_turn_updates_seeds_birth_location_and_schedules():
    st, _sim, item = _seeded()
    upd = nk.turn_updates(st)
    rid = item["subject_id"]
    assert rid in upd["location_heard"]["na_anel_dourado"]
    holders = {
        lk["holder_id"]
        for lk in upd["knowledge_links"]
        if lk["subject_id"] == rid and lk["channel"] == "local_rumor"
    }
    assert holders == {"npc:npc_mara"}
    # idempotente: segundo passe nao muda nada
    st2 = {**st, **upd}
    assert nk.turn_updates(st2) == {}


def test_born_in_another_turn_is_not_reseeded():
    st, _sim, _item = _seeded()
    st["world"]["turn_count"] = 9
    assert nk.turn_updates(st) == {}


def test_delivery_creates_only_told_to():
    st, _sim, item = _seeded(loc="brekmar")
    st["world"]["current_location_id"] = "brekmar"
    delivery = {
        "delivery_id": "d1",
        "subject_kind": "rumor",
        "subject_id": item["subject_id"],
        "from_location_id": "brekmar",
        "to_location_id": "brekmar",
        "hop": 1,
        "due_clock": 1,
        "created_turn": 5,
    }
    st["npcs"] = _npc("Tomas", "brekmar")
    st["knowledge_queue"] = [delivery]
    out = nk.deliver_due(st, 99)
    rels = {
        lk["relation"] for lk in out["knowledge_links"] if lk["subject_id"] == item["subject_id"]
    }
    assert rels == {"told_to"}


def test_label_always_boato_even_if_observed():
    st, _sim, item = _seeded()
    rid = item["subject_id"]
    for relations in (["told_to"], ["observed_by", "told_to"], ["believed_by"]):
        links = [
            nk._link(
                "npc:npc_mara",
                "rumor",
                rid,
                rel,
                source="loc:x",
                channel="local_rumor",
                hops=0,
                clock=1,
                turn=5,
                location_id="na_anel_dourado",
            )
            for rel in relations
        ]
        state = {**st, "knowledge_links": links}
        lines = nk.knowledge_lines(state, "Mara")
        assert lines and lines[0][1].startswith("[BOATO, não confirmado]")
        assert "[VIU]" not in lines[0][1]


def test_secret_rumor_never_propagates(monkeypatch):
    import services.memory_provenance as mp

    st, _sim, _item = _seeded()
    monkeypatch.setattr(mp, "find_strict_unrevealed", lambda text, state: "segredo")
    assert nk.turn_updates(st) == {}


def test_expired_rumor_drops_from_npc_context():
    st, _sim, item = _seeded()
    upd = nk.turn_updates(st)
    st = {**st, **upd}
    assert nk.knowledge_lines(st, "Mara")
    st["world"] = {**st["world"], "world_clock": {"day": 30, "period": "Manhã"}}
    assert nk.knowledge_lines(st, "Mara") == []
    assert rumors.text_for(st, item["subject_id"]) == ""


def test_rumor_reaches_neighbor_and_becomes_perceivable_there():
    st, _sim, item = _seeded(loc="nova_arcadia")
    rid = item["subject_id"]
    st["knowledge_queue"] = [
        {
            "delivery_id": "d-nb",
            "subject_kind": "rumor",
            "subject_id": rid,
            "from_location_id": "nova_arcadia",
            "to_location_id": "brekmar",
            "hop": 1,
            "due_clock": 1,
            "created_turn": 5,
        }
    ]
    out = nk.deliver_due(st, 99)
    assert rid in out["location_heard"]["brekmar"]
    # o heroi chega em Brekmar: o rumor de Nova Arcadia agora e ouvido la (canal b)
    hero = {**st, **out, "world": dict(st["world"], current_location_id="bk_docas_velhas")}
    hero["location_heard"] = {"bk_docas_velhas": [rid]}
    assert rumors.channel_of(hero, item) == "b"


def test_inherit_local_gives_new_npc_the_rumor_as_boato():
    st, _sim, item = _seeded()
    upd = nk.turn_updates(st)
    st = {**st, **upd}
    links = nk.inherit_local(st, "Novato", "na_anel_dourado", 9)
    assert any(lk["subject_kind"] == "rumor" and lk["relation"] == "told_to" for lk in links)
