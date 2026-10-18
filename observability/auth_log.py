"""SPEC-245: logs de rejeição de auth com motivo interno fechado (nunca e-mail/IP/token)."""

from __future__ import annotations

import threading
import time
from typing import Any

from observability.telemetry import log_event, pseudonym

# Catálogo fechado: motivo interno (log/métrica) != código público devolvido ao cliente.
SESSION_REASONS = frozenset({
    "missing", "expired", "bad_signature", "bad_aud_iss", "revoked", "tombstoned",
    "session_invalid", "server_misconfigured", "upstream_rejected", "unknown_kid",
    "jwks_unavailable", "bad_iss", "bad_aud", "upstream_unavailable",
})
_MESSAGE_REASONS = {
    "sessão ausente": "missing", "token ausente": "missing", "principal ausente": "missing",
    "sessão revogada": "revoked", "sessão inválida": "session_invalid",
    "token inválido": "bad_signature", "token sem subject": "bad_signature",
    "subject inválido": "bad_signature",
    "provedor de identidade indisponível": "jwks_unavailable",
    "account_deleted": "tombstoned", "account_deleted_or_invalid_blob_owner": "tombstoned",
    "auth_unavailable": "upstream_unavailable",
}
# GoTrue ``error_code`` conhecidos; qualquer outro valor vira "other" (cardinalidade fechada).
GOTRUE_CODES = frozenset({
    "invalid_credentials", "email_not_confirmed", "captcha_failed", "over_request_rate_limit",
    "over_email_send_rate_limit", "user_already_exists", "email_exists", "weak_password",
    "validation_failed", "session_not_found", "session_expired", "refresh_token_not_found",
    "refresh_token_already_used", "otp_expired", "user_not_found", "bad_jwt", "same_password",
    "signup_disabled", "email_address_invalid", "request_timeout", "unexpected_failure",
    "user_banned", "reauthentication_needed", "no_authorization", "bad_json",
})


def upstream_code(raw: str | None) -> str:
    if not raw:
        return "none"
    return raw if raw in GOTRUE_CODES else "other"


def session_reason(exc: BaseException) -> str:
    """Motivo interno fechado para um ``Unauthorized`` de sessão."""
    explicit = getattr(exc, "reason", None)
    if explicit in SESSION_REASONS:
        return explicit
    message = str(exc.args[0]) if getattr(exc, "args", None) else ""
    return _MESSAGE_REASONS.get(message, "session_invalid")


def reject(event: str, reason: str, *, level: str = "warning", **fields: Any) -> None:
    """Uma linha ``auth.<event>`` + métrica ``rpg_auth_rejections_total{reason}``. Nunca levanta."""
    try:
        from observability.metrics import metrics
        # Rótulo de métrica = só o prefixo fechado ("turnstile_error:<codes>" -> "turnstile_error");
        # os códigos do provider ficam apenas na linha de log (cardinalidade limitada).
        metrics.increment("rpg_auth_rejections_total", {"reason": str(reason).split(":", 1)[0][:40]})
        log_event("auth", event, level=level, reason=reason, **fields)
    except Exception:
        pass


def origin_host(origin: str | None, allowed: set[str] | list[str] | frozenset[str]) -> str:
    """Host da origem SOMENTE se estiver na allowlist; qualquer outra coisa vira ``other``."""
    from urllib.parse import urlsplit
    if not origin or origin not in set(allowed):
        return "other" if origin else "none"
    try:
        return (urlsplit(origin).netloc or "other")[:64]
    except ValueError:
        return "other"


# Amostragem do lockout: 1 linha por key_ref por minuto (a contagem completa fica na métrica).
_SAMPLE_WINDOW_S = 60.0
_sampled: dict[str, float] = {}
_sample_lock = threading.Lock()


def rate_limited(action: str, bucket: str, key: str, retry_after_s: int) -> None:
    try:
        key_ref = pseudonym(key)
        now = time.monotonic()
        with _sample_lock:
            if len(_sampled) > 2000:
                _sampled.clear()
            last = _sampled.get(key_ref)
            emit = last is None or now - last >= _SAMPLE_WINDOW_S
            if emit:
                _sampled[key_ref] = now
        from observability.metrics import metrics
        metrics.increment("rpg_auth_rejections_total", {"reason": "rate_limited"})
        if emit:
            log_event("auth", "rate_limited", level="warning", op=action, bucket=bucket,
                      key_ref=key_ref, retry_after_s=int(retry_after_s))
    except Exception:
        pass
