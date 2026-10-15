"""SPEC-195 reconciliation: stores (in-memory reference + Postgres) and the batch job.

Both stores apply the SAME pure plan (services.purchase_reconciliation). The job is idempotent:
plans are recomputed from the ledger under the owner lock, so replays post nothing.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from uuid import UUID, uuid4

from services.purchase_reconciliation import (
    GOOGLE, PARK_BASE_SECONDS, PARK_MAX_AGE_SECONDS, PARK_MAX_ATTEMPTS, PARK_MAX_SECONDS, STRIPE,
    Event, FinancialHold, Ledger, ReconciliationError, derive_state, fold, normalize_stripe_event,
    park_backoff_seconds, plan_adjustment, settlement_amount, target_milli, transition_allowed,
)

log = logging.getLogger("rpg.reconciliation")
VOID_OVERLAP_MS = 3_600_000
STRIPE_FINANCIAL = ("charge.refunded", "charge.dispute.created", "charge.dispute.closed")


@dataclass(frozen=True)
class PurchaseInfo:
    owner_id: UUID
    shard_milli: int
    gross_cents: int
    entry_id: UUID
    row_state: str | None = None


class Reconciler:
    """Cron entry point: ``reconcile_batch(max_items)``."""

    def __init__(self, store, google_client=None, google_purchases=None) -> None:
        self.store, self.google, self.google_purchases = store, google_client, google_purchases

    def ingest(self, event: Event) -> bool:
        """True if new, False for a duplicate provider event id (no-op)."""
        return self.store.insert_event(event)

    def reconcile_ref(self, provider: str, ref: str) -> str:
        return self.store.reconcile(provider, ref)

    def poll_google_voided(self, start_ms: int | None = None, end_ms: int | None = None,
                           max_pages: int = 5) -> int:
        if self.google is None:
            return 0
        started_ms = int(time.time() * 1000)
        if start_ms is None:  # persisted watermark: >page-size voids per window are never skipped
            start_ms = self.store.get_cursor(GOOGLE)
        added = 0
        for event in self.google.list_voided_events(start_ms, end_ms, max_pages=max_pages):
            added += 1 if self.ingest(event) else 0
        if getattr(self.google, "last_poll_complete", True):  # truncated poll: keep old watermark
            # overlap absorbs clock skew/late-indexed voids; event ids dedupe the re-read
            self.store.set_cursor(GOOGLE, started_ms - VOID_OVERLAP_MS)
        else:
            log.warning("google_void_poll_truncated pages=%s", max_pages)
        return added

    def reconcile_batch(self, max_items: int = 100) -> dict:
        ingested = self.store.ingest_backlog(max_items)
        applied = parked = failed = orphaned = 0
        for provider, ref in self.store.open_refs(max_items):
            try:
                outcome = self.store.reconcile(provider, ref)
            except Exception as exc:  # one poisoned purchase must not stall the batch
                failed += 1
                # error class only: messages may carry ids/amounts (no PII in logs)
                log.warning("reconcile_failed provider=%s error=%s", provider, type(exc).__name__)
                continue
            applied += outcome == "applied"
            parked += outcome == "parked"
            orphaned += outcome == "orphaned"
        retried = consume_failed = 0
        if self.google_purchases is not None:
            retried = int(self.google_purchases.retry_unconsumed(max(1, min(max_items, 50))))
            consume_failed = int((getattr(self.google_purchases, "last_retry", None) or {}).get("consume_failed", 0))
        totals = self.store.parking_counts()
        return {"ingested": ingested, "applied": applied, "parked": parked, "orphaned": orphaned,
                "failed": failed, "unconsumed_retried": retried, "consume_failed": consume_failed,
                "parked_total": totals.get("parked", 0), "orphaned_total": totals.get("orphaned", 0)}


# ---------------------------------------------------------------- in-memory reference store

class MemoryStore:
    """Reference implementation (tests). Mirrors the SQL ledger semantics exactly."""

    def __init__(self, clock=time.time) -> None:
        self.clock = clock
        self._tx = 0  # one stamp per top-level operation == Postgres transaction created_at
        self.lock = threading.RLock()
        self.accounts: dict[UUID, dict] = {}
        self.entries: list[dict] = []
        self.debt: list[dict] = []
        self.purchases: dict[tuple, PurchaseInfo] = {}
        self.events: dict[tuple, dict] = {}
        self.skips: set[tuple] = set()
        self.states: dict[tuple, str] = {}
        self.fees: list[dict] = []
        self.transitions: list[tuple] = []
        self.cursors: dict[str, int] = {}

    def get_cursor(self, provider) -> int | None:
        return self.cursors.get(provider)

    def set_cursor(self, provider, value_ms) -> None:
        self.cursors[provider] = max(value_ms, self.cursors.get(provider, 0))

    # wallet-side helpers -------------------------------------------------
    def _acct(self, owner):
        return self.accounts.setdefault(owner, {"available": 0, "reserved": 0})

    def available(self, owner) -> int:
        return self._acct(owner)["available"]

    def debt_of(self, owner) -> int:
        return sum(d["delta"] for d in self.debt if d["owner"] == owner)

    def _post(self, owner, etype, ref_type, ref_id, amount, delta, related=None) -> UUID:
        acct = self._acct(owner)
        if acct["available"] + delta < 0:
            raise ReconciliationError("negative_available")  # the CHECK constraint
        key = (owner, etype, ref_type, ref_id)
        if any((e["owner"], e["type"], e["rt"], e["rid"]) == key for e in self.entries):
            raise ReconciliationError("duplicate_entry")
        entry_id = uuid4()
        self.entries.append({"id": entry_id, "owner": owner, "type": etype, "rt": ref_type,
                             "rid": ref_id, "amount": amount, "delta": delta, "related": related})
        acct["available"] += delta
        return entry_id

    def _debt(self, owner, kind, key, amount, ref, reason=None):
        # same constraint as the migration: unique (owner_id, kind, reference_id)
        if any(d["owner"] == owner and d["kind"] == kind and d["ref"] == ref for d in self.debt):
            raise ReconciliationError("duplicate_debt_entry")
        delta = amount if kind == "open" else 0 if kind == "forgive_close" else -amount
        self.debt.append({"owner": owner, "kind": kind, "key": key, "amount": amount,
                          "delta": delta, "ref": ref, "tx": self._tx, "reason": reason})

    def _outstanding(self, owner, key) -> int:
        """Debt still owed for one purchase: open - settle - release - forgive."""
        return sum(d["delta"] for d in self.debt if d["owner"] == owner and d["key"] == key)

    def _fifo_keys(self, owner) -> list[str]:
        """Postgres order: (min(created_at) of the key's entries, purchase_key)."""
        first: dict[str, int] = {}
        for d in self.debt:
            if d["owner"] == owner and d["key"]:
                first.setdefault(d["key"], d["tx"])
        return [k for k in sorted(first, key=lambda k: (first[k], k)) if self._outstanding(owner, k) > 0]

    def forgive(self, owner, amount, reference, reason="admin") -> int:
        """Admin write-off, FIFO-attributed like wallet_debt._attribute."""
        with self.lock:
            self._tx += 1
            left = amount = min(amount, self.debt_of(owner))
            for key in self._fifo_keys(owner):
                take = min(left, self._outstanding(owner, key))
                if take > 0:
                    self._debt(owner, "forgive", key, take, f"{reference}:{key}", reason)
                    left -= take
                if not left:
                    break
            return amount - left

    def _settle(self, owner) -> int:
        amount = settlement_amount(self.debt_of(owner), self.available(owner))
        if amount <= 0:
            return 0
        entry = self._post(owner, "debt_settlement", "debt_settlement", str(uuid4()), amount, -amount)
        left = amount
        for key in self._fifo_keys(owner):
            take = min(left, self._outstanding(owner, key))
            if take > 0:
                self._debt(owner, "settle", key, take, f"{entry}:{key}")
                left -= take
            if not left:
                break
        return amount

    def credit_purchase(self, owner, provider, ref, shard_milli, gross_cents,
                        row_state="fulfilled") -> None:
        with self.lock:
            self._tx += 1
            rt = "payment:web" if provider == STRIPE else "payment:google_play"
            entry = self._post(owner, "purchase", rt, ref, shard_milli, shard_milli)
            self.purchases[(provider, ref)] = PurchaseInfo(owner, shard_milli, gross_cents, entry, row_state)
            self._settle(owner)

    def set_row_state(self, provider, ref, state) -> None:
        info = self.purchases[(provider, ref)]
        self.purchases[(provider, ref)] = PurchaseInfo(info.owner_id, info.shard_milli,
                                                       info.gross_cents, info.entry_id, state)

    def spend(self, owner, amount) -> None:
        """Reserve + settle as one step; fenced by financial hold."""
        with self.lock:
            if self.debt_of(owner) > 0:
                raise FinancialHold("financial_hold")
            if self.available(owner) < amount:
                raise ReconciliationError("insufficient")
            self._post(owner, "reserve", "reservation", str(uuid4()), amount, -amount)
            self._acct(owner)["reserved"] += amount
            self._acct(owner)["reserved"] -= amount  # settled immediately

    def spendable_tuple(self, owner):
        return (self.available(owner), self.debt_of(owner))

    # store protocol ------------------------------------------------------
    def insert_event(self, ev: Event) -> bool:
        with self.lock:
            key = (ev.provider, ev.event_id)
            if key in self.events:
                return False
            now = self.clock()
            self.events[key] = {"ev": ev, "status": "pending", "attempts": 0,
                                "next_at": now, "received": now}
            return True

    def ingest_backlog(self, limit) -> int:
        return 0

    def parking_counts(self) -> dict:
        with self.lock:
            out = {"parked": 0, "orphaned": 0}
            for rec in self.events.values():
                if rec["status"] in out:
                    out[rec["status"]] += 1
            return out

    def open_refs(self, limit):
        with self.lock:
            # only DUE rows; new (pending) events first so parked ones can never starve them
            now = self.clock()
            due = [r for r in self.events.values()
                   if r["status"] in ("pending", "parked") and r["next_at"] <= now]
            due.sort(key=lambda r: (r["status"] != "pending", r["received"]))
            seen = []
            for rec in due:
                k = (rec["ev"].provider, rec["ev"].ref)
                if k not in seen:
                    seen.append(k)
            seen = seen[:limit]
            # orphan recovery: the purchase was credited after the ref was given up on
            for rec in self.events.values():
                k = (rec["ev"].provider, rec["ev"].ref)
                if (rec["status"] == "orphaned" and k in self.purchases and k not in seen
                        and len(seen) < limit):
                    seen.append(k)
            return seen

    def _ledger(self, info: PurchaseInfo, key: str) -> Ledger:
        mine = [e for e in self.entries if e["related"] == info.entry_id]
        applied = sum(e["amount"] for e in mine if e["type"] in ("clawback", "refund", "reversal"))
        applied -= sum(e["amount"] for e in mine if e["type"] == "claw_release")
        d = [x for x in self.debt if x["owner"] == info.owner_id and x["key"] == key]
        amt = lambda k: sum(x["amount"] for x in d if x["kind"] == k)  # noqa: E731
        applied += amt("open") - amt("release") - amt("forgive_close")
        outstanding = amt("open") - amt("settle") - amt("release") - amt("forgive")
        return Ledger(self.available(info.owner_id), applied, outstanding,
                      amt("forgive") - amt("forgive_close"))

    def _seq(self, info: PurchaseInfo, key: str) -> int:
        """Per-purchase monotonic sequence over ALL adjustments (wallet + debt)."""
        return (sum(1 for e in self.entries if e["related"] == info.entry_id
                    and e["type"] in ("clawback", "claw_release"))
                + sum(1 for x in self.debt if x["key"] == key
                      and x["kind"] in ("open", "release", "forgive_close")) + 1)

    def reconcile(self, provider, ref) -> str:
        with self.lock:
            recs = [r for r in self.events.values()
                    if r["ev"].provider == provider and r["ev"].ref == ref]
            info = self.purchases.get((provider, ref))
            if info is None:
                now, alive = self.clock(), 0
                for r in recs:
                    if r["status"] in ("pending", "parked") and r["next_at"] <= now:
                        r["attempts"] += 1
                        if (r["attempts"] >= PARK_MAX_ATTEMPTS
                                or now - r["received"] >= PARK_MAX_AGE_SECONDS):
                            r["status"] = "orphaned"
                        else:
                            r["status"] = "parked"
                            r["next_at"] = now + park_backoff_seconds(r["attempts"])
                    alive += r["status"] in ("pending", "parked")
                return "orphaned" if recs and not alive else "parked"
            self._tx += 1
            key = f"{provider}:{ref}"
            facts = fold([r["ev"] for r in recs])
            target = target_milli(facts, info.shard_milli, info.gross_cents)
            plan = plan_adjustment(target, self._ledger(info, key))
            owner, n = info.owner_id, self._seq(info, key)
            if plan.clawback:
                self._post(owner, "clawback", "reconcile:" + provider, f"{ref}:{n}", plan.clawback,
                           -plan.clawback, info.entry_id)
            if plan.debt_open:
                self._debt(owner, "open", key, plan.debt_open, f"{key}:open:{n}")
            if plan.debt_release:
                self._debt(owner, "release", key, plan.debt_release, f"{key}:release:{n}")
            if plan.forgive_close:
                self._debt(owner, "forgive_close", key, plan.forgive_close, f"{key}:forgive_close:{n}")
            if plan.credit_release:
                self._post(owner, "claw_release", "reconcile:" + provider, f"{ref}:{n}",
                           plan.credit_release, plan.credit_release, info.entry_id)
                self._settle(owner)
            state = derive_state(provider, facts, gross_cents=info.gross_cents, row_state=info.row_state)
            old = self.states.get((provider, ref), "paid" if provider == STRIPE else "fulfilled")
            if not transition_allowed(provider, old, state):
                raise ReconciliationError(f"transition_forbidden:{old}->{state}")
            if old != state:
                self.transitions.append((provider, ref, old, state))
            self.states[(provider, ref)] = state
            for r in recs:
                if r["ev"].kind == "fee_reconciled" and r["status"] != "applied":
                    self.fees.append({"provider": provider, "ref": ref, "event": r["ev"].event_id,
                                      "fee_cents": r["ev"].amount_cents})
                r["status"] = "applied"
            return "applied"


# ------------------------------------------------------------------------- Postgres store

class PostgresStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    def insert_event(self, ev: Event) -> bool:
        with self.pool.connection() as db, db.transaction():
            return self._insert(db, ev)

    @staticmethod
    def _insert(db, ev: Event) -> bool:
        return db.execute("""insert into app.purchase_reconciliation_events
            (event_pk,provider,provider_event_id,kind,purchase_ref,amount_cents,sub_id,provider_created,reason)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (provider,provider_event_id) do nothing
            returning event_pk""", (uuid4(), ev.provider, ev.event_id, ev.kind, ev.ref, ev.amount_cents,
                                    ev.sub_id, ev.created, ev.reason)).fetchone() is not None

    def ingest_backlog(self, limit) -> int:
        """Normalize Stripe webhook rows (SPEC-189 store) not yet seen; includes real fees.

        Rows with no financial effect get a skip marker so they are never re-selected."""
        added = 0
        with self.pool.connection() as db, db.transaction():
            rows = db.execute("""select e.event_id,e.event_type,e.facts,e.provider_created
                from app.stripe_events e where e.event_type = any(%s)
                and not exists (select 1 from app.purchase_reconciliation_events r
                  where r.provider='stripe' and r.provider_event_id=e.event_id)
                and not exists (select 1 from app.purchase_reconciliation_skips k
                  where k.provider='stripe' and k.provider_event_id=e.event_id)
                order by e.received_at limit %s""", (list(STRIPE_FINANCIAL), limit)).fetchall()
            for row in rows:
                ev = normalize_stripe_event(row["event_type"], row["event_id"], row["facts"],
                                            int(row["provider_created"]))
                if ev is None:
                    db.execute("""insert into app.purchase_reconciliation_skips
                        (provider,provider_event_id,reason) values ('stripe',%s,'no_financial_effect')
                        on conflict do nothing""", (row["event_id"],))
                else:
                    added += bool(self._insert(db, ev))
            fees = db.execute("""select f.provider_reference,f.amount_cents,o.stripe_payment_intent as pi
                from app.payment_financial_events f join app.payment_orders o using (order_id)
                where f.kind='fee_reconciled' and o.stripe_payment_intent is not null
                and not exists (select 1 from app.purchase_reconciliation_events r
                  where r.provider='stripe' and r.provider_event_id='fee:'||f.provider_reference)
                limit %s""", (limit,)).fetchall()
            for row in fees:
                added += self._insert(db, Event(STRIPE, "fee:" + row["provider_reference"], "fee_reconciled",
                                                row["pi"], int(row["amount_cents"])))
        return added

    def open_refs(self, limit):
        """Only DUE rows (pending, or parked past their backoff); new events sort first."""
        with self.pool.connection() as db:
            rows = db.execute("""select provider,purchase_ref,
                  bool_or(status='pending') as fresh,min(received_at) as first
                from app.purchase_reconciliation_events
                where status in ('pending','parked') and next_attempt_at <= now()
                group by provider,purchase_ref order by not bool_or(status='pending'), first
                limit %s""", (limit,)).fetchall()
        refs = [(r["provider"], r["purchase_ref"]) for r in rows]
        if len(refs) < limit:  # orphan recovery: purchase credited after the ref was given up on
            with self.pool.connection() as db:
                rows = db.execute("""select distinct provider,purchase_ref
                    from app.purchase_reconciliation_events e where status='orphaned' and (
                      (provider='stripe' and exists (select 1 from app.payment_orders o
                         join app.wallet_entries w on w.entry_type='purchase'
                          and w.reference_type='payment:web' and w.reference_id=o.stripe_payment_intent
                         where o.stripe_payment_intent=e.purchase_ref))
                      or (provider='google_play' and exists (select 1 from app.google_play_purchases g
                         join app.wallet_entries w on w.entry_type='purchase'
                          and w.reference_type='payment:google_play' and w.reference_id=g.order_id
                         where g.order_id=e.purchase_ref)))
                    limit %s""", (limit - len(refs),)).fetchall()
            refs += [(r["provider"], r["purchase_ref"]) for r in rows
                     if (r["provider"], r["purchase_ref"]) not in refs]
        return refs

    def get_cursor(self, provider) -> int | None:
        with self.pool.connection() as db:
            row = db.execute("select watermark_ms from app.purchase_reconciliation_cursors "
                             "where provider=%s", (provider,)).fetchone()
        return int(row["watermark_ms"]) if row else None

    def set_cursor(self, provider, value_ms) -> None:
        with self.pool.connection() as db, db.transaction():
            db.execute("""insert into app.purchase_reconciliation_cursors(provider,watermark_ms)
                values (%s,%s) on conflict (provider) do update set updated_at=now(),
                watermark_ms=greatest(app.purchase_reconciliation_cursors.watermark_ms,excluded.watermark_ms)""",
                       (provider, value_ms))

    def parking_counts(self) -> dict:
        with self.pool.connection() as db:
            rows = db.execute("""select status,count(*) as n from app.purchase_reconciliation_events
                where status in ('parked','orphaned') group by status""").fetchall()
        return {r["status"]: int(r["n"]) for r in rows}

    @staticmethod
    def _purchase(db, provider, ref):
        if provider == STRIPE:
            row = db.execute("""select o.owner_id,o.shard_milli,o.gross_cents,w.entry_id,null::text as row_state
                from app.payment_orders o join app.wallet_entries w on w.entry_type='purchase'
                and w.reference_type='payment:web' and w.reference_id=o.stripe_payment_intent
                where o.stripe_payment_intent=%s""", (ref,)).fetchone()
        else:
            row = db.execute("""select g.owner_id,s.shard_milli,(s.gross_brl*100)::bigint as gross_cents,
                w.entry_id,g.state as row_state from app.google_play_purchases g
                join app.purchase_skus s using (sku_id)
                join app.wallet_entries w on w.entry_type='purchase'
                and w.reference_type='payment:google_play' and w.reference_id=g.order_id
                where g.order_id=%s""", (ref,)).fetchone()
        return PurchaseInfo(row["owner_id"], int(row["shard_milli"]), int(row["gross_cents"]),
                            row["entry_id"], row["row_state"]) if row else None

    @staticmethod
    def _park(db, provider, ref) -> str:
        """Bump due rows: exponential backoff, `orphaned` after N attempts / max age."""
        db.execute("""update app.purchase_reconciliation_events set
              attempt_count = attempt_count + 1,
              status = case when attempt_count + 1 >= %(max_n)s
                              or now() - received_at >= make_interval(secs => %(max_age)s)
                            then 'orphaned' else 'parked' end,
              next_attempt_at = now() + make_interval(
                  secs => least(%(base)s * power(2, attempt_count), %(cap)s))
            where provider=%(p)s and purchase_ref=%(r)s and status in ('pending','parked')
              and next_attempt_at <= now()""",
                   {"max_n": PARK_MAX_ATTEMPTS, "max_age": PARK_MAX_AGE_SECONDS, "base": PARK_BASE_SECONDS,
                    "cap": PARK_MAX_SECONDS, "p": provider, "r": ref})
        row = db.execute("""select count(*) as total,
              count(*) filter (where status in ('pending','parked')) as alive
            from app.purchase_reconciliation_events where provider=%s and purchase_ref=%s""",
                         (provider, ref)).fetchone()
        return "orphaned" if row["total"] and not row["alive"] else "parked"

    def reconcile(self, provider, ref) -> str:
        from infrastructure.wallet import PostgresWallet
        from infrastructure.wallet_debt import insert_debt_entry, settle_owner_debt
        with self.pool.connection() as db, db.transaction():
            db.execute("select pg_advisory_xact_lock(hashtextextended(%s,195))", (f"{provider}:{ref}",))
            info = self._purchase(db, provider, ref)
            if info is None:
                return self._park(db, provider, ref)
            account = PostgresWallet._locked_account(db, info.owner_id)
            key = f"{provider}:{ref}"
            rows = db.execute("""select provider,provider_event_id,kind,purchase_ref,amount_cents,sub_id,
                provider_created,reason from app.purchase_reconciliation_events
                where provider=%s and purchase_ref=%s""", (provider, ref)).fetchall()
            events = [Event(r["provider"], r["provider_event_id"], r["kind"], r["purchase_ref"],
                            r["amount_cents"], r["sub_id"], int(r["provider_created"]), r["reason"])
                      for r in rows]
            facts = fold(events)
            target = target_milli(facts, info.shard_milli, info.gross_cents)
            ledger = self._ledger(db, info, key, int(account["available_milli"]))
            plan = plan_adjustment(target, ledger)
            n = self._seq(db, info, key)
            rtype, rid = "reconcile:" + provider, f"{ref}:{n}"
            owner = info.owner_id
            if plan.clawback:
                PostgresWallet._post(db, owner, "clawback", rtype, rid, plan.clawback, -plan.clawback,
                                     0, related_entry_id=info.entry_id)
                db.execute("update app.wallet_accounts set available_milli=available_milli-%s,"
                           "updated_at=now() where owner_id=%s", (plan.clawback, owner))
            if plan.debt_open:
                insert_debt_entry(db, owner, "open", key, plan.debt_open, f"{key}:open:{n}")
            if plan.debt_release:
                insert_debt_entry(db, owner, "release", key, plan.debt_release, f"{key}:release:{n}")
            if plan.forgive_close:
                insert_debt_entry(db, owner, "forgive_close", key, plan.forgive_close,
                                  f"{key}:forgive_close:{n}")
            if plan.credit_release:
                PostgresWallet._post(db, owner, "claw_release", rtype, rid, plan.credit_release,
                                     plan.credit_release, 0, related_entry_id=info.entry_id)
                db.execute("update app.wallet_accounts set available_milli=available_milli+%s,"
                           "updated_at=now() where owner_id=%s", (plan.credit_release, owner))
                settle_owner_debt(db, owner)
            state = derive_state(provider, facts, gross_cents=info.gross_cents, row_state=info.row_state)
            prior = db.execute("select state from app.purchase_reconciliation_state where provider=%s "
                               "and purchase_ref=%s", (provider, ref)).fetchone()
            old = prior["state"] if prior else ("paid" if provider == STRIPE else "fulfilled")
            if not transition_allowed(provider, old, state):
                raise ReconciliationError(f"transition_forbidden:{old}->{state}")
            if old != state:
                db.execute("""insert into app.purchase_reconciliation_transitions
                    (transition_id,provider,purchase_ref,old_state,new_state) values (%s,%s,%s,%s,%s)""",
                           (uuid4(), provider, ref, old, state))
            db.execute("""insert into app.purchase_reconciliation_state(provider,purchase_ref,owner_id,state,target_milli)
                values (%s,%s,%s,%s,%s) on conflict (provider,purchase_ref)
                do update set state=excluded.state,target_milli=excluded.target_milli,updated_at=now()""",
                       (provider, ref, owner, state, target))
            for e in events:
                if e.kind == "fee_reconciled":
                    db.execute("""insert into app.purchase_fee_records(fee_id,provider,purchase_ref,provider_event_id,fee_cents)
                        values (%s,%s,%s,%s,%s) on conflict (provider,provider_event_id) do nothing""",
                               (uuid4(), provider, ref, e.event_id, e.amount_cents))
            db.execute("""update app.purchase_reconciliation_events set status='applied',applied_at=now()
                where provider=%s and purchase_ref=%s and status<>'applied'""", (provider, ref))
            return "applied"

    @staticmethod
    def _seq(db, info, key) -> int:
        """Per-purchase monotonic sequence over ALL adjustments (wallet + debt)."""
        w = db.execute("select count(*) as c from app.wallet_entries where related_entry_id=%s "
                       "and entry_type in ('clawback','claw_release')", (info.entry_id,)).fetchone()["c"]
        d = db.execute("select count(*) as c from app.wallet_debt_entries where owner_id=%s and "
                       "purchase_key=%s and kind in ('open','release','forgive_close')",
                       (info.owner_id, key)).fetchone()["c"]
        return int(w) + int(d) + 1

    @staticmethod
    def _ledger(db, info, key, available) -> Ledger:
        entries = db.execute("""select entry_type,coalesce(sum(amount_milli),0) as s from app.wallet_entries
            where related_entry_id=%s and entry_type in ('clawback','refund','reversal','claw_release')
            group by entry_type""", (info.entry_id,)).fetchall()
        by = {r["entry_type"]: int(r["s"]) for r in entries}
        debts = db.execute("""select kind,coalesce(sum(amount_milli),0) as s from app.wallet_debt_entries
            where owner_id=%s and purchase_key=%s group by kind""", (info.owner_id, key)).fetchall()
        d = {r["kind"]: int(r["s"]) for r in debts}
        applied = (by.get("clawback", 0) + by.get("refund", 0) + by.get("reversal", 0)
                   - by.get("claw_release", 0) + d.get("open", 0) - d.get("release", 0)
                   - d.get("forgive_close", 0))
        outstanding = d.get("open", 0) - d.get("settle", 0) - d.get("release", 0) - d.get("forgive", 0)
        return Ledger(available, applied, outstanding, d.get("forgive", 0) - d.get("forgive_close", 0))
