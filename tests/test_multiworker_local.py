from __future__ import annotations

import os

import pytest

from scripts.load_test import run


pytestmark = pytest.mark.infra_local


def test_dois_processos_commit_receipt_e_jobs_sem_duplicar(tmp_path):
    pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    result = run(dsn, workers=2, operations=4, output=tmp_path / "load.json")
    assert result["status"] == "passed"
    assert result["duplicate_turn_rows"] == 1
    assert result["jobs_succeeded"] == 4
