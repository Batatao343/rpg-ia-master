"""Roteamento multi-provider com fallback (spec roteamento-multi-provider).

`get_llm(temperature, tier)` devolve um `RoutedLLM` que embrulha uma LISTA
ordenada de candidatos `(provider, modelo)` do tier. No `.invoke()`/`.stream()`
tenta o preferido; qualquer falha (429/500/timeout/dep faltando/sem key) cai para
o próximo candidato; esgotou todos → `AIMessage` de erro (NUNCA levanta).

Convenção CRÍTICA preservada: o último recurso ainda é `AIMessage` (não instância
do modelo Pydantic), então o guard obrigatório (`isinstance`/`try` em todo
`with_structured_output`) continua valendo — o RoutedLLM não mascara isso.

Mecânica é Python: a política de roteamento é código determinístico (ROUTES),
não decisão do LLM. Overrides por env (R8): RPG_FORCE_MOCK, LLM_PROVIDER (legado),
RPG_ROUTES (JSON).
"""

import json
import logging
import os
import re
import threading
import time
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal, Optional
from collections.abc import Callable

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

if TYPE_CHECKING:
    from langchain_core.language_models import BaseLanguageModel

load_dotenv(override=True)  # .env é a fonte canônica das keys (sobrepõe env var do SO)

_LOG = logging.getLogger("rpg.llm")

_PROVIDER_LIMITERS: dict[tuple[str, int], threading.BoundedSemaphore] = {}
_PROVIDER_LIMITERS_LOCK = threading.Lock()


def _provider_limit(provider: str) -> int:
    key = f"RPG_LLM_MAX_CONCURRENCY_{provider.upper()}"
    raw = os.getenv(key, os.getenv("RPG_LLM_MAX_CONCURRENCY", "2"))
    try:
        return max(1, min(32, int(raw or 2)))
    except ValueError:
        return 2


@contextmanager
def _provider_slot(provider: str):
    """Bound in-flight calls without changing ordered fallback semantics."""
    limit = _provider_limit(provider)
    limiter_key = (provider, limit)
    with _PROVIDER_LIMITERS_LOCK:
        limiter = _PROVIDER_LIMITERS.setdefault(
            limiter_key,
            threading.BoundedSemaphore(limit),
        )
    started = time.perf_counter()
    limiter.acquire()
    waited = time.perf_counter() - started
    try:
        try:
            from observability.metrics import metrics

            metrics.observe(
                "rpg_llm_queue_wait_seconds",
                {"provider": provider},
                waited,
            )
        except Exception:
            pass
        yield
    finally:
        limiter.release()


Candidate = tuple  # (provider: str, model: str)


class ModelTier(Enum):
    CLASSIFY = "classify"  # menor/rápido: router, parse estruturado (temp 0)
    FAST = "fast"  # narração/roleplay (output-heavy)
    SMART = "smart"  # coerência: campanha, archivist, criador de ficha


# ---------------------------------------------------------------------------
LLMAttemptOutcome = Literal[
    "build_error",
    "circuit_open",
    "invoke_error",
    "stream_error",
    "stream_interrupted",  # SPEC-236: cut AFTER the first chunk (provider answered)
    "invalid_structured",
    "hedge_lost",  # SPEC-319 R5: hedge request abandoned (may still bill; counted as received)
    "success",
]


@dataclass(frozen=True)
class LLMAttemptEvent:
    """Uma tentativa concreta de candidato, inclusive antes do sucesso final."""

    provider: str
    model: str
    tier: ModelTier
    attempt_index: int
    latency_ms: int
    fell_back: bool
    outcome: LLMAttemptOutcome
    error: str | None
    structured: bool
    structured_failure_code: str | None = None
    recovery: str | None = None
    usage: dict[str, int | str] | None = None
    http_status: int = 0  # SPEC-248: status HTTP do provider quando a falha o expoe; senao 0
    error_type: str | None = (
        None  # SPEC-248: classe da excecao (``error`` pode ter texto do provider)
    )


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:]{0,60}$")


def _http_status(exc: BaseException) -> int:
    """Status HTTP de ``openai.APIStatusError``/``httpx.HTTPStatusError`` etc.; 0 se ausente."""
    for obj in (exc, getattr(exc, "response", None)):
        for attr in ("status_code", "http_status", "code"):
            value = getattr(obj, attr, None)
            if isinstance(value, int) and 100 <= value <= 599:
                return value
    return 0


def _log_attempt(
    provider: str,
    model: str,
    tier: "ModelTier",
    attempt_index: int,
    outcome: str,
    *,
    fell_back: bool = False,
    latency_ms: int = 0,
    error: str | None = None,
    http_status: int = 0,
    structured_failure_code: str | None = None,
    usage: dict | None = None,
) -> None:
    """SPEC-248 R1: uma linha ``llm.attempt`` por candidato tentado (sem prompt, sem texto de erro)."""
    try:
        from observability.telemetry import current_node, log_event

        error_type = (
            error
            if isinstance(error, str) and _IDENT_RE.match(error)
            else (None if not error else "other")
        )
        log_event(
            "llm",
            "attempt",
            level="debug" if outcome == "success" else "warning",
            provider=provider,
            model=model,
            tier=getattr(tier, "value", str(tier)),
            node=current_node(),
            attempt_index=attempt_index,
            outcome=outcome,
            http_status=int(http_status or 0),
            error_type=error_type,
            structured_failure_code=structured_failure_code,
            latency_ms=int(latency_ms),
            fell_back=bool(fell_back),
            cost_basis="usage" if usage else "none",
        )
    except Exception:  # silent-ok: o log nunca derruba o turno
        pass


def _log_exhausted(tier: "ModelTier", errors: list[str]) -> None:
    """SPEC-248 R2: todos os candidatos do tier falharam (so provider + tipo de falha)."""
    try:
        from observability.telemetry import current_node, log_event

        attempts = []
        for item in errors:
            head = item.split(" ", 1)
            provider = head[0].split(":", 1)[0]
            kind = head[1].split(":", 1)[0] if len(head) > 1 else "unknown"
            attempts.append({"provider": provider, "outcome": kind})
        log_event(
            "llm",
            "exhausted",
            level="error",
            tier=getattr(tier, "value", str(tier)),
            node=current_node(),
            attempts=attempts[:12],
        )
    except Exception:  # silent-ok: o log nunca derruba o turno
        pass


_ANNOUNCED: set[str] = set()


def _announce_once(event: str, reason: str, *, level: str) -> None:
    """SPEC-248 R3: MockLLM/FallbackLLM nunca sao escolhidos em silencio (1x por processo e motivo)."""
    key = f"{event}:{reason}"
    if key in _ANNOUNCED:
        return
    _ANNOUNCED.add(key)
    try:
        from observability.telemetry import log_event

        log_event(
            "llm",
            event,
            level=level,
            reason=reason,
            profile=(os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() or "legacy"),
        )
    except Exception:  # silent-ok: o log nunca derruba o turno
        pass


def _mock_level() -> str:
    return (
        "warning"
        if (os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() or "legacy") == "legacy"
        else "error"
    )


