"""SPEC-196 offline contracts: margin formulas, alerts, low-cardinality metrics, kill switches."""
from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import yaml
from fastapi import HTTPException
from fastapi.testclient import TestClient

import api
import llm_setup
from infrastructure.contracts import Principal
from infrastructure.finops_reader import FakeFinopsReader, OpsCounts
from infrastructure.google_play_payments import GooglePlayPurchases
from observability.metrics import LABELS, metrics
from services import cron_internal, finops
from services import finops_alerts as fa
from services import kill_switches as ks
from services.finops_job import run_finops
from services.google_play import GooglePlayError, obfuscated_account_id
from services.shard_pricing import PricingUnavailable

D = Decimal
T0 = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
PRICING = {"v1": finops.PricingRef("v1", D("5"), {
    "web": finops.FeeRate(D("0.04"), D("0.20")), "google_play": finops.FeeRate(D("0.15"), D("0"))})}


@pytest.fixture(autouse=True)
def _reset_switches(monkeypatch):
    monkeypatch.delenv("RPG_KILL_SWITCHES_OFF", raising=False)
    ks.set_switches(None)
    yield
    ks.set_switches(None)


def purchase(owner="o1", gross="10.00", shard=1000, channel="web", at=T0, fee=None, sku="s1",
             ref=None, first=None):
    return finops.PurchaseFact(ref or str(uuid4()), channel, sku, "v1", owner, at, D(gross), shard,
                               None if fee is None else D(fee), first)


# ---- formulas (golden numbers) --------------------------------------------------------------
def test_golden_margin_estimated_fee_and_variable_cost():
    usage = {"o1": finops.OwnerUsage({"llm": D("0.10")})}  # 0.10 USD x fx 5 = R$ 0.50
    rows, unalloc, missing = finops.compute_margins([purchase()], PRICING, usage)
    r = rows[0]
    assert (r.channel, r.fee_basis) == ("stripe", "estimated")
    assert r.channel_fee_brl == D("0.6000")  # 10.00*4% + 0.20
    assert r.variable_cost_brl == D("0.5000")
    assert r.contribution_margin_brl == D("8.9000") and r.margin_pct == D("0.890000")
    assert unalloc == 0 and missing == ()


def test_actual_fee_wins_and_mixed_is_flagged():
    rows, _, _ = finops.compute_margins(
        [purchase(fee="0.55"), purchase(owner="o2")], PRICING, {})
    assert rows[0].fee_basis == "mixed" and rows[0].fee_estimated_purchases == 1
    assert rows[0].channel_fee_brl == D("1.1500")  # 0.55 actual + 0.60 estimated
    only_actual, _, _ = finops.compute_margins([purchase(fee="0.55")], PRICING, {})
    assert only_actual[0].fee_basis == "actual" and only_actual[0].channel_fee_brl == D("0.5500")


def test_usage_allocated_pro_rata_by_shards_across_owner_purchases():
    ps = [purchase(shard=1000, sku="a"), purchase(shard=3000, sku="b", gross="30.00")]
    rows, _, _ = finops.compute_margins(ps, PRICING, {"o1": finops.OwnerUsage({"llm": D("1")})})
    by_sku = {r.sku_id: r for r in rows}
    assert by_sku["a"].variable_cost_brl == D("1.2500")  # 1 USD*5*(1/4)
    assert by_sku["b"].variable_cost_brl == D("3.7500")


def test_channels_are_never_mixed_and_google_fee_applies():
    rows, _, _ = finops.compute_margins(
        [purchase(), purchase(channel="google_play", sku="g1")], PRICING, {})
    got = {r.channel: r.channel_fee_brl for r in rows}
    assert got == {"stripe": D("0.6000"), "google_play": D("1.5000")}


def test_target_check_per_sku_channel_version_no_cross_mixing():
    usage = {"o1": finops.OwnerUsage({"llm": D("1.90")})}  # R$ 9.50 on a R$10 sku
    rows, _, _ = finops.compute_margins([purchase(), purchase(owner="o2", sku="s2")], PRICING, usage)
    skus = {s.sku_id: s for s in finops.sku_summary(rows)}
    assert skus["s1"].meets_target is False and skus["s1"].margin_pct == D("-0.010000")
    assert skus["s2"].meets_target is True


