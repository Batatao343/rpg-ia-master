"""Internal cron endpoints for serverless hosting (SPEC-192 R4/R5/R9).

Invoked by Supabase pg_cron + pg_net with ``Authorization: Bearer <RPG_CRON_SECRET>``.
Responses carry only counts/durations, never owner ids or emails.
"""
from __future__ import annotations

import hmac
import logging
import os
import threading
import time
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from observability.telemetry import safe_json

router = APIRouter(prefix="/internal/cron", tags=["internal"])
_log = logging.getLogger("rpg.cron")

MIN_SECRET_LEN = 32
FAILURE_ALERT_AT = 3
_failures: dict[str, int] = {}
_failures_lock = threading.Lock()


def authorize(request: Request) -> None:
    secret = os.getenv("RPG_CRON_SECRET", "")
    if len(secret) < MIN_SECRET_LEN:
        raise HTTPException(503, "cron_not_configured")  # fail closed
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(
            token.encode(), secret.encode()):
        raise HTTPException(401, "unauthorized")


def budget_seconds() -> float:
    try:
        wanted = float(os.getenv("RPG_CRON_BUDGET_SECONDS", "50"))
    except ValueError:
        wanted = 50.0
    try:
        max_duration = float(os.getenv("RPG_CRON_MAX_DURATION_SECONDS", "60"))
    except ValueError:
        max_duration = 60.0
    return max(1.0, min(wanted, max_duration - 5.0))


def _runtime():
    from infrastructure.runtime import get_runtime
    return get_runtime()


def _record(task: str, ok: bool, started: float, **fields: Any) -> None:
    with _failures_lock:
        _failures[task] = 0 if ok else _failures.get(task, 0) + 1
        consecutive = _failures[task]
    level = logging.ERROR if consecutive >= FAILURE_ALERT_AT else (
        logging.INFO if ok else logging.WARNING)
    _log.log(level, safe_json({
        "event": "rpg.cron", "task": task, "outcome": "ok" if ok else "failed",
        "consecutive_failures": consecutive,
        "duration_s": round(time.monotonic() - started, 3), **fields}))


def _run(task: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = fn()
    except Exception as exc:
        _record(task, False, started, error_type=type(exc).__name__)
        raise HTTPException(500, "cron_task_failed") from None
    failed = int(result.get("failed", 0))
    _record(task, failed == 0, started, **{k: v for k, v in result.items()
                                           if isinstance(v, (int, float, str))})
    body = {"ok": failed == 0, **result, "duration_s": round(time.monotonic() - started, 3)}
    if failed:  # non-2xx so pg_net's _http_response.status_code flags the run (count-only body)
        return JSONResponse(body, status_code=500)
    return body


@router.post("/jobs")
def cron_jobs(request: Request):
    authorize(request)

    def task():
        from workers.drain import drain_jobs
        return drain_jobs(budget_seconds(), max_jobs=int(os.getenv("RPG_CRON_MAX_JOBS", "50")),
                          worker_id=f"cron-{os.getpid()}")
    return _run("jobs", task)


@router.post("/account-deletions")
def cron_account_deletions(request: Request):
    authorize(request)

    def task():
        from scripts.recover_account_deletions import run_recovery_batch
        runtime = _runtime()
        if os.getenv("RPG_RUNTIME_PROFILE", "").strip().lower() != "hosted-supabase":
            raise RuntimeError("profile")
        payload = run_recovery_batch(runtime, 10)  # batch mode set explicitly; SKIP LOCKED dedups
        deleted = sum(1 for r in payload["results"] if r["status"] == "deleted")
        return {"claimed": payload["count"], "deleted": deleted,
                "failed": payload["count"] - deleted,
                "auth_buckets_purged": payload["auth_buckets_purged"]}
    return _run("account_deletions", task)


@router.post("/operations")
def cron_operations(request: Request):
    authorize(request)

    def task():
        from services.operation_recovery import recover_expired
        return {**recover_expired(_runtime().game_store.pool, 50), "failed": 0}
    return _run("operations", task)


def _reconciler():
    """SPEC-195 job wiring; Google parts are optional when Play is not configured."""
    from infrastructure.google_play_payments import GooglePlayPurchases, PostgresPurchaseStore
    from infrastructure.reconciliation import PostgresStore, Reconciler
    from services.google_play import GooglePlayClient, GooglePlayError, GooglePlaySettings
    pool = _runtime().game_store.pool
    try:
        client = GooglePlayClient(GooglePlaySettings.from_env())
        purchases = GooglePlayPurchases(PostgresPurchaseStore(pool), client)
    except GooglePlayError:
        client = purchases = None
    return Reconciler(PostgresStore(pool), client, purchases)


@router.post("/reconciliation")
def cron_reconciliation(request: Request):
    authorize(request)

    def task():
        from services.google_play import GooglePlayError
        job = _reconciler()
        google_new, google_error = 0, 0
        try:  # a Google outage must not block Stripe/parked reconciliation
            google_new = job.poll_google_voided()
        except GooglePlayError:
            google_error = 1
        result = job.reconcile_batch(int(os.getenv("RPG_CRON_MAX_RECONCILE", "100")))
        from observability.metrics import metrics
        for status in ("parked", "orphaned"):
            metrics.set_gauge("rpg_reconciliation_events", {"status": status}, result[f"{status}_total"])
        return {**result, "google_voided_new": google_new, "google_poll_errors": google_error,
                "failed": result["failed"] + google_error}
    return _run("reconciliation", task)


def _finops_reader():
    from infrastructure.finops_reader import PostgresFinopsReader
    return PostgresFinopsReader(_runtime().game_store.pool)


def _finops_recorder():
    """Persist each evaluation (app.finops_evaluations) for SQL/pg_cron staleness checks."""
    try:
        from infrastructure.finops_reader import PostgresFinopsEvaluationStore
        return PostgresFinopsEvaluationStore(_runtime().game_store.pool)
    except Exception:  # no Postgres pool (legacy profile): evaluation still runs
        return None


@router.post("/finops")
def cron_finops(request: Request):
    """SPEC-196: margin report + alert evaluation + Prometheus gauges (owner-free output)."""
    authorize(request)

    def task():
        from services.finops_job import run_finops
        return run_finops(_finops_reader(), recorder=_finops_recorder())
    return _run("finops", task)
