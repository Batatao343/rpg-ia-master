"""Real multi-connection races in a disposable local schema, removed on exit.

Committed setup is required for independent transactions to see the same order.
Canonical migrations are instantiated under an isolated schema; app is untouched.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone, UTC
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest

from infrastructure.contracts import Principal
from infrastructure.postgres import PostgresPool
from infrastructure.stripe_payments import StripePayments
from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
from services.stripe_checkout import StripeSettings
from services.usage_metering import RATE_CARD_VERSION
from tests.fakes.local_pricing import installed_card_max_age_seconds
from tests.test_stripe_checkout_local import FakeStripe, checkout, deliver, event


@pytest.fixture
def concurrent_payments():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.conninfo import conninfo_to_dict
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL absent")
    if conninfo_to_dict(dsn).get("host") not in {"127.0.0.1", "localhost", "::1"}:
        pytest.skip("isolated-schema race tests are local-only")
    schema = "spec189_race_" + uuid4().hex

    class Connection:
        def __init__(self, raw):
            self.raw = raw

        def execute(self, statement, params=None):
            return self.raw.execute(statement.replace("app.", schema + "."), params)

        def transaction(self):
            return self.raw.transaction()

    with psycopg.connect(dsn, row_factory=dict_row, autocommit=True) as admin:
        pool = None
        try:
            admin.execute("create schema " + schema)
            admin.execute(
                "create function "
                + schema
                + ".current_owner_id() returns uuid language sql as $$ select app.current_owner_id() $$"
            )
            for filename in [
                "20261008160000_pricing_versions.sql",
                "20261008170000_wallet_ledger.sql",
                "20261013120000_stripe_checkout.sql",
                "20261015140000_purchase_reconciliation.sql",
            ]:
                sql = Path("supabase/migrations", filename).read_text(encoding="utf-8")
                admin.execute(sql.replace("app.", schema + ".").replace("public.", schema + "."))
            db = Connection(admin)
            at = datetime(2026, 10, 13, 12, tzinfo=UTC)
            version, sku = "race-v", "race-sku"
            db.execute(
                """insert into app.pricing_versions
                (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,
                 fx_buffer_rate,rate_card_version,rate_card_sha256,rate_card_source,
                 rate_card_observed_at,rate_card_max_age_seconds,channel_fees)
                values (%s,0.03,5,'test',%s,864000,0.1,%s,%s,'test',%s,%s,%s)""",
                (
                    version,
                    at,
                    RATE_CARD_VERSION,
                    INSTALLED_RATE_CARD_SHA256,
                    INSTALLED_RATE_CARD_OBSERVED_AT,
                    installed_card_max_age_seconds(),
                    Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"}}),
                ),
            )
            db.execute(
                """insert into app.purchase_skus
                (sku_id,pricing_version_id,channel,store_product_id,gross_brl,shard_milli)
                values (%s,%s,'web',%s,10.50,311)""",
                (sku, version, sku),
            )
            pool = PostgresPool(dsn, max_size=4)

            class RoutedPool:
                @contextmanager
                def connection(self):
                    with pool.connection() as raw:
                        yield Connection(raw)

            owner = Principal(uuid4(), "test", "owner")
            repo = StripePayments(
                RoutedPool(),
                StripeSettings("sk_test_fixture", "whsec_fixture", "https://game.example", (sku,)),
                FakeStripe(),
                at=at,
            )
            yield SimpleNamespace(repo=repo, owner=owner, sku=sku, db=db)
        finally:
            if pool:
                pool.close()
            # schema is constructed exclusively from fixed prefix + UUID hex.
            admin.execute("drop schema if exists " + schema + " cascade")


def race(case, a, b):
    barrier = Barrier(2)

    def run(item):
        barrier.wait(timeout=5)
        return deliver(case, item)

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(run, item) for item in (a, b)]
        return [future.result(timeout=20) for future in futures]


@pytest.mark.parametrize("same_event", [True, False])
def test_paid_race_credits_one_purchase(concurrent_payments, same_event):
    c = concurrent_payments
    order = checkout(c)
    a = event(c, order)
    b = a if same_event else event(c, order, kind="checkout.session.async_payment_succeeded")
    race(c, a, b)
    assert c.repo.wallet.balance(c.owner).available_milli == 311
    assert (
        c.db.execute(
            "select count(*) n from app.wallet_entries where entry_type='purchase'"
        ).fetchone()["n"]
        == 1
    )


def test_orphan_refund_races_first_paid_without_resurrection(concurrent_payments):
    c = concurrent_payments
    order = checkout(c)
    race(c, event(c, order, kind="charge.refunded"), event(c, order))
    deliver(c, event(c, order))
    assert c.repo.wallet.balance(c.owner).available_milli == 0
    assert c.repo.order(c.owner, order["order_id"])["status"] == "refunded"
    assert (
        c.db.execute(
            "select count(*) n from app.payment_financial_events where kind='refund'"
        ).fetchone()["n"]
        == 1
    )
    assert c.db.execute("select sum(available_delta) amount from app.wallet_entries").fetchone()[
        "amount"
    ] in (None, 0)
