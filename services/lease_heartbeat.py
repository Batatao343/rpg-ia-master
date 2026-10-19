"""Bounded renewal lifecycle. The database fence remains the final authority."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import copy_context
from threading import Event, Thread

from infrastructure.contracts import LeaseHeld
from infrastructure.db_log import conflict as _db_conflict


class LeaseWatch:
    """``lost`` is set by the renewal loop; ``committed`` stops it (SPEC-236 R8).

    Once the owner's work is durably committed, a later renewal failure (the commit itself
    cleared the lease token) is benign and must never turn a saved turn into an error.
    """

    def __init__(self, confirm_completed: Callable[[], bool] | None = None) -> None:
        self.lost = Event()
        self.committed = Event()
        self._stop: Event | None = None
        self._confirm_completed = confirm_completed

    def mark_committed(self) -> None:
        self.committed.set()
        if self._stop is not None:
            self._stop.set()

    def check(self) -> None:
        if not self.lost.is_set() or self.committed.is_set():
            return
        if self._confirm_completed is not None:
            try:
                if self._confirm_completed():
                    self.committed.set()
                    return
            except Exception:  # silent-ok: desfecho desconhecido => resultado conservador lease_lost
                pass
        _db_conflict("lease_conflict", "lease_lost", op_kind="heartbeat")      # SPEC-254 R1
        raise LeaseHeld("lease_lost")


@contextmanager
def keep_lease_alive(renew: Callable[[], None] | None, *,
                    interval_seconds: float = 20,
                    confirm_completed: Callable[[], bool] | None = None) -> Iterator[LeaseWatch]:
    if interval_seconds <= 0:
        raise ValueError("positive heartbeat interval required")
    watch, stop = LeaseWatch(confirm_completed), Event()
    watch._stop = stop

    def tick() -> bool:
        from observability.metrics import metrics
        if watch.committed.is_set():
            return False  # stop renewing after the durable commit
        try:
            if renew is not None:
                renew()
            metrics.increment("rpg_lease_renewals_total", {"outcome": "ok"})
            return True
        except Exception as exc:
            if watch.committed.is_set():
                return False
            watch.lost.set()
            metrics.increment("rpg_lease_renewals_total", {"outcome": "lost"})
            from observability.telemetry import log_event
            log_event("db", "lease_renewal_failed", level="warning", error_type=type(exc).__name__)
            return False

    def loop() -> None:
        while not stop.wait(interval_seconds):
            if not tick():
                return

    thread = None
    try:
        if renew is not None:
            tick()
            watch.check()
            # SPEC-224: o renovador herda o principal do request, entao o UPDATE do lease roda
            # sob `rpg_api` (RLS por owner) e nao no login de sessao.
            thread = Thread(target=copy_context().run, args=(loop,), name="lease-heartbeat", daemon=True)
            thread.start()
        yield watch
        watch.check()
    finally:
        stop.set()
        if thread is not None:
            thread.join()  # DB adapters have bounded connect/query timeouts.
