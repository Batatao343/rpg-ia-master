"""SPEC-185 transactional Postgres check; all facts roll back after the test."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4

import pytest

from infrastructure.account_read_model import PostgresAccountReader
from infrastructure.contracts import Principal


pytestmark = pytest.mark.infra_local


class SingleConnectionPool:
    def __init__(self, connection):
        self.db = connection

    def connection(self):
        class Context:
            def __enter__(inner):
                return self.db

            def __exit__(inner, *_args):
                return False
        return Context()


def test_account_sql_uses_utc_owner_and_index_in_real_postgres():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    a, b, game, operation, event, reservation, entry = (uuid4() for _ in range(7))
    owner_a, owner_b = Principal(a, "test", str(a)), Principal(b, "test", str(b))
    version = "account-local-" + str(uuid4())
    at = datetime(2026, 10, 9, 0, 30, tzinfo=timezone.utc)
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        try:
            if connection.execute("select to_regclass('app.wallet_entries') as relation").fetchone()["relation"] is None:
                pytest.skip("migration SPEC-184 não aplicada")
            column = connection.execute(
                "select 1 from information_schema.columns where table_schema='app' "
                "and table_name='turns' and column_name='presentation_entry_id'",
            ).fetchone()
            if column is None:
                migration = Path("supabase/migrations/20261009120000_account_turn_attribution.sql")
                connection.execute(migration.read_text(encoding="utf-8"))
            connection.execute("set local time zone 'America/Sao_Paulo'")
            connection.execute(
                """insert into app.games(id,owner_id,schema_version,state,state_sha256,status,
                   player_name,class_name,player_level,location_name,world_day,game_over,combat_simulation)
                   values (%s,%s,1,%s,%s,'active','Ayla','Devoto',1,'Porto',1,false,false)""",
                (game, a, Jsonb({"game_id": str(game)}), "0" * 64),
            )
            connection.execute(
                """insert into app.operations(id,owner_id,game_id,kind,status,request_sha256)
                   values (%s,%s,%s,'turn','completed',%s)""",
                (operation, a, game, "0" * 64),
            )
            connection.execute(
                """insert into app.turns(operation_id,game_id,owner_id,sequence,timeline_epoch,
                   input_sha256,state_version_before,llm_cost_usd,presentation_entry_id)
                   values (%s,%s,%s,1,1,%s,1,0.000041550,'entry-a')""",
                (operation, game, a, "0" * 64),
            )
            connection.execute(
                """insert into app.usage_events(event_id,operation_id,owner_id,game_id,
                   component,attempt_ordinal,category,provider,model,outcome,cost_usd,cost_basis,
                   pricing_version,billing_exact,event_sha256)
                   values (%s,%s,%s,%s,'llm:test',0,'llm','test','test','success',
                           0.000041550,'estimated','test',false,%s)""",
                (event, operation, a, game, "a" * 64),
            )
            connection.execute(
                """insert into app.pricing_versions(version_id,shard_budget_unit_brl,
                   fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,fx_buffer_rate,
                   rate_card_version,rate_card_sha256,rate_card_source,rate_card_observed_at,
                   rate_card_max_age_seconds,channel_fees)
                   values (%s,0.03,5,'test',%s,86400,0.1,'test',%s,'test',%s,86400,%s)""",
                (version, at, "a" * 64, at,
                 Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"}})),
            )
            connection.execute("insert into app.wallet_accounts(owner_id) values (%s)", (a,))
            connection.execute(
                """insert into app.wallet_reservations(reservation_id,owner_id,reference_type,
                   reference_id,pricing_version_id,fence_token,ceiling_milli,settled_milli,
                   status,finished_at)
                   values (%s,%s,'speech_to_text',%s,%s,%s,1000,1000,'settled',%s)""",
                (reservation, a, str(uuid4()), version, uuid4(), at),
            )
            connection.execute(
                """insert into app.wallet_entries(entry_id,owner_id,entry_type,reference_type,
                   reference_id,reservation_id,pricing_version_id,amount_milli,
                   available_delta,reserved_delta,created_at)
                   values (%s,%s,'settle','reservation',%s,%s,%s,1000,0,-1000,%s)""",
                (entry, a, str(reservation), reservation, version, at),
            )
            reader = PostgresAccountReader(SingleConnectionPool(connection))
            record = [{"id": "entry-a", "epoch": 1, "role": "narrator"}]
            assert reader.history_costs(owner_a, game, record) == {
                "entry-a": {"cost_milli": None, "technical_cost_usd": "0.000041550",
                            "technical_cost_basis": "usage_ledger", "technical_cost_exact": False}}
            assert reader.history_costs(owner_b, game, record) == {}
            assert reader.operation_cost(owner_b, game, operation) is None
            series = reader.series(owner_a, "7d", now=datetime(2026, 10, 9, 12, tzinfo=timezone.utc))
            assert series["totals"]["voice"] == "1000"
            assert series["points"][-1]["voice"] == "1000"  # UTC day 9, local day 8
            assert reader.series(owner_b, "7d", now=datetime(2026, 10, 9, 12, tzinfo=timezone.utc))["totals"]["voice"] == "0"
            connection.execute(
                """with ops as (
                  insert into app.operations(id,owner_id,game_id,kind,status,request_sha256)
                  select gen_random_uuid(),%s,%s,'turn','completed',%s
                  from generate_series(1,500) returning id
                )
                insert into app.turns(operation_id,game_id,owner_id,sequence,timeline_epoch,
                  input_sha256,state_version_before,llm_cost_usd,presentation_entry_id)
                select id,%s,%s,row_number() over (order by id)+1,1,%s,1,0,
                  'other-'||id::text from ops""",
                (a, game, "0" * 64, game, a, "0" * 64),
            )
            connection.execute("analyze app.turns")
            connection.execute("set local enable_seqscan=off")
            plan = connection.execute(
                """explain select presentation_entry_id from app.turns
                   where owner_id=%s and game_id=%s and presentation_entry_id=any(%s)""",
                (a, game, ["entry-a"]),
            ).fetchall()
            assert any("turns_owner_history_entry_idx" in row["QUERY PLAN"] for row in plan), plan
        finally:
            connection.rollback()
