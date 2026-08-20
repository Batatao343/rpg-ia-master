"""Smoke local Auth→Postgres→RLS sem imprimir segredos."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastapi.testclient import TestClient


def _create_local_user(email: str, password: str) -> None:
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    response = httpx.post(
        f"{base}/auth/v1/admin/users",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        json={"email": email, "password": password, "email_confirm": True},
        timeout=10,
    )
    response.raise_for_status()


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    if response.status_code != 200:
        raise RuntimeError(f"login local falhou: {response.status_code}")
    return str(response.json()["csrf_token"])


def run() -> dict[str, object]:
    required = ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SERVICE_ROLE_KEY")
    if any(not os.getenv(key) for key in required):
        raise RuntimeError("env local Supabase incompleta")
    os.environ.update({
        "RPG_RUNTIME_PROFILE": "local",
        "DATABASE_URL": os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55322/postgres",
        ),
        "RPG_SESSION_SECRET": "local-smoke-secret-32-characters-minimum",
        "RPG_FORCE_MOCK": "1",
        "RPG_CORS_ORIGINS": "http://localhost:5173",
    })
    from infrastructure.runtime import reset_runtime
    reset_runtime()
    import api

    suffix = uuid4().hex[:12]
    password = "LocalSmoke!2026"
    email_a = f"valoria-a-{suffix}@example.test"
    email_b = f"valoria-b-{suffix}@example.test"
    _create_local_user(email_a, password)
    _create_local_user(email_b, password)
    headers: dict[str, str]
    with TestClient(api.app, base_url="http://localhost:5173") as client_a:
        csrf_a = _login(client_a, email_a, password)
        headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_a}
        options = client_a.get("/data/options").json()
        region = str(options["regions"][0])
        response = client_a.post("/game/new", headers=headers, json={
            "name": "Smoke A", "race": options["races"][0],
            "class_name": options["classes"][0], "region": region,
            "level": 1, "backstory": "", "action_id": str(uuid4()),
        })
        if response.status_code != 200:
            raise RuntimeError(f"new game local falhou: {response.status_code} {response.text[:200]}")
        game_id = str(response.json()["game_id"])
        assert client_a.get(f"/game/state?game_id={game_id}").status_code == 200
        action_id = str(uuid4())
        action_payload = {
            "game_id": game_id, "action_id": action_id,
            "input_text": "Observo a praça e converso com quem estiver por perto.",
        }
        action = client_a.post("/game/action/stream", headers=headers, json=action_payload)
        assert action.status_code == 200 and "event: state" in action.text
        confirmed_turn = client_a.get(f"/game/state?game_id={game_id}").json()["world"]["turn_count"]
        retry = client_a.post("/game/action", headers=headers, json=action_payload)
        assert retry.status_code == 200
        assert retry.json()["world"]["turn_count"] == confirmed_turn

    with TestClient(api.app, base_url="http://localhost:5173") as client_b:
        _login(client_b, email_b, password)
        isolated = client_b.get(f"/game/state?game_id={game_id}")
        assert isolated.status_code == 404
    reset_runtime()
    from observability.telemetry import pseudonym
    return {"auth": True, "turn": True, "owner_isolation": True,
            "game_id_ref": pseudonym(game_id)}


if __name__ == "__main__":
    print(run())
