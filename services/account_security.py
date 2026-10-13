"""SPEC-190: server signed recency/deletion proofs and auth abuse controls."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from infrastructure.contracts import Unauthorized

RECENT_COOKIE = "rpg_recent"
DELETE_COOKIE = "rpg_deletion"
GENERIC_MESSAGE = "Se o endereço puder receber mensagens, enviaremos as instruções."


def proof(owner: UUID, purpose: str, binding: str = "", *, now: int | None = None) -> str:
    secret = os.getenv("RPG_SESSION_SECRET", "")
    if len(secret) < 32:
        raise ValueError("session_secret_required")
    payload = f"{owner}:{purpose}:{int(time.time()) if now is None else now}:{hashlib.sha256(binding.encode()).hexdigest()}"
    return payload + ":" + hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def proof_owner(value: str | None, purpose: str, binding: str = "", *, max_age: int = 300) -> UUID:
    try:
        owner, actual, at, digest, signature = (value or "").split(":")
        expected = proof(UUID(owner), actual, binding, now=int(at))
        if (actual != purpose or not hmac.compare_digest(expected, value)
                or not 0 <= time.time() - int(at) <= max_age):
            raise ValueError
        return UUID(owner)
    except (ValueError, TypeError):
        raise Unauthorized("recent_session_required") from None


def captcha_config() -> dict:
    mode = os.getenv("RPG_AUTH_CAPTCHA_MODE", "app").strip().lower()
    return {"provider": "turnstile", "required": os.getenv("RPG_AUTH_CAPTCHA_REQUIRED", "0") == "1",
            "site_key": os.getenv("RPG_TURNSTILE_SITE_KEY", "").strip() or None,
            "mode": mode}


def validate_captcha(token: str | None, *, remote_ip: str, action: str) -> None:
    config = captcha_config()
    mode = config["mode"]
    if mode not in {"app", "gotrue"}:
        raise ValueError("captcha_unavailable")
    if mode == "gotrue":
        # GoTrue is publicly reachable with the publishable key. Its native
        # Turnstile verifier must consume this single-use token; the proxy only
        # enforces presence/configuration and forwards it unchanged.
        if not config["required"] or not config["site_key"]:
            raise ValueError("captcha_unavailable")
        if not token:
            raise Unauthorized("captcha_required")
        return
    if not config["required"]:
        return
    secret = os.getenv("RPG_TURNSTILE_SECRET", "").strip()
    if not secret or not config["site_key"]:
        raise ValueError("captcha_unavailable")
    if not token:
        raise Unauthorized("captcha_required")
    try:
        response = httpx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",
                              data={"secret": secret, "response": token, "remoteip": remote_ip}, timeout=5)
        result = response.json() if response.status_code == 200 else {}
        hosts = {urlsplit(origin.strip()).hostname for origin in os.getenv(
            "RPG_CORS_ORIGINS", "http://localhost:8000,http://localhost:5173").split(",")}
        if (not result.get("success") or result.get("hostname") not in hosts
                or result.get("action") != action):
            raise Unauthorized("captcha_invalid")
    except (httpx.HTTPError, ValueError):
        raise Unauthorized("captcha_invalid") from None


def auth_limit(runtime, request, *, action: str, email: str = "") -> None:
    """Independent IP and normalized-address buckets, including absent addresses."""
    remote = request.client.host if request.client else "unknown"
    for scope, value, limit in (("ip", remote, 20), ("email", email.strip().casefold(), 5)):
        if not value:
            continue
        key = hashlib.sha256(value.encode()).hexdigest()
        decision = runtime.rate_limiter.consume(f"auth:{action}:{scope}:{key}", limit=limit, window_seconds=900)
        if not decision.allowed:
            from fastapi import HTTPException
            raise HTTPException(429, "auth_rate_limit", headers={"Retry-After": str(decision.retry_after_seconds)})


def auth_email_bucket_keys(email: str) -> tuple[str, ...]:
    """The only address-derived buckets; remove them on account erasure."""
    digest = hashlib.sha256(email.strip().casefold().encode()).hexdigest()
    return tuple(f"auth:{action}:email:{digest}" for action in ("login", "signup", "reset", "verify"))
