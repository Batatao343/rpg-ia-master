from __future__ import annotations

import os

import pytest

import persistence
from playtest.runner import PlaytestPersistenceError, _require_persisted


def test_replace_atomico_repete_lock_efemero(monkeypatch, tmp_path):
    source = tmp_path / "source.tmp"
    destination = tmp_path / "save.json"
    source.write_text("ok", encoding="utf-8")
    real_replace = os.replace
    calls = 0

    def flaky(src, dst):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise PermissionError("scanner segurou o arquivo")
        return real_replace(src, dst)

    monkeypatch.setattr(persistence.os, "replace", flaky)
    monkeypatch.setattr(persistence.time, "sleep", lambda _seconds: None)
    persistence._replace_with_retry(str(source), str(destination))
    assert calls == 3 and destination.read_text(encoding="utf-8") == "ok"


def test_harness_promove_save_false_a_erro():
    with pytest.raises(PlaytestPersistenceError, match="turno 7"):
        _require_persisted(lambda _state: False, {}, phase="turno 7")
