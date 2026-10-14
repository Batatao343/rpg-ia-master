"""Deletion does not corrupt late Stripe accounting or retain checkout capability."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier, RLock
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from infrastructure.account_lifecycle import PostgresAccountLifecycle
from services.stripe_checkout import StripeError
from tests.test_stripe_checkout_local import payment_case, checkout, deliver, event


def install_lifecycle(c):
    if c.db.execute("select to_regclass('app.image_quotes') t").fetchone()["t"] is None:
        c.db.execute(Path("supabase/migrations/20261012160000_image_quotes.sql").read_text(encoding="utf-8"))
    c.db.execute(Path("supabase/migrations/20261013173632_account_lifecycle.sql").read_text(encoding="utf-8"))
    c.fake.expire_session=lambda _session_id: "expired"
    return PostgresAccountLifecycle(c.repo.pool,SimpleNamespace(delete_user=lambda _owner: None),
                                    SimpleNamespace(bucket="rpg-dynamic",delete=lambda _key: True),
                                    payments=c.repo)


def test_delayed_verified_paid_and_refund_still_reconcile_after_deletion(payment_case):
    c=payment_case
    lifecycle=install_lifecycle(c)
    order=checkout(c)
    assert lifecycle.delete(c.owner.user_id)=="deleted"
    deliver(c,event(c,order))
    assert c.repo.wallet.balance(c.owner).available_milli==0
    assert not c.db.execute("select 1 from app.wallet_entries where owner_id=%s and entry_type='purchase'",(c.owner.user_id,)).fetchone()
    hold=c.db.execute("select * from app.payment_financial_events where order_id=%s and kind='late_paid_after_delete'",(order["order_id"],)).fetchone()
    assert hold["outcome"]=="refund_required"
    assert c.repo.order(c.owner,order["order_id"])["status"]=="reconciliation_required"
    deliver(c,event(c,order,kind="charge.refunded"))
    assert c.repo.wallet.balance(c.owner).available_milli==0
    assert not c.db.execute("select 1 from app.wallet_entries where owner_id=%s and entry_type='purchase'",(c.owner.user_id,)).fetchone()
    assert c.db.execute("select checkout_url from app.payment_orders where owner_id=%s",(c.owner.user_id,)).fetchone()["checkout_url"] is None


def test_checkout_adapter_response_after_delete_cannot_restore_url(payment_case):
    c=payment_case
    lifecycle=install_lifecycle(c)
    create=c.fake.create_session
    def pause_then_delete(*args,**kwargs):
        result=create(*args,**kwargs)
        # Stripe create is in flight; recovery reuses its idempotency key.
        c.fake.create_session=create
        assert lifecycle.delete(c.owner.user_id)=="deleted"
        return result
    c.fake.create_session=pause_then_delete
    with pytest.raises(StripeError,match="account_deleted"):
        checkout(c)
    assert c.db.execute("select checkout_url from app.payment_orders where owner_id=%s",(c.owner.user_id,)).fetchone()["checkout_url"] is None


def _private_account(c, lifecycle):
    owner = c.owner.user_id
    game = uuid4()
    key = f"users/{owner}/games/{game}/private.webp"
    c.db.execute("insert into auth.users(id,email) values(%s,%s)", (owner, f"{owner}@example.test"))
    c.db.execute("""insert into app.games(id,owner_id,schema_version,state,state_sha256,status,
        player_name,class_name,player_level,location_name,world_day,game_over,combat_simulation)
        values(%s,%s,1,%s,%s,'active','private-name','Devoto',1,'Porto',1,false,false)""",
        (game, owner, Jsonb({"private": "story"}), "a" * 64))
    c.db.execute("insert into storage.objects(bucket_id,name) values('rpg-dynamic',%s)", (key,))

    def delete_blob(blob_key):
        c.db.execute("select set_config('storage.allow_delete_query','true',true)")
        c.db.execute("delete from storage.objects where bucket_id='rpg-dynamic' and name=%s", (blob_key,))
        return True

    def delete_user(user_id):
        c.db.execute("delete from auth.users where id=%s", (user_id,))

    lifecycle.blobs = SimpleNamespace(bucket="rpg-dynamic", delete=delete_blob)
    lifecycle.identity = SimpleNamespace(delete_user=delete_user)
    return game, key


def _assert_private_erased(c, game, key):
    owner = c.owner.user_id
    assert not c.db.execute("select 1 from auth.users where id=%s", (owner,)).fetchone()
    assert not c.db.execute("select 1 from app.games where id=%s", (game,)).fetchone()
    assert not c.db.execute("select 1 from storage.objects where name=%s", (key,)).fetchone()


def test_stripe_outage_erases_private_account_before_financial_retry(payment_case):
    c = payment_case
    lifecycle = install_lifecycle(c)
    game, key = _private_account(c, lifecycle)
    order = checkout(c)
    c.fake.expire_session = lambda _session_id: (_ for _ in ()).throw(StripeError("stripe_unavailable"))

    assert lifecycle.delete(c.owner.user_id) == "deleting"
    _assert_private_erased(c, game, key)
    row = c.db.execute("select * from app.payment_orders where order_id=%s", (order["order_id"],)).fetchone()
    assert row["checkout_url"] is None and row["checkout_closed_at"] is None
    assert c.db.execute("select status from app.account_deletions where owner_id=%s",
                        (c.owner.user_id,)).fetchone()["status"] == "deleting"
    deliver(c, event(c, order))
    assert c.repo.wallet.balance(c.owner).available_milli == 0
    assert c.db.execute("select outcome from app.payment_financial_events where order_id=%s",
                        (order["order_id"],)).fetchone()["outcome"] == "refund_required"

    c.fake.expire_session = lambda _session_id: "complete"
    assert lifecycle.finish(c.owner.user_id) == "deleted"
    _assert_private_erased(c, game, key)
    assert c.db.execute("select checkout_closed_at from app.payment_orders where order_id=%s",
                        (order["order_id"],)).fetchone()["checkout_closed_at"] is not None


def test_two_workers_finish_same_tombstone_with_overlapping_provider_calls(payment_case):
    c = payment_case
    lifecycle = install_lifecycle(c)
    game, key = _private_account(c, lifecycle)
    order = checkout(c)
    c.repo.wallet.adjust_admin(c.owner, adjustment_id=str(uuid4()), signed_milli=200,
                               actor_id=uuid4(), reason="Synthetic retained financial fact")
    ledger_before = c.db.execute("select * from app.wallet_entries where owner_id=%s",
                                 (c.owner.user_id,)).fetchall()
    lock = RLock()

    class LockedPool:
        @contextmanager
        def connection(self):
            with lock:
                yield c.db

    pool = LockedPool()
    lifecycle.pool = pool
    c.repo.pool = pool

    def delete_blob(blob_key):
        with pool.connection() as db:
            db.execute("select set_config('storage.allow_delete_query','true',true)")
            db.execute("delete from storage.objects where bucket_id='rpg-dynamic' and name=%s", (blob_key,))
        return True

    def delete_user(user_id):
        with pool.connection() as db:
            db.execute("delete from auth.users where id=%s", (user_id,))

    lifecycle.blobs = SimpleNamespace(bucket="rpg-dynamic", delete=delete_blob)
    lifecycle.identity = SimpleNamespace(delete_user=delete_user)
    lifecycle.begin(c.owner.user_id)
    barrier = Barrier(2)
    calls = []

    def expire_session(session_id):
        calls.append(session_id)
        barrier.wait(timeout=10)
        return "expired"

    c.fake.expire_session = expire_session
    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(lifecycle.finish, c.owner.user_id)
        second = workers.submit(lifecycle.finish, c.owner.user_id)
        assert first.result(timeout=20) == "deleted"
        assert second.result(timeout=20) == "deleted"

    assert calls == ["cs_test_" + order["order_id"]] * 2
    _assert_private_erased(c, game, key)
    assert c.db.execute("select * from app.wallet_entries where owner_id=%s",
                        (c.owner.user_id,)).fetchall() == ledger_before
    row = c.db.execute("select status,checkout_url,checkout_closed_at from app.payment_orders where order_id=%s",
                       (order["order_id"],)).fetchone()
    assert row["status"] == "expired" and row["checkout_url"] is None and row["checkout_closed_at"]
