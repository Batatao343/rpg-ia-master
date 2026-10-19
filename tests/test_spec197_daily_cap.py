"""SPEC-197 R7: daily spend cap -> automatic kill switches (never auto re-enable)."""

from __future__ import annotations

import os
from datetime import datetime, timezone, UTC
from decimal import Decimal as D

import pytest

from infrastructure.finops_reader import FakeFinopsReader
from services import finops
from services import finops_alerts as fa
from services.daily_spend_cap import ACTOR, CAP_SWITCHES, day_start, evaluate_daily_cap
from services.finops_job import run_finops
from services.kill_switches import IMAGE, NEW_PURCHASES, STT_FALLBACK, MemorySwitchStore

NOW = datetime(2026, 10, 15, 15, tzinfo=UTC)
PRICING = {"v1": finops.PricingRef("v1", D("5"), {})}


def reader(usd: str) -> FakeFinopsReader:
    g = fa.UsageGroup("deepseek", "m", "llm", "v1", "token_priced", "success", 1, D(usd))
    return FakeFinopsReader(pricing_refs=PRICING, groups=[g])


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("RPG_DAILY_SPEND_CAP_BRL", raising=False)
    monkeypatch.delenv("RPG_KILL_SWITCHES_OFF", raising=False)


def test_off_without_env_never_touches_switches():
    store = MemorySwitchStore()
    res = evaluate_daily_cap(reader("999"), store, NOW, D("5"))
    assert not res.enabled and store.audit_rows == []
    out = run_finops(reader("999"), now=NOW, switch_store=store)
    assert out["daily_cap_enabled"] is False and store.state == {}


def test_under_cap_does_nothing(monkeypatch):
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "50")
    store = MemorySwitchStore()
    res = evaluate_daily_cap(reader("2"), store, NOW, D("5"))  # R$ 10
    assert res.enabled and not res.exceeded and store.audit_rows == []


def test_exceeded_switches_off_audited_idempotent_no_reenable(monkeypatch):
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "50")
    store = MemorySwitchStore()
    out = run_finops(reader("20"), now=NOW, switch_store=store)  # R$ 100 > 50
    assert out["daily_cap_exceeded"] and set(out["daily_cap_switched_off"].split(",")) == set(
        CAP_SWITCHES
    )
    assert "daily_spend_cap" in out["alert_kinds"] and out["blocking_alerts"] >= 1
    assert store.state[IMAGE] is False and store.state[STT_FALLBACK] is False
    assert NEW_PURCHASES not in store.state
    assert {r["actor_id"] for r in store.audit_rows} == {ACTOR}
    assert all("daily spend cap" in r["reason"] for r in store.audit_rows)
    n = len(store.audit_rows)
    again = run_finops(reader("20"), now=NOW, switch_store=store)  # idempotent: no new writes
    assert len(store.audit_rows) == n and again["daily_cap_switched_off"] == ""
    run_finops(reader("0.1"), now=NOW, switch_store=store)  # spend back under cap: still OFF
    assert store.state[IMAGE] is False and len(store.audit_rows) == n


def test_partially_off_only_writes_missing(monkeypatch):
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "1")
    store = MemorySwitchStore({IMAGE: False})
    res = evaluate_daily_cap(reader("5"), store, NOW, D("5"))
    assert res.switched_off == [STT_FALLBACK] and res.already_off == [IMAGE]


def test_day_boundary_uses_sao_paulo_midnight():
    assert day_start(NOW) == datetime(2026, 10, 15, 3, tzinfo=UTC)


def test_invalid_cap_value_disables(monkeypatch):
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "abc")
    assert not evaluate_daily_cap(reader("99"), MemorySwitchStore(), NOW, D("5")).enabled


def test_store_failure_is_reported_not_raised(monkeypatch):
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "1")

    class Boom(MemorySwitchStore):
        def set(self, *a, **k):
            raise RuntimeError("db down")

    out = run_finops(reader("20"), now=NOW, switch_store=Boom())
    assert out["daily_cap_error"] == "RuntimeError"


@pytest.mark.infra_local
def test_postgres_store_audit_actor_and_idempotency(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    from infrastructure.kill_switch_store import PostgresSwitchStore
    from infrastructure.postgres import PostgresPool

    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "1")
    pool = PostgresPool(dsn, max_size=2)
    try:
        store = PostgresSwitchStore(pool)
        store.set(IMAGE, True, actor_id="lab", reason="lab-reset")
        store.set(STT_FALLBACK, True, actor_id="lab", reason="lab-reset")
        try:
            res = evaluate_daily_cap(reader("5"), store, NOW, D("5"))
            assert sorted(res.switched_off) == sorted(CAP_SWITCHES)
            assert store.load()[IMAGE] is False
            sys_rows = [a for a in store.audit(10) if a["actor_id"] == ACTOR]
            assert len(sys_rows) >= 2 and all(a["enabled"] is False for a in sys_rows[:2])
            again = evaluate_daily_cap(reader("5"), store, NOW, D("5"))
            assert again.switched_off == [] and sorted(again.already_off) == sorted(CAP_SWITCHES)
        finally:
            store.set(IMAGE, True, actor_id="lab", reason="lab-cleanup")
            store.set(STT_FALLBACK, True, actor_id="lab", reason="lab-cleanup")
    finally:
        pool.close()


