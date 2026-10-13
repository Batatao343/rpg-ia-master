"""SPEC-189 HTTP auth/CSRF, strict client body and external signature boundary."""
import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

import api
from infrastructure.contracts import Principal, Unauthorized
from services.auth_sessions import CsrfSigner
from tests.test_stripe_checkout import SECRET, signed


@pytest.fixture
def checkout_http(monkeypatch):
    owner = Principal(uuid4(), "test", "owner")
    def verify(cookie):
        if cookie != "session":
            raise Unauthorized("session required")
        return owner
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: SimpleNamespace(
        identity_verifier=SimpleNamespace(verify=verify)))
    monkeypatch.setenv("RPG_SESSION_SECRET", "checkout-test-secret-" * 3)
    calls = []
    class Repo:
        def checkout(self, principal, sku_id, request_id):
            assert principal == owner
            calls.append((sku_id, request_id))
            return {"order_id": str(uuid4()), "status": "checkout_pending", "checkout_url": "https://checkout.stripe.com/c/pay/test"}
        def order(self, principal, order_id):
            assert principal == owner
            return {"order_id": order_id, "status": "checkout_pending"}
        def accept_event(self, item, **kwargs):
            calls.append(item)
            return {"received": True}
    monkeypatch.setattr(api, "_stripe_payments", lambda: Repo(), raising=False)
    monkeypatch.setattr("services.stripe_checkout.StripeSettings.from_env", lambda: SimpleNamespace(webhook_secret=SECRET))
    token = CsrfSigner("checkout-test-secret-" * 3).issue()
    client = TestClient(api.app)
    return SimpleNamespace(client=client, calls=calls, token=token)


def test_checkout_requires_auth_csrf_and_rejects_client_price(checkout_http):
    c = checkout_http
    request = {"sku_id": "allowed", "request_id": str(uuid4())}
    assert c.client.post("/account/checkout", json=request).status_code == 401
    c.client.cookies.set("rpg_access", "session")
    assert c.client.post("/account/checkout", json=request).status_code == 401
    c.client.cookies.set("rpg_csrf", c.token)
    headers = {"x-csrf-token": c.token, "origin": api._CORS_ORIGINS[0]}
    assert c.client.post("/account/checkout", json={**request, "gross_brl": "0.01", "shard_milli": "999999"}, headers=headers).status_code == 422
    assert c.calls == []
    assert c.client.post("/account/checkout", json=request, headers=headers).status_code == 200
    assert len(c.calls) == 1


def test_order_get_and_return_urls_never_fulfill(checkout_http):
    c = checkout_http
    c.client.cookies.set("rpg_access", "session")
    oid = str(uuid4())
    assert c.client.get("/account/checkout/" + oid).json()["status"] == "checkout_pending"
    c.client.get("/?checkout=success&order_id=" + oid)
    c.client.get("/?checkout=cancel&order_id=" + oid)
    assert c.calls == []


def test_webhook_verifies_signature_before_repository(checkout_http, monkeypatch):
    c = checkout_http
    from tests.test_stripe_checkout import NOW
    monkeypatch.setattr("services.stripe_checkout.time.time", lambda: NOW)
    body, signature = signed({"id": "evt_api_fixture", "type": "unknown", "created": NOW,
                              "livemode": False, "data": {"object": {}}})
    assert c.client.post("/payments/stripe/webhook", content=b"not json").status_code == 400
    assert c.calls == []
    assert c.client.post("/payments/stripe/webhook", content=body, headers={"stripe-signature": signature}).status_code == 200
    assert len(c.calls) == 1
    assert c.client.post("/payments/stripe/webhook", content=body + b" ", headers={"stripe-signature": signature}).status_code == 400
    assert len(c.calls) == 1
    assert c.client.post("/payments/stripe/webhook", content=b"x" * 262145).status_code == 413


def test_default_disabled_without_provider_or_database_access(monkeypatch):
    import builtins
    original_import = builtins.__import__
    def import_without_postgres(name, *args, **kwargs):
        if name == "infrastructure.stripe_payments":
            raise AssertionError("disabled checkout imported optional Postgres dependency")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(api, "_database_profile", lambda: False)
    monkeypatch.delenv("RPG_STRIPE_ENABLED", raising=False)
    monkeypatch.setattr(builtins, "__import__", import_without_postgres)
    client = TestClient(api.app)
    assert client.get("/account/checkout/skus").status_code == 503
    assert client.post("/payments/stripe/webhook", content=json.dumps({})).status_code == 503
