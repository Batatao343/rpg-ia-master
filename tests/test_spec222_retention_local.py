"""SPEC-222 R7: TTL de metadados técnicos com fixtures datadas (Postgres local, rollback)."""

from __future__ import annotations

import os
from contextlib import nullcontext
from uuid import uuid4

import pytest

from services.retention import RETENTION_RULES, purge_expired

pytestmark = pytest.mark.infra_local


def test_purge_expired_respects_each_window_and_references():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    db = psycopg.connect(dsn, row_factory=dict_row)
    try:
        db.execute("select 1")

        class Pool:
            def connection(self):
                return nullcontext(db)

        owner, game = uuid4(), uuid4()
        db.execute(
            """insert into app.games(id,owner_id,schema_version,state,state_sha256,status,
            player_name,class_name,player_level,location_name,world_day,game_over,combat_simulation)
            values(%s,%s,1,%s,%s,'active','n','Devoto',1,'Porto',1,false,false)""",
            (game, owner, Jsonb({"game_id": str(game)}), "a" * 64),
        )

        def operation(age: str, status: str = "completed") -> object:
            op = uuid4()
            db.execute(
                """insert into app.operations(id,owner_id,game_id,kind,status,request_sha256,
                started_at,finished_at) values(%s,%s,%s,'turn',%s,%s,now()-%s::interval,now()-%s::interval)""",
                (op, owner, game, status, "a" * 64, age, age),
            )
            return op

        old_op, recent_op, old_with_turn, old_with_usage, old_running = (
            operation("100 days"),
            operation("10 days"),
            operation("100 days"),
            operation("100 days"),
            operation("100 days", "running"),
        )
        db.execute(
            """insert into app.turns(operation_id,game_id,owner_id,sequence,timeline_epoch,route,
            input_sha256,state_version_before) values(%s,%s,%s,1,0,'storyteller',%s,1)""",
            (old_with_turn, game, owner, "a" * 64),
        )

        def usage(op, age: str) -> object:
            event = uuid4()
            db.execute(
                """insert into app.usage_events(event_id,operation_id,owner_id,game_id,component,
                attempt_ordinal,category,provider,model,outcome,cost_usd,cost_basis,pricing_version,
                billing_exact,event_sha256) values(%s,%s,%s,%s,'narrator',0,'llm','p','m','success',0,
                'estimated','v1',false,%s)""",
                (event, op, owner, game, "e" * 64),
            )
            db.execute(
                "update app.usage_events set created_at=now()-%s::interval where event_id=%s",
                (age, event),
            )
            return event

        old_event = usage(old_with_usage, "14 months")
        kept_event = usage(recent_op, "12 months")

        def job(status: str, age: str) -> object:
            jid = uuid4()
            db.execute(
                """insert into app.jobs(id,owner_id,kind,dedupe_key,status,payload,max_attempts,updated_at)
                values(%s,%s,'embed_memory',%s,%s,'{}',3,now()-%s::interval)""",
                (jid, owner, str(uuid4()), status, age),
            )
            return jid

        old_job, recent_job, old_queued = (
            job("succeeded", "40 days"),
            job("dead", "5 days"),
            job("queued", "40 days"),
        )

        deleted_owner, compact_owner, fresh_owner = uuid4(), uuid4(), uuid4()
        for who, age in (
            (deleted_owner, "6 years"),
            (compact_owner, "40 days"),
            (fresh_owner, "5 days"),
        ):
            db.execute(
                """insert into app.account_deletions(owner_id,status,blob_keys,requested_at,
                sessions_revoked_at,completed_at) values(%s,'deleted','{}',now()-%s::interval-interval '1 day',
                now()-%s::interval,now()-%s::interval)""",
                (who, age, age, age),
            )
        db.execute("""insert into app.finops_evaluations(evaluated_at,blocking_alerts,alert_count,summary,alerts)
            values (now()-interval '200 days',0,0,'{}','[]'),(now()-interval '10 days',0,0,'{}','[]')""")
        before_finops = db.execute(
            "select count(*) n from app.finops_evaluations "
            "where evaluated_at < now()-interval '180 days'"
        ).fetchone()["n"]
        assert before_finops >= 1

        result = purge_expired(Pool())
        assert all(isinstance(v, int) for v in result.values())

        def exists(table, column, value):
            return (
                db.execute(f"select 1 from app.{table} where {column}=%s", (value,)).fetchone()
                is not None
            )

        assert not exists("operations", "id", old_op)
        assert exists("operations", "id", recent_op)
        assert exists("operations", "id", old_with_turn)  # turns are game history
        assert not exists("usage_events", "event_id", old_event)
        assert exists("usage_events", "event_id", kept_event)
        assert exists("operations", "id", old_running)  # never a running operation
        assert not exists("jobs", "id", old_job)
        assert exists("jobs", "id", recent_job) and exists("jobs", "id", old_queued)
        assert not exists("account_deletions", "owner_id", deleted_owner)
        compact = db.execute(
            "select * from app.account_deletions where owner_id=%s", (compact_owner,)
        ).fetchone()
        assert (
            compact["sessions_revoked_at"] is None
            and compact["requested_at"] == compact["completed_at"]
        )
        fresh = db.execute(
            "select * from app.account_deletions where owner_id=%s", (fresh_owner,)
        ).fetchone()
        assert fresh["sessions_revoked_at"] is not None
        assert (
            db.execute(
                "select count(*) n from app.finops_evaluations "
                "where evaluated_at < now()-interval '180 days'"
            ).fetchone()["n"]
            == 0
        )
        assert set(RETENTION_RULES) == {
            "operations",
            "jobs",
            "usage_events",
            "finops_evaluations",
            "account_deletions",
            "owner_daily_counters",
        }  # SPEC-219
    finally:
        db.rollback()
        db.close()