def test_cohort_is_week_of_first_purchase_even_outside_window():
    old = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows, _, _ = finops.compute_margins([purchase(first=old)], PRICING, {})
    assert rows[0].cohort == finops.week_cohort(old) == "2026-W36"


def test_missing_pricing_version_is_reported_never_costed_at_zero():
    p = finops.PurchaseFact("r", "web", "s", "v-unknown", "o1", T0, D("10"), 10)
    rows, _, missing = finops.compute_margins([p], PRICING, {})
    assert rows == [] and missing == ("v-unknown",)


def test_unit_costs_golden():
    u = finops.unit_costs({"llm": D("0.9"), "embedding": D("0.1"), "image": D("0.5"),
                           "stt": D("0.012")}, turns=1000, images=10, voice_ms=120000)
    assert u.cost_per_turn_usd == D("0.001000") and u.cost_per_image_usd == D("0.050000")
    assert u.cost_per_voice_minute_usd == D("0.006000") and u.voice_minutes == D("2.0000")
    assert finops.unit_costs({}, turns=0, images=0, voice_ms=0).cost_per_turn_usd is None


def test_fixed_infra_is_separate_and_never_inside_sku_margins(tmp_path):
    cfg = tmp_path / "fixed.json"
    cfg.write_text(json.dumps({"currency": "USD", "items": [
        {"name": "vercel", "monthly_usd": "20"}, {"name": "supabase", "monthly_usd": "5"}]}))
    fixed = finops.load_fixed_costs(cfg, window_days=30, fx_usd_brl=D("5"))
    assert fixed.monthly_total == D("25") and fixed.prorated_total == D("125.0000")
    usage = {"o1": finops.OwnerUsage({"llm": D("0.10")}), "free": finops.OwnerUsage({"llm": D("0.20")})}
    rep = finops.build_report([purchase()], PRICING, usage, window_cost_usd={"llm": D("0.30")},
                              turns=10, images=0, voice_ms=0, fixed=fixed)
    assert rep.totals["contribution_margin_brl"] == D("8.9000")  # fixed NOT subtracted
    assert rep.unallocated_variable_cost_brl == D("1.0000")  # free-tier usage kept visible
    assert rep.operating_result_brl == D("8.9000") - D("1.0000") - D("125.0000")
    assert finops.report_to_dict(rep)["fixed_infra"]["monthly_total"] == "25"
    committed = finops.load_fixed_costs()  # repo config: documented zeros (Free/Hobby)
    assert committed.monthly_total == 0 and {n for n, _ in committed.items} == {"vercel", "supabase"}


# ---- alerts + metrics ---------------------------------------------------------------------
def group(provider="deepseek", model="m", cat="llm", ver="v", outcome="success", n=1, usd="0.1"):
    return fa.UsageGroup(provider, model, cat, ver, "token_priced", outcome, n, D(usd))


def test_unknown_pricing_alerts_and_blocks():
    out = fa.unknown_pricing([group(ver="unknown-conservative-v1", n=3, model="mystery"), group()])
    assert len(out) == 1 and out[0].blocking and out[0].model == "mystery" and out[0].value == 3


def test_stale_rate_card_alerts_and_blocks_paid_effect(monkeypatch):
    alert = fa.stale_rate_cards([fa.Freshness("fx", T0 - timedelta(days=3), timedelta(days=1))], T0)
    assert alert and alert[0].blocking and alert[0].provider == "fx"
    assert not fa.stale_rate_cards([fa.Freshness("fx", T0, timedelta(days=1))], T0)
    far = datetime.now(timezone.utc) + timedelta(days=400)
    with pytest.raises(PricingUnavailable):
        fa.require_paid_effect("image", now=far)
    monkeypatch.setenv("RPG_FINOPS_BLOCK_STALE", "0")
    fa.require_paid_effect("image", now=far)  # emergency downgrade to alert-only


def test_cost_spike_vs_baseline():
    t = fa.Thresholds()
    base = [{"deepseek": D("1")}, {"deepseek": D("1")}]
    assert fa.cost_spike([group(usd="5")], base, t)
    assert not fa.cost_spike([group(usd="2")], base, t)
    assert not fa.cost_spike([group(usd="0.5")], base, t)  # below floor


def test_expensive_fallback_share():
    t = fa.Thresholds()
    cheap, dear = group(provider="deepseek", usd="1"), group(provider="anthropic", model="x", usd="2")
    out = fa.expensive_fallback([cheap, dear], t)
    assert [a.provider for a in out] == ["anthropic"]
    assert not fa.expensive_fallback([group(provider="deepseek", usd="2")], t)


