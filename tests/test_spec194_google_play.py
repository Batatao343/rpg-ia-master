"""SPEC-194 offline contracts: fake Google client + in-memory store."""
import json
import threading
from uuid import uuid4

import httpx
import pytest

from infrastructure.contracts import Principal
from infrastructure.google_play_payments import GooglePlayPurchases, _public
from services.google_play import (
    GooglePlayClient, GooglePlayError, GooglePlaySettings, ProductPurchase,
    obfuscated_account_id, token_digest,
)

TOKEN = "tok_" + "a" * 40
SKU = {"sku_id": "estilhas_pack_small", "shard_milli": 5000, "pricing_version_id": "v1"}


def owner():
    return Principal(uuid4(), "test", "x")


class FakeGoogle:
    def __init__(self, **over):
        self.base = dict(product_id="estilhas_pack_small", order_id="GPA.1", purchase_state=0,
                         consumption_state=0, acknowledgement_state=0, quantity=1,
                         purchase_time_millis=1, account_id=None, purchase_type=None)
        self.base.update(over)
        self.calls, self.fail_consume = [], False
        self.consume_error = "google_play_unavailable"

    def get_purchase(self, product_id, token):
        self.calls.append("get")
        return ProductPurchase(**self.base)

    def consume(self, product_id, token):
        self.calls.append("consume")
        if self.fail_consume:
            raise GooglePlayError(self.consume_error)


class MemStore:
    def __init__(self):
        self.rows, self.wallet, self.lock = {}, {}, threading.Lock()
        self.deleted, self.events = set(), []

    def sku_for_product(self, product_id):
        return SKU if product_id == "estilhas_pack_small" else None

    def owner_deleted(self, owner_id):
        return owner_id in self.deleted

    def get_by_token(self, sha):
        row = self.rows.get(sha)
        return dict(row) if row else None

    def fulfill(self, owner_id, sku, token, order_id, facts):
        with self.lock:
            sha = token_digest(token)
            if owner_id in self.deleted:
                raise GooglePlayError("account_deleted")
            if sha not in self.rows:
                if any(r["order_id"] == order_id for r in self.rows.values()):
                    raise GooglePlayError("google_play_token_conflict")
                self.wallet[owner_id] = self.wallet.get(owner_id, 0) + sku["shard_milli"]
                self.rows[sha] = dict(owner_id=owner_id, product_id=facts.product_id, sku_id=sku["sku_id"],
                                      shard_milli=sku["shard_milli"], token_sha256=sha, purchase_token=token,
                                      order_id=order_id, state="fulfilled")
                self.events.append("fulfilled")
            return dict(self.rows[sha])

    def set_state(self, sha, state):
        self.events.append(state)
        if self.rows[sha]["state"] != "consumed":
            self.rows[sha]["state"] = state

    def record_consume_failure(self, sha, limit):
        row = self.rows[sha]
        if row["state"] in ("consumed", "consume_failed"):
            return row["state"]
        row["consume_attempts"] = row.get("consume_attempts", 0) + 1
        row["state"] = "consume_failed" if row["consume_attempts"] >= limit else "fulfilled_unconsumed"
        return row["state"]

    def unconsumed(self, limit):
        return [dict(r) for r in self.rows.values()
                if r["state"] in ("fulfilled", "fulfilled_unconsumed")][:limit]


def setup(**over):
    who = owner()
    over.setdefault("account_id", obfuscated_account_id(who.user_id))
    store, google = MemStore(), FakeGoogle(**over)
    return who, store, google, GooglePlayPurchases(store, google)


def test_happy_path_credits_once_then_consumes_after_persist():
    who, store, google, svc = setup()
    result = svc.verify(who, "estilhas_pack_small", TOKEN)
    assert result["consumed"] and store.wallet[who.user_id] == 5000
    assert store.events == ["fulfilled", "consumed"] and google.calls == ["get", "consume"]
    blob = json.dumps(result)
    assert TOKEN not in blob and "private_key" not in blob


def test_replay_is_noop_same_result():
    who, store, google, svc = setup()
    first = svc.verify(who, "estilhas_pack_small", TOKEN)
    assert svc.verify(who, "estilhas_pack_small", TOKEN) == first
    assert store.wallet[who.user_id] == 5000 and google.calls.count("get") == 1


