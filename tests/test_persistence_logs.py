"""SPEC-253: migracao, schema recusado, retry atomico e meta de RAG logados."""
import json
import os

import pytest

import persistence
from observability import logging_setup

GID = "11111111-2222-3333-4444-555555555555"


def _lines(capsys):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            pass
    return out


@pytest.fixture(autouse=True)
def _log():
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug", "RPG_LOG_PROPAGATE": "1"})


def _events(capsys, name):
    return [l for l in _lines(capsys) if l.get("event") == name]


def test_migration_logged_from_to(capsys):
    capsys.readouterr()
    persistence.migrate_state({"schema_version": 3, "game_id": GID, "player": {}})
    ev = _events(capsys, "persistence.migrated")
    assert len(ev) == 1
    assert ev[0]["from_version"] == 3 and ev[0]["to_version"] == persistence.SCHEMA_VERSION
    assert GID not in json.dumps(ev[0])


def test_current_version_not_logged(capsys):
    capsys.readouterr()
    persistence.migrate_state({"schema_version": persistence.SCHEMA_VERSION})
    assert not _events(capsys, "persistence.migrated")


def test_newer_schema_logged(capsys):
    capsys.readouterr()
    with pytest.raises(persistence.IncompatibleSaveError):
        persistence.migrate_state({"schema_version": persistence.SCHEMA_VERSION + 5, "game_id": GID})
    ev = _events(capsys, "persistence.save_schema_newer")
    assert ev and ev[0]["found_version"] == persistence.SCHEMA_VERSION + 5
    assert ev[0]["supported_version"] == persistence.SCHEMA_VERSION
    assert GID not in json.dumps(ev[0])


def test_atomic_retry_logged(capsys, monkeypatch, tmp_path):
    def boom(a, b):
        raise PermissionError("C:/secret/path")
    monkeypatch.setattr(os, "replace", boom)
    capsys.readouterr()
    with pytest.raises(PermissionError):
        persistence._replace_with_retry("a", "b", attempts=3)
    lines = _lines(capsys)
    retries = [l for l in lines if l.get("event") == "persistence.atomic_retry"]
    failed = [l for l in lines if l.get("event") == "persistence.atomic_failed"]
    assert len(retries) == 2 and len(failed) == 1 and failed[0]["attempts"] == 3
    assert "secret" not in json.dumps(lines)


def test_save_failure_has_game_ref_and_duration(capsys, monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    monkeypatch.setattr(persistence, "_atomic_write_json",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    capsys.readouterr()
    assert persistence.save_game_state({"game_id": GID}) is False
    ev = _events(capsys, "persistence.save_failed")
    assert ev and ev[0]["error_type"] == "OSError" and "duration_ms" in ev[0]
    assert ev[0]["game_ref"] and GID not in json.dumps(ev[0])


def test_corrupt_meta_logged(capsys, tmp_path):
    import rag
    d = tmp_path / "faiss_lore_index"
    d.mkdir()
    (d / rag._META_FILE).write_text("{not json", encoding="utf-8")
    capsys.readouterr()
    assert rag._read_meta(str(d)) is None
    ev = _events(capsys, "rag.meta_unreadable")
    assert ev and ev[0]["index"] == "faiss_lore_index"
    assert str(tmp_path) not in json.dumps(ev[0])


def test_missing_meta_silent(capsys, tmp_path):
    import rag
    capsys.readouterr()
    assert rag._read_meta(str(tmp_path)) is None
    assert not _events(capsys, "rag.meta_unreadable")
