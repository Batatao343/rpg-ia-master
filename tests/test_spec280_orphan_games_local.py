"""SPEC-280 (Postgres local, rollback): Auth deletion erases games, keeps spend and wallet; orphan cleanup."""
from __future__ import annotations

import os
from decimal import Decimal
from uuid import uuid4

import pytest

pytestmark = pytest.mark.infra_local


@pytest.fixture
def db():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    conn = psycopg.connect(dsn, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def _game(db, owner, cost=Decimal("0.25")):
    from psycopg.types.json import Jsonb
    game, op, event = uuid4(), uuid4(), uuid4()
    db.execute("""insert into app.games(id,owner_id,schema_version,state,state_sha256,status,
        player_name,class_name,player_level,location_name,world_day,game_over,combat_simulation)
        values(%s,%s,1,%s,%s,'active','n','Devoto',1,'Porto',1,false,false)""",
               (game, owner, Jsonb({"game_id": str(game)}), "a" * 64))
    db.execute("""insert into app.operations(id,owner_id,game_id,kind,status,request_sha256,started_at,finished_at)
        values(%s,%s,%s,'turn','completed',%s,now(),now())""", (op, owner, game, "a" * 64))
    db.execute("""insert into app.usage_events(event_id,operation_id,owner_id,game_id,component,attempt_ordinal,
        category,provider,model,outcome,cost_usd,cost_basis,pricing_version,billing_exact,event_sha256)
        values(%s,%s,%s,%s,'narrator',0,'llm','p','m','success',%s,'token_priced','v1',false,%s)""",
               (event, op, owner, game, cost, "e" * 64))
    return game, event


def _auth_user(db):
    uid = uuid4()
    db.execute("insert into auth.users(id,email) values(%s,%s)", (uid, f"{uid}@example.test"))
    return uid


def test_auth_delete_erases_games_but_keeps_spend_and_wallet(db):
    owner, other = _auth_user(db), _auth_user(db)
    game, event = _game(db, owner)
    other_game, _ = _game(db, other)
    db.execute("insert into app.wallet_accounts(owner_id) values(%s)", (owner,))
    db.execute("delete from auth.users where id=%s", (owner,))
    assert db.execute("select 1 from app.games where id=%s", (game,)).fetchone() is None
    assert db.execute("select 1 from app.games where id=%s", (other_game,)).fetchone() is not None
    row = db.execute("select game_id,cost_usd from app.usage_events where event_id=%s", (event,)).fetchone()
    assert row["game_id"] is None and row["cost_usd"] == Decimal("0.25")
    assert db.execute("select 1 from app.wallet_accounts where owner_id=%s", (owner,)).fetchone() is not None


def test_plan_and_apply_remove_only_orphans_and_keep_spend(db):
    from scripts.admin_orphan_games import OrphanCleanupRefused, apply, plan
    live = _auth_user(db)
    live_game, _ = _game(db, live)
    orphan_owner, deleting_owner = uuid4(), uuid4()
    orphan_game, orphan_event = _game(db, orphan_owner)
    deleting_game, _ = _game(db, deleting_owner)
    db.execute("insert into app.account_deletions(owner_id) values(%s)", (deleting_owner,))
    p = plan(db)
    assert p["orphan_games"] >= 1 and p["skipped_account_deletion_in_progress"] >= 1
    assert p["orphan_usage_spend_usd"] >= Decimal("0.25")
    assert "ids" not in str(p) and str(orphan_owner) not in str(p)
    with pytest.raises(OrphanCleanupRefused):
        apply(db, expect=p["orphan_games"] + 1)
    out = apply(db, expect=p["orphan_games"])
    assert out["deleted_games"] == p["orphan_games"]
    assert out["spend_before_usd"] == out["spend_after_usd"]
    assert out["financial_rows_before"] == out["financial_rows_after"]
    assert db.execute("select 1 from app.games where id=%s", (orphan_game,)).fetchone() is None
    assert db.execute("select 1 from app.games where id=%s", (live_game,)).fetchone() is not None
    assert db.execute("select 1 from app.games where id=%s", (deleting_game,)).fetchone() is not None
    assert db.execute("select game_id from app.usage_events where event_id=%s",
                      (orphan_event,)).fetchone()["game_id"] is None
    assert plan(db)["orphan_games"] == 0


def test_refuses_when_usage_still_cascades(db):
    from scripts.admin_orphan_games import OrphanCleanupRefused, plan
    db.execute("alter table app.usage_events drop constraint usage_events_game_id_fkey")
    db.execute("""alter table app.usage_events add constraint usage_events_game_id_fkey
        foreign key (game_id) references app.games(id) on delete cascade""")
    with pytest.raises(OrphanCleanupRefused):
        plan(db)
