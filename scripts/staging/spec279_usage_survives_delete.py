"""SPEC-279 staging proof: deleting a campaign keeps its spend in the daily cap/FinOps sums.

Synthetic owner (random UUID, no Auth user) + game + 'turn' operation + 2 usage events
(1 spend of US$ 0.000001, 1 failed_no_usage). Measures the day's spend (global and owner) through
the real reader (`PostgresFinopsReader.usage_groups`/`owner_usage`/`ops_counts`), deletes the game,
measures again, then removes the synthetic usage rows so the staging day sum returns to its prior value.

  uv run --frozen python -m scripts.staging.spec279_usage_survives_delete --confirm-staging <ref>

Evidence (no ids/PII): docs/staging-wave-2026-10-17/evidence/spec279_usage_survives_delete.json
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from scripts.staging import common, s192

EVIDENCE = common.ROOT / "docs" / "staging-wave-2026-10-17" / "evidence"
COST = Decimal("0.000001")


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def connection(self):
        return nullcontext(self.conn)


def _measure(conn, owner) -> dict:
    from infrastructure.finops_reader import PostgresFinopsReader
    reader = PostgresFinopsReader(_Pool(conn))
    from services.daily_spend_cap import day_start
    now = datetime.now(timezone.utc)
    since, until = day_start(now), now + timedelta(minutes=5)
    day = sum((g.cost_usd for g in reader.usage_groups(since, until) if g.counts_as_spend), Decimal(0))
    mine = reader.owner_usage(since, until).get(str(owner))
    return {"day_spend_usd": day, "owner_spend_usd": mine.total_usd if mine else Decimal(0),
            "day_turns": reader.ops_counts(since, until).turns}


def run(env: dict) -> dict:
    from psycopg.types.json import Jsonb
    owner, game, op = uuid4(), uuid4(), uuid4()
    events = [uuid4(), uuid4()]

    def go(conn):
        out: dict = {"schema": {
            "operation_kind_column": conn.execute(
                "select count(*) n from information_schema.columns where table_schema='app' "
                "and table_name='usage_events' and column_name='operation_kind'").fetchone()["n"] == 1,
            "fks": {r["conname"]: r["confdeltype"] for r in conn.execute(
                "select conname, confdeltype from pg_constraint where conrelid='app.usage_events'::regclass "
                "and contype='f'").fetchall()}}}
        out["baseline"] = _measure(conn, owner)
        with conn.transaction():
            conn.execute("""insert into app.games(id,owner_id,schema_version,state,state_sha256,status,player_name,
                class_name,player_level,location_name,world_day,game_over,combat_simulation)
                values(%s,%s,1,%s,%s,'active','spec279','Devoto',1,'Porto',1,false,false)""",
                         (game, owner, Jsonb({"game_id": str(game)}), "a" * 64))
            conn.execute("""insert into app.operations(id,owner_id,game_id,kind,status,request_sha256,started_at,
                finished_at) values(%s,%s,%s,'turn','completed',%s,now(),now())""", (op, owner, game, "a" * 64))
            for i, (cost, basis, spend) in enumerate(((COST, "token_priced", True),
                                                      (Decimal(0), "failed_no_usage", False))):
                conn.execute("""insert into app.usage_events(event_id,operation_id,owner_id,game_id,component,
                    attempt_ordinal,category,provider,model,outcome,cost_usd,cost_basis,pricing_version,
                    billing_exact,event_sha256,counts_as_spend) values(%s,%s,%s,%s,'spec279',%s,'llm','spec279',
                    'spec279',%s,%s,%s,'spec279',false,%s,%s)""",
                             (events[i], op, owner, game, i, "success" if spend else "error", cost, basis,
                              "e" * 64, spend))
        out["before_delete"] = _measure(conn, owner)
        with conn.transaction():
            out["games_deleted"] = conn.execute("delete from app.games where id=%s", (game,)).rowcount
        out["after_delete"] = _measure(conn, owner)
        rows = conn.execute("""select game_id is null as game_detached, operation_id=%s as op_kept,
            operation_kind, cost_usd, counts_as_spend from app.usage_events where event_id=any(%s)
            order by attempt_ordinal""", (op, events)).fetchall()
        out["rows_after_delete"] = [dict(r) for r in rows]
        out["operation_row_gone"] = conn.execute("select count(*) n from app.operations where id=%s",
                                                 (op,)).fetchone()["n"] == 0
        with conn.transaction():
            out["cleanup_usage_deleted"] = conn.execute(
                "delete from app.usage_events where event_id=any(%s)", (events,)).rowcount
        out["after_cleanup"] = _measure(conn, owner)
        return out

    out = s192.query(env, go, retries=1)
    b, a = out["before_delete"], out["after_delete"]
    out["checks"] = {
        "owner_spend_unchanged": b["owner_spend_usd"] == a["owner_spend_usd"] == COST,
        # day-wide sums/turns are reported (before_delete/after_delete) but not asserted: a real turn
        # between the two reads would change them for reasons unrelated to this proof.
        "rows_kept": len(out["rows_after_delete"]) == 2 and all(
            r["game_detached"] and r["op_kept"] and r["operation_kind"] == "turn" for r in out["rows_after_delete"]),
        "cleanup_restored_owner": out["after_cleanup"]["owner_spend_usd"] == 0,
    }
    out["ok"] = all(out["checks"].values())
    return out


def main(argv=None) -> int:
    common.load_dotenv_quietly()
    ap = argparse.ArgumentParser()
    common.add_guard_args(ap)
    a = ap.parse_args(argv)
    common.require_staging(a.confirm_staging)
    out = {"at": s192.now_iso(), **run(s192.load_env())}
    print(common.write_evidence("spec279_usage_survives_delete", out,
                                EVIDENCE / "spec279_usage_survives_delete.json"))
    print("ok" if out["ok"] else "FAILED", out["checks"])
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
