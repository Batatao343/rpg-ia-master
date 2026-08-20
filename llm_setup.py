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
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable, Literal, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from pydantic import BaseModel

if TYPE_CHECKING:
    from langchain_core.language_models import BaseLanguageModel

load_dotenv(override=True)  # .env é a fonte canônica das keys (sobrepõe env var do SO)

_LOG = logging.getLogger("rpg.llm")

Candidate = tuple  # (provider: str, model: str)


class ModelTier(Enum):
    CLASSIFY = "classify"   # menor/rápido: router, parse estruturado (temp 0)
    FAST = "fast"           # narração/roleplay (output-heavy)
    SMART = "smart"         # coerência: campanha, archivist, criador de ficha


# ---------------------------------------------------------------------------
LLMAttemptOutcome = Literal[
    "build_error",
    "circuit_open",
    "invoke_error",
    "stream_error",
    "invalid_structured",
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
    error: Optional[str]
    structured: bool


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
_OPENAI_COMPAT_PROVIDERS = {"groq", "qwen", "glm", "minimax", "kimi", "deepseek",
                           "openai", "openai_compat"}

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
        ("minimax", "MiniMax-M2.5"),
        ("qwen", "qwen-plus"),
        ("groq", "openai/gpt-oss-120b"),       # free, narração; function_calling
        ("gemini", "gemini-flash-latest"),
    ],
    ModelTier.SMART: [
        ("deepseek", "deepseek-v4-flash"),
        ("groq", "openai/gpt-oss-120b"),       # free, coerência; function_calling
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
        raise ImportError("langchain-openai não instalado (uv sync --extra openai)") from e

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
    if provider == "deepseek" and model.startswith("deepseek-v4-"):
        # `deepseek-chat` era o alias não-pensante do Flash. O alias foi retirado
        # em 2026-07-24; preservar o modo evita raciocínio oculto/latência extra e
        # mantém function calling previsível nos schemas Pydantic.
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
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


def _open_circuit_if_permanent(provider: str, model: str,
                               exc: BaseException) -> None:
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
_TELEMETRY_HOOK: Optional[Callable[[str, str, ModelTier, int, bool], None]] = None
_ATTEMPT_TELEMETRY_HOOK: Optional[Callable[[LLMAttemptEvent], None]] = None


def set_llm_telemetry_hook(fn: Optional[Callable[[str, str, ModelTier, int, bool], None]]) -> None:
    """Registra callback `(provider, model, tier, latency_ms, fell_back)` disparado
    após cada invoke bem-sucedido. `None` desliga. Custo zero se não registrado."""
    global _TELEMETRY_HOOK
    _TELEMETRY_HOOK = fn


def set_llm_attempt_telemetry_hook(
        fn: Optional[Callable[[LLMAttemptEvent], None]]) -> None:
    """Registra callback estruturado para CADA candidato tentado.

    Diferente do hook legado success-only, este recebe também build/invoke
    errors e retornos estruturados inválidos. ``None`` desliga.
    """
    global _ATTEMPT_TELEMETRY_HOOK
    _ATTEMPT_TELEMETRY_HOOK = fn


def _emit_telemetry(provider: str, model: str, tier: ModelTier, latency_ms: int, fell_back: bool) -> None:
    hook = _TELEMETRY_HOOK
    if hook is None:
        return
    try:
        hook(provider, model, tier, latency_ms, fell_back)
    except Exception as e:  # telemetria NUNCA derruba o turno
        _LOG.warning("telemetry hook falhou: %s", e)


def _emit_attempt_telemetry(event: LLMAttemptEvent) -> None:
    hook = _ATTEMPT_TELEMETRY_HOOK
    if hook is None:
        return
    try:
        hook(event)
    except Exception as e:  # telemetria NUNCA derruba o turno
        _LOG.warning("attempt telemetry hook falhou: %s", e)


# ---------------------------------------------------------------------------
# RoutedLLM — embrulha candidatos ordenados; fallback em tempo de invoke
# ---------------------------------------------------------------------------
class RoutedLLM:
    """Tenta os candidatos em ordem; o 1º que responde vence. Último recurso:
    `AIMessage(content="")` (nunca levanta) — guard do nó segue obrigatório.

    `with_structured_output`/`bind_tools`/`with_retry` acumulam transformações
    reaplicadas a CADA candidato dentro do loop (cada provider resolve o método)."""

    is_fallback = False   # é um roteador vivo, não o fallback de erro
    is_mock = False

    def __init__(self, tier: ModelTier, temperature: float, candidates: list,
                 _transforms: Optional[list] = None):
        self.tier = tier
        self.temperature = temperature
        self.candidates = [tuple(c) for c in candidates]
        self._transforms = _transforms or []

    def _clone_with(self, transform) -> "RoutedLLM":
        return RoutedLLM(self.tier, self.temperature, self.candidates,
                         self._transforms + [transform])

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
            if (name == "with_structured_output" and provider in _OPENAI_COMPAT_PROVIDERS
                    and "method" not in k):
                k = {**k, "method": "function_calling"}
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

    def _validate_structured_result(self, result) -> tuple[bool, Optional[str], bool]:
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

    def invoke(self, input):
        errors = []
        for idx, (provider, model) in enumerate(self.candidates):
            fell_back = idx > 0
            circuit_reason = _OPEN_CIRCUITS.get((provider, model))
            if circuit_reason:
                errors.append(f"{provider}:{model} circuit:{circuit_reason}")
                _emit_attempt_telemetry(LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=0,
                    fell_back=fell_back,
                    outcome="circuit_open",
                    error=circuit_reason,
                    structured=self._pydantic_structured_contract() is not None,
                ))
                continue
            build_t0 = time.perf_counter()
            try:
                client = _get_cached_client(provider, model, self.temperature)
            except Exception as e:
                latency_ms = int((time.perf_counter() - build_t0) * 1000)
                errors.append(f"{provider}:{model} build:{e}")
                _LOG.warning("build falhou %s:%s (%s)", provider, model, e)
                _emit_attempt_telemetry(LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=latency_ms,
                    fell_back=fell_back,
                    outcome="build_error",
                    error=str(e),
                    structured=self._pydantic_structured_contract() is not None,
                ))
                _open_circuit_if_permanent(provider, model, e)
                continue
            try:
                client = self._apply(client, provider)
            except Exception as e:
                latency_ms = int((time.perf_counter() - build_t0) * 1000)
                errors.append(f"{provider}:{model} apply:{e}")
                _LOG.warning("apply falhou %s:%s (%s)", provider, model, e)
                _emit_attempt_telemetry(LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=latency_ms,
                    fell_back=fell_back,
                    outcome="build_error",
                    error=f"apply: {e}",
                    structured=self._pydantic_structured_contract() is not None,
                ))
                _open_circuit_if_permanent(provider, model, e)
                continue
            t0 = time.perf_counter()
            try:
                result = client.invoke(input)
                latency_ms = int((time.perf_counter() - t0) * 1000)
            except Exception as e:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                errors.append(f"{provider}:{model} invoke:{e}")
                _LOG.warning("invoke falhou %s:%s (%s)", provider, model, e)
                _emit_attempt_telemetry(LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=latency_ms,
                    fell_back=fell_back,
                    outcome="invoke_error",
                    error=str(e),
                    structured=self._pydantic_structured_contract() is not None,
                ))
                _open_circuit_if_permanent(provider, model, e)
                continue
            valid, validation_error, structured = self._validate_structured_result(result)
            if not valid:
                errors.append(
                    f"{provider}:{model} structured:{validation_error}"
                )
                _LOG.warning(
                    "structured inválido %s:%s (%s)",
                    provider,
                    model,
                    validation_error,
                )
                _emit_attempt_telemetry(LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=latency_ms,
                    fell_back=fell_back,
                    outcome="invalid_structured",
                    error=validation_error,
                    structured=structured,
                ))
                continue
            _emit_attempt_telemetry(LLMAttemptEvent(
                provider=provider,
                model=model,
                tier=self.tier,
                attempt_index=idx,
                latency_ms=latency_ms,
                fell_back=fell_back,
                outcome="success",
                error=None,
                structured=structured,
            ))
            _emit_telemetry(provider, model, self.tier, latency_ms, fell_back)
            return result
        _LOG.warning("tier %s: todos os candidatos falharam: %s",
                     self.tier.value, "; ".join(errors))
        # conteúdo vazio: sites de narração plain-invoke caem no fallback determinístico;
        # sites structured batem no guard (isinstance/try) do nó.
        return AIMessage(content="")

    def stream(self, input):
        errors = []
        for idx, (provider, model) in enumerate(self.candidates):
            fell_back = idx > 0
            structured = self._pydantic_structured_contract() is not None
            circuit_reason = _OPEN_CIRCUITS.get((provider, model))
            if circuit_reason:
                errors.append(f"{provider}:{model} circuit:{circuit_reason}")
                _emit_attempt_telemetry(LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=0,
                    fell_back=fell_back,
                    outcome="circuit_open",
                    error=circuit_reason,
                    structured=structured,
                ))
                continue
            build_t0 = time.perf_counter()
            try:
                client = _get_cached_client(provider, model, self.temperature)
                client = self._apply(client, provider)
            except Exception as e:
                latency_ms = int((time.perf_counter() - build_t0) * 1000)
                errors.append(f"{provider}:{model} build:{e}")
                _emit_attempt_telemetry(LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=latency_ms,
                    fell_back=fell_back,
                    outcome="build_error",
                    error=str(e),
                    structured=structured,
                ))
                _open_circuit_if_permanent(provider, model, e)
                continue
            t0 = time.perf_counter()
            try:
                it = iter(client.stream(input))
                first = next(it)
            except StopIteration:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                _emit_attempt_telemetry(LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=latency_ms,
                    fell_back=fell_back,
                    outcome="success",
                    error=None,
                    structured=structured,
                ))
                _emit_telemetry(provider, model, self.tier, latency_ms, fell_back)
                return
            except Exception as e:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                errors.append(f"{provider}:{model} stream:{e}")
                _LOG.warning("stream falhou %s:%s (%s)", provider, model, e)
                _emit_attempt_telemetry(LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=latency_ms,
                    fell_back=fell_back,
                    outcome="stream_error",
                    error=str(e),
                    structured=structured,
                ))
                _open_circuit_if_permanent(provider, model, e)
                continue
            yield first
            try:
                for chunk in it:
                    yield chunk
            except Exception as e:  # falha no meio do stream: encerra o que veio
                _LOG.warning("stream interrompido %s:%s (%s)", provider, model, e)
                latency_ms = int((time.perf_counter() - t0) * 1000)
                _emit_attempt_telemetry(LLMAttemptEvent(
                    provider=provider,
                    model=model,
                    tier=self.tier,
                    attempt_index=idx,
                    latency_ms=latency_ms,
                    fell_back=fell_back,
                    outcome="stream_error",
                    error=str(e),
                    structured=structured,
                ))
                _open_circuit_if_permanent(provider, model, e)
                return
            latency_ms = int((time.perf_counter() - t0) * 1000)
            _emit_attempt_telemetry(LLMAttemptEvent(
                provider=provider,
                model=model,
                tier=self.tier,
                attempt_index=idx,
                latency_ms=latency_ms,
                fell_back=fell_back,
                outcome="success",
                error=None,
                structured=structured,
            ))
            _emit_telemetry(provider, model, self.tier, latency_ms, fell_back)
            return
        _LOG.warning("tier %s (stream): todos falharam: %s", self.tier.value, "; ".join(errors))
        yield AIMessage(content="")