def _usage_snapshot(result: object) -> dict[str, int | str] | None:
    """Copy only numeric usage/cost metadata, never content or raw responses."""
    if isinstance(result, Mapping) and "raw" in result:
        result = result["raw"]
    source = getattr(result, "usage_metadata", None)
    metadata = getattr(result, "response_metadata", None)
    if not isinstance(metadata, Mapping):
        metadata = {}
    if not isinstance(source, Mapping):
        source = metadata.get("token_usage") or metadata.get("usage")
    if not isinstance(source, Mapping):
        source = {}
    provider_usage = metadata.get("token_usage") or metadata.get("usage") or {}
    if not isinstance(provider_usage, Mapping):
        provider_usage = {}
    input_details = source.get("input_token_details") or source.get("prompt_tokens_details") or {}
    output_details = (
        source.get("output_token_details") or source.get("completion_tokens_details") or {}
    )
    provider_input_details = provider_usage.get("prompt_tokens_details") or {}
    if not isinstance(input_details, Mapping):
        input_details = {}
    if not isinstance(output_details, Mapping):
        output_details = {}
    if not isinstance(provider_input_details, Mapping):
        provider_input_details = {}
    cached = source.get("prompt_cache_hit_tokens")
    if cached is None:
        cached = input_details.get("cache_read", input_details.get("cached_tokens"))
    if cached is None:
        cached = provider_usage.get(
            "prompt_cache_hit_tokens", provider_input_details.get("cached_tokens")
        )
    fields = {
        "input_tokens": source.get("input_tokens", source.get("prompt_tokens")),
        "output_tokens": source.get("output_tokens", source.get("completion_tokens")),
        "cached_tokens": cached,
        "audio_units": input_details.get("audio", output_details.get("audio")),
        "image_units": input_details.get("image", output_details.get("image")),
    }
    safe: dict[str, int | str] = {
        key: value
        for key, value in fields.items()
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
    }
    cost = metadata.get("cost_usd", source.get("cost_usd"))
    if isinstance(cost, (int, float, str)) and not isinstance(cost, bool):
        from services.usage_metering import _money

        valid_cost = _money(cost)
        if valid_cost is not None:
            safe["provider_cost_usd"] = str(valid_cost)
    return safe or None


# Registro de providers
# ---------------------------------------------------------------------------
# base_url OpenAI-compat por provider. IDs de endpoint confirmados na doc de cada
# provider no momento da impl — endpoint errado só faz o candidato cair no
# fallback (não derruba o turno).
PROVIDER_ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1",
    "qwen": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",  # Internacional (Singapura)
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "minimax": "https://api.minimax.io/v1",
    "kimi": "https://api.moonshot.ai/v1",
    "deepseek": "https://api.deepseek.com",
}

# provider -> nome da env var da key
PROVIDER_KEY_ENV = {
    "gemini": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
    "qwen": "QWEN_API_KEY",
    "glm": "GLM_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "kimi": "KIMI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openai_compat": "OPENAI_API_KEY",
}

# Providers OpenAI-compat: structured output vai por function_calling (ver _apply).
_OPENAI_COMPAT_PROVIDERS = {
    "groq",
    "qwen",
    "glm",
    "minimax",
    "kimi",
    "deepseek",
    "openai",
    "openai_compat",
}

# Total de gerações permitidas quando a rede respondeu, mas o parser Pydantic
# não recebeu uma tool call válida. Não se aplica a HTTP/quota/timeout.
STRUCTURED_SEMANTIC_MAX_ATTEMPTS = 3

# Stack default (R11 + achados do smoke real 2026-07-06). 1º = preferido; resto =
# fallback em ordem. Overridable por env sem editar código (RPG_ROUTES).
# Cada tier tem um candidato **Groq GRÁTIS** que funciona (via function_calling) —
# assim o jogo roda 100% no free tier do Groq mesmo sem os providers pagos. Os
# pagos (minimax/qwen/deepseek) ficam na frente e assumem quando têm saldo/key.
# 2026-07-16: DeepSeek é o provider PRIMÁRIO em todos os tiers (decisão do
# usuário pós-playtest longo — prosa melhor e custo ~$0.001/turno). Groq free
# segue como fallback vivo em todos os tiers.
ROUTES = {
    ModelTier.CLASSIFY: [
        ("deepseek", "deepseek-v4-flash"),
        ("groq", "openai/gpt-oss-20b"),
        ("gemini", "gemini-flash-lite-latest"),
    ],
    ModelTier.FAST: [
        ("deepseek", "deepseek-v4-flash"),
        ("groq", "openai/gpt-oss-120b"),
        ("minimax", "MiniMax-M2.5"),
        ("qwen", "qwen-plus"),
        ("gemini", "gemini-flash-latest"),
    ],
    ModelTier.SMART: [
        ("deepseek", "deepseek-v4-flash"),
        ("groq", "openai/gpt-oss-120b"),  # free, coerência; function_calling
        ("anthropic", "claude-sonnet-5"),
        ("gemini", "gemini-pro-latest"),
    ],
}


# ---------------------------------------------------------------------------
# Fallback resiliente (inalterado — convenção CRÍTICA)
# ---------------------------------------------------------------------------
class FallbackLLM:
    """Retorno seguro quando NENHUM provider pode ser inicializado."""

    is_fallback = True
    is_mock = False

    def __init__(self, error_message: str):
        self.error_message = error_message

    def bind_tools(self, *_args, **_kwargs):
        return self

    def with_structured_output(self, *_args, **_kwargs):
        return self

    def with_retry(self, *_args, **_kwargs):
        return self

    def invoke(self, _input):
        return AIMessage(content=self.error_message)

    def stream(self, _input):
        yield self.invoke(_input)


# ---------------------------------------------------------------------------
# Builders por provider — assinatura (temperature, model); levantam em falha
# ---------------------------------------------------------------------------
def _build_gemini(temperature: float, model: str) -> "BaseLanguageModel":
    from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory

    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY não configurada")
    timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        max_retries=0,  # Fail-fast: 429 de quota não é transitório
        request_timeout=timeout_seconds,
        safety_settings={
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        },
    )


def _build_ollama(temperature: float, model: str) -> "BaseLanguageModel":
    try:
        from langchain_ollama import ChatOllama
    except ImportError as e:
        raise ImportError("langchain-ollama não instalado (uv sync --extra ollama)") from e
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return ChatOllama(model=model, base_url=base_url, temperature=temperature)


