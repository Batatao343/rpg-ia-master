"""SPEC-222 R4/R5/R7 on REAL local PostgreSQL. Everything runs on ONE connection rolled back at the end.

Skips without RPG_TEST_DATABASE_URL or without the SPEC-222 migration applied.
"""
from __future__ import annotations

import os
from contextlib import nullcontext
from datetime import datetime, timezone, UTC
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from infrastructure.account_lifecycle import EXPORT_COLUMNS, PostgresAccountLifecycle
from infrastructure.contracts import Principal
from infrastructure.google_play_payments import GooglePlayPurchases, PostgresPurchaseStore
from services.google_play import (
    GooglePlayError,
    ProductPurchase,
    obfuscated_account_id,
    token_digest,
)
from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
from services.usage_metering import RATE_CARD_VERSION
from tests.fakes.local_pricing import installed_card_max_age_seconds

pytestmark = pytest.mark.infra_local
INTERNAL_COLUMNS = {"lease_token", "lease_owner", "lease_until", "request_sha256", "payload",
                    "result", "purchase_token", "fence_token", "embedding", "dedupe_key"}


class FakeGoogle:
    def __init__(self, product_id, order_id):
        self.base = dict(product_id=product_id, order_id=order_id, purchase_state=0, consumption_state=0,
                         acknowledgement_state=0, quantity=1, purchase_time_millis=1,
                         account_id=None, purchase_type=None)
        self.fail = False

    def get_purchase(self, product_id, token):
        return ProductPurchase(**self.base)

    def consume(self, product_id, token):
        if self.fail:
            raise GooglePlayError("google_play_unavailable")


class Blobs:
    bucket = "rpg-dynamic"

    def __init__(self):
        self.signed: list[tuple[str, int]] = []

    def signed_url(self, key, seconds):
        self.signed.append((key, seconds))
        return f"https://storage.test/{key}?token=x&expires={seconds}"

    def delete(self, key):
        return True


@pytest.fixture
def rb():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    db = psycopg.connect(dsn, row_factory=dict_row)
    try:
        if db.execute("select to_regproc('app.minimize_google_state') r").fetchone()["r"] is None:
            pytest.skip("migration SPEC-222 não aplicada")
        version, gp_sku = ("lab-" + uuid4().hex[:12] for _ in range(2))
        product = "gp_" + uuid4().hex[:12]
        at = datetime.now(UTC)
        db.execute("""insert into app.pricing_versions
            (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,
             fx_buffer_rate,rate_card_version,rate_card_sha256,rate_card_source,
             rate_card_observed_at,rate_card_max_age_seconds,channel_fees)
            values (%s,0.03,5,'lab',%s,864000,0.1,%s,%s,'lab',%s,%s,%s)""",
                   (version, at, RATE_CARD_VERSION, INSTALLED_RATE_CARD_SHA256,
                    INSTALLED_RATE_CARD_OBSERVED_AT, installed_card_max_age_seconds(),
                    Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"},
                           "google_play": {"percentage": "0.15", "fixed_brl": "0"}})))
        db.execute("""insert into app.purchase_skus
            (sku_id,pricing_version_id,channel,store_product_id,gross_brl,shard_milli)
            values (%s,%s,'google_play',%s,%s,311)""", (gp_sku, version, product, Decimal("10.50")))

        class Pool:
            def connection(self):
                return nullcontext(db)

        yield SimpleNamespace(db=db, pool=Pool(), product=product, Jsonb=Jsonb)
    finally:
        db.rollback()
        db.close()


def _purchase(rb, *, consume_fails=False):
    owner = Principal(uuid4(), "test", "gp")
    order, token = "GPA." + uuid4().hex[:12], "tok_" + uuid4().hex
    google = FakeGoogle(rb.product, order)
    google.base["account_id"] = obfuscated_account_id(owner.user_id)
    google.fail = consume_fails
    store = PostgresPurchaseStore(rb.pool)
    svc = GooglePlayPurchases(store, google)
    try:
        svc.verify(owner, rb.product, token)
    except GooglePlayError:
        pass
    return owner, token, store, svc


def _row(rb, token):
    return rb.db.execute("select * from app.google_play_purchases where token_sha256=%s",
                         (token_digest(token),)).fetchone()


