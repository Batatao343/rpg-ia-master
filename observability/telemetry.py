"""Correlação, pseudonimização e redaction sem dependência obrigatória."""

from __future__ import annotations

import contextvars
import hashlib
import hmac
import json
import logging
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


_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING,
           "error": logging.ERROR}


def log_event(area: str, event: str, *, level: str = "info", **fields: Any) -> None:
    """SPEC-222 R1: log técnico estruturado de produção (substitui ``print``).

    Campos devem ser contagens, ids de catálogo, nomes de classe de exceção ou
    pseudônimos — nunca texto do jogador, narração ou nome de personagem. Ainda
    assim passam por ``safe_json``/``redact``.
    """
    logging.getLogger(f"rpg.{area}").log(
        _LEVELS.get(level, logging.INFO),
        # SPEC-240 R1: correlacao automatica; campos explicitos do chamador vencem.
        safe_json({**correlation(), "event": f"{area}.{event}", **fields}))


_PROVIDER_CAPABILITIES = {"stt", "image", "embedding"}
_PROVIDER_OUTCOMES = {"success", "http_error", "timeout", "transport_error", "invalid_response",
                      "refused", "circuit_open", "kill_switch"}
_COST_BASES = {"exact", "estimated", "unknown"}


def log_provider_attempt(capability: str, provider: str, model: str, outcome: str, *,
                         http_status: int | None = None, latency_ms: float | None = None,
                         attempt: int = 1, fell_back: bool = False,
                         cost_basis: str = "unknown") -> None:
    """SPEC-258 R1/R2: ``provider.attempt`` (debug no sucesso, warning na falha) + metricas
    ``rpg_provider_*``. Todos os campos sao de conjunto fechado/numericos; nunca conteudo
    (audio, prompt, texto embeddado, URL, corpo de resposta). Nunca levanta."""
    try:
        from observability.metrics import metrics

        capability = capability if capability in _PROVIDER_CAPABILITIES else "other"
        outcome = outcome if outcome in _PROVIDER_OUTCOMES else "transport_error"
        cost_basis = cost_basis if cost_basis in _COST_BASES else "unknown"
        status = http_status if isinstance(http_status, int) and not isinstance(http_status, bool) else None
        metrics.increment("rpg_provider_attempts_total",
                          {"capability": capability, "provider": provider, "outcome": outcome})
        if latency_ms is not None:
            metrics.observe("rpg_provider_duration_seconds",
                            {"capability": capability, "provider": provider}, latency_ms / 1000.0)
        log_event("provider", "attempt", level="debug" if outcome == "success" else "warning",
                  capability=capability, provider=provider, model=model, outcome=outcome,
                  http_status=status,
                  latency_ms=round(latency_ms, 1) if latency_ms is not None else None,
                  attempt=attempt, fell_back=bool(fell_back), cost_basis=cost_basis)
    except Exception:  # silent-ok: telemetria de provider nunca derruba a chamada
        pass


