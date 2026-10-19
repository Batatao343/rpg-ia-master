"""SPEC-281: o client HTTP do Jev é construído fora do prazo de 1 s."""

from __future__ import annotations

import time

import pytest

from services import jev_rollout


class _SlowClient:
    built = 0

    def __init__(self) -> None:
        type(self).built += 1
        time.sleep(0.4)


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(jev_rollout, "_client", None)
    _SlowClient.built = 0
    import httpx
    monkeypatch.setattr(httpx, "Client", _SlowClient)
    yield


def test_off_does_not_build_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "off")
    assert jev_rollout.begin({}, "ando") is None
    assert _SlowClient.built == 0
    assert jev_rollout._client is None


def test_client_built_before_deadline_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "shadow")
    monkeypatch.setattr(jev_rollout, "_jev_switched_off", lambda: False)
    monkeypatch.setattr(jev_rollout, "JEV_DEADLINE_SECONDS", 0.2)  # < construção (0.4 s)

    class _Backend:
        def decide(self, request, *, idempotency_key):
            raise RuntimeError("stop")

    # backend=None => caminho de produção (_default_backend dentro do worker).
    t0 = time.monotonic()
    pending = jev_rollout.begin({}, "ando")
    elapsed = time.monotonic() - t0
    assert pending is not None
    assert _SlowClient.built == 1
    assert elapsed >= 0.4  # a construção foi paga ANTES do relógio
    # O relógio só começou depois: a espera não inclui os 0.4 s de construção.
    assert time.monotonic() - pending._started < 0.2
    assert jev_rollout._client is not None


def test_warm_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    jev_rollout.warm_client()
    jev_rollout.warm_client()
    assert _SlowClient.built == 1


def test_injected_backend_skips_warm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "shadow")
    monkeypatch.setattr(jev_rollout, "_jev_switched_off", lambda: False)

    class _B:
        def decide(self, request, *, idempotency_key):
            raise RuntimeError("x")

    assert jev_rollout.begin({}, "ando", backend=_B()) is not None
    assert _SlowClient.built == 0
