"""SPEC-297 Etapa 7 - Postgres local: RLS, claim por lease e LGPD (R19, R31).

Roda contra o Postgres local do Supabase (`RPG_TEST_DATABASE_URL`); sem ele, pula. Tudo
roda dentro de uma transação que faz rollback ao sair.
"""

import os
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from tests.spec297_support import entry

pytestmark = pytest.mark.infra_local

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


@pytest.fixture
def db():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL absent")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        if conn.execute("select to_regclass('app.shared_pool') t").fetchone()["t"] is None:
            conn.execute(
                Path("supabase/migrations/20261024100000_shared_pool.sql").read_text(
                    encoding="utf-8"
                )
            )
        yield conn
        conn.rollback()


@pytest.fixture
def store(db):
    from infrastructure.postgres_shared_pool import PostgresSharedPoolStore

    class Pool:
        def connection(self):
            return nullcontext(db)

    return PostgresSharedPoolStore(Pool())


def _as_tenant(db, owner):
    db.execute("set local role rpg_api")
    db.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(owner),))


def _as_system(db):
    db.execute("reset role")


def _insert_sql(db, e):
    db.execute(
        """insert into app.shared_pool (entry_id, namespace, status, region_id, name, name_fold,
           name_origin, document, origin_owner_id, origin_game_id, promote_after)
           values (%s,'npc_template',%s,'nova_arcadia',%s,%s,'narrator','{}'::jsonb,%s,%s,%s)""",
        (
            e.entry_id,
            e.status.value,
            e.name,
            e.name_fold,
            e.origin_owner_id,
            e.origin_game_id,
            e.promote_after,
        ),
    )


def test_rpg_api_cannot_insert_promoted(db):
    owner = uuid4()
    _as_tenant(db, owner)
    with pytest.raises(Exception, match="row-level security"):
        _insert_sql(db, entry(entry_id="pool_npc_x1", status="promoted", owner=owner))


def test_rpg_api_cannot_insert_for_other_owner(db):
    _as_tenant(db, uuid4())
    with pytest.raises(Exception, match="row-level security"):
        _insert_sql(db, entry(entry_id="pool_npc_x2", status="held", owner=uuid4()))


def test_rpg_api_cannot_update_status(db):
    owner = uuid4()
    _as_tenant(db, owner)
    _insert_sql(db, entry(entry_id="pool_npc_x3", status="held", owner=owner))
    with pytest.raises(Exception, match="permission denied"):
        db.execute("update app.shared_pool set status='promoted' where entry_id='pool_npc_x3'")


def test_rpg_api_reads_promoted_and_own_held_only(db, store):
    a, b = uuid4(), uuid4()
    _as_system(db)
    _insert_sql(db, entry(entry_id="pool_npc_pa", status="promoted", owner=a))
    _insert_sql(db, entry(entry_id="pool_npc_ha", status="held", owner=a, name="Alfa Um"))
    _insert_sql(db, entry(entry_id="pool_npc_hb", status="held", owner=b, name="Beta Dois"))
    _as_tenant(db, a)
    seen = {r["entry_id"] for r in db.execute("select entry_id from app.shared_pool").fetchall()}
    assert {"pool_npc_pa", "pool_npc_ha"} <= seen and "pool_npc_hb" not in seen


def test_other_tenant_cannot_read_held(db):
    a = uuid4()
    _as_system(db)
    _insert_sql(db, entry(entry_id="pool_npc_h9", status="held", owner=a))
    _as_tenant(db, uuid4())
    assert db.execute("select 1 from app.shared_pool where entry_id='pool_npc_h9'").fetchall() == []


def test_promoted_content_is_immutable_by_trigger(db):
    _as_system(db)
    _insert_sql(db, entry(entry_id="pool_npc_im", status="promoted", owner=uuid4()))
    with pytest.raises(Exception, match="shared_pool_promoted_is_immutable"):
        db.execute("update app.shared_pool set legend='x' where entry_id='pool_npc_im'")


def test_skip_locked_two_workers_no_double_eval(db, store):
    _as_system(db)
    for i in range(4):
        e = entry(
            entry_id=f"pool_npc_w{i}",
            status="held",
            owner=uuid4(),
            name=f"Worker Teste{i}",
            promote_after=NOW - timedelta(hours=1),
        )
        _insert_sql(db, e)
    first = store.due(NOW, 2)
    second = store.due(NOW, 4)  # o lease da 1a chamada tira essas 2 do alcance da 2a
    ids1, ids2 = {e.entry_id for e in first}, {e.entry_id for e in second}
    assert len(first) == 2 and ids1.isdisjoint(ids2) and len(ids1 | ids2) == 4