class _FallbackBucket(list):
    """Fallbacks do turno (``node.reason``, com repeticao) + chaves ja logadas neste turno."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: set[tuple[str, str]] = set()


_fallbacks: contextvars.ContextVar[_FallbackBucket | None] = contextvars.ContextVar(
    "rpg_turn_fallbacks", default=None)


def begin_fallbacks() -> tuple[contextvars.Token, list[str]]:
    """SPEC-250 R5: coleta ``node.reason`` dos fallbacks do turno (contado em ``rpg.turn``)."""
    bucket = _FallbackBucket()
    return _fallbacks.set(bucket), bucket


def end_fallbacks(token: contextvars.Token) -> None:
    _fallbacks.reset(token)


def log_fallback(node: str, reason: str, exc: BaseException | None = None, **fields: Any) -> None:
    """SPEC-250 R1: degradacao graciosa visivel. ``<node>.fallback`` (warning) com ``reason`` (codigo
    fechado) e ``error_type`` (so a classe, nunca a mensagem). Dentro de um turno, a linha sai 1x por
    (no, motivo); a contagem completa vai em ``rpg.turn.fallbacks``."""
    try:
        bucket = _fallbacks.get()
        if bucket is not None:
            bucket.append(f"{node}.{reason}")
            if (node, reason) in bucket.seen:
                return
            bucket.seen.add((node, reason))
        extra = {"error_type": type(exc).__name__} if exc is not None else {}
        log_event(node, "fallback", level="warning", reason=reason, **extra, **fields)
    except Exception:  # silent-ok: o log de fallback nunca derruba o turno
        pass


def safe_stack(exc: BaseException, limit: int = 5) -> list[str]:
    """``modulo:linha`` dos ``limit`` frames mais internos do codigo do projeto.

    Nunca inclui a mensagem da excecao, linhas de codigo ou valores locais."""
    import traceback
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    frames: list[str] = []
    try:
        for frame in traceback.extract_tb(exc.__traceback__):
            try:
                rel = Path(frame.filename).resolve().relative_to(root)
            except (ValueError, OSError):
                continue
            if rel.parts and rel.parts[0] in {".venv", "node_modules", "site-packages"}:
                continue
            frames.append(f"{rel.as_posix()}:{frame.lineno}")
    except Exception:
        return []
    return frames[-limit:][::-1]


def correlation() -> dict[str, str]:
    return dict(_correlation.get())


def _merge_correlation(current: dict[str, str], values: Mapping[str, object]) -> None:
    for key, value in values.items():
        if value is None:
            continue
        if key in {"owner_id", "game_id"}:
            ref = pseudonym(value)
            current[f"{key}_ref"] = ref                       # nome legado (1 release)
            current[f"{key[:-3]}_ref"] = ref                  # owner_ref / game_ref
        elif key == "action_id":
            current["action_ref"] = pseudonym(value)          # id cru nunca entra
        else:
            current[key] = str(value)[:128]


@contextmanager
def correlation_scope(**values: object) -> Iterator[dict[str, str]]:
    current = correlation()
    _merge_correlation(current, values)
    token = _correlation.set(current)
    try:
        yield current
    finally:
        _correlation.reset(token)


_node: contextvars.ContextVar[str] = contextvars.ContextVar("rpg_graph_node", default="")


def current_node() -> str:
    """SPEC-248: no do grafo em execucao (para atribuir chamadas LLM a um no)."""
    return _node.get()


@contextmanager
def node_scope(name: str) -> Iterator[None]:
    token = _node.set(str(name)[:40])
    try:
        yield
    finally:
        _node.reset(token)


def with_node(name: str, fn):
    """Embrulha um no do grafo para que ``current_node()`` valha durante sua execucao."""
    import functools

    @functools.wraps(fn)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        with node_scope(name):
            return fn(*args, **kwargs)
    return _wrapped


@contextmanager
def request_scope(request_id: str) -> Iterator[dict[str, str]]:
    """Raiz de uma requisicao: parte de um contexto LIMPO (nao herda game/action de fora)."""
    token = _correlation.set({"request_id": str(request_id)[:128]})
    try:
        yield correlation()
    finally:
        _correlation.reset(token)


def bind_correlation(**values: object) -> None:
    """Acrescenta campos ao contexto ATUAL sem escopo (vale ate o fim desta tarefa/thread).

    Usado no inicio dos handlers sincronos (rodam em contexto proprio por request)."""
    current = correlation()
    _merge_correlation(current, values)
    _correlation.set(current)


def contextualize(fn):
    """Captura o contexto de correlacao agora e o aplica quando ``fn`` rodar em outra thread
    (``Thread(target=contextualize(f))``, ``pool.submit(contextualize(f))``, callbacks)."""
    ctx = contextvars.copy_context()

    def _runner(*args: Any, **kwargs: Any) -> Any:
        return ctx.copy().run(fn, *args, **kwargs)

    return _runner


def run_with_context(fn, *args: Any, **kwargs: Any) -> Any:
    """Executa ``fn`` ja em uma copia do contexto atual (equivale a ``contextualize(fn)(...)``)."""
    return contextualize(fn)(*args, **kwargs)


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