def test_wallet_mismatch_backlog_provider_failure_margin():
    t = fa.Thresholds()
    assert fa.wallet_mismatch(2, 500) and not fa.wallet_mismatch(0, 0)
    old, fresh = fa.Backlog("google_play", 3, 7200), fa.Backlog("stripe", 1, 10)
    assert [a.channel for a in fa.webhook_backlog([old, fresh], t)] == ["google_play"]
    bad = [group(provider="groq", outcome="invoke_error", n=15), group(provider="groq", n=10)]
    assert fa.provider_failures(bad, t) and not fa.provider_failures([group(n=10)], t)
    low = finops.SkuMargin("stripe", "s1", "v1", 1, D(10), D(1), "actual", D(9), D("0.1"), D("0.01"), False)
    assert fa.margin_below_target([low])[0].sku_id == "s1"


def test_metric_labels_are_low_cardinality_and_never_ids():
    forbidden = {"user_id", "game_id", "owner_id", "order_id", "purchase_ref", "operation_id"}
    for name, labels in LABELS.items():
        if name.startswith("rpg_finops"):
            assert not labels & forbidden and labels <= {"kind", "channel", "sku_id", "provider", "model"}
    owner = str(uuid4())
    assert fa.safe_label(owner) == "other" and fa.safe_label("a@b.com") == "other"
    assert fa.safe_label("deepseek-v4-flash") == "deepseek-v4-flash"


def test_run_finops_publishes_owner_free_metrics_and_response():
    owner = str(uuid4())
    reader = FakeFinopsReader(
        pricing_refs=PRICING,
        freshness=[fa.Freshness("fx", T0 - timedelta(days=9), timedelta(days=1))],
        purchase_facts=[purchase(owner=owner, at=T0 - timedelta(days=1))],
        usage={owner: finops.OwnerUsage({"llm": D("2")})},
        groups=[group(ver="unknown-conservative-v1", model=owner)],
        ops=OpsCounts(turns=10), mismatch=(1, 5))
    result = run_finops(reader, now=T0)
    blob = json.dumps(result, default=str) + metrics.render_prometheus()
    assert owner not in blob
    assert {"unknown_pricing", "stale_rate_card", "wallet_mismatch"} <= set(result["alert_kinds"].split(","))
    assert result["blocking_alerts"] >= 2 and result["skus_below_target"] == 1
    snap = metrics.snapshot()
    assert any(k.startswith("rpg_finops_alert_active") and v == 1 for k, v in snap.items())
    assert any(k.startswith("rpg_finops_margin_ratio") for k in snap)
    for key in snap:
        if key.startswith("rpg_finops"):
            assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", key)


def test_alert_rules_yaml_valid_and_metrics_registered():
    rules = yaml.safe_load(Path("observability/alerts/finops.yml").read_text(encoding="utf-8"))
    exprs = [r["expr"] for g in rules["groups"] for r in g["rules"]]
    names = {a["alert"] for g in rules["groups"] for a in g["rules"]}
    assert {"FinopsUnknownPricing", "FinopsStaleRateCard", "FinopsCostSpike", "FinopsExpensiveFallback",
            "FinopsWalletMismatch", "FinopsWebhookBacklog", "FinopsProviderFailure",
            "FinopsMarginBelowTarget"} <= names
    for metric in set(re.findall(r"\b(rpg_[a-z0-9_]+)\b", "\n".join(exprs))):
        assert metric in LABELS
    kinds = set(re.findall(r'kind="([a-z_]+)"', "\n".join(exprs)))
    assert kinds <= set(fa.ALERT_KINDS) | {"image_generation", "finops"}
    fixtures = yaml.safe_load(Path("observability/alerts/finops.test.yml").read_text(encoding="utf-8"))
    assert fixtures["rule_files"] == ["finops.yml"] and fixtures["tests"][0]["alert_rule_test"]


