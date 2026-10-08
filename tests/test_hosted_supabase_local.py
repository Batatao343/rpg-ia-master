"""Real local Postgres pool bound; never contacts hosted Supabase."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import threading
import time

import pytest

from infrastructure.postgres import PostgresPool


@pytest.mark.infra_local
def test_pool_concurrent_active_connections_never_exceed_max() -> None:
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL local required")
    pool = PostgresPool(dsn, min_size=0, max_size=2, timeout=5)
    active = 0
    peak = 0
    lock = threading.Lock()

    def use_connection(_index: int) -> None:
        nonlocal active, peak
        with pool.connection() as connection:
            assert connection.execute("select 1").fetchone() is not None
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.06)
            with lock:
                active -= 1

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(use_connection, range(16)))
        assert peak == 2  # Both slots were exercised; eight workers never exceeded them.
        assert pool._pool.get_stats()["pool_size"] <= 2
    finally:
        pool.close()