def _build_openai(provider: str, temperature: float, model: str) -> "BaseLanguageModel":
    """OpenAI + qualquer endpoint OpenAI-compat (groq/qwen/glm/minimax/kimi/deepseek)."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        raise ImportError("langchain-openai não instalado (uv sync)") from e

    key_env = PROVIDER_KEY_ENV.get(provider, "OPENAI_API_KEY")
    api_key = os.getenv(key_env)
    if not api_key:
        raise ValueError(f"{key_env} não configurada (provider {provider})")

    if provider in ("openai", "openai_compat"):
        base_url = os.getenv("OPENAI_BASE_URL") or None
    else:
        base_url = PROVIDER_ENDPOINTS.get(provider)
        if not base_url:
            raise ValueError(f"endpoint desconhecido para provider {provider!r}")

    kwargs = {}
    if provider in {"deepseek", "groq"}:
        # Both chat-completion APIs expose final stream usage via stream_options.
        kwargs["stream_usage"] = True
    if provider == "deepseek" and model.startswith("deepseek-v4-"):
        # `deepseek-chat` era o alias não-pensante do Flash. O alias foi retirado
        # em 2026-07-24; preservar o modo evita raciocínio oculto/latência extra e
        # mantém function calling previsível nos schemas Pydantic.
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    global_timeout = os.getenv("LLM_TIMEOUT_SECONDS")
    timeout_seconds = float(
        global_timeout
        if global_timeout is not None
        else (os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "12") if provider == "deepseek" else "90")
    )
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_retries=0,
        timeout=timeout_seconds,
        **kwargs,
    )


def _build_anthropic(temperature: float, model: str) -> "BaseLanguageModel":
    """Claude via langchain-anthropic (extra opcional: uv sync --extra anthropic).
    Ausência da dep ⇒ ImportError ⇒ candidato pulado (não derruba a chain)."""
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as e:
        raise ImportError("langchain-anthropic não instalado (uv sync --extra anthropic)") from e
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY não configurada")
    # Modelos Claude 5+ (ex.: claude-sonnet-5) REJEITAM `temperature` (400
    # "temperature is deprecated for this model"). Omitir = usa o default do modelo.
    timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
    return ChatAnthropic(
        model=model,
        api_key=api_key,
        max_retries=0,
        timeout=timeout_seconds,
    )


def _build_client(provider: str, model: str, temperature: float) -> "BaseLanguageModel":
    """Dispatcher de construção (seam de teste). Levanta em qualquer falha —
    o RoutedLLM captura e pula pro próximo candidato."""
    if provider == "gemini":
        return _build_gemini(temperature, model)
    if provider == "ollama":
        return _build_ollama(temperature, model)
    if provider == "anthropic":
        return _build_anthropic(temperature, model)
    return _build_openai(provider, temperature, model)


# Cache por (provider, model, temperature) — evita reconstruir client a cada turno (R7).
_CLIENT_CACHE: dict = {}
_OPEN_CIRCUITS: dict[tuple[str, str], str] = {}


def reset_llm_circuit_breakers() -> None:
    """Reabre todos os candidatos; chamado no início de cada campanha."""
    _OPEN_CIRCUITS.clear()


def _permanent_provider_error(exc: BaseException) -> bool:
    """Classificação fechada das falhas que não melhoram no próximo invoke."""
    value = str(exc or "").casefold()
    markers = (
        "401 unauthorized",
        "402 payment",
        "403 forbidden",
        "404 not found",
        "payment required",
        "insufficient balance",
        "invalid api key",
        "authentication failed",
        "não configurada",
        "nao configurada",
        "key ausente",
        "não instalado",
        "nao instalado",
    )
    return any(marker in value for marker in markers)


def _open_circuit_if_permanent(provider: str, model: str, exc: BaseException) -> None:
    if _permanent_provider_error(exc):
        _OPEN_CIRCUITS[(provider, model)] = str(exc)[:500]


def _get_cached_client(provider: str, model: str, temperature: float) -> "BaseLanguageModel":
    key = (provider, model, temperature)
    client = _CLIENT_CACHE.get(key)
    if client is None:
        client = _build_client(provider, model, temperature)  # pode levantar (não cacheia falha)
        _CLIENT_CACHE[key] = client
    return client


# ---------------------------------------------------------------------------
# Telemetria (R9) — hook opcional consumido pela Fase 5.3
# ---------------------------------------------------------------------------
_TELEMETRY_HOOK: Callable[[str, str, ModelTier, int, bool], None] | None = None
_ATTEMPT_TELEMETRY_HOOK: Callable[[LLMAttemptEvent], None] | None = None
_SCOPED_ATTEMPT_HOOK: ContextVar[Callable[[LLMAttemptEvent], None] | None] = ContextVar(
    "scoped_llm_attempt_hook", default=None
)
_SCOPED_SPEND_GUARD: ContextVar[Callable[[str, str], None] | None] = ContextVar(
    "scoped_llm_spend_guard", default=None
)


@contextmanager
def llm_attempt_scope(fn: Callable[[LLMAttemptEvent], None]):
    token = _SCOPED_ATTEMPT_HOOK.set(fn)
    try:
        yield
    finally:
        _SCOPED_ATTEMPT_HOOK.reset(token)


@contextmanager
def llm_spend_guard_scope(fn: Callable[[str, str], None]):
    """Paid operation guard; failure propagates before network dispatch.

    Unlike telemetry this callback is authoritative and is never swallowed.
    Every fallback and structured retry invokes it independently.
    """
    token = _SCOPED_SPEND_GUARD.set(fn)
    try:
        yield
    finally:
        _SCOPED_SPEND_GUARD.reset(token)


def _kill_switch_disabled(provider: str, model: str) -> bool:
    """True when an operator disabled ``model:<provider>/<model>``; never raises (fail-safe)."""
    try:
        from services.kill_switches import model_disabled

        return model_disabled(provider, model)
    except Exception:
        return False


def _authorize_provider_attempt(provider: str, model: str) -> None:
    guard = _SCOPED_SPEND_GUARD.get()
    if guard is not None:
        guard(provider, model)


def set_llm_telemetry_hook(fn: Callable[[str, str, ModelTier, int, bool], None] | None) -> None:
    """Registra callback `(provider, model, tier, latency_ms, fell_back)` disparado
    após cada invoke bem-sucedido. `None` desliga. Custo zero se não registrado."""
    global _TELEMETRY_HOOK
    _TELEMETRY_HOOK = fn


def set_llm_attempt_telemetry_hook(fn: Callable[[LLMAttemptEvent], None] | None) -> None:
    """Registra callback estruturado para CADA candidato tentado.

    Diferente do hook legado success-only, este recebe também build/invoke
    errors e retornos estruturados inválidos. ``None`` desliga.
    """
    global _ATTEMPT_TELEMETRY_HOOK
    _ATTEMPT_TELEMETRY_HOOK = fn


def _emit_telemetry(
    provider: str, model: str, tier: ModelTier, latency_ms: int, fell_back: bool
) -> None:
    hook = _TELEMETRY_HOOK
    if hook is None:
        return
    try:
        hook(provider, model, tier, latency_ms, fell_back)
    except Exception as e:  # telemetria NUNCA derruba o turno
        _LOG.warning("telemetry hook falhou: %s", type(e).__name__)


def _emit_attempt_telemetry(event: LLMAttemptEvent) -> None:
    _log_attempt(
        event.provider,
        event.model,
        event.tier,
        event.attempt_index,
        event.outcome,
        fell_back=event.fell_back,
        latency_ms=event.latency_ms,
        error=event.error_type or event.error,
        http_status=event.http_status,
        structured_failure_code=event.structured_failure_code,
        usage=event.usage,
    )
    for hook in (_ATTEMPT_TELEMETRY_HOOK, _SCOPED_ATTEMPT_HOOK.get()):
        if hook is None:
            continue
        try:
            hook(event)
        except Exception as e:  # telemetria NUNCA derruba o turno
            _LOG.warning("attempt telemetry hook falhou: %s", type(e).__name__)


_UNSET = object()
_STREAM_CANCELLED = object()  # SPEC-319: tentativa abandonada por perder o hedge

# SPEC-319 R5: hedge. Teto de custo: no maximo ~10% das chamadas (e 1 por chamada).
HEDGE_MAX_RATIO = 0.10
HEDGE_MIN_CALLS = 10  # melhor-esforco POR INSTANCIA (processo); ver spec §7
_HEDGE_LOCK = threading.Lock()
_HEDGE_STATS = {"calls": 0, "hedges": 0}


def _hedge_ms() -> int:
    """`RPG_LLM_HEDGE_MS=<int>` (0 = desligado, default)."""
    try:
        return max(0, int(os.getenv("RPG_LLM_HEDGE_MS", "0") or 0))
    except ValueError:
        return 0


def _log_hedge(tier: "ModelTier", hedge_ms: int, *, winner: int, first: int) -> None:
    """SPEC-319 R5: `hedged` + `hedge_won` (o 2o candidato venceu o 1o)."""
    try:
        from observability.telemetry import current_node, log_event

        log_event(
            "llm",
            "hedge",
            level="info",
            tier=getattr(tier, "value", str(tier)),
            node=current_node(),
            hedge_ms=int(hedge_ms),
            hedged=True,
            hedge_won=winner != first,
        )
    except Exception:  # silent-ok: o log nunca derruba o turno
        pass


# ---------------------------------------------------------------------------
# RoutedLLM — embrulha candidatos ordenados; fallback em tempo de invoke
# ---------------------------------------------------------------------------
class RoutedLLM:
    """Tenta os candidatos em ordem; o 1º que responde vence. Último recurso:
    `AIMessage(content="")` (nunca levanta) — guard do nó segue obrigatório.

    `with_structured_output`/`bind_tools`/`with_retry` acumulam transformações
    reaplicadas a CADA candidato dentro do loop (cada provider resolve o método)."""

    is_fallback = False  # é um roteador vivo, não o fallback de erro
    is_mock = False

    def __init__(
        self, tier: ModelTier, temperature: float, candidates: list, _transforms: list | None = None
    ):
        self.tier = tier
        self.temperature = temperature
        self.candidates = [tuple(c) for c in candidates]
        self._transforms = _transforms or []

    def _clone_with(self, transform) -> "RoutedLLM":
        return RoutedLLM(
            self.tier, self.temperature, self.candidates, self._transforms + [transform]
        )

    def with_structured_output(self, schema, *a, **k) -> "RoutedLLM":
        return self._clone_with(("with_structured_output", (schema, *a), k))

    def bind_tools(self, *a, **k) -> "RoutedLLM":
        return self._clone_with(("bind_tools", a, k))

    def with_retry(self, *a, **k) -> "RoutedLLM":
        return self._clone_with(("with_retry", a, k))

    def _apply(self, client, provider: str):
        for name, a, k in self._transforms:
            # Endpoints OpenAI-compat (Groq etc.) usam STRICT json_schema por padrão,
            # que rejeita schema com dict aberto (StoryUpdate.payload). function_calling
            # (tool calling) não tem essa restrição — vira o método padrão nesses
            # providers, a menos que o call site já tenha escolhido um.
            if (
                name == "with_structured_output"
                and provider in _OPENAI_COMPAT_PROVIDERS
                and "method" not in k
            ):
                k = {**k, "method": "function_calling"}
            if (
                name == "with_structured_output"
                and a
                and isinstance(a[0], type)
                and issubclass(a[0], BaseModel)
            ):
                # Keep evidence internally. Public return shape is restored by
                # _normalize_internal_structured_result.
                k = {**k, "include_raw": True}
            client = getattr(client, name)(*a, **k)
        return client

    def _pydantic_structured_contract(self):
        """Retorna ``(schema, include_raw)`` para o último schema Pydantic."""
        for name, args, kwargs in reversed(self._transforms):
            if name != "with_structured_output" or not args:
                continue
            schema = args[0]
            try:
                is_pydantic = isinstance(schema, type) and issubclass(schema, BaseModel)
            except TypeError:
                is_pydantic = False
            if is_pydantic:
                return schema, bool(kwargs.get("include_raw", False))
            return None
        return None

    def _input_for_provider(self, input, provider: str):
        """Evita que OpenAI-compat trate uma última AIMessage como resposta final.

        O arquivista legitimamente envia histórico que pode terminar na fala do
        assistente. Alguns modelos Groq então continuam a fala em texto, apesar
        do ``tool_choice`` obrigatório, e o endpoint rejeita a resposta. Uma
        instrução humana neutra mantém o histórico e torna explícito que falta
        produzir a saída estruturada.
        """
        if (
            provider in _OPENAI_COMPAT_PROVIDERS
            and self._pydantic_structured_contract() is not None
            and isinstance(input, (list, tuple))
            and input
            and isinstance(input[-1], AIMessage)
        ):
            return [
                *input,
                HumanMessage(
                    content=(
                        "Produza agora somente a saída estruturada solicitada pela "
                        "ferramenta; a mensagem anterior é contexto, não uma resposta final."
                    )
                ),
            ]
        return input

    def _input_for_structured_retry(
        self,
        input,
        provider: str,
        failure_code: str | None = None,
    ):
        """Prepare a semantic regeneration after a malformed tool response.

        This is separate from HTTP retries: it only runs after the provider
        answered but failed the Pydantic post-condition. The caller's message
        list is never mutated.
        """
        prepared = self._input_for_provider(input, provider)
        if not isinstance(prepared, (list, tuple)):
            return prepared
        schema = self._pydantic_structured_contract()
        schema_name = schema[0].__name__ if schema else "solicitado"
        return [
            *prepared,
            HumanMessage(
                content=(
                    f"A saída estruturada anterior falhou no contrato {schema_name} "
                    f"(causa: {failure_code or 'invalid_structured'}). Tente novamente "
                    "e responda somente pela ferramenta solicitada."
                )
            ),
        ]

    def _validate_structured_result(self, result) -> tuple[bool, str | None, bool]:
        """Valida a pós-condição que providers nem sempre cumprem.

        Schemas não-Pydantic e invocações plain mantêm a compatibilidade
        histórica: qualquer retorno do client é aceito.
        """
        contract = self._pydantic_structured_contract()
        if contract is None:
            return True, None, False
        schema, include_raw = contract
        expected = schema.__name__
        if include_raw:
            if not isinstance(result, dict):
                return False, f"include_raw retornou {type(result).__name__}, esperado dict", True
            parsing_error = result.get("parsing_error")
            if parsing_error is not None:
                return False, f"parsing_error: {parsing_error}", True
            parsed = result.get("parsed")
            if not isinstance(parsed, schema):
                return (
                    False,
                    f"parsed retornou {type(parsed).__name__}, esperado {expected}",
                    True,
                )
            return True, None, True
        if not isinstance(result, schema):
            return (
                False,
                f"structured retornou {type(result).__name__}, esperado {expected}",
                True,
            )
        return True, None, True

    @staticmethod
    def _json_object_from_text(content: object) -> dict | None:
        """Extract one bounded JSON object without eval or permissive coercion."""
        if isinstance(content, list):
            content = " ".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in content
            )
        text = str(content or "").strip()
        if not text or len(text) > 65_536:
            return None
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].strip().lower() in {"```", "```json"}:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        decoder = json.JSONDecoder()
        starts = [0] if text.startswith("{") else []
        starts.extend(index for index, char in enumerate(text) if char == "{" and index != 0)
        for start in starts:
            try:
                value, _end = decoder.raw_decode(text[start:])
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                return value
        return None

    def _normalize_internal_structured_result(
        self,
        result,
    ) -> tuple[object, str | None, str | None]:
        """Restore the caller's return shape and recover valid raw JSON locally."""
        contract = self._pydantic_structured_contract()
        if contract is None:
            return result, None, None
        schema, caller_include_raw = contract
        if isinstance(result, schema):
            if caller_include_raw:
                return {"raw": None, "parsed": result, "parsing_error": None}, None, None
            return result, None, None
        if not isinstance(result, dict):
            return result, "no_tool_call", None
        parsed = result.get("parsed")
        parsing_error = result.get("parsing_error")
        if isinstance(parsed, schema) and parsing_error is None:
            return (result if caller_include_raw else parsed), None, None
        raw = result.get("raw")
        calls = list(getattr(raw, "tool_calls", None) or [])
        calls.extend(getattr(raw, "invalid_tool_calls", None) or [])
        expected_name = schema.model_json_schema().get("title") or schema.__name__
        if calls and any(call.get("name") != expected_name for call in calls):
            return result, "wrong_tool", None
        payload = self._json_object_from_text(getattr(raw, "content", ""))
        if payload is not None:
            try:
                recovered = schema.model_validate(payload)
            except Exception:
                return result, "schema_validation", None
            if recovered is not None:
                if caller_include_raw:
                    return (
                        {"raw": raw, "parsed": recovered, "parsing_error": None},
                        None,
                        "local_json",
                    )
                return recovered, None, "local_json"
        if parsing_error is not None:
            return result, "parsing_error", None
        if parsed is None:
            return result, "no_tool_call", None
        return result, "schema_validation", None

    def invoke(self, input):
        errors = []
        attempt_index = 0
        structured_contract = self._pydantic_structured_contract()
        for provider_index, (provider, model) in enumerate(self.candidates):
            fell_back = provider_index > 0
            if _kill_switch_disabled(provider, model):  # SPEC-196: operator switched model off
                errors.append(f"{provider}:{model} kill_switch")
                _log_attempt(
                    provider, model, self.tier, attempt_index, "kill_switch", fell_back=fell_back
                )
                continue
            circuit_reason = _OPEN_CIRCUITS.get((provider, model))
            if circuit_reason:
                errors.append(f"{provider}:{model} circuit")
                _emit_attempt_telemetry(
                    LLMAttemptEvent(
                        provider=provider,
                        model=model,
                        tier=self.tier,
                        attempt_index=attempt_index,
                        latency_ms=0,
                        fell_back=fell_back,
                        outcome="circuit_open",
                        error=circuit_reason,
                        structured=structured_contract is not None,
                    )
                )
                attempt_index += 1
                continue
            build_t0 = time.perf_counter()
            try:
                client = _get_cached_client(provider, model, self.temperature)
            except Exception as e:
                latency_ms = int((time.perf_counter() - build_t0) * 1000)
                errors.append(f"{provider}:{model} build:{type(e).__name__}")
                _emit_attempt_telemetry(
                    LLMAttemptEvent(
                        provider=provider,
                        model=model,
                        tier=self.tier,
                        attempt_index=attempt_index,
                        latency_ms=latency_ms,
                        fell_back=fell_back,
                        outcome="build_error",
                        error=type(e).__name__,
                        http_status=_http_status(e),
                        structured=structured_contract is not None,
                    )
                )
                attempt_index += 1
                _open_circuit_if_permanent(provider, model, e)
                continue
            try:
                client = self._apply(client, provider)
            except Exception as e:
                latency_ms = int((time.perf_counter() - build_t0) * 1000)
                errors.append(f"{provider}:{model} apply:{type(e).__name__}")
                _emit_attempt_telemetry(
                    LLMAttemptEvent(
                        provider=provider,
                        model=model,
                        tier=self.tier,
                        attempt_index=attempt_index,
                        latency_ms=latency_ms,
                        fell_back=fell_back,
                        outcome="build_error",
                        error=f"apply:{type(e).__name__}",
                        http_status=_http_status(e),
                        structured=structured_contract is not None,
                    )
                )
                attempt_index += 1
                _open_circuit_if_permanent(provider, model, e)
                continue
            # Uma resposta HTTP válida sem o tool call/schema pedido é um erro
            # semântico recuperável. Regenera no máximo duas vezes no MESMO
            # provider; erros de rede/quota continuam fail-fast.
            semantic_attempts = (
                STRUCTURED_SEMANTIC_MAX_ATTEMPTS if structured_contract is not None else 1
            )
            last_failure_code: str | None = None
            for semantic_attempt in range(semantic_attempts):
                request_input = (
                    self._input_for_structured_retry(input, provider, last_failure_code)
                    if semantic_attempt
                    else self._input_for_provider(input, provider)
                )
                t0 = time.perf_counter()
                _authorize_provider_attempt(provider, model)
                try:
                    with _provider_slot(provider):
                        result = client.invoke(request_input)
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                except Exception as e:
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                    errors.append(f"{provider}:{model} invoke:{type(e).__name__}")
                    _emit_attempt_telemetry(
                        LLMAttemptEvent(
                            provider=provider,
                            model=model,
                            tier=self.tier,
                            attempt_index=attempt_index,
                            latency_ms=latency_ms,
                            fell_back=fell_back,
                            outcome="invoke_error",
                            error=type(e).__name__,
                            http_status=_http_status(e),
                            structured=structured_contract is not None,
                            structured_failure_code="transport",
                            usage=_usage_snapshot(e),
                        )
                    )
                    attempt_index += 1
                    _open_circuit_if_permanent(provider, model, e)
                    break
                usage_snapshot = _usage_snapshot(result)
                result, failure_code, recovery = self._normalize_internal_structured_result(result)
                valid, validation_error, structured = self._validate_structured_result(result)
                if not valid:
                    last_failure_code = failure_code or "schema_validation"
                    errors.append(f"{provider}:{model} structured:{last_failure_code}")
                    _emit_attempt_telemetry(
                        LLMAttemptEvent(
                            provider=provider,
                            model=model,
                            tier=self.tier,
                            attempt_index=attempt_index,
                            latency_ms=latency_ms,
                            fell_back=fell_back,
                            outcome="invalid_structured",
                            error=last_failure_code,
                            structured=structured,
                            structured_failure_code=failure_code,
                            usage=usage_snapshot,
                        )
                    )
                    attempt_index += 1
                    continue
                _emit_attempt_telemetry(
                    LLMAttemptEvent(
                        provider=provider,
                        model=model,
                        tier=self.tier,
                        attempt_index=attempt_index,
                        latency_ms=latency_ms,
                        fell_back=fell_back,
                        outcome="success",
                        error=None,
                        structured=structured,
                        recovery=recovery,
                        usage=usage_snapshot,
                    )
                )
                _emit_telemetry(provider, model, self.tier, latency_ms, fell_back)
                return result
        _log_exhausted(self.tier, errors)
        # conteúdo vazio: sites de narração plain-invoke caem no fallback determinístico;
        # sites structured batem no guard (isinstance/try) do nó.
        return AIMessage(content="")

    async def ainvoke(self, input):
        """Async-compatible boundary with exact sync routing semantics.

        Provider fallback remains single-flight and ordered. The synchronous
        clients run in the event loop's bounded executor, so callers can overlap
        independent requests without copying or drifting the routing state
        machine.
        """
        import asyncio

        return await asyncio.to_thread(self.invoke, input)

    def stream(self, input):
        errors = []
        for idx, (provider, model) in enumerate(self.candidates):
            fell_back = idx > 0
            if _kill_switch_disabled(provider, model):  # SPEC-196
                errors.append(f"{provider}:{model} kill_switch")
                _log_attempt(provider, model, self.tier, idx, "kill_switch", fell_back=fell_back)
                continue
            structured = self._pydantic_structured_contract() is not None
            circuit_reason = _OPEN_CIRCUITS.get((provider, model))
            if circuit_reason:
                errors.append(f"{provider}:{model} circuit")
                _emit_attempt_telemetry(
                    LLMAttemptEvent(
                        provider=provider,
                        model=model,
                        tier=self.tier,
                        attempt_index=idx,
                        latency_ms=0,
                        fell_back=fell_back,
                        outcome="circuit_open",
                        error=circuit_reason,
                        structured=structured,
                    )
                )
                continue
            build_t0 = time.perf_counter()
            try:
                client = _get_cached_client(provider, model, self.temperature)
                client = self._apply(client, provider)
            except Exception as e:
                latency_ms = int((time.perf_counter() - build_t0) * 1000)
                errors.append(f"{provider}:{model} build:{type(e).__name__}")
                _emit_attempt_telemetry(
                    LLMAttemptEvent(
                        provider=provider,
                        model=model,
                        tier=self.tier,
                        attempt_index=idx,
                        latency_ms=latency_ms,
                        fell_back=fell_back,
                        outcome="build_error",
                        error=type(e).__name__,
                        http_status=_http_status(e),
                        structured=structured,
                    )
                )
                _open_circuit_if_permanent(provider, model, e)
                continue
            t0 = time.perf_counter()
            _authorize_provider_attempt(provider, model)
            try:
                it = iter(client.stream(input))
                first = next(it)
            except StopIteration:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                _emit_attempt_telemetry(
                    LLMAttemptEvent(
                        provider=provider,
                        model=model,
                        tier=self.tier,
                        attempt_index=idx,
                        latency_ms=latency_ms,
                        fell_back=fell_back,
                        outcome="success",
                        error=None,
                        structured=structured,
                    )
                )
                _emit_telemetry(provider, model, self.tier, latency_ms, fell_back)
                return
            except Exception as e:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                errors.append(f"{provider}:{model} stream:{type(e).__name__}")
                _emit_attempt_telemetry(
                    LLMAttemptEvent(
                        provider=provider,
                        model=model,
                        tier=self.tier,
                        attempt_index=idx,
                        latency_ms=latency_ms,
                        fell_back=fell_back,
                        outcome="stream_error",
                        error=type(e).__name__,
                        http_status=_http_status(e),
                        structured=structured,
                    )
                )
                _open_circuit_if_permanent(provider, model, e)
                continue
            usage_snapshot = _usage_snapshot(first)
            try:
                yield first
                for chunk in it:
                    usage_snapshot = _usage_snapshot(chunk) or usage_snapshot
                    yield chunk
            except GeneratorExit:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                _emit_attempt_telemetry(
                    LLMAttemptEvent(
                        provider=provider,
                        model=model,
                        tier=self.tier,
                        attempt_index=idx,
                        latency_ms=latency_ms,
                        fell_back=fell_back,
                        outcome="stream_interrupted",
                        error="consumer_closed",
                        structured=structured,
                        usage=usage_snapshot,
                    )
                )
                raise
            except Exception as e:  # falha no meio do stream: encerra o que veio
                latency_ms = int((time.perf_counter() - t0) * 1000)
                _emit_attempt_telemetry(
                    LLMAttemptEvent(
                        provider=provider,
                        model=model,
                        tier=self.tier,
                        attempt_index=idx,
                        latency_ms=latency_ms,
                        fell_back=fell_back,
                        outcome="stream_interrupted",
                        error=str(e),
                        error_type=type(e).__name__,
                        http_status=_http_status(e),
                        structured=structured,
                        usage=usage_snapshot,
                    )
                )
                _open_circuit_if_permanent(provider, model, e)
                return
            latency_ms = int((time.perf_counter() - t0) * 1000)
            _emit_attempt_telemetry(
                LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=latency_ms,
                    fell_back=fell_back,
                    outcome="success",
                    error=None,
                    structured=structured,
                    usage=usage_snapshot,
                )
            )
            _emit_telemetry(provider, model, self.tier, latency_ms, fell_back)
            return
        _log_exhausted(self.tier, errors)
        yield AIMessage(content="")

    # ------------------------------------------------------------------
    # SPEC-319: streaming de tokens da narracao + hedge na cauda
    # ------------------------------------------------------------------
    def stream_structured(
        self,
        input,
        schema,
        *,
        on_delta: Callable[[str], None] | None = None,
        on_reset: Callable[[], None] | None = None,
        key: str | None = None,
    ):
        """Equivalente a `with_structured_output(schema).invoke(input)` com o campo de narracao
        (`key`, default `narrative`) entregue token a token em `on_delta`.

        So candidatos OpenAI-compat streamam (tool call via `bind_tools`); os demais usam o
        invoke estruturado de sempre. Falha no meio do stream => `on_reset()` e proximo
        candidato. Esgotou => `AIMessage(content="")` (o guard do chamador segue obrigatorio)."""
        return self._stream_route(input, schema, key, on_delta, on_reset)

    def stream_text(
        self,
        input,
        *,
        on_delta: Callable[[str], None] | None = None,
        on_reset: Callable[[], None] | None = None,
    ):
        """Equivalente a `invoke(input)` (texto plano) com os deltas em `on_delta`."""
        return self._stream_route(input, None, None, on_delta, on_reset)

    def _stream_route(self, input, schema, key, on_delta, on_reset):
        errors: list[str] = []
        sent = {"n": 0}

        def emit(text: str) -> None:
            sent["n"] += 1
            if on_delta is not None:
                on_delta(text)

        def reset() -> None:
            if sent["n"]:
                sent["n"] = 0
                if on_reset is not None:
                    on_reset()

        tried: set[int] = set()
        hedge_ms = _hedge_ms() if (schema is not None and self.tier is ModelTier.FAST) else 0
        if hedge_ms > 0:
            result, tried = self._hedged_first(input, schema, key, emit, errors, hedge_ms)
            if result is not None:
                return result
            reset()
        for idx, (provider, model) in enumerate(self.candidates):
            if idx in tried:
                continue
            result = self._stream_attempt(
                idx, provider, model, input, schema, key, emit, lambda: False, errors
            )
            if result is not None:
                return result
            reset()  # R4: o parcial deste candidato nao vale para o proximo
        _log_exhausted(self.tier, errors)
        return AIMessage(content="")

    def _stream_attempt(
        self, idx, provider, model, input, schema, key, emit, cancelled, errors
    ) -> object:
        """Uma tentativa em UM candidato. Devolve o resultado, `None` (falhou; proximo) ou
        `_STREAM_CANCELLED` (perdeu o hedge; a telemetria fica com o coordenador)."""
        fell_back = idx > 0
        structured = schema is not None
        if _kill_switch_disabled(provider, model):  # SPEC-196
            errors.append(f"{provider}:{model} kill_switch")
            _log_attempt(provider, model, self.tier, idx, "kill_switch", fell_back=fell_back)
            return None
        circuit_reason = _OPEN_CIRCUITS.get((provider, model))
        if circuit_reason:
            errors.append(f"{provider}:{model} circuit")
            _emit_attempt_telemetry(
                LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=0,
                    fell_back=fell_back,
                    outcome="circuit_open",
                    error=circuit_reason,
                    structured=structured,
                )
            )
            return None
        if provider not in _OPENAI_COMPAT_PROVIDERS:
            # D4: sem parser incremental para Anthropic/Gemini => invoke estruturado (SPEC-316).
            res = self._invoke_single(provider, model, input, schema)
            if res is None:
                errors.append(f"{provider}:{model} invoke:invalid")
            return res
        if (
            isinstance(input, (list, tuple))
            and input
            and isinstance(input[-1], AIMessage)
            and structured
        ):
            # mesma instrucao neutra do `_input_for_provider` (OpenAI-compat + ultima msg do assistente)
            input = [
                *input,
                HumanMessage(
                    content=(
                        "Produza agora somente a saida estruturada solicitada pela ferramenta; "
                        "a mensagem anterior e contexto, nao uma resposta final."
                    )
                ),
            ]
        build_t0 = time.perf_counter()
        try:
            client = _get_cached_client(provider, model, self.temperature)
            if structured:
                tool_name = schema.model_json_schema().get("title") or schema.__name__
                client = client.bind_tools([schema], tool_choice=tool_name)
        except Exception as e:
            errors.append(f"{provider}:{model} build:{type(e).__name__}")
            _emit_attempt_telemetry(
                LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=int((time.perf_counter() - build_t0) * 1000),
                    fell_back=fell_back,
                    outcome="build_error",
                    error=type(e).__name__,
                    http_status=_http_status(e),
                    structured=structured,
                )
            )
            _open_circuit_if_permanent(provider, model, e)
            return None
        from services.partial_narrative import NarrativeExtractor

        extractor = NarrativeExtractor(key) if structured else None
        args_parts: list[str] = []
        content_parts: list[str] = []
        first_index: object = _UNSET
        usage = None
        chunks = 0
        t0 = time.perf_counter()
        _authorize_provider_attempt(provider, model)
        try:
            with _provider_slot(provider):
                it = iter(client.stream(input))
                try:
                    for chunk in it:
                        if cancelled():
                            return _STREAM_CANCELLED
                        chunks += 1
                        usage = _usage_snapshot(chunk) or usage
                        if not structured:
                            text = getattr(chunk, "content", "")
                            if isinstance(text, str) and text:
                                content_parts.append(text)
                                emit(text)
                            continue
                        piece = ""
                        for tc in getattr(chunk, "tool_call_chunks", None) or []:
                            tc_index = tc.get("index")
                            if first_index is _UNSET:
                                first_index = tc_index
                            if tc_index != first_index:
                                continue
                            arg = tc.get("args")
                            if arg:
                                args_parts.append(arg)
                                piece += extractor.feed(arg)
                        text = getattr(chunk, "content", "")
                        if (
                            isinstance(text, str)
                            and text
                            and not args_parts
                            and ("".join(content_parts) + text).lstrip().startswith("{")
                        ):
                            content_parts.append(text)
                            piece += extractor.feed(text)
                        if piece:
                            emit(piece)
                finally:
                    close = getattr(it, "close", None)
                    if callable(close):
                        try:
                            close()
                        except Exception:  # silent-ok: fechar o iterador e melhor-esforco
                            pass
        except Exception as e:
            if cancelled():
                return _STREAM_CANCELLED
            latency_ms = int((time.perf_counter() - t0) * 1000)
            errors.append(f"{provider}:{model} stream:{type(e).__name__}")
            _emit_attempt_telemetry(
                LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=latency_ms,
                    fell_back=fell_back,
                    outcome="stream_interrupted" if chunks else "stream_error",
                    error=str(e) if chunks else type(e).__name__,
                    error_type=type(e).__name__,
                    http_status=_http_status(e),
                    structured=structured,
                    usage=usage,
                )
            )
            _open_circuit_if_permanent(provider, model, e)
            return None
        if cancelled():
            return _STREAM_CANCELLED
        latency_ms = int((time.perf_counter() - t0) * 1000)
        result: object | None
        failure = "no_tool_call"
        if structured:
            result = self._parse_streamed(schema, "".join(args_parts) or "".join(content_parts))
            if result is None and (args_parts or content_parts):
                failure = "schema_validation"
        else:
            full = "".join(content_parts)
            result = AIMessage(content=full) if full.strip() else None
            failure = "empty"
        if result is None:
            errors.append(f"{provider}:{model} structured:{failure}")
            _emit_attempt_telemetry(
                LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=latency_ms,
                    fell_back=fell_back,
                    outcome="invalid_structured",
                    error=failure,
                    structured=structured,
                    structured_failure_code=failure,
                    usage=usage,
                )
            )
            if structured:
                # P2-8: o `invoke` regenera ate 3x no mesmo provider; o stream so tenta 1x. Antes
                # de abandonar o candidato, recorre ao invoke estruturado completo dele.
                return self._invoke_single(provider, model, input, schema)
            return None
        _emit_attempt_telemetry(
            LLMAttemptEvent(
                provider=provider,
                model=model,
                tier=self.tier,
                attempt_index=idx,
                latency_ms=latency_ms,
                fell_back=fell_back,
                outcome="success",
                error=None,
                structured=structured,
                usage=usage,
            )
        )
        _emit_telemetry(provider, model, self.tier, latency_ms, fell_back)
        return result

    def _invoke_single(self, provider: str, model: str, input, schema):
        """`invoke` (com regeneracao semantica) restrito a UM candidato; `None` se invalido."""
        sub = RoutedLLM(
            self.tier,
            self.temperature,
            [(provider, model)],
            [("with_structured_output", (schema,), {})] if schema is not None else [],
        )
        res = sub.invoke(input)
        ok = (
            isinstance(res, schema)
            if schema is not None
            else bool(str(getattr(res, "content", "") or "").strip())
        )
        return res if ok else None

    def _parse_streamed(self, schema, raw: str):
        """JSON completo da tool call -> instancia de `schema` (ou None). Mesma validacao Pydantic
        do invoke; nunca levanta."""
        if not raw.strip():
            return None
        try:
            return schema.model_validate_json(raw)
        except Exception:  # silent-ok: JSON invalido => invalid_structured no chamador
            payload = self._json_object_from_text(raw)
            if payload is None:
                return None
            try:
                return schema.model_validate(payload)
            except Exception:  # silent-ok: idem (o chamador registra a tentativa)
                return None

    def _hedged_first(self, input, schema, key, emit, errors, hedge_ms: int):
        """R5: dispara o 2o candidato se o 1o nao emitiu NENHUM delta em `hedge_ms`.

        Devolve `(resultado|None, indices_tentados)`. O 1o a emitir delta (ou a concluir valido)
        vence; o outro e abandonado (a request HTTP termina sozinha — SPEC-143 §2.6) e registrado
        como `hedge_lost`. No maximo 1 hedge por chamada, com teto de ~10% das chamadas."""
        import contextvars
        import queue

        eligible = [
            (i, p, m)
            for i, (p, m) in enumerate(self.candidates)
            if p in _OPENAI_COMPAT_PROVIDERS
            and not _kill_switch_disabled(p, m)
            and not _OPEN_CIRCUITS.get((p, m))
        ][:2]
        with _HEDGE_LOCK:
            _HEDGE_STATS["calls"] += 1
        if len(eligible) < 2:
            return None, set()
        q: queue.Queue = queue.Queue()
        cancels = {i: threading.Event() for i, _p, _m in eligible}
        started: dict[int, tuple[str, str, float]] = {}

        def start(i: int, p: str, m: str) -> None:
            started[i] = (p, m, time.perf_counter())
            ctx = contextvars.copy_context()

            def runner() -> None:
                res = self._stream_attempt(
                    i,
                    p,
                    m,
                    input,
                    schema,
                    key,
                    lambda text, _i=i: q.put(("delta", _i, text)),
                    cancels[i].is_set,
                    errors,
                )
                q.put(("end", i, res))

            threading.Thread(target=ctx.run, args=(runner,), daemon=True).start()

        def abandon(winner: int) -> None:
            for i, (p, m, t_start) in started.items():
                if i == winner or i in ended:
                    continue  # quem ja terminou (falhou) nao e "hedge perdido"
                cancels[i].set()
                _emit_attempt_telemetry(
                    LLMAttemptEvent(
                        provider=p,
                        model=m,
                        tier=self.tier,
                        attempt_index=i,
                        latency_ms=int((time.perf_counter() - t_start) * 1000),
                        fell_back=i > 0,
                        outcome="hedge_lost",
                        error=None,
                        structured=True,
                    )
                )

        def finish(winner: int, hedged: bool) -> None:
            if hedged:
                _log_hedge(self.tier, hedge_ms, winner=winner, first=eligible[0][0])

        first_i, first_p, first_m = eligible[0]
        second_i, second_p, second_m = eligible[1]
        start(first_i, first_p, first_m)
        deadline = time.monotonic() + hedge_ms / 1000.0
        winner: int | None = None
        hedged = False
        no_budget = False
        ended: set[int] = set()
        while True:
            timeout = (
                None if (len(started) > 1 or no_budget) else max(0.0, deadline - time.monotonic())
            )
            try:
                kind, i, payload = q.get(timeout=timeout)
            except queue.Empty:
                with _HEDGE_LOCK:
                    # instancia fria (Vercel): so hedgeia depois de HEDGE_MIN_CALLS chamadas, senao
                    # a 1a chamada de cada instancia sempre passaria do teto de 10 %
                    allowed = _HEDGE_STATS["calls"] >= HEDGE_MIN_CALLS and (
                        _HEDGE_STATS["hedges"] + 1 <= HEDGE_MAX_RATIO * _HEDGE_STATS["calls"]
                    )
                    if allowed:
                        _HEDGE_STATS["hedges"] += 1
                if not allowed:
                    no_budget = True  # sem orcamento: segue so com o 1o
                    continue
                hedged = True
                start(second_i, second_p, second_m)
                continue
            if kind == "delta":
                if winner is None:
                    winner = i
                    abandon(winner)
                if i == winner:
                    emit(payload)
                continue
            ended.add(i)
            if winner is None:
                if payload is not None:
                    winner = i
                    abandon(winner)
                    finish(winner, hedged)
                    return payload, set(started)
                if len(started) == 1 and second_i not in started:
                    start(second_i, second_p, second_m)  # 1o falhou: segue para o 2o ja
                    continue
                if ended >= set(started):
                    return None, set(started)
                continue
            if i == winner:
                finish(winner, hedged)
                return payload, set(started)
            # fim do perdedor: ignorado


