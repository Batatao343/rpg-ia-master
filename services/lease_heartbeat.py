"""Bounded renewal lifecycle. The database fence remains the final authority."""
from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Callable, Iterator
from threading import Event, Thread

from infrastructure.contracts import LeaseHeld


class LeaseWatch:
    def __init__(self) -> None:
        self.lost = Event()

    def check(self) -> None:
        if self.lost.is_set():
            raise LeaseHeld("lease_lost")


@contextmanager
def keep_lease_alive(renew: Callable[[], None] | None, *,
                    interval_seconds: float = 20) -> Iterator[LeaseWatch]:
    if interval_seconds <= 0:
        raise ValueError("positive heartbeat interval required")
    watch, stop = LeaseWatch(), Event()

    def tick() -> bool:
        from observability.metrics import metrics
        try:
            if renew is not None:
                renew()
            metrics.increment("rpg_lease_renewals_total", {"outcome": "ok"})
            return True
        except Exception:
            watch.lost.set()
            metrics.increment("rpg_lease_renewals_total", {"outcome": "lost"})
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
            thread = Thread(target=loop, name="lease-heartbeat", daemon=True)
            thread.start()
        yield watch
        watch.check()
    finally:
        stop.set()
        if thread is not None:
            thread.join()  # DB adapters have bounded connect/query timeouts.
