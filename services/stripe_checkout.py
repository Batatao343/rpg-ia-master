"""SPEC-189 raw signature boundary and narrowly scoped Stripe test-mode adapter."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

MAX_WEBHOOK_BYTES = 256 * 1024


class StripeError(ValueError):
    pass


class OpenOrdersLimit(StripeError):
    """SPEC-219 R2: ordens abertas demais para o owner (nao e falha do provedor)."""


def verify_event(body: bytes, signature: str, secret: str, *, now: int | None = None) -> dict:
    """Authenticate exact bytes and timestamp before decoding any JSON fields."""
    if len(body) > MAX_WEBHOOK_BYTES or not secret.startswith("whsec_"):
        raise StripeError("stripe_signature_invalid")
    try:
        parts = [item.split("=", 1) for item in signature.split(",")]
        timestamps = [value for key, value in parts if key == "t"]
        hashes = [value for key, value in parts if key == "v1"]
        if len(timestamps) != 1:
            raise ValueError
        timestamp = int(timestamps[0])
        if abs((int(time.time()) if now is None else now) - timestamp) > 300:
            raise ValueError
        digest = hmac.new(secret.encode(), timestamps[0].encode() + b"." + body, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(digest, value) for value in hashes):
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise StripeError("stripe_signature_invalid") from exc
    try:
        event = json.loads(body)
        if (not isinstance(event, dict) or event.get("livemode") is not False
                or not isinstance(event.get("id"), str) or not event["id"].startswith("evt_")
                or len(event["id"]) > 160 or not isinstance(event.get("type"), str)
                or not 1 <= len(event["type"]) <= 150
                or not isinstance(event.get("created"), int) or isinstance(event.get("created"), bool)
                or event["created"] < 0 or not isinstance(event.get("data", {}).get("object"), dict)
                or event["data"]["object"].get("livemode") is True):
            raise StripeError("stripe_event_invalid_or_live")
        return event
    except (ValueError, AttributeError, TypeError, RecursionError) as exc:
        raise StripeError("stripe_event_invalid_or_live") from exc


@dataclass(frozen=True)
class StripeSettings:
    secret_key: str
    webhook_secret: str
    origin: str
    allowed_skus: tuple[str, ...]

    @staticmethod
    def _valid_origin(origin: str) -> bool:
        parsed = urlsplit(origin)
        return (parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username
                and not parsed.password and not parsed.path and not parsed.query and not parsed.fragment)

    @classmethod
    def for_cleanup(cls) -> StripeSettings:
        """Close old sessions even when new checkout sales are disabled."""
        key = os.getenv("STRIPE_SECRET_KEY", "")
        origin = os.getenv("RPG_CHECKOUT_ORIGIN", "").rstrip("/")
        try:
            valid = cls._valid_origin(origin)
        except ValueError:
            valid = False
        if not key.startswith("sk_test_") or not valid:
            raise StripeError("stripe_cleanup_unconfigured")
        return cls(key, "", origin, ())

    @classmethod
    def for_reconciliation(cls) -> StripeSettings:
        """Accept signed late webhooks after the sales kill switch is off."""
        key = os.getenv("STRIPE_SECRET_KEY", "")
        secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        if not key.startswith("sk_test_") or not secret.startswith("whsec_"):
            raise StripeError("stripe_reconciliation_unconfigured")
        return cls(key, secret, "", ())

    @classmethod
    def from_env(cls) -> StripeSettings:
        try:
            key, secret = os.getenv("STRIPE_SECRET_KEY", ""), os.getenv("STRIPE_WEBHOOK_SECRET", "")
            origin = os.getenv("RPG_CHECKOUT_ORIGIN", "").rstrip("/")
            skus = json.loads(os.getenv("RPG_STRIPE_ALLOWED_SKUS", "[]"))
            if (os.getenv("RPG_STRIPE_ENABLED", "0") != "1" or not key.startswith("sk_test_")
                    or not secret.startswith("whsec_") or not cls._valid_origin(origin)
                    or not isinstance(skus, list) or not skus
                    or any(not isinstance(s, str) or not 0 < len(s) <= 120 for s in skus)):
                raise ValueError
            return cls(key, secret, origin, tuple(skus))
        except (ValueError, TypeError) as exc:
            raise StripeError("stripe_disabled_or_unconfigured_test_mode") from exc


class StripeTestAdapter:
    def __init__(self, secret_key: str, *, transport=None) -> None:
        if not secret_key.startswith("sk_test_"):
            raise StripeError("stripe_test_key_required")
        self.secret_key, self.transport = secret_key, transport

    def _request(self, method: str, path: str, *, data=None, key: str | None = None) -> dict:
        headers = {"Authorization": "Bearer " + self.secret_key}
        if key:
            headers["Idempotency-Key"] = key
        try:
            with httpx.Client(transport=self.transport, timeout=15, follow_redirects=False) as client:
                response = client.request(method, "https://api.stripe.com/v1/" + path,
                                          data=data, headers=headers)
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict) or result.get("livemode") is True:
                    raise StripeError("stripe_live_response_rejected")
                return result
        except (httpx.HTTPError, ValueError) as exc:
            raise StripeError("stripe_provider_unavailable") from exc

    def create_session(self, order_id: str, *, amount_cents: int,
                       success_url: str, cancel_url: str) -> dict:
        result = self._request("POST", "checkout/sessions", key="checkout:" + order_id, data={
            "mode": "payment", "success_url": success_url, "cancel_url": cancel_url,
            "metadata[order_id]": order_id, "payment_intent_data[metadata][order_id]": order_id,
            "line_items[0][price_data][currency]": "brl",
            "line_items[0][price_data][unit_amount]": str(amount_cents),
            "line_items[0][price_data][product_data][name]": "Estilhas",
            "line_items[0][quantity]": "1",
        })
        if (result.get("livemode") is not False or not str(result.get("id", "")).startswith("cs_test_")
                or not checkout_url_valid(result.get("url"))):
            raise StripeError("stripe_session_invalid")
        return result

    def expire_session(self, session_id: str) -> str:
        """Close an open test Checkout session; report already closed sessions."""
        if not re.fullmatch(r"cs_test_[A-Za-z0-9_-]{1,150}", session_id):
            raise StripeError("stripe_session_invalid")
        try:
            result = self._request("POST", f"checkout/sessions/{session_id}/expire")
        except StripeError:
            # Stripe rejects expiration once a session completes or expires.
            # A read also distinguishes that state from a transient API failure.
            result = self._request("GET", f"checkout/sessions/{session_id}")
        if result.get("id") != session_id or result.get("livemode") is not False:
            raise StripeError("stripe_session_invalid")
        status = result.get("status")
        if status not in {"expired", "complete"}:
            raise StripeError("stripe_session_not_closed")
        return status

    def payment_economics(self, payment_intent: str) -> dict | None:
        """Resolve the actual balance transaction, never fees from a customer payload."""
        if not re.fullmatch(r"pi_[A-Za-z0-9_-]{1,150}", payment_intent):
            raise StripeError("stripe_intent_invalid")
        intent = self._request("GET", "payment_intents/" + payment_intent + "?expand[]=latest_charge.balance_transaction")
        if intent.get("id") != payment_intent or intent.get("livemode") is not False:
            raise StripeError("stripe_intent_invalid")
        charge = intent.get("latest_charge")
        balance = charge.get("balance_transaction") if isinstance(charge, dict) else None
        if not isinstance(balance, dict) or charge.get("payment_intent") != payment_intent:
            return None
        if (balance.get("currency") != "brl" or not isinstance(balance.get("fee"), int)
                or isinstance(balance["fee"], bool) or balance["fee"] < 0
                or not str(balance.get("id", "")).startswith("txn_")):
            return None
        return {"balance_transaction_id": balance["id"], "fee_cents": balance["fee"],
                "currency": "brl"}


def checkout_url_valid(url) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname == "checkout.stripe.com"
                and not parsed.username and not parsed.password and parsed.port in (None, 443))
    except ValueError:
        return False