# ---------------------------------------------------------------------------
# Resolução de rotas + overrides
# ---------------------------------------------------------------------------
def _any_key_available() -> bool:
    return any(os.getenv(env) for env in set(PROVIDER_KEY_ENV.values()))


def _load_routes() -> dict:
    """ROUTES default ou override (RPG_ROUTES: caminho de arquivo JSON ou o próprio JSON inline)."""
    path = os.getenv("RPG_ROUTES")
    if not path:
        return ROUTES
    try:
        if path.lstrip().startswith("{"):
            # SPEC-317 R1: JSON inline (Vercel nao tem arquivo extra no bundle)
            raw = json.loads(path)
        else:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        parsed = {ModelTier(name): [tuple(c) for c in cands] for name, cands in raw.items()}
        return {**ROUTES, **parsed}
    except Exception as e:
        from observability.telemetry import log_event

        log_event(
            "llm", "routes_invalid", level="warning", error_type=type(e).__name__
        )  # nunca o JSON da env
        return ROUTES


# Modelos por-tier do provider legado (LLM_PROVIDER=<x>). Gemini mantém o
# comportamento atual; ollama/openai leem env por-tier.
def _legacy_model(provider: str, tier: ModelTier) -> str | None:
    if provider == "gemini":
        return {
            ModelTier.CLASSIFY: "gemini-flash-lite-latest",
            ModelTier.FAST: "gemini-flash-latest",
            ModelTier.SMART: "gemini-pro-latest",
        }[tier]
    if provider == "ollama":
        return {
            ModelTier.CLASSIFY: os.getenv(
                "OLLAMA_MODEL_CLASSIFY", os.getenv("OLLAMA_MODEL_FAST", "llama3.2")
            ),
            ModelTier.FAST: os.getenv("OLLAMA_MODEL_FAST", "llama3.2"),
            ModelTier.SMART: os.getenv("OLLAMA_MODEL_SMART", "llama3.1"),
        }[tier]
    if provider in ("openai", "openai_compat"):
        return {
            ModelTier.CLASSIFY: os.getenv(
                "OPENAI_MODEL_CLASSIFY", os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini")
            ),
            ModelTier.FAST: os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini"),
            ModelTier.SMART: os.getenv("OPENAI_MODEL_SMART", "gpt-4o"),
        }[tier]
    return None