# ---------------------------------------------------------------------------
# Resolução de rotas + overrides
# ---------------------------------------------------------------------------
def _any_key_available() -> bool:
    return any(os.getenv(env) for env in set(PROVIDER_KEY_ENV.values()))


def _load_routes() -> dict:
    """ROUTES default ou override por arquivo (RPG_ROUTES, JSON)."""
    path = os.getenv("RPG_ROUTES")
    if not path:
        return ROUTES
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        parsed = {ModelTier(name): [tuple(c) for c in cands] for name, cands in raw.items()}
        return {**ROUTES, **parsed}
    except Exception as e:
        _LOG.warning("RPG_ROUTES inválido (%s); usando ROUTES default", e)
        return ROUTES


# Modelos por-tier do provider legado (LLM_PROVIDER=<x>). Gemini mantém o
# comportamento atual; ollama/openai leem env por-tier.
def _legacy_model(provider: str, tier: ModelTier) -> Optional[str]:
    if provider == "gemini":
        return {
            ModelTier.CLASSIFY: "gemini-flash-lite-latest",
            ModelTier.FAST: "gemini-flash-latest",
            ModelTier.SMART: "gemini-pro-latest",
        }[tier]
    if provider == "ollama":
        return {
            ModelTier.CLASSIFY: os.getenv("OLLAMA_MODEL_CLASSIFY",
                                          os.getenv("OLLAMA_MODEL_FAST", "llama3.2")),
            ModelTier.FAST: os.getenv("OLLAMA_MODEL_FAST", "llama3.2"),
            ModelTier.SMART: os.getenv("OLLAMA_MODEL_SMART", "llama3.1"),
        }[tier]
    if provider in ("openai", "openai_compat"):
        return {
            ModelTier.CLASSIFY: os.getenv("OPENAI_MODEL_CLASSIFY",
                                          os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini")),
            ModelTier.FAST: os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini"),
            ModelTier.SMART: os.getenv("OPENAI_MODEL_SMART", "gpt-4o"),
        }[tier]
    return None


def _legacy_get_llm(provider: str, temperature: float, tier: ModelTier):
    """LLM_PROVIDER=<x> força TODOS os tiers a um único provider (ignora ROUTES)."""
    # Gemini sem chave preserva o comportamento atual (jogável offline via MockLLM).
    if provider == "gemini" and not os.getenv("GOOGLE_API_KEY"):
        if os.getenv("RPG_NO_MOCK"):
            return FallbackLLM("GOOGLE_API_KEY não configurada")
        from mock_llm import MockLLM
        return MockLLM(temperature=temperature)

    model = _legacy_model(provider, tier)
    if model is None:
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
        from mock_llm import MockLLM
        return MockLLM(temperature=temperature)

    provider_override = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider_override:
        return _legacy_get_llm(provider_override, temperature, tier)

    if not _any_key_available():
        if os.getenv("RPG_NO_MOCK"):
            return FallbackLLM("Nenhuma key de provider configurada")
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
