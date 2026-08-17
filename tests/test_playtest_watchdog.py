"""Regressões da spec hardening-playtest-watchdog."""
from __future__ import annotations

import json
import os
import socket
import time
from datetime import datetime, timedelta

import pytest

from playtest import telemetry
from playtest import runner


def test_watchdog_interrompe_espera_no_teto_sem_bloquear_saida():
    started = time.monotonic()
    with pytest.raises(runner.PlaytestTimeoutError) as caught:
        runner._run_with_watchdog(
            lambda: time.sleep(0.25),
            timeout_seconds=0.02,
            phase="turno 3",
        )
    elapsed = time.monotonic() - started

    assert elapsed < 0.15
    assert caught.value.phase == "turno 3"


def test_watchdog_rejeita_resultado_que_chegou_apos_salto_do_relogio(
    monkeypatch,
):
    wall = iter((100.0, 260.0))
    monkeypatch.setattr(runner.time, "time", lambda: next(wall))

    with pytest.raises(runner.PlaytestTimeoutError) as caught:
        runner._run_with_watchdog(
            lambda: "resultado tardio",
            timeout_seconds=120,
            phase="turno 64",
        )

    assert caught.value.phase == "turno 64"
    assert caught.value.elapsed_seconds >= 160
    assert "160" in str(caught.value)


def test_runner_timeout_de_startup_aborta_sem_falso_turno(
    tmp_path, monkeypatch,
):
    import main

    class SlowStartupGraph:
        def invoke(self, state):
            time.sleep(0.25)
            return state

    monkeypatch.setattr(main, "app", SlowStartupGraph())
    monkeypatch.setattr(runner, "PLAYTEST_SAVES_DIR", str(tmp_path / "saves"))
    monkeypatch.setattr(runner, "_build_initial_state", lambda *_a, **_k: {
        "game_id": "00000000-0000-0000-0000-000000000001",
        "messages": [],
        "player": {},
        "world": {},
        "event_log": [],
    })

    result = runner.run_campaign(
        "explorador",
        turns=2,
        seed=1,
        invariants=False,
        turn_timeout_seconds=0.02,
    )

    assert result.turns_completed == 0
    assert result.aborted_reason and result.aborted_reason.startswith("timeout:")
    assert result.errors[0]["phase"] == "startup"
    assert "PlaytestTimeoutError" in result.errors[0]["exc"]


def test_finish_run_preserva_status_aborted(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    telemetry.begin_run(
        "run-abortada", profiles=["explorador"], turns=3, seed=1, real=True,
    )

    inspected = telemetry.finish_run(
        "run-abortada", status="aborted", reason="timeout: startup",
    )

    assert inspected["status"] == "aborted"
    assert inspected["complete"] is False
    meta = json.loads(
        (tmp_path / "run-abortada" / telemetry.RUN_META_FILENAME).read_text(
            encoding="utf-8",
        )
    )
    assert meta["abort_reason"] == "timeout: startup"


def test_recover_stale_runs_aborta_antiga_e_preserva_recente(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    old = tmp_path / "old"
    recent = tmp_path / "recent"
    old.mkdir()
    recent.mkdir()
    base = {
        "schema_version": 2,
        "status": "running",
        "complete": False,
        "expected": {},
        "campaigns": {},
    }
    (old / telemetry.RUN_META_FILENAME).write_text(
        json.dumps({**base, "run_id": "old", "created_at": "2000-01-01T00:00:00"}),
        encoding="utf-8",
    )
    (recent / telemetry.RUN_META_FILENAME).write_text(
        json.dumps({
            **base,
            "run_id": "recent",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }),
        encoding="utf-8",
    )

    recovered = telemetry.recover_stale_runs(max_age_seconds=60)

    assert recovered == ["old"]
    old_meta = json.loads(
        (old / telemetry.RUN_META_FILENAME).read_text(encoding="utf-8")
    )
    recent_meta = json.loads(
        (recent / telemetry.RUN_META_FILENAME).read_text(encoding="utf-8")
    )
    assert old_meta["status"] == "aborted"
    assert old_meta["abort_reason"] == "stale_running_manifest"
    assert recent_meta["status"] == "running"


def test_recover_stale_preserva_manifesto_antigo_de_pid_vivo(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr(telemetry, "_pid_is_alive", lambda pid: pid == 4242)
    now = datetime(2026, 8, 3, 12, 0, 0)
    run = tmp_path / "long-running"
    run.mkdir()
    (run / telemetry.RUN_META_FILENAME).write_text(json.dumps({
        "schema_version": 3,
        "run_id": "long-running",
        "created_at": (now - timedelta(hours=9)).isoformat(),
        "heartbeat_at": (now - timedelta(hours=9)).isoformat(),
        "status": "running",
        "complete": False,
        "owner": {"pid": 4242, "host": socket.gethostname()},
        "expected": {},
        "campaigns": {},
    }), encoding="utf-8")

    recovered = telemetry.recover_stale_runs(max_age_seconds=60, now=now)

    assert recovered == []
    meta = json.loads(
        (run / telemetry.RUN_META_FILENAME).read_text(encoding="utf-8")
    )
    assert meta["status"] == "running"


def test_recover_stale_aborta_pid_morto_com_heartbeat_antigo(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr(telemetry, "_pid_is_alive", lambda _pid: False)
    now = datetime(2026, 8, 3, 12, 0, 0)
    run = tmp_path / "dead-owner"
    run.mkdir()
    (run / telemetry.RUN_META_FILENAME).write_text(json.dumps({
        "schema_version": 3,
        "run_id": "dead-owner",
        "created_at": (now - timedelta(hours=9)).isoformat(),
        "heartbeat_at": (now - timedelta(hours=7)).isoformat(),
        "status": "running",
        "complete": False,
        "owner": {"pid": 9999, "host": socket.gethostname()},
        "expected": {},
        "campaigns": {},
    }), encoding="utf-8")

    assert telemetry.recover_stale_runs(max_age_seconds=60, now=now) == [
        "dead-owner"
    ]


def test_recover_stale_preserva_heartbeat_recente_sem_pid_verificavel(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    now = datetime(2026, 8, 3, 12, 0, 0)
    run = tmp_path / "remote-active"
    run.mkdir()
    (run / telemetry.RUN_META_FILENAME).write_text(json.dumps({
        "schema_version": 3,
        "run_id": "remote-active",
        "created_at": (now - timedelta(hours=9)).isoformat(),
        "heartbeat_at": (now - timedelta(seconds=10)).isoformat(),
        "status": "running",
        "complete": False,
        "owner": {"pid": 77, "host": "outro-host"},
        "expected": {},
        "campaigns": {},
    }), encoding="utf-8")

    assert telemetry.recover_stale_runs(max_age_seconds=60, now=now) == []


def test_begin_e_touch_run_gravam_owner_e_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    telemetry.begin_run(
        "owned", profiles=["explorador"], turns=1, seed=1, real=False,
    )
    before = json.loads(
        (tmp_path / "owned" / telemetry.RUN_META_FILENAME).read_text(
            encoding="utf-8",
        )
    )
    touched_at = datetime.now() + timedelta(seconds=5)

    assert telemetry.touch_run("owned", now=touched_at) is True
    after = json.loads(
        (tmp_path / "owned" / telemetry.RUN_META_FILENAME).read_text(
            encoding="utf-8",
        )
    )
    assert before["schema_version"] == 3
    assert before["owner"] == {"pid": os.getpid(), "host": socket.gethostname()}
    assert before["heartbeat_at"]
    assert after["heartbeat_at"] == touched_at.isoformat(timespec="seconds")
