"""Transport-independent execution and fenced operation lifecycle."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from typing import Any, ContextManager

from services.lease_heartbeat import keep_lease_alive


@contextmanager
def operation_scope(coordinator: Any, claim: Any, *,
                    spend_scope: ContextManager[None] | None = None) -> Iterator[Any]:
    renew = getattr(coordinator, 'heartbeat', None) if claim is not None else None
    completed = getattr(coordinator, 'is_completed', None) if claim is not None else None
    try:
        with (spend_scope or nullcontext()), keep_lease_alive(
            (lambda: renew(claim)) if renew else None,
            interval_seconds=float(getattr(coordinator, 'lease_seconds', 180)) / 4,
            # SPEC-236 R8: a renewal that loses only because the commit cleared the lease is
            # benign; the durable operation status decides, not the racing heartbeat tick.
            confirm_completed=(lambda: bool(completed(claim))) if completed else None,
        ) as lease:
            yield lease
    except BaseException as exc:
        if claim is not None:
            try:
                coordinator.fail(claim, type(exc).__name__)
            except Exception:
                pass  # Fence may already belong to another worker.
        raise


def execute_graph(graph: Any, state: dict, *, progress: Callable | None = None) -> dict:
    if progress is None:
        return graph.invoke(state)
    final = None
    for chunk in graph.stream(state, stream_mode=['updates', 'values']):
        progress(chunk)
        mode, data = chunk
        if mode == 'values':
            final = data
    if final is None:
        raise RuntimeError('stream did not produce final state')
    return final
