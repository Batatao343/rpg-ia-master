"""Cron-callable FinOps evaluation (SPEC-196): report + alerts + metrics, owner-free output."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from services import finops
from services.finops_alerts import (
    AlertInputs, Thresholds, evaluate_alerts, installed_freshness, publish_alert_metrics, publish_evaluation_age,
    publish_margin_metrics, publish_switch_metrics,
)
from services.kill_switches import get_switches


def run_finops(reader, now: datetime | None = None, *, report_days: int | None = None,
               alert_hours: int | None = None, baselines: int = 3,
               fixed_path: Path | None = None, recorder=None) -> dict:
    """``recorder.record(now, summary, alerts)`` (optional) persists the evaluation owner-free so
    staleness is checkable via SQL when there is no Prometheus scrape target (Vercel)."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    report_days = report_days or int(os.getenv("RPG_FINOPS_REPORT_DAYS", "30"))
    alert_hours = alert_hours or int(os.getenv("RPG_FINOPS_ALERT_HOURS", "24"))
    pricing, fresh = reader.pricing()
    since = now - timedelta(days=report_days)
    purchases = reader.purchases(since, now)
    usage = reader.owner_usage(since, now)
    window_cost: dict[str, Decimal] = {}
    for g in reader.usage_groups(since, now):
        grp = finops.COST_GROUPS.get(g.category, "other")
        window_cost[grp] = window_cost.get(grp, Decimal("0")) + g.cost_usd
    ops = reader.ops_counts(since, now)
    newest = finops.newest_pricing(pricing)
    fx = newest.fx_usd_brl if newest else None
    fixed = finops.load_fixed_costs(fixed_path, window_days=report_days, fx_usd_brl=fx)
    report = finops.build_report(
        purchases, pricing, usage, window_cost_usd=window_cost, turns=ops.turns,
        images=ops.images, voice_ms=ops.voice_ms, voice_cost_usd=ops.voice_cost_usd, fixed=fixed)

    span = timedelta(hours=alert_hours)
    groups_now = reader.usage_groups(now - span, now)
    base = []
    for i in range(1, baselines + 1):
        by: dict[str, Decimal] = {}
        for g in reader.usage_groups(now - span * (i + 1), now - span * i):
            by[g.provider] = by.get(g.provider, Decimal("0")) + g.cost_usd
        base.append(by)
    n_mis, abs_mis = reader.wallet_mismatch()
    off = sorted(k for k, v in get_switches().snapshot().items() if not v)
    alerts = evaluate_alerts(AlertInputs(
        usage_groups=groups_now, freshness=[*fresh, *installed_freshness()],
        wallet_mismatch_accounts=n_mis, wallet_mismatch_abs_milli=abs_mis,
        backlogs=reader.backlogs(now), baseline_cost_by_provider=base, skus=report.skus,
        switches_off=off, unpriced_purchases=report.unpriced_purchases,
        unpriced_versions=report.missing_pricing), now, Thresholds.from_env())
    publish_alert_metrics(alerts)
    publish_margin_metrics(report.skus, report.unit_costs)
    publish_switch_metrics(off)
    publish_evaluation_age(evaluated=True)
    summary = {"failed": 0, "alerts": len(alerts), "blocking_alerts": sum(a.blocking for a in alerts),
            "alert_kinds": ",".join(sorted({a.kind for a in alerts})), "skus": len(report.skus),
            "skus_below_target": sum(1 for s in report.skus if s.meets_target is False),
            "switches_off": len(off), "purchases": sum(r.purchases for r in report.rows),
            "unpriced_purchases": report.unpriced_purchases,
            "report": finops.report_to_dict(report)}
    if recorder is not None:
        try:
            recorder.record(now, {k: v for k, v in summary.items() if k != "report"},
                            [{"kind": a.kind, "message": a.message, "blocking": a.blocking,
                              "channel": a.channel, "sku_id": a.sku_id, "provider": a.provider}
                             for a in alerts])
            summary["evaluation_recorded"] = True
        except Exception as exc:  # observability must not fail the evaluation itself
            summary["evaluation_recorded"] = False
            summary["evaluation_record_error"] = type(exc).__name__
    return summary
