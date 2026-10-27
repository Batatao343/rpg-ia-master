"""SPEC-337 R16/R17/R18 contra GoTrue + Postgres (RLS) reais.

Roda só com ``RPG_AUDIT_BROWSER_URL`` (API local do ``audit_local_gate``). Omissões
documentadas: ``/account/checkout/{order_id}`` (criar pedido exige Stripe/rede) e a
semente de uma geração de arte ``ready`` (L2 contra Postgres) — ambos ficam cobertos
só no offline (``test_http_idor_offline.py``).
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
import pytest

from infrastructure.contracts import Principal
from tests.fakes.local_auth import create_confirmed_user, delete_confirmed_user
from tests.test_http_idor_offline import _ROUTES
from tests.test_postgres_jobs_local import infra  # noqa: F401

pytestmark = [pytest.mark.infra_local, pytest.mark.security_local]

PASSWORD = "LocalAuditOnly-2026!"


def _login(base: str, email: str) -> httpx.Client:
    client = httpx.Client(base_url=base, timeout=30, trust_env=False)
    login = client.post(
        "/auth/login", headers={"Origin": base}, json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    client.headers.update({"Origin": base, "X-CSRF-Token": login.json()["csrf_token"]})
    return client


def _new_game(client: httpx.Client, name: str) -> UUID:
    options = client.get("/data/options").json()
    created = client.post(
        "/game/new",
        json={
            "name": name,
            "race": options["races"][0],
            "class_name": options["classes"][0],
            "region": options["regions"][0],
            "action_id": str(uuid4()),
        },
    )
    assert created.status_code == 200, created.text
    return UUID(created.json()["game_id"])


@pytest.fixture
def duo(infra):  # noqa: F811
    base = os.getenv("RPG_AUDIT_BROWSER_URL")
    if not base:
        pytest.skip("local audit API required")
    assert urlsplit(base).hostname in {"127.0.0.1", "localhost"}
    store, _, coordinator, _ = infra
    users: list[UUID] = []
    clients: list[httpx.Client] = []
    games: list[tuple[Principal, UUID]] = []
    try:
        emails = [f"idor-{who}-{uuid4().hex}@example.test" for who in ("a", "b")]
        for email in emails:
            users.append(create_confirmed_user(email, PASSWORD))
        client_a, client_b = (_login(base, email) for email in emails)
        clients += [client_a, client_b]
        principal_a = Principal(users[0], "test", str(users[0]), local=True)
        seed = f"Semente-{uuid4().hex[:8]}"
        game_a = _new_game(client_a, seed)
        games.append((principal_a, game_a))
        yield {
            "a": client_a,
            "b": client_b,
            "principal_a": principal_a,
            "game_a": game_a,
            "seed": seed,
            "store": store,
            "coordinator": coordinator,
            "track": lambda game: games.append((principal_a, game)),
        }
    finally:
        for client in clients:
            client.close()
        for principal, game in games:
            store.delete(principal, game)
        for user in users:
            delete_confirmed_user(user)


@pytest.mark.parametrize(
    "method,path,body", _ROUTES, ids=[f"{m} {p.split('?')[0]}" for m, p, _ in _ROUTES]
)
def test_principal_b_cannot_touch_game_a_local(duo, method, path, body):
    gid = str(duo["game_a"])
    # controle positivo (L3): A lê a própria campanha na mesma execução.
    assert duo["a"].get("/game/state", params={"game_id": gid}).status_code == 200
    url = path.replace("{g}", gid)
    kwargs = {}
    if body is not None:
        kwargs["json"] = {
            k: (v.replace("{g}", gid) if isinstance(v, str) else v) for k, v in body.items()
        }
    before = duo["store"].get(duo["principal_a"], duo["game_a"])
    response = duo["b"].request(method, url, headers={"Idempotency-Key": str(uuid4())}, **kwargs)
    assert response.status_code in {400, 403, 404, 409}, (method, path, response.text[:200])
    assert duo["seed"] not in response.text
    after = duo["store"].get(duo["principal_a"], duo["game_a"])
    assert after is not None and after.version == before.version


def test_delete_key_reuse_conflicts_on_postgres(duo):
    """R17: key de um turno concluído reaproveitada no DELETE -> 409; o jogo permanece."""
    key = uuid4()
    game = duo["game_a"]
    claim = duo["coordinator"].claim(
        duo["principal_a"],
        key,
        game_id=game,
        kind="turn",
        request_hash="a" * 64,
        base_version=1,
    )
    duo["coordinator"].complete(claim, committed_version=1, receipt={"ok": "turno"})
    out = duo["a"].delete(f"/game/save/{game}", headers={"Idempotency-Key": str(key)})
    assert out.status_code == 409, out.text
    assert out.json()["detail"] == "operation_request_mismatch"
    assert duo["store"].get(duo["principal_a"], game) is not None

    # retry legítimo do MESMO delete segue idempotente (guarda do game_id=None).
    spare = _new_game(duo["a"], "Descartavel")
    duo["track"](spare)
    retry_key = str(uuid4())
    first = duo["a"].delete(f"/game/save/{spare}", headers={"Idempotency-Key": retry_key})
    again = duo["a"].delete(f"/game/save/{spare}", headers={"Idempotency-Key": retry_key})
    assert first.status_code == 200 and again.status_code == 200, (first.text, again.text)
    assert again.json() == {"ok": True}
    # a mesma key apontando para OUTRA campanha é recusada.
    mismatch = duo["a"].delete(f"/game/save/{game}", headers={"Idempotency-Key": retry_key})
    assert mismatch.status_code == 409


def test_art_quality_cross_game_on_postgres(duo):
    """R18 no Postgres: precisa de uma geração `ready` semeável sem rede."""
    pytest.skip("sem geração de arte 'ready' semeável sem rede nesta stack; coberto offline")