# ---- kill switches ---------------------------------------------------------------------------
def test_switch_default_enabled_and_failsafe_on_store_error():
    class Boom:
        def load(self):
            raise RuntimeError("db down")
    sw = ks.KillSwitches(Boom(), ttl=0)
    assert sw.is_enabled(ks.IMAGE) and sw.is_enabled("model:x/y")
    mem = ks.MemorySwitchStore({ks.IMAGE: False})
    sw = ks.KillSwitches(mem, ttl=1000)
    assert not sw.is_enabled(ks.IMAGE)
    mem.state[ks.IMAGE] = True  # cached within TTL
    assert not sw.is_enabled(ks.IMAGE)
    sw.invalidate()
    assert sw.is_enabled(ks.IMAGE)
    with pytest.raises(ks.SwitchOff):
        ks.KillSwitches(ks.MemorySwitchStore({ks.IMAGE: False}), ttl=0).require(ks.IMAGE)


def test_store_audit_is_append_only_and_requires_actor_and_reason():
    mem = ks.MemorySwitchStore()
    mem.set(ks.IMAGE, False, actor_id="ana", reason="cost spike")
    mem.set(ks.IMAGE, True, actor_id="ana", reason="back to normal")
    rows = mem.audit()
    assert [r["enabled"] for r in rows] == [True, False] and rows[1]["previous_enabled"] is True
    for bad in (dict(actor_id="", reason="r"), dict(actor_id="a", reason="")):
        with pytest.raises(ValueError):
            mem.set(ks.IMAGE, False, **bad)
    with pytest.raises(ValueError):
        mem.set("bogus_key", False, actor_id="a", reason="r")
    assert len(mem.audit_rows) == 2


def test_admin_cli_is_dry_run_by_default_and_audits_on_apply(capsys):
    from scripts import admin_kill_switch as cli
    mem = ks.MemorySwitchStore()
    args = ["off", ks.IMAGE, "--actor", "ana", "--reason", "x"]
    assert cli.main(args, store=mem) == 0 and mem.state == {} and not mem.audit_rows
    assert cli.main([*args, "--apply"], store=mem) == 0
    assert mem.state == {ks.IMAGE: False} and mem.audit_rows[0]["actor_id"] == "ana"
    with pytest.raises(SystemExit):
        cli.main(["off", ks.IMAGE], store=mem)  # actor/reason required
    assert cli.main(["off", "nope", "--actor", "a", "--reason", "r", "--apply"], store=mem) == 2


def test_model_switch_skips_candidate_and_falls_back(monkeypatch):
    calls = []

    class Client:
        def __init__(self, tag):
            self.tag = tag

        def invoke(self, _input):
            from langchain_core.messages import AIMessage
            calls.append(self.tag)
            return AIMessage(content="ok")

    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda p, m, t: Client(f"{p}/{m}"))
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({ks.model_key("pa", "ma"): False}), ttl=0))
    out = llm_setup.RoutedLLM(llm_setup.ModelTier.FAST, 0, [("pa", "ma"), ("pb", "mb")]).invoke("x")
    assert out.content == "ok" and calls == ["pb/mb"]


def test_image_switch_refuses_new_generation_but_not_reading(monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")
    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "1")
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({ks.IMAGE: False}), ttl=0))
    with pytest.raises(HTTPException) as exc:
        api._image_finance()
    assert (exc.value.status_code, exc.value.detail) == (503, "image_generation_disabled")
    assert TestClient(api.app).get("/health").status_code in {200, 401, 404}  # app still serves


def test_stt_fallback_switch_drops_only_the_expensive_candidate(monkeypatch):
    from services import speech_to_text as stt
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    stt.SPEECH_CIRCUIT._state.clear()
    assert [c.provider for c in stt.configured_candidates()] == ["groq", "openai"]
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({ks.STT_FALLBACK: False}), ttl=0))
    assert [c.provider for c in stt.configured_candidates()] == ["groq"]
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore(
        {ks.model_key("groq", "whisper-large-v3-turbo"): False}), ttl=0))
    assert [c.provider for c in stt.configured_candidates()] == ["openai"]


def test_jev_switch_returns_to_current_classifier(monkeypatch):
    from services import jev_rollout
    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "shadow")
    events = []
    jev_rollout.set_jev_rollout_telemetry_hook(events.append)
    try:
        ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({ks.JEV: False}), ttl=0))
        assert jev_rollout.begin({}, "olho") is None
        assert events and events[0].outcome == "kill_switch"
    finally:
        jev_rollout.set_jev_rollout_telemetry_hook(None)