def _legacy_get_llm(provider: str, temperature: float, tier: ModelTier):
    """LLM_PROVIDER=<x> força TODOS os tiers a um único provider (ignora ROUTES)."""
    # Gemini sem chave preserva o comportamento atual (jogável offline via MockLLM).
    if provider == "gemini" and not os.getenv("GOOGLE_API_KEY"):
        if os.getenv("RPG_NO_MOCK"):
            _announce_once("fallback_llm_selected", "legacy_gemini_no_key", level="error")
            return FallbackLLM("GOOGLE_API_KEY não configurada")
        _announce_once("mock_selected", "legacy_gemini_no_key", level=_mock_level())
        from mock_llm import MockLLM

        return MockLLM(temperature=temperature)

    model = _legacy_model(provider, tier)
    if model is None:
        _announce_once("fallback_llm_selected", "unknown_provider", level="error")
        return FallbackLLM(f"Provider desconhecido: {provider!r}")
    # embrulha em RoutedLLM (1 candidato) para semântica uniforme de fallback/telemetria
    return RoutedLLM(tier, temperature, [(provider, model)])


def get_llm(temperature: float = 0.1, tier: ModelTier = ModelTier.FAST):
    """Resolve os candidatos do tier (respeitando overrides) e devolve um `RoutedLLM`.
    Assinatura pública inalterada — back-compat total nos call sites.

    Ordem de resolução (R8):
      1. RPG_FORCE_MOCK=1  → MockLLM (suíte / offline determinístico)
      2. LLM_PROVIDER=<x>  → provider legado único (ignora ROUTES)
      3. sem key nenhuma   → MockLLM (zero-config) ou FallbackLLM (RPG_NO_MOCK)
      4. default           → ROUTES (multi-provider com fallback)
    """
    if os.getenv("RPG_FORCE_MOCK"):
        _announce_once("mock_selected", "force_mock", level=_mock_level())
        from mock_llm import MockLLM

        return MockLLM(temperature=temperature)

    provider_override = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider_override:
        return _legacy_get_llm(provider_override, temperature, tier)

    if not _any_key_available():
        if os.getenv("RPG_NO_MOCK"):
            _announce_once("fallback_llm_selected", "no_keys", level="error")
            return FallbackLLM("Nenhuma key de provider configurada")
        _announce_once("mock_selected", "no_keys", level=_mock_level())
        from mock_llm import MockLLM

        return MockLLM(temperature=temperature)

    return RoutedLLM(tier, temperature, _load_routes().get(tier, []))


