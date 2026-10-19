"""SPEC-257: logs de pagamento (Stripe, Google Play, carteira) com codigos fechados e pseudonimos.

Nunca registra ``purchase_token``, ``client_secret``, e-mail do pagador, valores de cartao nem
corpo de resposta de provider. Nunca levanta: observabilidade nao pode alterar o fluxo financeiro.
"""

from __future__ import annotations

import re
import time
from typing import Any

from observability.telemetry import log_event, pseudonym

_CODE = re.compile(r"^[a-z][a-z0-9_.]{0,59}$")
_PRODUCT = re.compile(r"^[a-z0-9][a-z0-9_.]{0,127}$")


def _code(value: Any) -> str:
    text = str(value or "")
    return text if _CODE.match(text) else "other"


def _count(provider: str, outcome: str) -> None:
    from observability.metrics import metrics

    metrics.increment("rpg_payment_verifications_total", {"provider": provider, "outcome": outcome})


def stripe_webhook(
    outcome: str,
    started: float,
    *,
    event: dict | None = None,
    apply_result: str | None = None,
    error_code: str | None = None,
) -> None:
    """``payments.stripe_webhook``: 1 linha por entrega, com ``outcome`` fechado."""
    try:
        event_type = str((event or {}).get("type") or "")[:60] or None
        if outcome in {"applied", "duplicate"} and event is not None:
            from infrastructure.stripe_payments import FINANCIAL_EVENTS, PAID_EVENTS

            if event_type not in PAID_EVENTS and event_type not in FINANCIAL_EVENTS:
                outcome = "ignored_type"
        level = "info" if outcome in {"applied", "duplicate", "ignored_type"} else "warning"
        log_event(
            "payments",
            "stripe_webhook",
            level=level,
            outcome=outcome,
            event_type=event_type,
            event_ref=pseudonym(event["id"]) if event and event.get("id") else None,
            apply_result=apply_result,
            error_code=_code(error_code) if error_code else None,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        _count("stripe", outcome)
    except Exception:  # silent-ok: o log nunca altera a resposta ao Stripe
        pass


def google_verify(
    outcome: str, body: Any, started: float, *, upstream_status: int = 0, level: str = "info"
) -> None:
    """``payments.google_verify``: ``outcome`` = codigo de ``GooglePlayError`` ou credited/pending."""
    try:
        product = str(getattr(body, "product_id", "") or "")
        order_id = getattr(body, "order_id", None)
        outcome = _code(outcome)
        log_event(
            "payments",
            "google_verify",
            level=level,
            outcome=outcome,
            product_id=product if _PRODUCT.match(product) else None,
            order_ref=pseudonym(order_id) if order_id else None,
            upstream_status=int(upstream_status or 0),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        _count("google_play", outcome)
    except Exception:  # silent-ok: o log nunca altera a resposta de compra
        pass


def checkout_failed(stage: str, exc: BaseException) -> None:
    """``payments.checkout_failed`` (error): estagio + classe + codigo do StripeError."""
    try:
        code = exc.args[0] if getattr(exc, "args", None) else ""
        log_event(
            "payments",
            "checkout_failed",
            level="error",
            stage=_code(stage),
            error_type=type(exc).__name__,
            error_code=_code(code) if code else None,
        )
    except Exception:  # silent-ok: o log nunca altera a resposta
        pass


def fee_reconcile_failed(stage: str, exc: BaseException) -> None:
    """``payments.fee_reconcile_failed`` (warning): codigo do erro so se for snake_case fechado."""
    try:
        code = exc.args[0] if getattr(exc, "args", None) else ""
        log_event(
            "payments",
            "fee_reconcile_failed",
            level="warning",
            stage=_code(stage),
            error_type=type(exc).__name__,
            error_code=_code(code) if code else None,
        )
    except Exception:  # silent-ok: o log nunca altera a conciliacao
        pass


def wallet_event(event: str, reservation_id: Any, exc: BaseException, *, stage: str) -> None:
    """``wallet.settle_failed|recovery_item_failed|reservation_uncertain`` (warning)."""
    try:
        log_event(
            "wallet",
            event,
            level="warning",
            op_ref=pseudonym(reservation_id),
            stage=_code(stage),
            error_type=type(exc).__name__,
        )
    except Exception:  # silent-ok: o log nunca altera a conciliacao
        pass
