"""SPEC-351 Etapa 6 — /game/prologue e /game/new com cenário ligado às tramas."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api
import api_core
import persistence
from services import shared_pool as sp
from services.shared_pool_models import PoolNamespace, PoolStatus
from tests.spec297_support import make_store

SECRET = "u" * 40
PAYLOAD = {
    "name": "Kaelen",
    "class_name": "Sangromante",
    "race": "Humano",
    "region": "Nova Arcádia",
    "backstory": "renegado de família nobre",
    "level": 1,
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    monkeypatch.setenv("RPG_SESSION_SECRET", SECRET)
    return TestClient(api.app)


def _prologue(client):
    resp = client.post("/game/prologue", json=PAYLOAD)
    assert resp.status_code == 200
    return resp.json()


def test_prologue_returns_token_and_new_fields(client):
    body = _prologue(client)
    sc = body["scenario"]
    assert body["scenario_token"].count(".") >= 4
    assert sc["seeking"] and sc["thread_refs"] and sc["plot_npc_id"]
    assert sc["personal_npc"]["bond"] and sc["personal_npc"]["name"]


def test_new_game_with_old_scenario_unchanged(client):
    old = {
        "prologue": "p",
        "opening_scene_brief": "Cena velha.",
        "arc_title": "Arco Velho",
        "beats": ["a", "b", "c"],
        "climax": "c",
        "seed_npcs": [{"name": "Velho", "role": "r", "attitude": "aliado", "persona": "p"}],
    }
    resp = client.post("/game/new", json={**PAYLOAD, "scenario": old})
    assert resp.status_code == 200
    state = persistence.load_game_state(persistence.save_path(resp.json()["game_id"]))
    assert "Velho" in state["npcs"]
    assert "opening_thread" not in state["campaign_plan"]


def test_new_game_with_threaded_scenario_writes_thread(client):
    body = _prologue(client)
    resp = client.post(
        "/game/new",
        json={**PAYLOAD, "scenario": body["scenario"], "scenario_token": body["scenario_token"]},
    )
    assert resp.status_code == 200
    state = persistence.load_game_state(persistence.save_path(resp.json()["game_id"]))
    thread = state["campaign_plan"]["opening_thread"]
    assert thread["thread_refs"] == body["scenario"]["thread_refs"]
    assert thread["plot_npc_key"] in state["npcs"]
    personal = state["npcs"][body["scenario"]["personal_npc"]["name"]]
    assert personal["bond"] and personal["seed_motives"]  # semente verificada pelo token


def test_forged_refs_and_plot_npc_are_discarded(client):
    body = _prologue(client)
    forged = dict(body["scenario"], thread_refs=["porta_inventada"], plot_npc_id="npc_valerius")
    resp = client.post("/game/new", json={**PAYLOAD, "scenario": forged})
    assert resp.status_code == 200
    state = persistence.load_game_state(persistence.save_path(resp.json()["game_id"]))
    thread = state["campaign_plan"]["opening_thread"]
    assert "porta_inventada" not in thread["thread_refs"]
    assert thread["plot_npc_key"] != "Valerius" and "npc_valerius" not in {
        n.get("id") for n in state["npcs"].values()
    }
    personal = state["npcs"][body["scenario"]["personal_npc"]["name"]]
    assert "seed_motives" not in personal  # sem token: sem semente verificada


def test_caps_return_422(client):
    body = _prologue(client)
    too_many_refs = dict(body["scenario"], thread_refs=["a", "b", "c"])
    assert client.post("/game/new", json={**PAYLOAD, "scenario": too_many_refs}).status_code == 422
    long_seek = dict(body["scenario"], seeking="x" * 201)
    assert client.post("/game/new", json={**PAYLOAD, "scenario": long_seek}).status_code == 422
    bad_bond = json_bond = dict(body["scenario"])
    bad_bond["personal_npc"] = dict(body["scenario"]["personal_npc"], bond="b" * 301)
    assert client.post("/game/new", json={**PAYLOAD, "scenario": json_bond}).status_code == 422
    huge_token = {**PAYLOAD, "scenario": body["scenario"], "scenario_token": "t" * 1025}
    assert client.post("/game/new", json=huge_token).status_code == 422


def test_submit_after_persist_and_failure_does_not_break_new_game(client, tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "shadow")
    store = make_store(tmp_path)
    monkeypatch.setattr(sp, "get_store", lambda: store)
    order: list[str] = []
    real_save = api_core.save_game_state
    monkeypatch.setattr(
        api_core, "save_game_state", lambda s: (order.append("save"), real_save(s))[1]
    )
    real_submit = sp.submit
    body = _prologue(client)
    mine = body["scenario"]["personal_npc"]["name"]

    def spy(ns, doc, **k):
        if doc.get("name") == mine:
            order.append("submit")
        return real_submit(ns, doc, **k)

    monkeypatch.setattr(sp, "submit", spy)
    payload = {**PAYLOAD, "scenario": body["scenario"], "scenario_token": body["scenario_token"]}
    assert client.post("/game/new", json=payload).status_code == 200
    assert order.index("submit") > max(i for i, v in enumerate(order) if v == "save")
    entries = [
        e
        for e in store.select(namespace=PoolNamespace.NPC, statuses=[PoolStatus.HELD])
        if e.name == mine
    ]
    assert len(entries) == 1 and "bond" not in entries[0].document

    def boom(*a, **k):
        raise RuntimeError("pool caiu")

    monkeypatch.setattr(sp, "submit", boom)
    assert client.post("/game/new", json=payload).status_code == 200


def test_pool_off_means_no_submit_via_api(client, tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "off")
    store = make_store(tmp_path)
    monkeypatch.setattr(sp, "get_store", lambda: store)
    body = _prologue(client)
    payload = {**PAYLOAD, "scenario": body["scenario"], "scenario_token": body["scenario_token"]}
    assert client.post("/game/new", json=payload).status_code == 200
    mine = body["scenario"]["personal_npc"]["name"]
    got = store.select(namespace=PoolNamespace.NPC, statuses=list(PoolStatus))
    assert [e for e in got if e.name == mine] == []