def is_simulated() -> bool:
    """True quando `get_llm()` devolveria MockLLM (modo simulado, sem provider real).

    Espelha a ordem de resolução do get_llm — auditoria A4: a flag `simulated`
    da API olhava só GOOGLE_API_KEY e mentia com o jogo 100% real no Groq."""
    if os.getenv("RPG_FORCE_MOCK"):
        return True
    if os.getenv("RPG_NO_MOCK"):
        return False
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider:
        return provider == "gemini" and not os.getenv("GOOGLE_API_KEY")
    return not _any_key_available()


def llm_mode() -> str:
    """SPEC-249/248: modo efetivo do LLM — ``routes|legacy:<provider>|mock|fallback``.

    Espelha a ordem de resolução de ``get_llm`` (sem instanciar nada)."""
    if os.getenv("RPG_FORCE_MOCK"):
        return "mock"
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider:
        if provider == "gemini" and not os.getenv("GOOGLE_API_KEY"):
            return "fallback" if os.getenv("RPG_NO_MOCK") else "mock"
        return f"legacy:{provider[:24]}"
    if not _any_key_available():
        return "fallback" if os.getenv("RPG_NO_MOCK") else "mock"
    return "routes"


def providers_with_key() -> list[str]:
    """Nomes (nunca valores) dos providers com chave configurada."""
    return sorted(p for p, env in PROVIDER_KEY_ENV.items() if os.getenv(env))
