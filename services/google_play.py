"""SPEC-194 Google Play Billing: backend-only verification client and policy.

Everything the Android app sends (product id, purchase token, order id) is
untrusted. Only the Google Play Developer API response, fetched with the
service account kept in the backend environment, is evidence of a purchase.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx

API_ROOT = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"

PURCHASED, CANCELLED, PENDING = 0, 1, 2
PRODUCT_RE = re.compile(r"[a-z0-9][a-z0-9_.]{0,127}")
TOKEN_RE = re.compile(r"[A-Za-z0-9._\-]{16,2048}")
ORDER_RE = re.compile(r"[A-Za-z0-9._\-]{1,128}")


class GooglePlayError(ValueError):
    """Stable machine code in args[0]; never carries provider payloads."""

    upstream_status: int = 0     # SPEC-257 R2: HTTP status da Play API quando houver (so o numero)


def _account_key() -> bytes:
    key = os.getenv("RPG_PLAY_ACCOUNT_KEY", "")
    if len(key) < 32:
        raise GooglePlayError("google_play_unconfigured")  # fail closed: no keyless identifiers
    return key.encode()


def obfuscated_account_id(owner_id) -> str:
    """Value the app must pass to setObfuscatedAccountId at purchase time.

    HMAC-SHA256(RPG_PLAY_ACCOUNT_KEY, "rpg-play-v1:" + owner_id), hex (64 chars): not derivable from
    the owner id alone, so a client cannot mint another account's id.
    """
    return hmac.new(_account_key(), b"rpg-play-v1:" + str(owner_id).encode(), hashlib.sha256).hexdigest()


def token_digest(purchase_token: str) -> str:
    return hashlib.sha256(purchase_token.encode()).hexdigest()


@dataclass(frozen=True)
class ProductPurchase:
    """Sanitized subset of androidpublisher purchases.products resource."""
    product_id: str
    order_id: str | None
    purchase_state: int
    consumption_state: int
    acknowledgement_state: int
    quantity: int
    purchase_time_millis: int | None
    account_id: str | None
    purchase_type: int | None

    @classmethod
    def from_api(cls, data: dict) -> ProductPurchase:
        if not isinstance(data, dict) or not isinstance(data.get("productId"), str):
            raise GooglePlayError("google_play_response_invalid")

        def num(key, default=None):
            value = data.get(key, default)
            if isinstance(value, str) and value.isdigit():
                value = int(value)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, int):
                raise GooglePlayError("google_play_response_invalid")
            return value
        order, account = data.get("orderId"), data.get("obfuscatedExternalAccountId")
        return cls(data["productId"], order if isinstance(order, str) else None,
                   num("purchaseState", -1), num("consumptionState", 0),
                   num("acknowledgementState", 0), num("quantity", 1),
                   num("purchaseTimeMillis"), account if isinstance(account, str) else None,
                   num("purchaseType"))

    def snapshot(self) -> dict:
        """Sanitized state persisted for SPEC-195 reconciliation (no token/PII)."""
        return {"purchase_state": self.purchase_state, "consumption_state": self.consumption_state,
                "acknowledgement_state": self.acknowledgement_state, "quantity": self.quantity,
                "purchase_type": self.purchase_type}


@dataclass(frozen=True)
class GooglePlaySettings:
    package_name: str
    service_account: dict

    @classmethod
    def from_env(cls) -> GooglePlaySettings:
        package = os.getenv("GOOGLE_PLAY_PACKAGE_NAME", "")
        raw = os.getenv("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "").strip()
        try:
            if raw and not raw.startswith("{"):
                raw = Path(raw).read_text(encoding="utf-8")
            account = json.loads(raw)
            if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+", package)
                    or not isinstance(account, dict) or not account.get("private_key")
                    or not account.get("client_email")):
                raise ValueError
        except (OSError, ValueError, TypeError) as exc:
            raise GooglePlayError("google_play_unconfigured") from exc
        return cls(package, account)


_shared: tuple[tuple, GooglePlayClient] | None = None
_shared_lock = threading.Lock()


def shared_client() -> GooglePlayClient:
    """Per-process client (keeps the OAuth bearer between requests). Rebuilt if the env changes."""
    global _shared
    key = (os.getenv("GOOGLE_PLAY_PACKAGE_NAME", ""), os.getenv("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", ""))
    with _shared_lock:
        if _shared is None or _shared[0] != key:
            _shared = (key, GooglePlayClient(GooglePlaySettings.from_env()))
        return _shared[1]


class GooglePlayClient:
    """Minimal androidpublisher v3 client. Transport is injectable for tests."""

    def __init__(self, settings: GooglePlaySettings, *, transport=None, clock=time.time) -> None:
        self.settings, self.transport, self.clock = settings, transport, clock
        self._bearer: tuple[str, float] | None = None
        self._bearer_lock = threading.Lock()

    def _assertion(self) -> str:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        def b64(raw: bytes) -> bytes:
            return base64.urlsafe_b64encode(raw).rstrip(b"=")
        now = int(self.clock())
        claims = {"iss": self.settings.service_account["client_email"], "scope": SCOPE,
                  "aud": TOKEN_URL, "iat": now, "exp": now + 3600}
        signing = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()) + b"." + \
            b64(json.dumps(claims, separators=(",", ":")).encode())
        key = serialization.load_pem_private_key(
            self.settings.service_account["private_key"].encode(), password=None)
        return (signing + b"." + b64(key.sign(signing, padding.PKCS1v15(), hashes.SHA256()))).decode()

    def _headers(self, client: httpx.Client) -> dict:
        with self._bearer_lock:  # one token refresh at a time; reused until expiry-60s
            if self._bearer is None or self._bearer[1] <= self.clock() + 60:
                response = client.post(TOKEN_URL, data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": self._assertion()})
                response.raise_for_status()
                body = response.json()
                self._bearer = (body["access_token"], self.clock() + int(body.get("expires_in", 3000)))
            return {"Authorization": "Bearer " + self._bearer[0]}

    def _call(self, method: str, product_id: str, token: str, suffix: str = "", *, body=None):
        url = (f"{API_ROOT}/{quote(self.settings.package_name, safe='')}/purchases/products/"
               f"{quote(product_id, safe='')}/tokens/{quote(token, safe='')}{suffix}")
        try:
            with httpx.Client(transport=self.transport, timeout=15, follow_redirects=False) as client:
                response = client.request(method, url, headers=self._headers(client), json=body)
                if response.status_code in (400, 404, 410):
                    err = GooglePlayError("google_play_purchase_not_found")
                    err.upstream_status = int(response.status_code)
                    raise err
                response.raise_for_status()
                return response.json() if response.content else {}
        except GooglePlayError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError) as exc:
            # Includes signing failures; key material never enters the message.
            err = GooglePlayError("google_play_unavailable")
            status = getattr(getattr(exc, "response", None), "status_code", 0)
            err.upstream_status = int(status) if isinstance(status, int) else 0
            raise err from exc

    def get_purchase(self, product_id: str, token: str) -> ProductPurchase:
        return ProductPurchase.from_api(self._call("GET", product_id, token))

    def consume(self, product_id: str, token: str) -> None:
        self._call("POST", product_id, token, ":consume")

    def acknowledge(self, product_id: str, token: str) -> None:
        self._call("POST", product_id, token, ":acknowledge", body={})

    def list_voided_events(self, start_ms: int | None = None, end_ms: int | None = None,
                           *, max_pages: int = 5, page_size: int = 1000):
        """purchases.voidedpurchases.list -> normalized SPEC-195 events.

        GET .../applications/{package}/purchases/voidedpurchases. startTime cannot be older than
        30 days (Google); the poll window therefore defaults to the last 30 days and pages by
        tokenPagination.nextPageToken, sent back as the `token` query parameter with `maxResults`
        (the REST reference lists them as pageSelection.*; the wire names are the bare ones).
        type=0 (in-app only) is the default; consumables only.
        """
        from services.purchase_reconciliation import normalize_google_voided
        now_ms = int(self.clock() * 1000)
        end_ms = min(end_ms or now_ms, now_ms)
        start_ms = max(start_ms or 0, end_ms - 30 * 86400 * 1000 + 60_000)
        url = f"{API_ROOT}/{quote(self.settings.package_name, safe='')}/purchases/voidedpurchases"
        params: dict = {"startTime": start_ms, "endTime": end_ms, "type": 0,
                        "maxResults": page_size}
        events = []
        self.last_poll_complete = False  # True only when pagination ended before max_pages ran out
        try:
            with httpx.Client(transport=self.transport, timeout=15, follow_redirects=False) as client:
                for _ in range(max_pages):
                    response = client.get(url, headers=self._headers(client), params=params)
                    response.raise_for_status()
                    body = response.json()
                    for item in body.get("voidedPurchases", []) or []:
                        event = normalize_google_voided(item) if isinstance(item, dict) else None
                        if event is not None:
                            events.append(event)
                    token = (body.get("tokenPagination") or {}).get("nextPageToken")
                    if not token:
                        self.last_poll_complete = True
                        break
                    params = {**params, "token": token}
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError) as exc:
            raise GooglePlayError("google_play_unavailable") from exc
        return events
