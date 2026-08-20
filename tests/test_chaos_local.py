from __future__ import annotations

import os

import pytest

from scripts.chaos_test import run


pytestmark = pytest.mark.chaos_local


def test_fencing_recovery_e_rollback_atomico(tmp_path):
    pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    result = run(dsn, output=tmp_path / "chaos.json")
    assert result["status"] == "passed"
    assert all(result["scenarios"].values())
