"""SPEC-236 offline repros: phantom cost of failed attempts, cross-day cap override,
STT definitive rejection, rate-card window, benign post-commit heartbeat, fail-closed switches."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from uuid import UUID

import pytest

from infrastructure.contracts import LeaseHeld
from infrastructure.finops_reader import FakeFinopsReader
from services import finops
from services import finops_alerts as fa
from services.daily_spend_cap import ACTOR, evaluate_daily_cap
from services.finops_job import run_finops
from services.kill_switches import IMAGE, STT_FALLBACK, KillSwitches, MemorySwitchStore
from services.usage_metering import exact_billable_cost, normalize_attempts, operation_cost

OPERATION = UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime(2026, 10, 15, 15, tzinfo=timezone.utc)
PRICING = {"v1": finops.PricingRef("v1", D("5"), {})}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for name in ("RPG_DAILY_SPEND_CAP_BRL", "RPG_KILL_SWITCHES_OFF", "RPG_KILL_SWITCH_FAIL_CLOSED",
                 "RPG_RATE_CARD_MAX_AGE_DAYS", "RPG_RATE_CARD_WARN_DAYS",
                 "RPG_KILL_SWITCH_CAP_FAIL_OPEN"):
        monkeypatch.delenv(name, raising=False)


# --- R1 -------------------------------------------------------------------------------------
def test_failed_attempt_costs_zero():
    events = normalize_attempts([
        {"provider": "deepseek", "model": "deepseek-v4-flash", "outcome": "invoke_error",
         "network_attempted": True, "usage": None},
        {"provider": "groq", "model": "openai/gpt-oss-120b", "outcome": "success",
         "network_attempted": True, "usage": {"input_tokens": 1000, "output_tokens": 300}},
    ], operation_id=OPERATION)
    failed, ok = events
    assert [e.cost_usd for e in events] == [D("0"), D("0.000330000")]
    assert failed.cost_basis == "failed_no_usage" and failed.billing_exact is False
    assert failed.counts_as_spend is False and failed.pricing_version == "failed-no-usage-v1"
    assert ok.counts_as_spend is True and ok.cost_basis == "token_priced"
    assert operation_cost(events) == D("0.000330000")
    # a failure is not billing-exact: wallet settlement still refuses to treat it as known
    assert exact_billable_cost(events) is None


@pytest.mark.parametrize("outcome", ["invalid_structured", "invalid_response", "success"])
def test_answered_attempt_without_usage_stays_conservative(outcome):
    # The provider answered (and may have charged): never silently zero.
    event = normalize_attempts([{"provider": "groq", "model": "openai/gpt-oss-20b",
                                 "outcome": outcome, "network_attempted": True, "usage": None}],
                               operation_id=OPERATION)[0]
    assert event.cost_usd == D("1.000000000") and event.counts_as_spend is True


@pytest.mark.parametrize("mode", ["consumer_closed", "midstream_error"])
def test_stream_cut_after_first_chunk_is_conservative_spend(monkeypatch, mode):
    """Repro (review Astra): a stream that broke AFTER the first chunk has no usage block, but the
    provider generated (and billed) tokens. It must not become failed_no_usage/zero; the daily
    cap counts it, and it stays non-exact so a wallet reservation remains uncertain."""
    import llm_setup
    from langchain_core.messages import AIMessageChunk

    class FakeClient:
        def stream(self, _input):
            yield AIMessageChunk(content="first")
            if mode == "midstream_error":
                raise RuntimeError("connection reset")
            yield AIMessageChunk(content="never consumed")

    attempts = []
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda *_args: FakeClient())
    monkeypatch.setattr(llm_setup, "_ATTEMPT_TELEMETRY_HOOK", attempts.append)
    stream = llm_setup.RoutedLLM(llm_setup.ModelTier.FAST, 0,
                                 [("deepseek", "deepseek-v4-flash")]).stream("prompt")
    assert next(stream).content == "first"
    if mode == "consumer_closed":
        stream.close()
    else:
        list(stream)
    assert [a.outcome for a in attempts] == ["stream_interrupted"]
    event = normalize_attempts([{"provider": a.provider, "model": a.model, "outcome": a.outcome,
                                 "network_attempted": True, "usage": a.usage}
                                for a in attempts], operation_id=OPERATION)[0]
    assert event.cost_basis != "failed_no_usage" and event.cost_usd > 0
    assert event.counts_as_spend is True and event.billing_exact is False
    assert exact_billable_cost([event]) is None


def test_stream_failure_before_first_chunk_stays_failed_no_usage():
    event = normalize_attempts([{"provider": "deepseek", "model": "deepseek-v4-flash",
                                 "outcome": "stream_error", "network_attempted": True,
                                 "usage": None}], operation_id=OPERATION)[0]
    assert event.cost_basis == "failed_no_usage" and event.counts_as_spend is False


def test_failed_attempt_with_usage_keeps_its_price():
    event = normalize_attempts([{"provider": "groq", "model": "openai/gpt-oss-20b",
                                 "outcome": "invoke_error", "network_attempted": True,
                                 "usage": {"input_tokens": 1000, "output_tokens": 300}}],
                               operation_id=OPERATION)[0]
    assert event.cost_basis == "token_priced" and event.cost_usd > 0 and event.counts_as_spend


def test_turn_cost_log_excludes_failed_attempts():
    import api
    fields = api._llm_log_fields([], [
        {"provider": "deepseek", "model": "deepseek-v4-flash", "outcome": "invoke_error",
         "network_attempted": True, "usage": None},
        {"provider": "groq", "model": "openai/gpt-oss-120b", "outcome": "success",
         "network_attempted": True, "usage": {"input_tokens": 1000, "output_tokens": 300}},
    ])
    assert fields["cost_usd_est"] == pytest.approx(0.00033)
    assert fields["llm_failed_no_usage"] == 1 and fields["cost_basis"] == "normalized"


# --- R2 -------------------------------------------------------------------------------------
def _failures_and_cents() -> FakeFinopsReader:
    failed = fa.UsageGroup("deepseek", "deepseek-v4-flash", "llm", "failed-no-usage-v1",
                           "failed_no_usage", "invoke_error", 9, D("0"), False)
    legacy = fa.UsageGroup("deepseek", "deepseek-v4-flash", "llm", "unknown-conservative-v1",
                           "estimated", "invoke_error", 3, D("0"), False)  # backfilled rows
    ok = fa.UsageGroup("groq", "openai/gpt-oss-20b", "llm", "v1", "token_priced", "success",
                       1, D("0.01"))
    return FakeFinopsReader(pricing_refs=PRICING, groups=[failed, legacy, ok])


def test_daily_cap_ignores_failed_attempts(monkeypatch):
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "1")
    store = MemorySwitchStore()
    res = evaluate_daily_cap(_failures_and_cents(), store, NOW, D("6"))
    assert res.enabled and not res.exceeded and res.spent_brl == D("0.06")
    assert store.audit_rows == []


def test_failed_attempts_are_reported_apart_and_never_spike():
    reader = _failures_and_cents()
    out = run_finops(reader, now=NOW, switch_store=MemorySwitchStore())
    kinds = set(out["alert_kinds"].split(",")) - {""}
    assert "cost_spike" not in kinds and "unknown_pricing" not in kinds
    assert out["provider_failures_no_usage"] == 12
    assert out["provider_failures_no_usage_by_provider"] == "deepseek=12"
    assert out["report_version"] == "finops-spend-v2"
    # a first-ever spike from a provider with no history still needs REAL spend
    groups = [fa.UsageGroup("deepseek", "m", "llm", "x", "failed_no_usage", "error", 50, D("0"),
                            False)]
    assert fa.cost_spike(groups, [{}], fa.Thresholds()) == []


# --- R3 -------------------------------------------------------------------------------------
def _store_with(trip_hours_ago: float, reenable_hours_ago: float) -> MemorySwitchStore:
    store = MemorySwitchStore()
    store.set(IMAGE, False, actor_id=ACTOR, reason="daily spend cap exceeded: x")
    store.set(IMAGE, True, actor_id="human-operator", reason="religado de manhã")
    store.audit_rows[0]["at"] = time.time() - trip_hours_ago * 3600
    store.audit_rows[1]["at"] = time.time() - reenable_hours_ago * 3600
    return store


def _cap_reader(usd: str) -> FakeFinopsReader:
    g = fa.UsageGroup("openai", "gpt-image", "image", "v1", "rate_card", "success", 1, D(usd))
    return FakeFinopsReader(pricing_refs=PRICING, groups=[g])


def test_manual_override_only_same_day(monkeypatch):
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "1")
    now = datetime.now(timezone.utc)
    from services.daily_spend_cap import day_start
    since = day_start(now)
    # yesterday's trip + this morning's re-enable must NOT disarm today's cap
    hours_today = (now - since).total_seconds() / 3600
    store = _store_with(hours_today + 20, min(hours_today, 4) * 0.5)
    res = evaluate_daily_cap(_cap_reader("5"), store, now, D("5"))
    assert IMAGE in res.switched_off and IMAGE not in res.manual_override
    # a trip today followed by a human re-enable today is respected
    if hours_today > 0.1:
        store = _store_with(hours_today * 0.6, hours_today * 0.3)
        res = evaluate_daily_cap(_cap_reader("5"), store, now, D("5"))
        assert res.manual_override == [IMAGE] and IMAGE not in res.switched_off


# --- R5 (pure) ------------------------------------------------------------------------------
def test_stt_rejection_is_exact_zero_and_timeout_stays_unknown():
    from services.speech_pricing import SPEECH_PRICING_VERSION, is_definitive_no_charge, speech_event
    rejected = speech_event(OPERATION, 0, "groq", "whisper-large-v3-turbo", "rejected", {},
                            definitive_no_charge=True)
    assert rejected.cost_usd == 0 and rejected.billing_exact is True
    assert rejected.cost_basis == "definitive_no_charge" and rejected.counts_as_spend is False
    assert rejected.pricing_version == SPEECH_PRICING_VERSION
    assert [is_definitive_no_charge(s) for s in (400, 401, 429, 499, 500, 503, 200)] == \
        [True, True, True, True, False, False, False]
    unknown = speech_event(OPERATION, 0, "groq", "whisper-large-v3-turbo", "unknown", {})
    assert unknown.billing_exact is False and unknown.cost_usd > 0


def test_stt_429_then_fallback_success_is_all_exact():
    import asyncio
    import io
    import wave
    from services.speech_to_text import Candidate, ProviderReading, SpeechCircuit, transcribe_audio

    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        wav.writeframes(bytes(2) * 16000)

    class FakeFinance:
        events: list = []

        def begin(self, *args):
            pass

        def admit(self, *args):
            pass

        def finish(self, events, success):
            self.events = events
            return "settled"

    class Provider:
        def __init__(self):
            self.readings = [ProviderReading(429, None, {}),
                             ProviderReading(200, "Ayla", {"input_tokens": 100, "audio_tokens": 100,
                                                           "text_tokens": 0, "output_tokens": 20})]

        async def transcribe(self, candidate, path):
            return self.readings.pop(0)

    finance = FakeFinance()
    asyncio.run(transcribe_audio(output.getvalue(), "audio/wav", OPERATION, finance,
                                 provider=Provider(),
                                 candidates=[Candidate("groq", "whisper-large-v3-turbo"),
                                             Candidate("openai", "gpt-4o-mini-transcribe")],
                                 circuit=SpeechCircuit()))
    events = finance.events
    assert [e.cost_basis for e in events] == ["definitive_no_charge", "rate_card"]
    assert all(e.billing_exact for e in events)


# --- R7 -------------------------------------------------------------------------------------
def test_rate_card_window_configurable(monkeypatch):
    from services.image_pricing import _CARD as image_card, require_image_prices
    from services.shard_pricing import PricingUnavailable
    from services.speech_pricing import require_speech_prices
    observed = datetime.fromisoformat(image_card["observed_at"])
    model = image_card["model"]
    require_image_prices(model, observed + timedelta(days=25))  # D-B default 30 d
    require_speech_prices(observed + timedelta(days=25))
    with pytest.raises(PricingUnavailable):
        require_image_prices(model, observed + timedelta(days=31))
    with pytest.raises(PricingUnavailable):
        require_speech_prices(observed + timedelta(days=31))
    monkeypatch.setenv("RPG_RATE_CARD_MAX_AGE_DAYS", "14")
    with pytest.raises(PricingUnavailable):
        require_image_prices(model, observed + timedelta(days=15))
    monkeypatch.setenv("RPG_RATE_CARD_MAX_AGE_DAYS", "garbage")  # never widens silently
    with pytest.raises(PricingUnavailable):
        require_image_prices(model, observed + timedelta(days=31))


def test_rate_card_expiring_warns_before_blocking():
    card = fa.Freshness("image", NOW - timedelta(days=28), timedelta(days=30))
    warn = fa.expiring_rate_cards([card], NOW)
    assert [a.kind for a in warn] == ["rate_card_expiring"] and not warn[0].blocking
    assert fa.stale_rate_cards([card], NOW) == []
    early = fa.Freshness("image", NOW - timedelta(days=25), timedelta(days=30))
    assert fa.expiring_rate_cards([early], NOW) == []
    expired = fa.Freshness("image", NOW - timedelta(days=31), timedelta(days=30))
    assert fa.expiring_rate_cards([expired], NOW) == []
    assert [a.blocking for a in fa.stale_rate_cards([expired], NOW)] == [True]
    fx = fa.Freshness("fx", NOW - timedelta(hours=23), timedelta(days=1))
    assert fa.expiring_rate_cards([fx], NOW) == []  # fx has its own cadence


def test_installed_cards_use_the_configured_window(monkeypatch):
    windows = {f.name: f.max_age for f in fa.installed_freshness()}
    assert windows["image"] == windows["speech"] == timedelta(days=30)
    monkeypatch.setenv("RPG_RATE_CARD_MAX_AGE_DAYS", "14")
    assert {f.name: f.max_age for f in fa.installed_freshness()}["image"] == timedelta(days=14)


# --- R8 -------------------------------------------------------------------------------------
def test_heartbeat_after_commit_is_benign():
    from services.turn_execution import operation_scope

    class Coordinator:
        lease_seconds = 0.04  # tick every 10 ms
        committed = False
        failed: list[str] = []

        def heartbeat(self, claim):
            if self.committed:  # commit cleared the lease token
                raise LeaseHeld("fencing token inválido")

        def is_completed(self, claim):
            return self.committed

        def fail(self, claim, code):
            self.failed.append(code)

    coordinator = Coordinator()
    with operation_scope(coordinator, object()):
        coordinator.committed = True  # commit_game ran
        time.sleep(0.05)  # a tick lands after the commit
    assert coordinator.failed == []


def test_lost_lease_without_commit_still_raises():
    from services.turn_execution import operation_scope

    class Coordinator:
        lease_seconds = 0.04
        failed: list[str] = []

        def __init__(self):
            self.calls = 0

        def heartbeat(self, claim):
            self.calls += 1
            if self.calls > 1:
                raise LeaseHeld("fencing token inválido")

        def is_completed(self, claim):
            return False

        def fail(self, claim, code):
            self.failed.append(code)

    coordinator = Coordinator()
    with pytest.raises(LeaseHeld):
        with operation_scope(coordinator, object()):
            time.sleep(0.05)
    assert coordinator.failed == ["LeaseHeld"]


def test_watch_mark_committed_stops_renewal():
    from services.lease_heartbeat import keep_lease_alive
    calls = []
    with keep_lease_alive(lambda: calls.append(1), interval_seconds=0.01) as watch:
        watch.mark_committed()
        seen = len(calls)
        time.sleep(0.05)
    assert len(calls) <= seen + 1


# --- R10 (kill switches) --------------------------------------------------------------------
class _Broken:
    def load(self):
        raise RuntimeError("db down")


def test_cap_switches_fail_closed_on_cold_start(monkeypatch):
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "50")
    switches = KillSwitches(_Broken(), ttl=0)
    assert switches.is_enabled(IMAGE) is False and switches.is_enabled(STT_FALLBACK) is False
    assert switches.is_enabled("new_purchases") is True


def test_switches_fail_open_without_cap(monkeypatch):
    switches = KillSwitches(_Broken(), ttl=0)
    assert switches.is_enabled(IMAGE) is True
    monkeypatch.setenv("RPG_DAILY_SPEND_CAP_BRL", "50")
    monkeypatch.setenv("RPG_KILL_SWITCH_CAP_FAIL_OPEN", "1")
    assert KillSwitches(_Broken(), ttl=0).is_enabled(IMAGE) is True


def test_wallet_hold_alerts_are_raised():
    reader = FakeFinopsReader(pricing_refs=PRICING, holds=(2, 4000.0, 1))
    out = run_finops(reader, now=NOW, switch_store=MemorySwitchStore())
    kinds = set(out["alert_kinds"].split(","))
    assert {"wallet_uncertain_hold", "wallet_spend_anomaly"} <= kinds
    assert out["wallet_uncertain_holds"] == 2


def test_stream_interrupted_keeps_its_audit_error_code():
    """Sol review: renaming the post-first-chunk outcome must not degrade the audit export."""
    from services.audit_trace import ERROR_CODES
    assert ERROR_CODES["stream_interrupted"] == "llm_stream_error"
