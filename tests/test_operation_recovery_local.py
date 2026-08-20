from __future__ import annotations

import hashlib
import os
from uuid import uuid4

import pytest

from services.operation_recovery import abandon_expired, orphan_operations


pytestmark = pytest.mark.infra_local


def test_recovery_lists_and_abandons_only_expired_running_operation():
    pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    from infrastructure.postgres import PostgresPool

    pool = PostgresPool(dsn)
    owner, expired, completed = uuid4(), uuid4(), uuid4()
    digest = hashlib.sha256(b"fixture").hexdigest()
    with pool.connection() as connection, connection.transaction():
        connection.execute(
            """insert into app.operations
            (id,owner_id,kind,status,lease_until,request_sha256)
            values(%s,%s,'turn','running',now()-interval '1 second',%s),
                  (%s,%s,'turn','completed',null,%s)""",
            (expired, owner, digest, completed, owner, digest),
        )
    assert [row["id"] for row in orphan_operations(pool, owner_id=owner)] == [expired]
    assert abandon_expired(pool, expired) is True
    assert abandon_expired(pool, expired) is False
    with pool.connection() as connection, connection.transaction():
        status = connection.execute(
            "select status from app.operations where id=%s", (completed,),
        ).fetchone()["status"]
        assert status == "completed"
        connection.execute("delete from app.operations where id in (%s,%s)", (expired, completed))
    pool.close()
