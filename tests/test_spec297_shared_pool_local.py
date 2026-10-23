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
