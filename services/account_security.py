"""SPEC-190: server signed recency/deletion proofs and auth abuse controls."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from infrastructure.contracts import SessionSecretError, Unauthorized

RECENT_COOKIE = "rpg_recent"
DELETE_COOKIE = "rpg_deletion"
GENERIC_MESSAGE = "Se o endereço puder receber mensagens, enviaremos as instruções."


def proof(owner: UUID, purpose: str, binding: str = "", *, now: int | None = None) -> str:
    secret = os.getenv("RPG_SESSION_SECRET", "")
    if len(secret) < 32:
        raise SessionSecretError("session_secret_required")
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


# SPEC-220 R4 / D-C: limites por e-mail.
LOGIN_EMAIL_FAILURES = (10, 900)        # só falhas de credencial, chave (e-mail, IP); sucesso zera
EMAIL_IP_ATTEMPTS = (5, 900)            # signup/reset/verify: chave (e-mail, IP)
EMAIL_ONLY_ATTEMPTS = (20, 3600)        # folgado, contra e-mail bombing de IPs distintos
IP_ATTEMPTS = (20, 900)
EMAIL_ACTIONS = ("login", "signup", "reset", "verify")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _normal(email: str) -> str:
    return email.strip().casefold()


def _too_many(decision) -> None:
    if not decision.allowed:
        from fastapi import HTTPException
        raise HTTPException(429, "auth_rate_limit", headers={"Retry-After": str(decision.retry_after_seconds)})


def _remote(request) -> str:
    return request.client.host if request and request.client else "unknown"


def _login_failure_key(email: str, remote: str) -> str:
    # Revisão Sol: chave (e-mail, IP) — falhas de um atacante não trancam a vítima
    # em outro IP; o bucket por IP (20/15 min) segue limitando força bruta distribuída.
    return f"auth:login:emailip:{_digest(_normal(email))}:{_digest(remote)}"


def auth_limit(runtime, request, *, action: str, email: str = "", stage: str = "attempt") -> None:
    """IP bucket per attempt; address buckets per SPEC-220 R4.

    login: the (address, IP) bucket counts only credential failures (``stage="failure"``)
    and is merely inspected on each attempt, so a correct login is never consumed.
    signup/reset/verify: per-attempt (address, IP) bucket + a looser address-only one.
    """
    remote = _remote(request)
    address = _normal(email)
    limiter = runtime.rate_limiter
    if stage == "failure":
        if action == "login" and address:
            _too_many(limiter.consume(_login_failure_key(address, remote), limit=LOGIN_EMAIL_FAILURES[0],
                                      window_seconds=LOGIN_EMAIL_FAILURES[1]))
        return
    _too_many(limiter.consume(f"auth:{action}:ip:{_digest(remote)}", limit=IP_ATTEMPTS[0],
                              window_seconds=IP_ATTEMPTS[1]))
    if not address:
        return
    if action == "login":
        peek = getattr(limiter, "peek", None)
        if peek is not None:
            _too_many(peek(_login_failure_key(address, remote), limit=LOGIN_EMAIL_FAILURES[0],
                           window_seconds=LOGIN_EMAIL_FAILURES[1]))
        return
    digest = _digest(address)
    _too_many(limiter.consume(f"auth:{action}:emailip:{digest}:{_digest(remote)}",
                              limit=EMAIL_IP_ATTEMPTS[0], window_seconds=EMAIL_IP_ATTEMPTS[1]))
    _too_many(limiter.consume(f"auth:{action}:email:{digest}", limit=EMAIL_ONLY_ATTEMPTS[0],
                              window_seconds=EMAIL_ONLY_ATTEMPTS[1]))


def auth_success(runtime, *, action: str, email: str, request=None) -> None:
    """A correct login clears the (address, IP) failure counter (SPEC-220 R4)."""
    reset = getattr(runtime.rate_limiter, "reset", None)
    if action == "login" and _normal(email) and reset is not None:
        reset(_login_failure_key(email, _remote(request)))


def auth_email_bucket_keys(email: str) -> tuple[str, ...]:
    """Exact address-derived buckets; remove them on account erasure."""
    digest = _digest(_normal(email))
    return tuple(f"auth:{action}:email:{digest}" for action in EMAIL_ACTIONS)


def auth_email_bucket_prefixes(email: str) -> tuple[str, ...]:
    """Prefixes of the (address, IP) buckets; erasure deletes by prefix."""
    digest = _digest(_normal(email))
    return tuple(f"auth:{action}:emailip:{digest}:" for action in EMAIL_ACTIONS)
