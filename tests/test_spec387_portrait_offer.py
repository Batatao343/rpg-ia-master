"""SPEC-387 R5-R7: leitura de preço/registro/chaves sem cache de falha, 1 retry de checkout, causa medida."""

from __future__ import annotations

import sys
import types

import pytest
from psycopg_pool import PoolTimeout

import api
from services import kill_switches as ks
from services.checkout_retry import retry_once


class _Repo:
    outcomes: list = []
    calls = 0

    def __init__(self, *_a, **_k):
        pass

    def peek_ceiling(self, _kind):
        _Repo.calls += 1
        out = _Repo.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


@pytest.fixture
def price_env(monkeypatch):
    _Repo.outcomes, _Repo.calls = [], 0
    monkeypatch.setitem(
        sys.modules,
        "services.image_quotes",
        types.SimpleNamespace(ImageQuoteRepository=_Repo),
    )
    rt = types.SimpleNamespace(resources=[object()])
    monkeypatch.setitem(
        sys.modules, "infrastructure.runtime", types.SimpleNamespace(get_runtime=lambda: rt)
    )
    monkeypatch.setitem(api._PORTRAIT_PRICE_CACHE, "at", 0.0)
    monkeypatch.setitem(api._PORTRAIT_PRICE_CACHE, "value", None)
    return _Repo


def test_price_failure_not_cached(price_env):
    price_env.outcomes = [RuntimeError("boom"), 15]
    assert api._portrait_price_estilhas() is None
    assert api._PORTRAIT_PRICE_CACHE["at"] == 0.0  # nada guardado
    assert api._portrait_price_estilhas() == 1  # próxima view tenta de novo e acha
    assert price_env.calls == 2


def test_checkout_retry_once_price_registry_switches(price_env):
    price_env.outcomes = [PoolTimeout("checkout"), 15]
    assert api._portrait_price_estilhas() == 1
    assert price_env.calls == 2
    price_env.outcomes = [PoolTimeout("a"), PoolTimeout("b")]
    api._PORTRAIT_PRICE_CACHE["at"] = 0.0
    assert api._portrait_price_estilhas() is None  # 2ª falha: sem oferta, sem exceção

    state = {"n": 0}

    class Store:
        def load(self):
            state["n"] += 1
            if state["n"] == 1:
                raise PoolTimeout("checkout")
            return {"image_generation": True}

    sw = ks.KillSwitches(Store(), ttl=0)
    assert sw.snapshot().get("image_generation") is True and state["n"] == 2

    calls = []

    def reg():
        calls.append(1)
        if len(calls) == 1:
            raise PoolTimeout("x")
        return "rows"

    assert retry_once(reg) == "rows" and len(calls) == 2


def test_execute_error_not_retried(price_env):
    calls = []

    def boom():
        calls.append(1)
        raise ValueError("execute")

    with pytest.raises(ValueError):
        retry_once(boom)
    assert calls == [1]


def test_offer_omitted_event_cause(price_env, monkeypatch):
    seen = []
    import services.portrait_offer_log as pol

    monkeypatch.setattr(pol, "log_event", lambda *a, **k: seen.append((a, k)))
    price_env.outcomes = [RuntimeError("boom")]
    assert api._portrait_price_estilhas() is None
    ((args, kw),) = seen
    assert args == ("creature_portrait", "offer_omitted")
    assert kw["cause"] == "price_peek_failed" and kw["error_class"] == "RuntimeError"
    assert "game" not in "".join(kw)