def test_new_purchase_switches_are_scoped_by_channel():
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({ks.purchases_key("google_play"): False}), ttl=0))
    ks.require_purchases("stripe")
    with pytest.raises(ks.SwitchOff):
        ks.require_purchases("google_play")
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({ks.NEW_PURCHASES: False}), ttl=0))
    for channel in ("stripe", "google_play"):
        with pytest.raises(ks.SwitchOff):
            ks.require_purchases(channel)


def test_google_new_purchase_refused_but_replay_still_returns():
    from tests.test_spec194_google_play import TOKEN, FakeGoogle, MemStore
    who = Principal(uuid4(), "t", "x")
    store, google = MemStore(), FakeGoogle(account_id=obfuscated_account_id(who.user_id))
    svc = GooglePlayPurchases(store, google)
    first = svc.verify(who, "estilhas_pack_small", TOKEN)
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({ks.NEW_PURCHASES: False}), ttl=0))
    assert svc.verify(who, "estilhas_pack_small", TOKEN) == first  # existing purchase: replay allowed
    other = "tok_" + "b" * 40
    google.base["order_id"] = "GPA.2"
    with pytest.raises(GooglePlayError, match="new_purchases_disabled"):
        svc.verify(who, "estilhas_pack_small", other)
    assert len(store.rows) == 1  # nothing fulfilled


def test_stripe_checkout_new_order_refused_when_switch_off():
    from infrastructure.stripe_payments import StripePayments

    class Cur:
        def fetchone(self):
            return None

    class Db:
        def execute(self, *_a, **_k):
            return Cur()

        @contextmanager
        def transaction(self):
            yield

    class Pool:
        @contextmanager
        def connection(self):
            yield Db()

    svc = StripePayments(Pool(), SimpleNamespace(allowed_skus={"sku"}), None)
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({ks.purchases_key("stripe"): False}), ttl=0))
    with pytest.raises(ks.SwitchOff):
        svc.checkout(Principal(uuid4(), "t", "x"), "sku", uuid4())


def test_kill_switch_migration_is_backend_only_and_audited():
    sql = Path("supabase/migrations/20261015150000_finops_kill_switches.sql").read_text(encoding="utf-8")
    assert "force row level security" in sql and "kill_switch_audit_immutable" in sql
    assert "revoke all on app.kill_switches, app.kill_switch_audit from public, anon, authenticated, rpg_api" in sql
    assert not re.search(r"grant\s+\w+.*kill_switch", sql, re.I)
    assert "app.set_kill_switch" in sql and "security definer" in sql


# ---- cron --------------------------------------------------------------------------------------
def test_cron_finops_auth_and_owner_free_response(monkeypatch):
    secret = "s" * 40
    monkeypatch.setenv("RPG_CRON_SECRET", secret)
    client = TestClient(api.app)
    assert client.post("/internal/cron/finops").status_code == 401
    assert client.post("/internal/cron/finops", headers={"Authorization": "Bearer nope"}).status_code == 401
    owner = str(uuid4())
    reader = FakeFinopsReader(pricing_refs=PRICING,
                              purchase_facts=[purchase(owner=owner, at=datetime.now(timezone.utc) - timedelta(days=1))])
    monkeypatch.setattr(cron_internal, "_finops_reader", lambda: reader)
    res = client.post("/internal/cron/finops", headers={"Authorization": f"Bearer {secret}"})
    assert res.status_code == 200 and res.json()["ok"] and owner not in res.text
    assert res.json()["purchases"] == 1


# ---- postgres (skipped without a lab database) -------------------------------------------------
@pytest.mark.infra_local
def test_postgres_kill_switch_store_audit_roundtrip():
    psycopg = pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL absent")
    from psycopg.rows import dict_row
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        if db.execute("select to_regclass('app.kill_switches') t").fetchone()["t"] is None:
            db.execute(Path("supabase/migrations/20261015150000_finops_kill_switches.sql")
                       .read_text(encoding="utf-8"))
        try:
            db.execute("select app.set_kill_switch(%s,%s,%s,%s)", (ks.IMAGE, False, "ana", "t1"))
            db.execute("select app.set_kill_switch(%s,%s,%s,%s)", (ks.IMAGE, True, "ana", "t2"))
            rows = db.execute("select enabled,previous_enabled from app.kill_switch_audit "
                              "where key=%s order by audit_id", (ks.IMAGE,)).fetchall()
            assert [r["enabled"] for r in rows][-2:] == [False, True]
            with pytest.raises(psycopg.Error):
                db.execute("update app.kill_switch_audit set reason='x'")
        finally:
            db.rollback()


