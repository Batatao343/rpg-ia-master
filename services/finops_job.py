"""Cron-callable FinOps evaluation (SPEC-196): report + alerts + metrics, owner-free output."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone, UTC
from decimal import Decimal
from pathlib import Path

from services import finops
from services.daily_spend_cap import evaluate_daily_cap
from services.finops_alerts import (
    Alert,
    AlertInputs,
    Thresholds,
    evaluate_alerts,
    failed_no_usage_by_provider,
    installed_freshness,
    publish_alert_metrics,
    publish_evaluation_age,
    publish_margin_metrics,
    publish_switch_metrics,
    spend_groups,
)
from services.kill_switches import get_switches


def run_finops(
    reader,
    now: datetime | None = None,
    *,
    report_days: int | None = None,
    alert_hours: int | None = None,
    baselines: int = 3,
    fixed_path: Path | None = None,
    recorder=None,
    switch_store=None,
) -> dict:
    """``recorder.record(now, summary, alerts)`` (optional) persists the evaluation owner-free so
    staleness is checkable via SQL when there is no Prometheus scrape target (Vercel)."""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    report_days = report_days or int(os.getenv("RPG_FINOPS_REPORT_DAYS", "30"))
    alert_hours = alert_hours or int(os.getenv("RPG_FINOPS_ALERT_HOURS", "24"))
    pricing, fresh = reader.pricing()
    since = now - timedelta(days=report_days)
    purchases = reader.purchases(since, now)
    usage = reader.owner_usage(since, now)
    window_cost: dict[str, Decimal] = {}
    window_groups = reader.usage_groups(since, now)
    for g in spend_groups(window_groups):
        grp = finops.COST_GROUPS.get(g.category, "other")
        window_cost[grp] = window_cost.get(grp, Decimal("0")) + g.cost_usd
    ops = reader.ops_counts(since, now)
    newest = finops.newest_pricing(pricing)
    fx = newest.fx_usd_brl if newest else None
    fixed = finops.load_fixed_costs(fixed_path, window_days=report_days, fx_usd_brl=fx)
    report = finops.build_report(
        purchases,
        pricing,
        usage,
        window_cost_usd=window_cost,
        turns=ops.turns,
        images=ops.images,
        voice_ms=ops.voice_ms,
        voice_cost_usd=ops.voice_cost_usd,
        fixed=fixed,
    )

    span = timedelta(hours=alert_hours)
    groups_now = reader.usage_groups(now - span, now)
    base = []
    for i in range(1, baselines + 1):
        by: dict[str, Decimal] = {}
        for g in spend_groups(reader.usage_groups(now - span * (i + 1), now - span * i)):
            by[g.provider] = by.get(g.provider, Decimal("0")) + g.cost_usd
        base.append(by)
    n_mis, abs_mis = reader.wallet_mismatch()
    holds = getattr(reader, "wallet_holds", None)
    uncertain, uncertain_age, anomalies = holds(now) if holds is not None else (0, 0.0, 0)
    off = sorted(k for k, v in get_switches().snapshot().items() if not v)
    alerts = evaluate_alerts(
        AlertInputs(
            usage_groups=groups_now,
            freshness=[*fresh, *installed_freshness()],
            wallet_mismatch_accounts=n_mis,
            wallet_mismatch_abs_milli=abs_mis,
            backlogs=reader.backlogs(now),
            baseline_cost_by_provider=base,
            skus=report.skus,
            switches_off=off,
            unpriced_purchases=report.unpriced_purchases,
            unpriced_versions=report.missing_pricing,
            wallet_uncertain=uncertain,
            wallet_uncertain_oldest_seconds=uncertain_age,
            wallet_anomalies=anomalies,
        ),
        now,
        Thresholds.from_env(),
    )
    # Daily spend cap (opt-in via RPG_DAILY_SPEND_CAP_BRL): auto-off only, never auto-on.
    cap_summary: dict = {}
    cap_failed = 0
    try:
        store = switch_store if switch_store is not None else get_switches()._resolve_store()
        cap = evaluate_daily_cap(reader, store, now, fx)
        alerts = [*alerts, *cap.alerts]
        cap_summary = cap.summary()
        if cap.switched_off:
            get_switches().invalidate()
            off = sorted({*off, *cap.switched_off})
    except Exception as exc:  # the cap must not break the evaluation; surfaced in the summary
        cap_summary = {"daily_cap_error": type(exc).__name__}
        cap_failed = 1
        alerts = [
            *alerts,
            Alert(
                "daily_spend_cap_error",
                f"daily spend cap evaluation failed: {type(exc).__name__}: {str(exc)[:200]}",
                blocking=True,
            ),
        ]
    if (
        cap_summary.get("daily_cap_error") and not cap_failed
    ):  # store problem reported by the evaluator
        cap_failed = 1
        alerts = [
            *alerts,
            Alert(
                "daily_spend_cap_error",
                "daily spend cap error: " + cap_summary["daily_cap_error"],
                blocking=True,
            ),
        ]
    publish_alert_metrics(alerts)
    publish_margin_metrics(report.skus, report.unit_costs)
    publish_switch_metrics(off)
    publish_evaluation_age(evaluated=True)
    summary = {
        "failed": cap_failed,
        "alerts": len(alerts),
        "blocking_alerts": sum(a.blocking for a in alerts),
        "alert_kinds": ",".join(sorted({a.kind for a in alerts})),
        "skus": len(report.skus),
        "skus_below_target": sum(1 for s in report.skus if s.meets_target is False),
        "switches_off": len(off),
        "purchases": sum(r.purchases for r in report.rows),
        "unpriced_purchases": report.unpriced_purchases,
        # SPEC-236 R2: spend sums exclude failed attempts without usage (report v2); those
        # are shown apart as a count per provider, never as cost.
        "report_version": "finops-spend-v2",
        "provider_failures_no_usage": sum(failed_no_usage_by_provider(window_groups).values()),
        "provider_failures_no_usage_by_provider": ",".join(
            f"{p}={n}" for p, n in failed_no_usage_by_provider(groups_now).items()
        ),
        "wallet_uncertain_holds": uncertain,
        **cap_summary,
        "report": finops.report_to_dict(report),
    }
    if recorder is not None:
        try:
            recorder.record(
                now,
                {k: v for k, v in summary.items() if k != "report"},
                [
                    {
                        "kind": a.kind,
                        "message": a.message,
                        "blocking": a.blocking,
                        "channel": a.channel,
                        "sku_id": a.sku_id,
                        "provider": a.provider,
                    }
                    for a in alerts
                ],
            )
            summary["evaluation_recorded"] = True
        except Exception as exc:  # observability must not fail the evaluation itself
            summary["evaluation_recorded"] = False
            summary["evaluation_record_error"] = type(exc).__name__
    return summary