def test_google_token_nulled_after_consume(rb):
    owner, token, _store, svc = _purchase(rb)
    row = _row(rb, token)
    assert row["state"] == "consumed"
    assert row["purchase_token"] is None
    assert row["token_sha256"] == token_digest(token)  # idempotency anchor survives
    assert set(row["google_state"]) <= {"purchase_state", "consumption_state", "purchase_type", "quantity"}
    # Replaying the same purchase stays idempotent without the raw token.
    assert svc.verify(owner, rb.product, token)["consumed"]


def test_token_cannot_be_restored_or_replaced(rb):
    import psycopg
    _owner, token, _store, _svc = _purchase(rb)
    rb.db.execute("savepoint s")
    with pytest.raises(psycopg.Error):
        rb.db.execute("update app.google_play_purchases set purchase_token=%s where token_sha256=%s",
                      ("tok_" + uuid4().hex, token_digest(token)))
    rb.db.execute("rollback to savepoint s")


def test_unconsumed_keeps_token_until_terminal(rb):
    _owner, token, _store, _svc = _purchase(rb, consume_fails=True)
    row = _row(rb, token)
    assert row["state"] == "fulfilled_unconsumed" and row["purchase_token"] == token


def test_account_deletion_minimizes_google_rows(rb):
    owner, token, store, _svc = _purchase(rb, consume_fails=True)
    rb.db.execute("update app.google_play_purchases set google_state=google_state||'{\"extra\":\"x\"}',"
                  "updated_at=now()-interval '5 minutes' where token_sha256=%s", (token_digest(token),))
    PostgresAccountLifecycle(rb.pool, identity=None, blobs=Blobs()).begin(owner.user_id)
    row = _row(rb, token)
    assert row["purchase_token"] is None and "extra" not in row["google_state"]
    assert row["owner_id"] == owner.user_id  # retained (RETAINED_WITH_REASON), only minimized
    assert all(r["token_sha256"] != token_digest(token) for r in store.unconsumed(500))


def test_export_includes_new_tables_columns_and_signed_urls(rb):
    owner, token, _store, _svc = _purchase(rb)
    game, job = uuid4(), uuid4()
    key = f"users/{owner.user_id}/games/{game}/player/hero/full.webp"
    rb.db.execute("""insert into app.games(id,owner_id,schema_version,state,state_sha256,status,
        player_name,class_name,player_level,location_name,world_day,game_over,combat_simulation)
        values(%s,%s,1,%s,%s,'active','n','Devoto',1,'Porto',1,false,false)""",
                  (game, owner.user_id, rb.Jsonb({"game_id": str(game)}), "a" * 64))
    rb.db.execute("""insert into app.assets(id,owner_id,game_id,entity_id,asset_kind,variant,status,
        visibility,bucket,object_key,mime_type,bytes,width,height,sha256)
        values(%s,%s,%s,'hero','player','full','ready','public','rpg-dynamic',%s,'image/webp',10,1,1,%s)""",
                  (uuid4(), owner.user_id, game, key, "b" * 64))
    rb.db.execute("""insert into app.jobs(id,owner_id,game_id,kind,dedupe_key,status,payload,max_attempts,
        lease_token,lease_owner,lease_until)
        values(%s,%s,%s,'embed_memory',%s,'running',%s,3,%s,'worker',now()+interval '5 minutes')""",
                  (job, owner.user_id, game, str(uuid4()), rb.Jsonb({"private": "prompt"}), uuid4()))
    blobs = Blobs()
    export = PostgresAccountLifecycle(rb.pool, identity=None, blobs=blobs).export(owner)
    data = export["data"]
    for table in ("google_play_purchases", "wallet_debt_entries", "purchase_reconciliation_state"):
        assert table in data
    assert len(data["google_play_purchases"]) == 1
    for table, rows in data.items():
        for row in rows:
            assert not INTERNAL_COLUMNS & set(row), (table, INTERNAL_COLUMNS & set(row))
            if table in EXPORT_COLUMNS:
                assert set(row) == set(EXPORT_COLUMNS[table])
    assert data["jobs"][0]["id"] == job and "payload" not in data["jobs"][0]
    assert blobs.signed == [(key, 300)]
    assert export["asset_downloads"][0]["object_key"] == key
    assert export["asset_downloads"][0]["expires_in_seconds"] == 300
