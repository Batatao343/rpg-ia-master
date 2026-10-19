"""SPEC-195 pure reconciliation core: closed state machines, event fold, adjustment plan.

No I/O. The claim for a purchase is a pure function of the SET of normalized provider events
(cumulative maxima + terminal-status-wins), so arrival order and duplicates cannot change it.
"""

from __future__ import annotations

from dataclasses import dataclass

STRIPE, GOOGLE = "stripe", "google_play"
KINDS = {
    "refund",
    "dispute_open",
    "dispute_won",
    "dispute_lost",
    "voided",
    "revoked",
    "fee_reconciled",
}
# Estados Stripe: created, paid, refunded_partial, refunded_full, disputed, dispute_won, dispute_lost.
# Estados Google: pending, purchased, fulfilled, consumed, voided, revoked.
# Closed transition tables: nothing returns to created/paid; refunded_full and voided/revoked
# are terminal (voided and revoked are the same financial outcome).
STRIPE_TRANSITIONS = {
    "created": {"paid"},
    "paid": {"refunded_partial", "refunded_full", "disputed", "dispute_won", "dispute_lost"},
    "refunded_partial": {"refunded_full", "disputed", "dispute_lost"},
    "disputed": {"dispute_won", "dispute_lost", "refunded_partial", "refunded_full"},
    "dispute_won": {"refunded_partial", "refunded_full", "disputed", "dispute_lost"},
    "dispute_lost": {"refunded_full", "disputed"},
    "refunded_full": set(),
}
GOOGLE_TRANSITIONS = {
    "pending": {"purchased", "fulfilled", "consumed"},
    "purchased": {"fulfilled", "consumed", "voided", "revoked"},
    "fulfilled": {"consumed", "voided", "revoked"},
    "consumed": {"voided", "revoked"},
    "voided": set(),
    "revoked": set(),
}
TRANSITIONS = {STRIPE: STRIPE_TRANSITIONS, GOOGLE: GOOGLE_TRANSITIONS}
# voidedReason (Google VoidedPurchase): 0 Other, 1 Remorse, 2 Not_received, 3 Defective,
# 4 Accidental_purchase, 5 Fraud, 6 Friendly_fraud, 7 Chargeback, 8 Unacknowledged_purchase.
# Only fraud/chargeback outcomes are revocations; 8 is Google's auto-refund of an unacknowledged
# purchase (plain void). Unknown/other reasons -> plain voided.
REVOKE_REASONS = {5, 6, 7}
# Parking (events whose purchase is not credited yet): exponential backoff, then `orphaned`.
PARK_BASE_SECONDS, PARK_MAX_SECONDS = 300, 6 * 3600
PARK_MAX_ATTEMPTS, PARK_MAX_AGE_SECONDS = 8, 14 * 86400


def park_backoff_seconds(attempts: int) -> int:
    return min(PARK_BASE_SECONDS * 2 ** max(0, attempts - 1), PARK_MAX_SECONDS)


class ReconciliationError(ValueError):
    pass


class FinancialHold(ValueError):
    """Account has unsettled refund debt: new paid operations are fenced."""


def transition_allowed(provider: str, old: str, new: str) -> bool:
    return old == new or new in TRANSITIONS[provider].get(old, set())


@dataclass(frozen=True)
class Event:
    provider: str
    event_id: str
    kind: str
    ref: str  # Stripe payment_intent / Google order_id
    amount_cents: int | None = None
    sub_id: str | None = None  # dispute id / charge id
    created: int = 0
    reason: int | None = None

    def __post_init__(self):
        if (
            self.provider not in TRANSITIONS
            or self.kind not in KINDS
            or not self.event_id
            or not self.ref
        ):
            raise ReconciliationError("event_invalid")
        if self.amount_cents is not None and (
            isinstance(self.amount_cents, bool)
            or not isinstance(self.amount_cents, int)
            or self.amount_cents < 0
        ):
            raise ReconciliationError("event_amount_invalid")


@dataclass(frozen=True)
class Facts:
    refunded_cents: int = 0
    disputes: tuple = ()  # ((dispute_id, amount_cents, status), ...) sorted
    voided: bool = False
    revoked: bool = False
    fee_cents: int | None = None


_RANK = {"open": 0, "won": 1, "lost": 2}


def fold(events) -> Facts:
    """Order/duplicate independent."""
    refunded, voided, revoked, fee = 0, False, False, None
    disputes: dict[str, list] = {}
    fee_key = None
    seen = set()
    for ev in events:
        if (ev.provider, ev.event_id) in seen:
            continue
        seen.add((ev.provider, ev.event_id))
        if ev.kind == "refund":
            refunded = max(refunded, ev.amount_cents or 0)
        elif ev.kind in ("dispute_open", "dispute_won", "dispute_lost"):
            status = ev.kind.split("_")[1]
            cur = disputes.setdefault(ev.sub_id or ev.event_id, [0, "open"])
            cur[0] = max(cur[0], ev.amount_cents or 0)
            if _RANK[status] > _RANK[cur[1]]:
                cur[1] = status
        elif ev.kind in ("voided", "revoked"):
            voided = True
            revoked = revoked or ev.kind == "revoked"
        elif ev.kind == "fee_reconciled":
            key = (ev.created, ev.event_id)
            if fee_key is None or key > fee_key:
                fee_key, fee = key, ev.amount_cents
    return Facts(
        refunded, tuple(sorted((k, v[0], v[1]) for k, v in disputes.items())), voided, revoked, fee
    )