def test_concurrent_duplicates_single_credit():
    who, store, google, svc = setup()
    out, errors = [], []

    def run():
        try:
            out.append(svc.verify(who, "estilhas_pack_small", TOKEN))
        except GooglePlayError as exc:
            errors.append(str(exc))
    threads = [threading.Thread(target=run) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert store.wallet[who.user_id] == 5000 and not errors


@pytest.mark.parametrize("over,code", [
    ({"product_id": "estilhas_pack_huge"}, "google_play_product_mismatch"),
    ({"purchase_state": 1}, "google_play_purchase_cancelled"),
    ({"account_id": "f" * 64}, "google_play_account_mismatch"),
    ({"account_id": None}, "google_play_account_mismatch"),
    ({"quantity": 3}, "google_play_quantity_unsupported"),
    ({"order_id": None}, "google_play_order_mismatch"),
    ({"consumption_state": 1}, "google_play_already_consumed"),
])
def test_untrusted_or_invalid_purchase_never_credits(over, code):
    who, store, _, svc = setup(**over)
    if over.get("account_id", 1) in ("f" * 64, None) and "account_id" in over:
        svc.client.base["account_id"] = over["account_id"]
    with pytest.raises(GooglePlayError, match=code):
        svc.verify(who, "estilhas_pack_small", TOKEN)
    assert store.wallet == {} and store.rows == {}


def test_pending_does_not_credit():
    who, store, _, svc = setup(purchase_state=2)
    assert svc.verify(who, "estilhas_pack_small", TOKEN) == {"status": "pending"}
    assert store.wallet == {}


def test_tampered_inputs_rejected_before_google():
    who, store, google, svc = setup()
    for product, token, order in [("unknown_sku", TOKEN, None), ("estilhas_pack_small", "short", None),
                                  ("estilhas_pack_small", TOKEN, "bad order!"), ("../x", TOKEN, None)]:
        with pytest.raises(GooglePlayError):
            svc.verify(who, product, token, order)
    assert google.calls == [] and store.wallet == {}
    with pytest.raises(GooglePlayError, match="order_mismatch"):
        svc.verify(who, "estilhas_pack_small", TOKEN, "GPA.other")


def test_other_account_cannot_claim_or_replay_token():
    who, store, _, svc = setup()
    svc.verify(who, "estilhas_pack_small", TOKEN)
    thief = owner()
    with pytest.raises(GooglePlayError, match="token_conflict"):
        svc.verify(thief, "estilhas_pack_small", TOKEN)
    assert thief.user_id not in store.wallet


def test_consume_failure_keeps_credit_and_retry_is_idempotent():
    who, store, google, svc = setup()
    google.fail_consume = True
    result = svc.verify(who, "estilhas_pack_small", TOKEN)
    assert result["state"] == "fulfilled_unconsumed" and store.wallet[who.user_id] == 5000
    google.fail_consume = False
    assert svc.retry_unconsumed() == 1
    assert store.rows[token_digest(TOKEN)]["state"] == "consumed"
    assert svc.retry_unconsumed() == 0 and store.wallet[who.user_id] == 5000
    # Client resend after a failed consume also recovers without a second credit.
    google.fail_consume = True
    other = "tok_" + "b" * 40
    google.base["order_id"] = "GPA.2"
    svc.verify(who, "estilhas_pack_small", other)
    google.fail_consume = False
    assert svc.verify(who, "estilhas_pack_small", other)["consumed"]
    assert store.wallet[who.user_id] == 10000


def test_repurchase_after_consume_uses_new_token_and_order():
    who, store, google, svc = setup()
    svc.verify(who, "estilhas_pack_small", TOKEN)
    google.base["order_id"] = "GPA.2"
    svc.verify(who, "estilhas_pack_small", "tok_" + "c" * 40)
    assert store.wallet[who.user_id] == 10000


def test_deleted_account_fenced():
    who, store, google, svc = setup()
    store.deleted.add(who.user_id)
    with pytest.raises(GooglePlayError, match="account_deleted"):
        svc.verify(who, "estilhas_pack_small", TOKEN)
    assert google.calls == [] and store.wallet == {}


def test_public_shape_has_no_price_or_token():
    row = dict(state="consumed", product_id="p", sku_id="s", shard_milli=1)
    assert set(_public(row)) == {"status", "state", "product_id", "sku_id", "shard_milli", "consumed"}


def test_client_signs_jwt_and_calls_documented_endpoints():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    pem = rsa.generate_private_key(65537, 2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()
    seen = []

    def handle(request):
        seen.append((request.method, str(request.url)))
        if request.url.host == "oauth2.googleapis.com":
            assert b"assertion=" in request.content
            return httpx.Response(200, json={"access_token": "at", "expires_in": 3600})
        assert request.headers["authorization"] == "Bearer at"
        if request.url.path.endswith(":consume"):
            return httpx.Response(200, content=b"")
        return httpx.Response(200, json={"productId": "estilhas_pack_small", "purchaseState": 0,
                                         "orderId": "GPA.1", "quantity": 1})
    client = GooglePlayClient(GooglePlaySettings("com.example.rpg", {"private_key": pem, "client_email": "a@b"}),
                              transport=httpx.MockTransport(handle))
    assert client.get_purchase("estilhas_pack_small", TOKEN).order_id == "GPA.1"
    client.consume("estilhas_pack_small", TOKEN)
    assert seen[1][1].startswith("https://androidpublisher.googleapis.com/androidpublisher/v3/applications/com.example.rpg/purchases/products/estilhas_pack_small/tokens/")
    assert seen[2][1].endswith(":consume") and len([s for s in seen if "oauth2" in s[1]]) == 1


def test_provider_errors_are_stable_codes(monkeypatch):
    client = GooglePlayClient(GooglePlaySettings("com.example.rpg", {"private_key": "bad", "client_email": "a@b"}),
                              transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(GooglePlayError, match="google_play_unavailable") as info:
        client.get_purchase("estilhas_pack_small", TOKEN)
    assert "bad" not in str(info.value)
    monkeypatch.delenv("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", raising=False)
    with pytest.raises(GooglePlayError, match="unconfigured"):
        GooglePlaySettings.from_env()


def test_migration_is_fenced_and_not_client_granted():
    from pathlib import Path
    sql = Path("supabase/migrations/20261015130000_google_play_purchases.sql").read_text(encoding="utf-8")
    for needle in ("token_sha256 text not null unique", "order_id text not null unique",
                   "force row level security", "account_write_fence", "revoke all on app.google_play_purchases"):
        assert needle in sql
    assert "grant select" not in sql and "grant insert" not in sql


def test_poison_consume_marks_consumed_when_google_says_so():
    who, store, google, svc = setup()
    google.fail_consume, google.consume_error = True, "google_play_purchase_not_found"
    out = svc.verify(who, "estilhas_pack_small", TOKEN)   # first GET unconsumed, consume 404
    assert out["state"] == "fulfilled_unconsumed" and store.rows[token_digest(TOKEN)]["consume_attempts"] == 1
    google.base["consumption_state"] = 1                  # Google already consumed it
    assert svc.retry_unconsumed() == 1
    assert store.rows[token_digest(TOKEN)]["state"] == "consumed" and store.wallet[who.user_id] == 5000


def test_poison_consume_goes_terminal_after_eight_attempts_and_leaves_the_batch(caplog):
    who, store, google, svc = setup()
    google.fail_consume, google.consume_error = True, "google_play_purchase_not_found"
    svc.verify(who, "estilhas_pack_small", TOKEN)                       # attempt 1
    with caplog.at_level("ERROR", logger="rpg.google_play"):
        for _ in range(6):
            assert svc.retry_unconsumed() == 1
        assert store.rows[token_digest(TOKEN)]["state"] == "fulfilled_unconsumed"   # 7 so far
        assert svc.retry_unconsumed() == 1                              # attempt 8 -> terminal
    row = store.rows[token_digest(TOKEN)]
    assert row["state"] == "consume_failed" and row["consume_attempts"] == 8
    assert svc.last_retry == {"retried": 1, "consume_failed": 1}
    assert "google_play_consume_failed_terminal" in caplog.text and TOKEN not in caplog.text
    assert svc.retry_unconsumed() == 0                                  # excluded from the retry batch
    assert svc.verify(who, "estilhas_pack_small", TOKEN)["state"] == "consume_failed"   # no more consume calls
    assert store.wallet[who.user_id] == 5000


def test_transient_consume_errors_never_count_toward_poison():
    who, store, google, svc = setup()
    google.fail_consume = True   # unavailable (5xx)
    svc.verify(who, "estilhas_pack_small", TOKEN)
    for _ in range(12):
        svc.retry_unconsumed()
    assert store.rows[token_digest(TOKEN)]["state"] == "fulfilled_unconsumed"
    assert store.rows[token_digest(TOKEN)].get("consume_attempts", 0) == 0


def test_account_id_is_hmac_keyed_and_fails_closed(monkeypatch):
    import hashlib
    import hmac
    uid = uuid4()
    expect = hmac.new(b"k" * 32, b"rpg-play-v1:" + str(uid).encode(), hashlib.sha256).hexdigest()
    monkeypatch.setenv("RPG_PLAY_ACCOUNT_KEY", "k" * 32)
    got = obfuscated_account_id(uid)
    assert got == expect and len(got) == 64
    assert got != hashlib.sha256(b"rpg-play-v1:" + str(uid).encode()).hexdigest()   # no longer keyless
    monkeypatch.setenv("RPG_PLAY_ACCOUNT_KEY", "k" * 31)
    with pytest.raises(GooglePlayError, match="google_play_unconfigured"):
        obfuscated_account_id(uid)
    monkeypatch.delenv("RPG_PLAY_ACCOUNT_KEY")
    with pytest.raises(GooglePlayError, match="google_play_unconfigured"):
        obfuscated_account_id(uid)


def test_shared_client_is_cached_per_env_and_bearer_reused(monkeypatch):
    import services.google_play as gp
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    pem = rsa.generate_private_key(65537, 2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()
    monkeypatch.setattr(gp, "_shared", None)
    monkeypatch.setenv("GOOGLE_PLAY_PACKAGE_NAME", "com.example.rpg")
    monkeypatch.setenv("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", json.dumps({"private_key": pem, "client_email": "a@b"}))
    first = gp.shared_client()
    assert gp.shared_client() is first
    seen = []

    def handle(request):
        seen.append(request.url.host)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "at", "expires_in": 3600})
        return httpx.Response(200, json={"productId": "estilhas_pack_small", "purchaseState": 0})
    first.transport = httpx.MockTransport(handle)
    threads = [threading.Thread(target=first.get_purchase, args=("estilhas_pack_small", TOKEN)) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert seen.count("oauth2.googleapis.com") == 1   # one OAuth exchange shared by all threads
    monkeypatch.setenv("GOOGLE_PLAY_PACKAGE_NAME", "com.example.other")
    assert gp.shared_client() is not first


@pytest.mark.parametrize("purchase_type", [0, 2])
def test_test_purchases_rejected_by_default_without_consume(monkeypatch, purchase_type):
    """SPEC-225 R8: license tester (0) e rewarded (2) não creditam nem consomem por default."""
    monkeypatch.delenv("RPG_PLAY_ACCEPT_TEST_PURCHASES", raising=False)
    who, store, google, svc = setup(purchase_type=purchase_type)
    with pytest.raises(GooglePlayError, match="google_play_test_purchase_rejected"):
        svc.verify(who, "estilhas_pack_small", TOKEN)
    assert store.wallet == {} and store.rows == {} and "consume" not in google.calls


def test_test_purchase_credited_only_with_explicit_env(monkeypatch):
    monkeypatch.setenv("RPG_PLAY_ACCEPT_TEST_PURCHASES", "1")
    who, store, google, svc = setup(purchase_type=0)
    result = svc.verify(who, "estilhas_pack_small", TOKEN)
    assert result["status"] != "pending" and store.wallet[who.user_id] == 5000
    assert "consume" in google.calls


def test_normal_purchase_type_none_still_credits(monkeypatch):
    monkeypatch.delenv("RPG_PLAY_ACCEPT_TEST_PURCHASES", raising=False)
    who, store, _, svc = setup(purchase_type=None)
    svc.verify(who, "estilhas_pack_small", TOKEN)
    assert store.wallet[who.user_id] == 5000