# ---- SPEC-196 follow-ups F1..F8 ------------------------------------------------------------------
def test_f1_store_error_is_logged_counted_and_fail_open_by_default(caplog):
    class Boom:
        def load(self):
            raise RuntimeError("secret-dsn-leak")
    before = sum(v for k, v in metrics.snapshot().items()
                 if k.startswith("rpg_kill_switch_load_errors_total"))
    with caplog.at_level("WARNING", logger="rpg.kill_switches"):
        sw = ks.KillSwitches(Boom(), ttl=0)
        assert sw.is_enabled(ks.NEW_PURCHASES) and sw.is_enabled(ks.IMAGE)
    assert "RuntimeError" in caplog.text and "secret-dsn-leak" not in caplog.text
    after = sum(v for k, v in metrics.snapshot().items()
                if k.startswith("rpg_kill_switch_load_errors_total"))
    assert after == before + 2


def test_f1_fail_closed_only_without_cached_value(monkeypatch):
    monkeypatch.setenv("RPG_KILL_SWITCH_FAIL_CLOSED", "new_purchases,image_generation,bogus key")

    class Flaky:
        ok = False

        def load(self):
            if not self.ok:
                raise RuntimeError("down")
            return {ks.IMAGE: True}
    store = Flaky()
    sw = ks.KillSwitches(store, ttl=0)
    assert not sw.is_enabled(ks.NEW_PURCHASES) and not sw.is_enabled(ks.IMAGE)
    assert sw.is_enabled(ks.STT_FALLBACK)  # not listed: stays open
    store.ok = True
    assert sw.is_enabled(ks.NEW_PURCHASES) and sw.is_enabled(ks.IMAGE)  # recovered
    store.ok = False
    assert sw.is_enabled(ks.IMAGE)  # a good snapshot exists: keep it, never close on a blip


def test_f1_alert_rule_for_load_errors_exists():
    rules = yaml.safe_load(Path("observability/alerts/finops.yml").read_text(encoding="utf-8"))
    exprs = {r["alert"]: r["expr"] for g in rules["groups"] for r in g["rules"]}
    assert "rpg_kill_switch_load_errors_total" in exprs["KillSwitchStoreUnreadable"]
    assert "FinopsEvaluationStale" in exprs and "FinopsUnknownPurchasePricing" in exprs


def test_f2_unknown_purchase_pricing_is_blocking_alert_and_in_summary():
    bad = finops.PurchaseFact("r1", "web", "s1", "v-unknown", "o1", T0 - timedelta(days=1),
                              D("10.00"), 1000)
    reader = FakeFinopsReader(pricing_refs=PRICING,
                              purchase_facts=[bad, purchase(at=T0 - timedelta(days=1))])
    out = run_finops(reader, now=T0)
    assert out["unpriced_purchases"] == 1 and out["purchases"] == 1
    assert "finops_unknown_purchase_pricing" in out["alert_kinds"].split(",")
    assert out["blocking_alerts"] >= 1
    alerts = fa.unknown_purchase_pricing(1, ["v-unknown"])
    assert alerts[0].blocking and alerts[0].kind in fa.ALERT_KINDS
    assert fa.unknown_purchase_pricing(0, []) == []


def test_f3_net_of_refunds_and_disputes_golden():
    usage = {"o1": finops.OwnerUsage({"llm": D("0.10")})}  # R$ 0.50
    p = finops.PurchaseFact("r", "web", "s1", "v1", "o1", T0, D("10.00"), 1000,
                            refund_brl=D("4.00"), dispute_brl=D("1.00"))
    rows, _, _ = finops.compute_margins([p], PRICING, usage)
    r = rows[0]
    assert (r.gross_brl, r.refund_brl, r.dispute_brl, r.net_revenue_brl) == (
        D("10.0000"), D("4.0000"), D("1.0000"), D("5.0000"))
    assert r.contribution_margin_brl == D("3.9000")  # 5.00 - 0.60 fee - 0.50 usage
    assert r.margin_pct == D("0.780000")  # over NET revenue, not gross