def reversed_cents(facts: Facts, gross_cents: int) -> int:
    active = sum(a for _, a, s in facts.disputes if s in ("open", "lost"))
    return min(gross_cents, facts.refunded_cents + active)


def target_milli(facts: Facts, shard_milli: int, gross_cents: int) -> int:
    """Total credits that must be clawed back for this purchase (never above shard_milli)."""
    if facts.voided:
        return shard_milli
    if gross_cents <= 0:
        raise ReconciliationError("gross_invalid")
    return shard_milli * reversed_cents(facts, gross_cents) // gross_cents


def stripe_state(facts: Facts, gross_cents: int) -> str:
    """State of an already-credited Stripe purchase (before credit it is 'created')."""
    if facts.refunded_cents >= gross_cents:
        return "refunded_full"
    statuses = {s for _, _, s in facts.disputes}
    if "open" in statuses:
        return "disputed"
    if "lost" in statuses:
        return "dispute_lost"
    if facts.refunded_cents > 0:
        return "refunded_partial"
    if "won" in statuses:
        return "dispute_won"
    return "paid"


def google_state(facts: Facts, row_state: str | None) -> str:
    if facts.voided:
        return "revoked" if facts.revoked else "voided"
    if row_state == "consumed":
        return "consumed"
    return "fulfilled" if row_state else "pending"


def derive_state(
    provider: str, facts: Facts, *, gross_cents: int, row_state: str | None = None
) -> str:
    return (
        stripe_state(facts, gross_cents) if provider == STRIPE else google_state(facts, row_state)
    )


@dataclass(frozen=True)
class Ledger:
    """Per-purchase + owner snapshot read under the account lock."""

    available_milli: int
    applied_milli: int  # clawed + debt opened - released (credit and debt) - forgive_close
    outstanding_debt_milli: int  # this purchase's open debt not yet settled/released/forgiven
    forgiven_milli: int = 0  # debt forgiven by an admin and not yet closed by a release


@dataclass(frozen=True)
class Plan:
    clawback: int = 0
    debt_open: int = 0
    debt_release: int = 0
    credit_release: int = 0
    forgive_close: int = 0  # released portion that was forgiven: closes it, returns no money

    @property
    def empty(self) -> bool:
        return not (
            self.clawback
            or self.debt_open
            or self.debt_release
            or self.credit_release
            or self.forgive_close
        )


def plan_adjustment(target: int, ledger: Ledger) -> Plan:
    delta = target - ledger.applied_milli
    if delta > 0:
        claw = min(max(ledger.available_milli, 0), delta)
        return Plan(clawback=claw, debt_open=delta - claw)
    if delta < 0:
        back = -delta
        debt = min(back, max(ledger.outstanding_debt_milli, 0))
        rest = back - debt
        # Only money actually taken from the wallet (clawed or paid via settlement) can return.
        money = max(
            0,
            ledger.applied_milli
            - max(ledger.outstanding_debt_milli, 0)
            - max(ledger.forgiven_milli, 0),
        )
        credit = min(rest, money)
        return Plan(debt_release=debt, credit_release=credit, forgive_close=rest - credit)
    return Plan()


def settlement_amount(debt_milli: int, available_milli: int) -> int:
    return max(0, min(debt_milli, available_milli))


# ---- provider normalization -------------------------------------------------------------


def normalize_stripe_event(
    event_type: str, event_id: str, facts: dict, created: int = 0
) -> Event | None:
    """Map a sanitized app.stripe_events row to a normalized event (None = no financial effect)."""
    ref = facts.get("payment_intent")
    if not ref:
        return None
    status = facts.get("dispute_status")
    if event_type == "charge.refunded":
        return Event(
            STRIPE,
            event_id,
            "refund",
            ref,
            facts.get("amount_refunded") or 0,
            facts.get("object_id"),
            created,
        )
    if event_type == "charge.dispute.created":
        if status is None or str(status).startswith("warning_") or status == "prevented":
            return None  # inquiry: no funds withdrawn
        return Event(
            STRIPE,
            event_id,
            "dispute_open",
            ref,
            facts.get("amount") or 0,
            facts.get("object_id"),
            created,
        )
    if event_type == "charge.dispute.closed":
        if status == "lost":
            kind = "dispute_lost"
        elif status in ("won", "warning_closed", "prevented"):
            kind = "dispute_won"
        else:
            return None
        return Event(
            STRIPE, event_id, kind, ref, facts.get("amount") or 0, facts.get("object_id"), created
        )
    return None


def normalize_google_voided(item: dict) -> Event | None:
    """Map one VoidedPurchase resource (purchases.voidedpurchases.list) to an event."""
    order = item.get("orderId")
    if not isinstance(order, str) or not order:
        return None
    try:
        voided_at = int(item.get("voidedTimeMillis") or 0)
        reason = int(item["voidedReason"]) if item.get("voidedReason") is not None else None
    except (TypeError, ValueError):
        return None
    kind = "revoked" if reason in REVOKE_REASONS else "voided"
    return Event(GOOGLE, f"void:{order}:{voided_at}", kind, order, None, None, voided_at, reason)