def test_account_deletion_deletes_held_unlinks_promoted(db):
    from infrastructure.postgres_shared_pool import PostgresSharedPoolStore

    owner = uuid4()
    _as_system(db)
    for eid, status in (
        ("pool_npc_d1", "held"),
        ("pool_npc_d2", "promoted"),
        ("pool_npc_d3", "rejected"),
        ("pool_npc_d4", "local_only"),
    ):
        _insert_sql(db, entry(entry_id=eid, status=status, owner=owner, name=f"Del {eid}"))
    PostgresSharedPoolStore.erase_owner(db, owner)
    rows = {
        r["entry_id"]: r
        for r in db.execute(
            "select entry_id, origin_owner_id, origin_game_id from app.shared_pool "
            "where entry_id like 'pool_npc_d%'"
        ).fetchall()
    }
    assert set(rows) == {"pool_npc_d2"}
    assert (
        rows["pool_npc_d2"]["origin_owner_id"] is None
        and rows["pool_npc_d2"]["origin_game_id"] is None
    )


def test_write_fence_blocks_deleted_owner(db):
    owner = uuid4()
    _as_system(db)
    if db.execute("select to_regclass('app.account_deletions') t").fetchone()["t"] is None:
        pytest.skip("account_deletions ausente")
    db.execute("insert into app.account_deletions (owner_id) values (%s)", (owner,))
    with pytest.raises(Exception, match="account_deleted"):
        _insert_sql(db, entry(entry_id="pool_npc_fz", status="held", owner=owner))


def test_live_row_without_owner_is_rejected_by_check(db):
    _as_system(db)
    with pytest.raises(Exception, match="shared_pool_owner_required"):
        _insert_sql(db, entry(entry_id="pool_npc_no", status="held", owner=None))


def test_usage_sink_and_owner_lookup_against_real_schema(db, store):
    from infrastructure.usage_events import spend_schema_ready  # noqa: F401
    from workers import shared_pool_jobs as jobs

    _as_system(db)
    attempts = [
        {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "outcome": "success",
            "network_attempted": True,
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
    ]
    jobs.make_usage_sink(store.pool)(entry(entry_id="pool_npc_u1"), attempts)
    row = db.execute(
        "select count(*) n from app.usage_events where owner_id=%s and component like 'pool_eval%%'",
        (jobs.SYSTEM_OWNER_ID,),
    ).fetchone()
    assert row["n"] == 1
    user = uuid4()
    db.execute(
        "insert into auth.users (id, email, raw_user_meta_data) values (%s, %s, %s::jsonb)",
        (user, f"{user}@example.test", '{"full_name": "Pessoa De Teste"}'),
    )
    values = jobs.make_owner_values(store.pool)(entry(owner=user))
    assert f"{user}@example.test" in values and "Pessoa De Teste" in values


def test_export_includes_owner_pool_rows(db):
    _as_system(db)
    owner = uuid4()
    _insert_sql(db, entry(entry_id="pool_npc_ex", status="held", owner=owner))
    rows = db.execute(
        "select entry_id from app.shared_pool where origin_owner_id=%s", (owner,)
    ).fetchall()
    assert [r["entry_id"] for r in rows] == ["pool_npc_ex"]


def test_skip_locked_across_two_real_connections():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL absent")
    from infrastructure.postgres_shared_pool import PostgresSharedPoolStore

    owner = uuid4()
    ids = [f"pool_npc_sk{i}_{uuid4().hex[:6]}" for i in range(4)]
    with psycopg.connect(dsn, row_factory=dict_row, autocommit=True) as setup:
        if setup.execute("select to_regclass('app.shared_pool') t").fetchone()["t"] is None:
            setup.execute(
                Path("supabase/migrations/20261024100000_shared_pool.sql").read_text(
                    encoding="utf-8"
                )
            )
        for i, eid in enumerate(ids):
            _insert_sql(
                setup,
                entry(
                    entry_id=eid,
                    status="held",
                    owner=owner,
                    name=f"Sk Teste{i}",
                    promote_after=NOW - timedelta(hours=1),
                ),
            )
    try:
        with (
            psycopg.connect(dsn, row_factory=dict_row) as holder,
            psycopg.connect(dsn, row_factory=dict_row, autocommit=True) as worker,
        ):
            # worker 1 segura o lock de 2 linhas numa transação ABERTA
            held = holder.execute(
                "select entry_id from app.shared_pool where origin_owner_id=%s "
                "order by created_at, entry_id limit 2 for update",
                (owner,),
            ).fetchall()
            assert len(held) == 2

            class Pool:
                def connection(self):
                    return nullcontext(worker)

            got = PostgresSharedPoolStore(Pool()).due(NOW, 4)
            mine = {e.entry_id for e in got} & set(ids)
            assert mine.isdisjoint({r["entry_id"] for r in held}) and len(mine) == 2
            holder.rollback()
    finally:
        with psycopg.connect(dsn, autocommit=True) as cleanup:
            cleanup.execute("delete from app.shared_pool where origin_owner_id=%s", (owner,))
