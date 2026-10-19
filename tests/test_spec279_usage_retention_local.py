"""SPEC-279 (Postgres local, rollback): deleting a campaign keeps its spend; deleting the account erases it."""

from __future__ import annotations

import os
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone, UTC
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


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def connection(self):
        return nullcontext(self.conn)


def _campaign(db, owner):
    from psycopg.types.json import Jsonb

    game, op = uuid4(), uuid4()
    db.execute(
        """insert into app.games(id,owner_id,schema_version,state,state_sha256,status,
        player_name,class_name,player_level,location_name,world_day,game_over,combat_simulation)
        values(%s,%s,1,%s,%s,'active','n','Devoto',1,'Porto',1,false,false)""",
        (game, owner, Jsonb({"game_id": str(game)}), "a" * 64),
    )
    db.execute(
        """insert into app.operations(id,owner_id,game_id,kind,status,request_sha256,started_at,finished_at)
        values(%s,%s,%s,'turn','completed',%s,now(),now())""",
        (op, owner, game, "a" * 64),
    )
    events = []
    for ordinal, (cost, basis, spend) in enumerate(
        ((Decimal("0.123456789"), "token_priced", True), (Decimal("0"), "failed_no_usage", False))
    ):
        event = uuid4()
        db.execute(
            """insert into app.usage_events(event_id,operation_id,owner_id,game_id,component,
            attempt_ordinal,category,provider,model,outcome,cost_usd,cost_basis,pricing_version,
            billing_exact,event_sha256,counts_as_spend) values(%s,%s,%s,%s,'narrator',%s,'llm','p','m',
            %s,%s,%s,'v1',false,%s,%s)""",
            (
                event,
                op,
                owner,
                game,
                ordinal,
                "success" if spend else "error",
                cost,
                basis,
                "e" * 64,
                spend,
            ),
        )
        events.append(event)
    return game, op, events


def _day_spend(reader, owner):
    since = datetime.now(UTC) - timedelta(days=1)
    until = datetime.now(UTC) + timedelta(minutes=5)
    groups = sum(
        (g.cost_usd for g in reader.usage_groups(since, until) if g.counts_as_spend), Decimal(0)
    )
    per_owner = reader.owner_usage(since, until).get(str(owner))
    return groups, per_owner, reader.ops_counts(since, until).turns


def test_campaign_delete_keeps_spend_kind_and_history(db):
    from infrastructure.account_read_model import PostgresAccountReader
    from infrastructure.contracts import Principal
    from infrastructure.finops_reader import PostgresFinopsReader

    owner = uuid4()
    game, op, events = _campaign(db, owner)
    kinds = db.execute(
        "select operation_kind from app.usage_events where event_id=any(%s)", (events,)
    ).fetchall()
    assert {r["operation_kind"] for r in kinds} == {"turn"}  # snapshot taken by the trigger
    reader = PostgresFinopsReader(_Pool(db))
    before = _day_spend(reader, owner)
    principal = Principal(user_id=owner, issuer="test", subject=str(owner))
    history_before = PostgresAccountReader(_Pool(db)).usage(principal)["items"]

    assert db.execute("delete from app.games where id=%s", (game,)).rowcount == 1
    assert db.execute("select 1 from app.operations where id=%s", (op,)).fetchone() is None

    rows = db.execute(
        """select game_id,operation_id,operation_kind,cost_usd,counts_as_spend,owner_id
        from app.usage_events where event_id=any(%s)""",
        (events,),
    ).fetchall()
    assert len(rows) == 2
    assert all(r["game_id"] is None and r["operation_id"] == op for r in rows)
    assert all(r["operation_kind"] == "turn" and r["owner_id"] == owner for r in rows)
    assert _day_spend(reader, owner) == before
    assert before[1] is not None
    history_after = PostgresAccountReader(_Pool(db)).usage(principal)["items"]
    assert [(i["id"], i["operation"]) for i in history_after] == [
        (i["id"], i["operation"]) for i in history_before
    ]


def test_attribution_still_fails_closed(db):
    import psycopg

    owner = uuid4()
    game, op, _ = _campaign(db, owner)
    db.execute("savepoint s")
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            """insert into app.usage_events(event_id,operation_id,owner_id,game_id,component,
            attempt_ordinal,category,provider,model,outcome,cost_usd,cost_basis,pricing_version,
            billing_exact,event_sha256,operation_kind) values(%s,%s,%s,%s,'x',9,'llm','p','m','success',0,
            'estimated','v1',false,%s,'new_game')""",
            (uuid4(), op, uuid4(), game, "e" * 64),
        )
    db.execute("rollback to savepoint s")
    # a client-supplied kind is overwritten by the canonical operation kind
    event = uuid4()
    db.execute(
        """insert into app.usage_events(event_id,operation_id,owner_id,game_id,component,
        attempt_ordinal,category,provider,model,outcome,cost_usd,cost_basis,pricing_version,
        billing_exact,event_sha256,operation_kind) values(%s,%s,%s,%s,'x',9,'llm','p','m','success',0,
        'estimated','v1',false,%s,'new_game')""",
        (event, op, owner, game, "e" * 64),
    )
    assert (
        db.execute(
            "select operation_kind from app.usage_events where event_id=%s", (event,)
        ).fetchone()["operation_kind"]
        == "turn"
    )


def test_account_erasure_still_removes_usage(db):
    from infrastructure.account_lifecycle import PRIVATE_TABLES

    owner = uuid4()
    _campaign(db, owner)
    db.execute("insert into app.account_deletions(owner_id) values(%s)", (owner,))
    for table in PRIVATE_TABLES:  # same order as AccountLifecycle.finish
        db.execute(f"delete from app.{table} where owner_id=%s", (owner,))
    assert (
        db.execute(
            "select count(*) n from app.usage_events where owner_id=%s", (owner,)
        ).fetchone()["n"]
        == 0
    )


def test_deleted_operation_id_cannot_be_reclaimed(db):
    """Review P1: a client reusing a deleted operation's id must not run unmetered."""
    owner = uuid4()
    game, op, _ = _campaign(db, owner)
    db.execute("delete from app.games where id=%s", (game,))
    new_game, _, _ = _campaign(db, owner)
    inserted = db.execute(
        """insert into app.operations(id,owner_id,game_id,kind,status,request_sha256)
        values(%s,%s,%s,'turn','running',%s) on conflict do nothing returning id""",
        (op, owner, new_game, "b" * 64),
    ).fetchone()
    assert inserted is None
    assert db.execute("select 1 from app.operations where id=%s", (op,)).fetchone() is None