def test_f3_target_uses_net_revenue_and_full_refund_is_a_loss():
    usage = {"o1": finops.OwnerUsage({"llm": D("0.70")})}  # R$ 3.50
    gross_rows, _, _ = finops.compute_margins([purchase()], PRICING, usage)
    assert finops.sku_summary(gross_rows)[0].meets_target is True  # 59% on gross
    refunded = finops.PurchaseFact("r", "web", "s1", "v1", "o1", T0, D("10.00"), 1000,
                                   refund_brl=D("6.00"))
    rows, _, _ = finops.compute_margins([refunded], PRICING, usage)
    sku = finops.sku_summary(rows)[0]
    assert sku.meets_target is False and sku.margin_pct == D("-0.025000")  # (4-.6-3.5)/4
    full = finops.PurchaseFact("r2", "web", "s2", "v1", "o9", T0, D("10.00"), 1000,
                               refund_brl=D("10.00"))
    rows, _, _ = finops.compute_margins([full], PRICING, {})
    sku = finops.sku_summary(rows)[0]
    assert sku.margin_pct is None and sku.meets_target is False  # fee paid, nothing earned
    over = finops.PurchaseFact("r3", "web", "s3", "v1", "o8", T0, D("10.00"), 1000,
                               refund_brl=D("8.00"), dispute_brl=D("9.00"))
    rows, _, _ = finops.compute_margins([over], PRICING, {})
    assert rows[0].net_revenue_brl == D("0.0000")  # clamped: never negative revenue


def test_f3_reader_sql_covers_195_and_legacy_entries():
    import inspect

    from infrastructure.finops_reader import PostgresFinopsReader
    sql = inspect.getsource(PostgresFinopsReader.purchases)
    for needle in ("clawback", "claw_release", "'reversal'", "wallet_debt_entries", "'open'",
                   "'release'", "purchase_key", "dispute_lost"):
        assert needle in sql


def test_f6_newest_pricing_version_drives_unallocated_fx_and_fixed_infra(tmp_path):
    pricing = {"old": finops.PricingRef("old", D("4"), PRICING["v1"].fees),
               "new": finops.PricingRef("new", D("6"), PRICING["v1"].fees)}
    assert finops.newest_pricing(pricing).version_id == "new" and finops.newest_pricing({}) is None
    _, unalloc, _ = finops.compute_margins([], pricing, {"ghost": finops.OwnerUsage({"llm": D("1")})})
    assert unalloc == D("6.0000")
    fixed_file = tmp_path / "fixed.json"
    fixed_file.write_text(json.dumps({"currency": "USD", "items": [{"name": "x", "monthly_usd": "10"}]}))
    out = run_finops(FakeFinopsReader(pricing_refs=pricing), now=T0, report_days=30,
                     fixed_path=fixed_file)
    assert out["report"]["fixed_infra"]["prorated_total"] == "60.0000"  # 10 USD x fx 6


class _Recorder:
    def __init__(self):
        self.calls = []

    def record(self, now, summary, alerts):
        self.calls.append((now, summary, alerts))


def test_f7_evaluation_is_recorded_owner_free_and_age_gauge_published():
    owner = str(uuid4())
    rec = _Recorder()
    reader = FakeFinopsReader(
        pricing_refs=PRICING, purchase_facts=[purchase(owner=owner, at=T0 - timedelta(days=1))],
        usage={owner: finops.OwnerUsage({"llm": D("1")})}, mismatch=(2, 7))
    out = run_finops(reader, now=T0, recorder=rec)
    assert out["evaluation_recorded"] is True and len(rec.calls) == 1
    _, summary, alerts = rec.calls[0]
    assert owner not in json.dumps([summary, alerts], default=str)
    assert "report" not in summary and any(a["kind"] == "wallet_mismatch" for a in alerts)

    class Broken:
        def record(self, *a):
            raise RuntimeError("db")
    again = run_finops(reader, now=T0, recorder=Broken())
    assert again["evaluation_recorded"] is False and again["evaluation_record_error"] == "RuntimeError"
    fa.publish_evaluation_age(1000.0, evaluated=True)
    fa.publish_evaluation_age(1090.0)
    snap = metrics.snapshot()
    key = next(k for k in snap if k.startswith("rpg_finops_evaluation_age_seconds"))
    assert snap[key] == 90.0


