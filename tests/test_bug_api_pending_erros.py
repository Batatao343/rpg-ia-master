"""SPEC-235 — soft-lock da ação pendente, export unicode, chip do Abismo, backstory nulo."""

from __future__ import annotations

import json
import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import persistence
from infrastructure.postgres_turns import reclaimable


def _row(**kw):
    base = {"game_id": "g", "kind": "turn", "status": "failed", "base_game_version": 3}
    base.update(kw)
    return base


def test_failed_operation_reclaim_after_version_bump():
    # op falhou na versão 3; equip avançou o jogo para 4; mesma chave deve ser re-claimável
    assert reclaimable(_row(), game_id="g", kind="turn", base_version=4)


def test_reclaim_strict_for_running_and_completed_and_foreign():
    assert not reclaimable(_row(status="running"), game_id="g", kind="turn", base_version=4)
    assert not reclaimable(_row(status="completed"), game_id="g", kind="turn", base_version=4)
    assert reclaimable(_row(status="running"), game_id="g", kind="turn", base_version=3)
    assert not reclaimable(_row(), game_id="other", kind="turn", base_version=3)
    assert not reclaimable(_row(), game_id="g", kind="equip", base_version=3)


def test_equip_with_failed_pending_409(monkeypatch):
    import api
    from infrastructure import request_context, runtime

    gid = str(uuid.uuid4())
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr(api, "_failed_pending_operation", lambda state: "op-falha")
    monkeypatch.setattr(
        request_context, "current_principal", lambda: SimpleNamespace(user_id=uuid.uuid4())
    )
    coordinator = SimpleNamespace(
        receipt=lambda *a, **k: None,
        claim=lambda *a, **k: pytest.fail("claim não deve ocorrer com pendência falha"),
    )
    monkeypatch.setattr(
        runtime, "get_runtime", lambda: SimpleNamespace(turn_coordinator=coordinator)
    )
    with pytest.raises(HTTPException) as err:
        api._begin_state_mutation(
            {"game_id": gid}, action_id=str(uuid.uuid4()), kind="equip", payload={}
        )
    assert err.value.status_code == 409
    assert err.value.detail["code"] == "pending_operation"
    assert err.value.detail["operation_id"] == "op-falha"


def test_death_not_gated_by_failed_pending(monkeypatch):
    import api
    from infrastructure import request_context, runtime

    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr(
        api, "_failed_pending_operation", lambda state: pytest.fail("death não é gated")
    )
    monkeypatch.setattr(
        request_context, "current_principal", lambda: SimpleNamespace(user_id=uuid.uuid4())
    )
    sentinel = object()
    coordinator = SimpleNamespace(receipt=lambda *a, **k: None, claim=lambda *a, **k: sentinel)
    monkeypatch.setattr(
        runtime, "get_runtime", lambda: SimpleNamespace(turn_coordinator=coordinator)
    )
    claim, _, receipt = api._begin_state_mutation(
        {"game_id": str(uuid.uuid4())}, action_id=str(uuid.uuid4()), kind="death", payload={}
    )
    assert claim is sentinel and receipt is None


@pytest.fixture()
def client(monkeypatch):
    import api

    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    from fastapi.testclient import TestClient

    return TestClient(api.app)


def test_chronicle_export_unicode_name(client, tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = str(uuid.uuid4())
    data = {
        "schema_version": persistence.SCHEMA_VERSION,
        "game_id": gid,
        "game_over": False,
        "player": {
            "name": "Дмитрий",
            "class_name": "Sangromante",
            "level": 1,
            "inventory": [],
            "known_abilities": [],
        },
        "world": {"current_location": "Nova Arcádia", "world_clock": {"day": 1, "period": "Manhã"}},
        "chronicle": [],
        "message_history": [],
    }
    with open(os.path.join(str(tmp_path), f"{gid}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    r = client.get("/game/chronicle/export", params={"game_id": gid})
    assert r.status_code == 200
    header = r.headers["content-disposition"]
    header.encode("latin-1")
    assert 'filename="cronica_cronica.txt"' in header
    assert "filename*=UTF-8''cronica_%D0%94" in header


def test_abyss_tier_hidden_zero():
    import api

    medico = {"class_name": "Médico de Campo", "abyss_charge": 0, "max_entropy": 10, "entropy": 10}
    assert api._abyss_tier_view(medico) == "nenhum"
    assert api._abyss_tier_view(dict(medico, abyss_charge=5)) == "?"


def test_backstory_null():
    import api

    req = api.CreateCharacterRequest(
        name="Kaelen",
        race="Humano",
        class_name="Sangromante",
        region="Nova Arcádia",
        backstory=None,
    )
    assert (req.backstory or "") == ""
    import inspect

    src = inspect.getsource(api)
    assert "{req.backstory}" not in src
