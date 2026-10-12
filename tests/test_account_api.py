"""SPEC-185 HTTP owner boundary and narrative fallback."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

import api
from infrastructure.contracts import Principal, Unauthorized
from infrastructure.request_context import current_principal


def test_account_requires_session_and_never_uses_client_owner(monkeypatch):
    a, b = uuid4(), uuid4()

    class Identity:
        def verify(self, cookie):
            if cookie == "a":
                return Principal(a, "test", str(a))
            if cookie == "b":
                return Principal(b, "test", str(b))
            raise Unauthorized("sessão ausente")

    runtime = SimpleNamespace(identity_verifier=Identity(),
                              game_store=SimpleNamespace(pool=object()))
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: runtime)

    class Reader:
        def __init__(self, _pool):
            pass

        def balance(self, principal):
            return {"available_milli": "10" if principal.user_id == a else "20",
                    "reserved_milli": "0"}

        def history_costs(self, principal, game_id, entries):
            assert principal.user_id == a and str(game_id) == gid
            assert len(entries) == 1
            return {"entry-a": {"cost_milli": "7", "technical_cost_usd": "0.000000007",
                                 "technical_cost_basis": "usage_ledger",
                                 "technical_cost_exact": True}}

    monkeypatch.setattr("infrastructure.account_read_model.PostgresAccountReader", Reader)
    gid = str(uuid4())
    state = {"game_id": gid, "continuity": {"timeline_epoch": 1},
             "presentation_history": [{"id": "entry-a", "epoch": 1, "turn": 4,
                                        "role": "narrator", "text": "A", "type": "STORY"}]}
    monkeypatch.setattr(api, "load_game_state", lambda _path: state if current_principal().user_id == a else None)
    client = TestClient(api.app)
    assert client.get("/account/balance").status_code == 401
    assert client.get("/account/balance", cookies={"rpg_access": "a"}).json()["available_milli"] == "10"
    assert client.get("/account/balance", cookies={"rpg_access": "b"}).json()["available_milli"] == "20"
    good = client.get(f"/game/history?game_id={gid}", cookies={"rpg_access": "a"})
    assert good.status_code == 200 and good.json()["entries"][0]["cost_milli"] == "7"
    assert good.json()["entries"][0]["technical_cost_usd"] == "0.000000007"
    assert "cost_milli" not in state["presentation_history"][0]
    assert client.get(f"/game/history?game_id={gid}", cookies={"rpg_access": "b"}).status_code == 404


def test_history_survives_financial_projection_failure(monkeypatch):
    owner = uuid4()
    gid = str(uuid4())
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: SimpleNamespace(
        identity_verifier=SimpleNamespace(verify=lambda _cookie: Principal(owner, "test", str(owner))),
        game_store=SimpleNamespace(pool=object())))
    monkeypatch.setattr(api, "load_game_state", lambda _path: {
        "game_id": gid, "continuity": {"timeline_epoch": 0},
        "presentation_history": [{"id": "entry", "epoch": 0, "turn": 1,
                                  "role": "narrator", "text": "A história continua", "type": "STORY"}],
    })

    def fail(*_args):
        raise RuntimeError("read model down")

    monkeypatch.setattr("infrastructure.account_read_model.PostgresAccountReader.history_costs", fail)
    response = TestClient(api.app).get(f"/game/history?game_id={gid}")
    assert response.status_code == 200
    assert response.json()["entries"][0]["text"] == "A história continua"
    assert response.json()["entries"][0]["cost_milli"] is None