def test_f7_margin_gauge_cleared_when_sku_leaves_window():
    def run(sku):
        reader = FakeFinopsReader(pricing_refs=PRICING,
                                  purchase_facts=[purchase(sku=sku, at=T0 - timedelta(days=1))])
        run_finops(reader, now=T0)
    run("gone-sku")
    assert any("gone-sku" in k for k in metrics.snapshot() if k.startswith("rpg_finops_margin_ratio"))
    run("kept-sku")
    keys = [k for k in metrics.snapshot() if k.startswith("rpg_finops_margin_ratio")]
    assert any("kept-sku" in k for k in keys) and not any("gone-sku" in k for k in keys)


def test_f7_evaluations_migration_is_backend_only():
    sql = Path("supabase/migrations/20261015151000_finops_evaluations.sql").read_text(encoding="utf-8")
    assert "force row level security" in sql and "app.finops_evaluations" in sql
    assert "revoke all on app.finops_evaluations from public, anon, authenticated, rpg_api" in sql
    assert not re.search(r"grant\s", sql, re.I) and "owner_id" not in sql


def test_f4_google_profile_hides_purchases_when_switch_off(monkeypatch):
    import infrastructure.request_context as rc
    monkeypatch.setattr(rc, "current_principal", lambda: SimpleNamespace(user_id=uuid4()))
    ok = json.loads(api.google_play_profile().body)
    assert ok["purchases_disabled"] is False and ok["obfuscated_account_id"]
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({"new_purchases:google_play": False}), ttl=0))
    off = json.loads(api.google_play_profile().body)
    assert off == {"purchases_disabled": True, "reason": "new_purchases_disabled"}


def test_f5_job_deferred_requeues_without_burning_attempt_or_failing():
    from infrastructure.contracts import JobDeferred, JobRequest
    from infrastructure.local_adapters import InlineJobQueue
    from workers.job_worker import JobWorker
    queue = InlineJobQueue()
    job_id = queue.enqueue(JobRequest("generate_dynamic_art", "k1", {}, 3))
    paused = {"on": True}

    def handler(_payload):
        if paused["on"]:
            raise JobDeferred("image_generation_disabled", 60.0)
        return {"status": "ready"}
    worker = JobWorker(queue, {"generate_dynamic_art": handler}, worker_id="w")
    assert worker.run_once() == 1
    row = queue._jobs[job_id]
    assert (row.status, row.attempt, row.error_code) == ("queued", 0, "image_generation_disabled")
    paused["on"] = False
    assert worker.run_once() == 1 and queue._jobs[job_id].status == "succeeded"


def test_f5_art_worker_defers_when_image_switch_off_before_any_provider_call(monkeypatch):
    import workers.run_worker as rw
    from infrastructure.contracts import JobDeferred
    runtime = SimpleNamespace(resources=[object()], memory_store=object(), blob_store=None)
    monkeypatch.setattr(rw, "get_runtime", lambda: runtime)
    monkeypatch.setattr(rw, "PgVectorMemoryStore", object)
    handlers = rw.build_handlers()
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({ks.IMAGE: False}), ttl=0))
    payload = {"generation": {"generation_id": str(uuid4())}, "owner_id": str(uuid4()),
               "game_id": str(uuid4()), "asset_id": str(uuid4())}
    with pytest.raises(JobDeferred) as exc:
        handlers["generate_dynamic_art"](payload)
    assert exc.value.reason == "image_generation_disabled"


def test_f5_guard_applies_to_new_quotes_not_to_replay_of_existing_generation(monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")
    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "1")
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({ks.IMAGE: False}), ttl=0))
    monkeypatch.setattr("infrastructure.runtime.get_runtime",
                        lambda: SimpleNamespace(resources=[object()]))
    monkeypatch.setattr("infrastructure.request_context.current_principal", lambda: object())
    with pytest.raises(HTTPException):
        api._image_finance()  # quote / new confirm: refused
    runtime, _principal, _repo = api._image_finance(guard=False)  # confirm replay lookup: allowed
    assert runtime.resources


def test_f8_game_state_readable_with_image_switch_off(monkeypatch):
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    client = TestClient(api.app)
    created = client.post("/game/new", json={
        "name": "Reader", "race": "Humano", "class_name": "Sangromante",
        "region": "Nova Arcádia", "level": 1, "backstory": ""})
    assert created.status_code == 200, created.text
    gid = created.json()["game_id"]
    ks.set_switches(ks.KillSwitches(ks.MemorySwitchStore({ks.IMAGE: False}), ttl=0))
    state = client.get("/game/state", params={"game_id": gid})
    assert state.status_code == 200 and state.json()["game_id"] == gid
