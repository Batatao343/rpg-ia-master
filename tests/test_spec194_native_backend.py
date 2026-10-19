"""SPEC-194 native-side backend: android Stripe refusal, products route, local fake, SKU seed plan."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

import api
from infrastructure.contracts import Principal
from infrastructure.google_play_payments import GooglePlayPurchases
from services.google_play import obfuscated_account_id
from services.google_play_fake import FAKE_PREFIX, FakeGooglePlayClient, fake_allowed
from tests.test_spec194_google_play import MemStore
from tests.test_stripe_checkout_api import checkout_http  # noqa: F401  (fixture)


def _auth(c):
    c.client.cookies.set("rpg_access", "session")
    c.client.cookies.set("rpg_csrf", c.token)
    return {"x-csrf-token": c.token, "origin": api._CORS_ORIGINS[0], "x-rpg-client": "android"}


def test_android_header_refuses_stripe_checkout_and_catalog(checkout_http):  # noqa: F811
    c = checkout_http
    h = _auth(c)
    body = {"sku_id": "allowed", "request_id": str(uuid4())}
    r = c.client.post("/account/checkout", json=body, headers=h)
    assert r.status_code == 403 and r.json()["detail"] == "stripe_unavailable_on_android"
    r = c.client.get("/account/checkout/skus", headers=h)
    assert r.status_code == 403 and r.json()["detail"] == "stripe_unavailable_on_android"
    assert c.calls == []
    web = {k: v for k, v in h.items() if k != "x-rpg-client"}
    assert c.client.post("/account/checkout", json=body, headers=web).status_code == 200


def test_google_products_route_lists_ids_without_price(checkout_http, monkeypatch):  # noqa: F811
    c = checkout_http
    h = _auth(c)
    rows = [{"product_id": "estilhas_pack_small", "sku_id": "gp_a", "shard_milli": "5000"}]
    monkeypatch.setattr("infrastructure.google_play_payments.PostgresPurchaseStore.__init__", lambda self, pool: None)
    monkeypatch.setattr("infrastructure.google_play_payments.PostgresPurchaseStore.list_products", lambda self: rows)
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: SimpleNamespace(
        identity_verifier=SimpleNamespace(verify=lambda cookie: Principal(uuid4(), "t", "o")),
        game_store=SimpleNamespace(pool=None)))
    r = c.client.get("/account/purchases/google/products", headers=h)
    assert r.status_code == 200 and r.json() == {"items": rows}
    assert "gross" not in r.text and "price" not in r.text


def test_fake_client_only_local_profile_with_flag(monkeypatch):
    monkeypatch.delenv("RPG_GOOGLE_PLAY_FAKE", raising=False)
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")
    assert not fake_allowed()
    monkeypatch.setenv("RPG_GOOGLE_PLAY_FAKE", "1")
    assert fake_allowed()
    for profile in ("hosted", "hosted-supabase", "portable", "legacy"):
        monkeypatch.setenv("RPG_RUNTIME_PROFILE", profile)
        assert not fake_allowed()


def test_fake_client_drives_verify_credit_once_and_rejects_foreign_account():
    who = Principal(uuid4(), "t", "o")
    store = MemStore()
    svc = GooglePlayPurchases(store, FakeGooglePlayClient())
    token = f"{FAKE_PREFIX}{obfuscated_account_id(who.user_id)}-0001"
    out = svc.verify(who, "estilhas_pack_small", token)
    assert out["consumed"] and store.wallet[who.user_id] == 5000
    assert svc.verify(who, "estilhas_pack_small", token)["consumed"] and store.wallet[who.user_id] == 5000
    other = Principal(uuid4(), "t", "o")
    with pytest.raises(Exception, match="google_play_account_mismatch"):
        svc.verify(other, "estilhas_pack_small", f"{FAKE_PREFIX}{obfuscated_account_id(who.user_id)}-0002")


def test_seed_plan_mirrors_only_versions_with_google_fee_and_is_idempotent():
    from scripts.seed_google_play_skus import plan, product_id_for
    rows = [{"sku_id": "Pack-Small", "pricing_version_id": "v1", "gross_brl": "9.90", "shard_milli": 5000,
             "channel_fees": {"web": {}, "google_play": {}}},
            {"sku_id": "old", "pricing_version_id": "v0", "gross_brl": "1", "shard_milli": 1, "channel_fees": {"web": {}}}]
    p = plan(rows, set())
    assert p[0]["store_product_id"] == "pack-small".replace("-", "_") == product_id_for("Pack-Small")
    assert p[0]["channel"] == "google_play" and not p[0]["exists"]
    assert p[1]["reason"] == "pricing_version_without_google_play_fee"
    assert plan(rows, {"pack_small"})[0]["exists"] is True


def test_fake_refused_on_vercel_or_hosted_even_with_flag(monkeypatch):
    monkeypatch.setenv("RPG_GOOGLE_PLAY_FAKE", "1")
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")
    assert fake_allowed()
    monkeypatch.setenv("VERCEL", "1")
    assert not fake_allowed()
    monkeypatch.delenv("VERCEL")
    for profile in ("hosted-supabase", "hosted"):
        monkeypatch.setenv("RPG_RUNTIME_PROFILE", profile)
        assert not fake_allowed()


def test_checklist_forbids_fake_play_flag_in_production():
    # scripts/release (SPEC-197) lands in a later commit; the test activates once it exists.
    checklist = pytest.importorskip("scripts.release.checklist")
    FORBIDDEN_IN_PROD = checklist.FORBIDDEN_IN_PROD
    assert "RPG_GOOGLE_PLAY_FAKE" in FORBIDDEN_IN_PROD


def test_api_google_play_refuses_fake_flag_on_vercel_and_missing_key(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: type("R", (), {"game_store": type("G", (), {"pool": None})()})())
    monkeypatch.setenv("RPG_GOOGLE_PLAY_FAKE", "1")
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "hosted-supabase")
    with pytest.raises(HTTPException) as info:
        api._google_play()
    assert info.value.status_code == 503 and info.value.detail == "google_play_unconfigured"
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")
    monkeypatch.delenv("RPG_PLAY_ACCOUNT_KEY")
    with pytest.raises(HTTPException) as info:
        api._google_play()
    assert info.value.status_code == 503 and info.value.detail == "google_play_unconfigured"
    monkeypatch.setenv("RPG_PLAY_ACCOUNT_KEY", "k" * 32)
    assert api._google_play() is not None   # local + flag + key: fake client allowed


def test_verify_maps_wallet_conflict_to_409(monkeypatch):
    from fastapi import HTTPException

    from infrastructure.wallet import WalletConflict

    class Boom:
        def verify(self, *a):
            raise WalletConflict("x")
    monkeypatch.setattr(api, "_google_play", lambda: Boom())
    monkeypatch.setattr("infrastructure.request_context.current_principal", lambda: Principal(uuid4(), "t", "o"))
    with pytest.raises(HTTPException) as info:
        api.google_play_verify(api.GooglePlayVerifyRequest(product_id="p1", purchase_token="t" * 20))
    assert info.value.status_code == 409 and info.value.detail == "google_play_wallet_conflict"
