"""Correlação, pseudonimização e redaction sem dependência obrigatória."""

from __future__ import annotations

import contextvars
import hashlib
import hmac
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Mapping
from uuid import uuid4


_correlation: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar(
    "rpg_correlation", default={},
)
_SENSITIVE_KEYS = {
    "authorization", "cookie", "set-cookie", "access_token", "refresh_token",
    "jwt", "password", "email", "prompt", "input_text", "action", "narrative",
    "state", "save", "signed_url", "url", "private_brief", "payload",
}
_TOKEN_RE = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+")
_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_SIGNED_RE = re.compile(r"https?://\S+(?:token|signature|sig|expires)=\S+", re.I)
_otel_tracer: Any = None
_otel_initialized = False


def _native_tracer() -> Any:
    """Inicializa OTLP/HTTP somente quando endpoint e extra existem."""
    global _otel_initialized, _otel_tracer
    if _otel_initialized:
        return _otel_tracer
    _otel_initialized = True
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if not endpoint:
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({
            "service.name": os.getenv("OTEL_SERVICE_NAME", "valoria-api")[:100],
        }))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        _otel_tracer = trace.get_tracer("valoria")
    except Exception:
        _otel_tracer = None
    return _otel_tracer


def new_request_id(value: str | None = None) -> str:
    candidate = str(value or "").strip()
    return candidate[:64] if re.fullmatch(r"[A-Za-z0-9._:-]{8,64}", candidate) else uuid4().hex


def pseudonym(value: object, *, secret: str | None = None) -> str:
    key = (secret or os.getenv("RPG_TELEMETRY_SECRET") or "local-telemetry-only").encode()
    return hmac.new(key, str(value).encode(), hashlib.sha256).hexdigest()[:16]


def redact(value: Any, *, key: str = "") -> Any:
    if key.casefold() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        cleaned = _TOKEN_RE.sub("Bearer [REDACTED]", value)
        cleaned = _EMAIL_RE.sub("[EMAIL]", cleaned)
        cleaned = _SIGNED_RE.sub("[SIGNED_URL]", cleaned)
        return cleaned[:2000]
    return value


def safe_json(event: Mapping[str, Any]) -> str:
    return json.dumps(redact(event), ensure_ascii=False, sort_keys=True, default=str)


def correlation() -> dict[str, str]:
    return dict(_correlation.get())


@contextmanager
def correlation_scope(**values: object) -> Iterator[dict[str, str]]:
    current = correlation()
    for key, value in values.items():
        if value is None:
            continue
        if key in {"owner_id", "game_id"}:
            current[f"{key}_ref"] = pseudonym(value)
        else:
            current[key] = str(value)[:128]
    token = _correlation.set(current)
    try:
        yield current
    finally:
        _correlation.reset(token)


@dataclass
class Span:
    name: str
    attributes: dict[str, Any]

    def set_attribute(self, key: str, value: Any) -> None:
        if key.casefold() not in _SENSITIVE_KEYS:
            self.attributes[key] = redact(value, key=key)

    def record_exception(self, exception: BaseException) -> None:
        self.attributes["exception.type"] = type(exception).__name__


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Span]:
    """Span seguro; o exporter opcional nunca derruba o domínio."""
    safe_attributes = redact({**correlation(), **attributes})
    current = Span(name, safe_attributes)
    tracer = _native_tracer()
    native_context = tracer.start_as_current_span(name) if tracer else None
    native = native_context.__enter__() if native_context else None
    try:
        if native:
            for key, value in safe_attributes.items():
                native.set_attribute(str(key), str(value)[:256])
        yield current
    except BaseException as exc:
        current.record_exception(exc)
        if native:
            native.record_exception(exc)
        raise
    finally:
        if native_context:
            native_context.__exit__(None, None, None)