def test_model_switches_opt_in(monkeypatch):
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "1")
    monkeypatch.setenv(
        "RPG_DAILY_SPEND_CAP_MODEL_SWITCHES", "model:anthropic/claude-x, model:gemini/pro"
    )
    store = MemorySwitchStore()
    res = evaluate_daily_cap(reader("5"), store, NOW, D("5"))
    assert set(res.switched_off) == {*CAP_SWITCHES, "model:anthropic/claude-x", "model:gemini/pro"}
    assert store.state["model:gemini/pro"] is False


def test_model_switches_invalid_key_errors(monkeypatch):
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "1")
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_MODEL_SWITCHES", "new_purchases")
    out = run_finops(reader("20"), now=NOW, switch_store=MemorySwitchStore())
    assert out["failed"] == 1 and "daily_spend_cap_error" in out["alert_kinds"]


def test_manual_reenable_same_day_not_retripped(monkeypatch):
    import time

    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "1")
    now = datetime.now(UTC)
    store = MemorySwitchStore()
    evaluate_daily_cap(reader("5"), store, now, D("5"))
    store.set(IMAGE, True, actor_id="human", reason="ok")
    res = evaluate_daily_cap(reader("5"), store, now, D("5"))
    assert (
        res.manual_override == [IMAGE]
        and res.switched_off == []
        and res.already_off == [STT_FALLBACK]
    )
    assert store.state[IMAGE] is True
    # a human re-enable from before today's boundary does not block a new trip
    store.audit_rows[-1]["at"] = time.time() - 3 * 86400
    assert evaluate_daily_cap(reader("5"), store, now, D("5")).switched_off == [IMAGE]


@pytest.mark.parametrize("val", ["abc", "20", "-13", ""])
def test_tz_offset_validation(monkeypatch, val):
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "1")
    monkeypatch.setenv("RPG_DAILY_SPEND_TZ_OFFSET_HOURS", val)
    out = run_finops(reader("20"), now=NOW, switch_store=MemorySwitchStore())
    if val == "":
        assert out["failed"] == 0
    else:
        assert out["failed"] == 1 and out["daily_cap_error"] == "CapConfigError"
        assert "daily_spend_cap_error" in out["alert_kinds"] and out["blocking_alerts"] >= 1


# --- SPEC-219 R8: cap de texto opt-in no caminho do turno ----------------------------------


def test_model_switch_text_shortcut_expands_routes(monkeypatch):
    from services.daily_spend_cap import cap_switches

    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_MODEL_SWITCHES", "text")
    keys = cap_switches()
    assert set(CAP_SWITCHES) <= set(keys)
    assert "model:deepseek/deepseek-v4-flash" in keys and "model:groq/openai/gpt-oss-120b" in keys
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "1")
    store = MemorySwitchStore()
    res = evaluate_daily_cap(reader("5"), store, NOW, D("5"))
    assert store.state["model:deepseek/deepseek-v4-flash"] is False
    assert "model:deepseek/deepseek-v4-flash" in res.switched_off


def test_text_cap_default_off_never_reads(monkeypatch):
    from services import daily_spend_cap as cap

    cap.reset_text_cap_cache()
    monkeypatch.setenv(
        "RPG_DAILY_SPEND_CAP_BRL", "1"
    )  # cap ligado, mas SEM RPG_DAILY_SPEND_CAP_TEXT
    monkeypatch.delenv("RPG_DAILY_SPEND_CAP_TEXT", raising=False)

    def boom():
        raise AssertionError("nao deve ler")

    assert cap.text_cap_exceeded(boom) is False


def test_text_cap_exceeded_is_cached_and_fail_open(monkeypatch):
    from services import daily_spend_cap as cap

    cap.reset_text_cap_cache()
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "50")
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_TEXT", "1")
    reads = []

    def factory():
        reads.append(1)
        return reader("20")  # R$ 100 > 50

    clock = {"t": 1000.0}
    assert cap.text_cap_exceeded(factory, now=NOW, clock=lambda: clock["t"]) is True
    assert cap.text_cap_exceeded(factory, now=NOW, clock=lambda: clock["t"] + 10) is True
    assert len(reads) == 1  # cache de 30 s
    assert cap.text_cap_exceeded(factory, now=NOW, clock=lambda: clock["t"] + 31) is True
    assert len(reads) == 2
    cap.reset_text_cap_cache()

    def broken():
        raise RuntimeError("db down")

    assert cap.text_cap_exceeded(broken, now=NOW) is False  # nao derruba o jogo
    cap.reset_text_cap_cache()


def test_text_cap_under_budget_allows(monkeypatch):
    from services import daily_spend_cap as cap

    cap.reset_text_cap_cache()
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "50")
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_TEXT", "1")
    assert cap.text_cap_exceeded(lambda: reader("1"), now=NOW) is False
    cap.reset_text_cap_cache()


def test_turn_returns_503_when_text_cap_exceeded(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4

    import api
    from infrastructure.contracts import Principal
    from infrastructure.request_context import reset_current_principal, set_current_principal
    from services import daily_spend_cap as cap

    cap.reset_text_cap_cache()
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "1")
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_TEXT", "1")
    runtime = SimpleNamespace(
        game_store=SimpleNamespace(pool=None), rate_limiter=None, daily_quota=None
    )
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: runtime)
    monkeypatch.setattr(
        "infrastructure.finops_reader.PostgresFinopsReader", lambda pool: reader("20")
    )
    owner = uuid4()
    token = set_current_principal(Principal(owner, "auth", str(owner)))
    try:
        with pytest.raises(api.QuotaExceeded) as exc:
            api._enforce_owner_budget("turn")
        assert exc.value.status_code == 503 and exc.value.detail == "daily_spend_cap"
    finally:
        reset_current_principal(token)
        cap.reset_text_cap_cache()
