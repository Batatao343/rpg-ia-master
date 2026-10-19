"""FinOps data access (SPEC-196). Read-only SQL over existing tables + an in-memory fake.

The Postgres reader must run on the privileged backend pool (same as reconciliation):
``usage_events``/``wallet_entries`` are RLS-forced per owner. Owner ids stay inside this
module and the pure aggregators; they never reach metrics, alerts or the cron response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from collections.abc import Mapping

from infrastructure.db_roles import admin_connection
from infrastructure.usage_events import has_column, spend_schema_ready
from services.finops import COST_GROUPS, FeeRate, OwnerUsage, PricingRef, PurchaseFact
from services.finops_alerts import Backlog, Freshness, UsageGroup

DURATION_STT_PROVIDERS = ("groq",)  # audio_units are milliseconds only for duration metering
SUCCESS = ("success", "ok", "completed")


@dataclass(frozen=True)
class OpsCounts:
    turns: int = 0
    images: int = 0
    voice_ms: int = 0
    voice_cost_usd: Decimal = Decimal("0")


def _fees(raw: Mapping) -> dict[str, FeeRate]:
    return {
        str(ch): FeeRate(Decimal(str(v["percentage"])), Decimal(str(v["fixed_brl"])))
        for ch, v in raw.items()
    }


class PostgresFinopsReader:
    def __init__(self, pool) -> None:
        self.pool = pool

    def pricing(self):
        with admin_connection(self.pool) as db:
            rows = db.execute("select * from app.pricing_versions order by created_at").fetchall()
        refs = {
            r["version_id"]: PricingRef(
                r["version_id"], Decimal(r["fx_usd_brl"]), _fees(r["channel_fees"])
            )
            for r in rows
        }
        fresh: list[Freshness] = []
        if rows:  # only the newest version authorizes new sales
            last = rows[-1]
            fresh = [
                Freshness(
                    "fx", last["fx_observed_at"], timedelta(seconds=last["fx_max_age_seconds"])
                ),
                Freshness(
                    "rate_card",
                    last["rate_card_observed_at"],
                    timedelta(seconds=last["rate_card_max_age_seconds"]),
                ),
            ]
        return refs, fresh

    def purchases(self, since, until):
        with admin_connection(self.pool) as db:
            rows = db.execute(
                """
                select w.reference_id as ref, w.owner_id::text as owner_key, w.created_at,
                  s.sku_id, s.channel, s.pricing_version_id, s.gross_brl, s.shard_milli,
                  w.amount_milli as purchase_milli,
                  -- SPEC-195 net reversal: clawback + legacy refund/reversal - claw_release,
                  -- plus refund debt opened - debt released (debt key = provider:reference).
                  (select coalesce(sum(case x.entry_type when 'claw_release' then -x.amount_milli
                                       else x.amount_milli end), 0)
                     from app.wallet_entries x where x.related_entry_id=w.entry_id
                      and x.entry_type in ('clawback','refund','reversal','claw_release'))
                  + (select coalesce(sum(case d.kind when 'open' then d.amount_milli
                                          when 'release' then -d.amount_milli else 0 end), 0)
                       from app.wallet_debt_entries d where d.owner_id=w.owner_id
                        and d.purchase_key = (case s.channel when 'web' then 'stripe'
                                              else s.channel end) || ':' || w.reference_id)
                  as reversed_milli,
                  (exists (select 1 from app.wallet_entries x where x.related_entry_id=w.entry_id
                            and x.entry_type='reversal')
                   or exists (select 1 from app.purchase_reconciliation_state st
                               where st.purchase_ref=w.reference_id
                                 and st.state in ('disputed','dispute_lost'))) as disputed,
                  (select min(x.created_at) from app.wallet_entries x
                    where x.owner_id=w.owner_id and x.entry_type='purchase') as first_at,
                  (select sum(f.fee_cents) from app.purchase_fee_records f
                    where f.purchase_ref=w.reference_id
                      and f.provider = case s.channel when 'web' then 'stripe' else s.channel end
                  ) as fee_cents
                from app.wallet_entries w join app.purchase_skus s on s.sku_id=w.sku_id
                where w.entry_type='purchase' and w.created_at >= %s and w.created_at < %s
                """,
                (since, until),
            ).fetchall()
        out = []
        for r in rows:
            gross = Decimal(r["gross_brl"])
            purchase_milli = int(r["purchase_milli"] or 0)
            reversed_brl = Decimal("0")
            if purchase_milli > 0 and int(r["reversed_milli"] or 0) > 0:
                share = min(Decimal(int(r["reversed_milli"])) / Decimal(purchase_milli), Decimal(1))
                reversed_brl = (gross * share).quantize(Decimal("0.0001"))
            out.append(
                PurchaseFact(
                    r["ref"],
                    r["channel"],
                    r["sku_id"],
                    r["pricing_version_id"],
                    r["owner_key"],
                    r["created_at"],
                    gross,
                    int(r["shard_milli"]),
                    None if r["fee_cents"] is None else Decimal(r["fee_cents"]) / 100,
                    r["first_at"],
                    Decimal("0") if r["disputed"] else reversed_brl,
                    reversed_brl if r["disputed"] else Decimal("0"),
                )
            )
        return out

    def owner_usage(self, since, until):
        with admin_connection(self.pool) as db:
            spend = "and counts_as_spend" if spend_schema_ready(db) else ""
            rows = db.execute(
                f"""select owner_id::text as owner_key, category, sum(cost_usd) as usd
                from app.usage_events where created_at >= %s and created_at < %s
                  {spend}
                group by 1,2""",
                (since, until),
            ).fetchall()
        acc: dict[str, dict[str, Decimal]] = {}
        for r in rows:
            group = COST_GROUPS.get(r["category"], "other")
            d = acc.setdefault(r["owner_key"], {})
            d[group] = d.get(group, Decimal("0")) + Decimal(r["usd"])
        return {k: OwnerUsage(v) for k, v in acc.items()}

    def usage_groups(self, since, until):
        with admin_connection(self.pool) as db:
            spend = "counts_as_spend" if spend_schema_ready(db) else "true as counts_as_spend"
            rows = db.execute(
                f"""select provider, model, category, pricing_version, cost_basis,
                outcome, {spend}, count(*) as n, sum(cost_usd) as usd from app.usage_events
                where created_at >= %s and created_at < %s group by 1,2,3,4,5,6,7""",
                (since, until),
            ).fetchall()
        # SPEC-236 R2: non-spend groups keep their count (provider-failure panel) but never cost.
        return [
            UsageGroup(
                r["provider"],
                r["model"],
                r["category"],
                r["pricing_version"],
                r["cost_basis"],
                r["outcome"],
                int(r["n"]),
                Decimal(r["usd"]) if r["counts_as_spend"] else Decimal("0"),
                bool(r["counts_as_spend"]),
            )
            for r in rows
        ]

    def ops_counts(self, since, until):
        with admin_connection(self.pool) as db:
            # SPEC-279: a deleted campaign keeps its usage (operation row gone, id kept); the
            # kind snapshot keeps it counted. Pre-migration schema falls back to the join.
            kind = (
                "coalesce(e.operation_kind,o.kind)"
                if has_column(db, "app.usage_events", "operation_kind")
                else "o.kind"
            )
            row = db.execute(
                f"""select
                count(distinct e.operation_id) filter (where {kind}='turn') as turns,
                count(*) filter (where e.category='image' and e.outcome = any(%s)) as images,
                coalesce(sum(e.audio_units) filter (where e.category='speech_to_text'
                    and e.provider = any(%s)),0) as voice_ms,
                coalesce(sum(e.cost_usd) filter (where e.category='speech_to_text'
                    and e.provider = any(%s)
                    and e.cost_basis not in ('failed_no_usage','definitive_no_charge')),0) as voice_cost
                from app.usage_events e left join app.operations o on o.id=e.operation_id
                where e.created_at >= %s and e.created_at < %s""",
                (
                    list(SUCCESS),
                    list(DURATION_STT_PROVIDERS),
                    list(DURATION_STT_PROVIDERS),
                    since,
                    until,
                ),
            ).fetchone()
        return OpsCounts(
            int(row["turns"]), int(row["images"]), int(row["voice_ms"]), Decimal(row["voice_cost"])
        )

    def wallet_mismatch(self):
        with admin_connection(self.pool) as db:
            row = db.execute("""select count(*) as n, coalesce(sum(d),0) as total from (
                select abs(a.available_milli - coalesce(sum(e.available_delta),0))
                     + abs(a.reserved_milli - coalesce(sum(e.reserved_delta),0)) as d
                from app.wallet_accounts a left join app.wallet_entries e on e.owner_id=a.owner_id
                group by a.owner_id, a.available_milli, a.reserved_milli) t where d <> 0""").fetchone()
        return int(row["n"]), int(row["total"])

    def wallet_holds(self, now):
        """SPEC-236 R4/R10: (uncertain reservations, oldest age s, capped anomalies). Owner-free."""
        with admin_connection(self.pool) as db:
            anomalies = (
                "count(*) filter (where financial_anomaly_milli > 0)"
                if has_column(db, "app.wallet_reservations", "financial_anomaly_milli")
                else "0"
            )
            row = db.execute(
                f"""select count(*) filter (where status='uncertain') as n,
                extract(epoch from (%s - min(created_at) filter (where status='uncertain'))) as age,
                {anomalies} as anomalies
                from app.wallet_reservations""",
                (now,),
            ).fetchone()
        return int(row["n"] or 0), float(row["age"] or 0), int(row["anomalies"] or 0)

    def backlogs(self, now):
        with admin_connection(self.pool) as db:
            rows = db.execute(
                """select provider, count(*) as n,
                extract(epoch from (%s - min(received_at))) as age
                from app.purchase_reconciliation_events where status <> 'applied'
                group by provider""",
                (now,),
            ).fetchall()
            stuck = db.execute(
                """select count(*) as n,
                extract(epoch from (%s - min(updated_at))) as age
                from app.payment_orders where status='reconciliation_required'""",
                (now,),
            ).fetchone()
        out = [Backlog(r["provider"], int(r["n"]), float(r["age"] or 0)) for r in rows]
        if stuck and stuck["n"]:
            out.append(Backlog("stripe", int(stuck["n"]), float(stuck["age"] or 0)))
        return out


@dataclass
class FakeFinopsReader:
    """In-memory reader for tests/sims."""

    pricing_refs: dict[str, PricingRef] = field(default_factory=dict)
    freshness: list[Freshness] = field(default_factory=list)
    purchase_facts: list[PurchaseFact] = field(default_factory=list)
    usage: dict[str, OwnerUsage] = field(default_factory=dict)
    groups: list[UsageGroup] = field(default_factory=list)
    ops: OpsCounts = field(default_factory=OpsCounts)
    mismatch: tuple[int, int] = (0, 0)
    backlog_list: list[Backlog] = field(default_factory=list)
    holds: tuple[int, float, int] = (0, 0.0, 0)

    def pricing(self):
        return self.pricing_refs, self.freshness

    def purchases(self, since, until):
        return [p for p in self.purchase_facts if since <= p.at < until]

    def owner_usage(self, since, until):
        return self.usage

    def usage_groups(self, since, until):
        return self.groups

    def ops_counts(self, since, until):
        return self.ops

    def wallet_mismatch(self):
        return self.mismatch

    def backlogs(self, now):
        return self.backlog_list

    def wallet_holds(self, now):
        return self.holds


class PostgresFinopsEvaluationStore:
    """Append-only record of each cron evaluation (app.finops_evaluations); owner-free."""

    def __init__(self, pool) -> None:
        self.pool = pool

    def record(self, now, summary: dict, alerts: list[dict]) -> None:
        from psycopg.types.json import Jsonb

        with admin_connection(self.pool) as db:
            db.execute(
                "insert into app.finops_evaluations"
                "(evaluated_at, blocking_alerts, alert_count, summary, alerts) "
                "values (%s,%s,%s,%s,%s)",
                (
                    now,
                    int(summary.get("blocking_alerts", 0)),
                    len(alerts),
                    Jsonb(summary),
                    Jsonb(alerts),
                ),
            )
