from __future__ import annotations

import json
import os
from copy import deepcopy
from uuid import uuid4

import pytest

from infrastructure.contracts import Conflict, Principal
from services.game_serialization import document_sha256, serialize_game_state
from services.game_transfer import export_game, import_saves, scan_saves, verify_export


pytestmark = pytest.mark.infra_local


def _state(game_id):
    return {
        "schema_version": 8,
        "game_id": str(game_id),
        "player": {
            "name": "Transferência", "class_name": "Devoto do Abismo", "level": 1,
            "virtudes": {"corpo": 2}, "vitalidade": 18, "max_vitalidade": 18,
        },
        "world": {
            "current_location": "Nova Arcádia", "turn_count": 0,
            "world_clock": {"day": 1, "period": "Manhã"},
        },
        "messages": [],
        "event_log": [{
            "event_id": "transfer-evt", "turn": 0, "type": "campaign_started",
            "payload": {"source": "fixture"}, "source": "test",
        }],
    }


def test_import_preview_resume_export_and_divergent_collision(tmp_path):
    pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    from infrastructure.postgres import PostgresGameStore, PostgresPool

    pool = PostgresPool(dsn)
    owner_id, game_id = uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    source = tmp_path / "source"
    source.mkdir()
    save = source / f"{game_id}.json"
    state = _state(game_id)
    save.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    corrupt = source / "corrupt.json"
    corrupt.write_text("{", encoding="utf-8")

    previews = scan_saves(source)
    assert {row.status for row in previews} == {"valid", "corrupt"}
    dry_rows = import_saves(pool, principal, source, dry_run=True)
    assert next(row for row in dry_rows if row["game_id"])["status"] == "would_import"
    assert PostgresGameStore(pool).get(principal, game_id) is None

    journal = tmp_path / "journal.jsonl"
    rows = import_saves(pool, principal, source, dry_run=False, journal_path=journal)
    assert {row["status"] for row in rows} == {"corrupt", "imported"}
    assert save.exists() and corrupt.exists()
    rows = import_saves(pool, principal, source, dry_run=False, journal_path=journal)
    assert {row["status"] for row in rows} == {"corrupt", "journal_skip"}

    bundle = export_game(pool, principal, game_id)
    assert verify_export(bundle) == []
    assert bundle["state_sha256"] == document_sha256(
        serialize_game_state(PostgresGameStore(pool).get(principal, game_id).state)
    )

    divergent = deepcopy(state)
    divergent["player"]["gold"] = 999
    save.write_text(json.dumps(divergent, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(Conflict):
        import_saves(pool, principal, save, dry_run=False)
    PostgresGameStore(pool).delete(principal, game_id)
    pool.close()
