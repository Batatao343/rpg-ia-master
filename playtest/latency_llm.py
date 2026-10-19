"""SPEC-200 R12: LLM simulado com latencia injetada e DETERMINISTICA (so playtest/scripts).

Nunca importado pelo runtime de producao. Envolve o ``get_llm`` (que sob
``RPG_FORCE_MOCK=1`` devolve o MockLLM) e, a cada chamada:

* sorteia a latencia por PRNG semeado ``(seed, jornada, rep, chamada)``;
* modo ``virtual``: avanca o ``FakeClock`` (zero espera real);
* modo ``scaled``: ``time.sleep(ms * escala)`` (smoke de browser);
* emite ``LLMAttemptEvent`` para que contagens/fases/fallbacks existam na telemetria.

Perfis versionados: ``flat-fast``, ``typical``, ``slow-tail``, ``fallback-once``.
"""

from __future__ import annotations

import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections.abc import Callable

from llm_setup import LLMAttemptEvent, ModelTier, _emit_attempt_telemetry, _emit_telemetry

PROFILE_VERSION = 1

# tier -> (base_ms, jitter_fraction)
_TYPICAL = {"classify": (300, 0.20), "fast": (2500, 0.20), "smart": (4000, 0.20)}

PROFILES: dict[str, dict[str, Any]] = {
    "flat-fast": {
        "tiers": {"classify": (50, 0.0), "fast": (100, 0.0), "smart": (150, 0.0)},
        "tail_prob": 0.0,
        "tail_mult": 1.0,
        "fallback_once": False,
    },
    "typical": {"tiers": _TYPICAL, "tail_prob": 0.0, "tail_mult": 1.0, "fallback_once": False},
    # cauda longa: 10% das chamadas custam 4x (exercita o p95)
    "slow-tail": {"tiers": _TYPICAL, "tail_prob": 0.10, "tail_mult": 4.0, "fallback_once": False},
    # 1a tentativa de cada tier, em cada turno, falha e cai para o proximo candidato
    "fallback-once": {"tiers": _TYPICAL, "tail_prob": 0.0, "tail_mult": 1.0, "fallback_once": True},
}

PRIMARY = ("deepseek", "mock-latency-primary")
SECONDARY = ("groq", "mock-latency-fallback")


def _tier_key(tier: Any) -> str:
    return str(getattr(tier, "value", tier) or "fast").lower()


@dataclass
class LatencyContext:
    """Estado da injecao; um por run (os campos de turno sao reiniciados por turno)."""

    profile: str = "typical"
    seed: int = 0
    mode: str = "virtual"  # virtual | scaled
    scale: float = 1.0
    clock: Callable[[], float] | None = None  # FakeClock (tem .advance) no modo virtual
    journey: str = ""
    rep: int = 0
    call_index: int = 0
    failed_tiers: set = field(default_factory=set)
    total_injected_ms: int = 0

    def __post_init__(self) -> None:
        if self.profile not in PROFILES:
            raise ValueError(f"perfil de latencia desconhecido: {self.profile}")
        if self.mode not in {"virtual", "scaled"}:
            raise ValueError("mode deve ser virtual|scaled")

    def start_turn(self, journey: str, rep: int) -> None:
        self.journey, self.rep, self.call_index = journey, rep, 0
        self.failed_tiers = set()

    def _rng(self, call: int) -> random.Random:
        return random.Random(f"{self.seed}|{self.journey}|{self.rep}|{call}")

    def sample_ms(self, tier: str, *, fraction: float = 1.0) -> int:
        spec = PROFILES[self.profile]
        base, jitter = spec["tiers"].get(tier, spec["tiers"]["fast"])
        call = self.call_index
        self.call_index += 1
        rng = self._rng(call)
        ms = base * (1.0 + (rng.uniform(-1.0, 1.0) * jitter))
        if spec["tail_prob"] and rng.random() < spec["tail_prob"]:
            ms *= spec["tail_mult"]
        return max(1, int(round(ms * fraction)))

    def spend(self, ms: int) -> None:
        self.total_injected_ms += ms
        if self.mode == "virtual":
            advance = getattr(self.clock, "advance", None)
            if advance is not None:
                advance(ms / 1000.0)
        else:
            time.sleep(ms * self.scale / 1000.0)

    def run_call(self, tier: Any, structured: bool) -> None:
        """Injeta a latencia (e eventos de tentativa) de UMA chamada logica ao LLM."""
        key = _tier_key(tier)
        model_tier = tier if isinstance(tier, ModelTier) else ModelTier(key)
        spec = PROFILES[self.profile]
        index = 0
        fell_back = False
        if spec["fallback_once"] and key not in self.failed_tiers:
            self.failed_tiers.add(key)
            failed_ms = self.sample_ms(key, fraction=0.5)
            self.spend(failed_ms)
            _emit_attempt_telemetry(
                LLMAttemptEvent(
                    provider=PRIMARY[0],
                    model=PRIMARY[1],
                    tier=model_tier,
                    attempt_index=0,
                    latency_ms=failed_ms,
                    fell_back=False,
                    outcome="invoke_error",
                    error="InjectedFailure",
                    structured=structured,
                )
            )
            index, fell_back = 1, True
        provider, model = SECONDARY if fell_back else PRIMARY
        ms = self.sample_ms(key)
        self.spend(ms)
        _emit_attempt_telemetry(
            LLMAttemptEvent(
                provider=provider,
                model=model,
                tier=model_tier,
                attempt_index=index,
                latency_ms=ms,
                fell_back=fell_back,
                outcome="success",
                error=None,
                structured=structured,
            )
        )
        _emit_telemetry(provider, model, model_tier, ms, fell_back)


class _StructuredLatency:
    def __init__(self, inner: Any, tier: Any, ctx: LatencyContext) -> None:
        self._inner, self._tier, self._ctx = inner, tier, ctx

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, messages, *args, **kwargs):
        self._ctx.run_call(self._tier, True)
        return self._inner.invoke(messages, *args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


class LatencyInjectingLLM:
    def __init__(self, inner: Any, tier: Any, ctx: LatencyContext) -> None:
        self._inner, self._tier, self._ctx = inner, tier, ctx

    def with_structured_output(self, *args, **kwargs):
        return _StructuredLatency(
            self._inner.with_structured_output(*args, **kwargs), self._tier, self._ctx
        )

    def with_retry(self, *_a, **_k):
        return self

    def bind_tools(self, *_a, **_k):
        return self

    def invoke(self, messages, *args, **kwargs):
        self._ctx.run_call(self._tier, False)
        return self._inner.invoke(messages, *args, **kwargs)

    def stream(self, messages, *args, **kwargs):
        yield self.invoke(messages, *args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


_installed: list[tuple] = []
_ORIGINAL: Callable[..., Any] | None = None
_CURRENT: LatencyContext | None = None


def _shim(temperature: float = 0.1, tier: ModelTier = ModelTier.FAST):
    """Unico ponto de injecao. Fica INERTE (devolve o LLM original) fora de um
    ``install``: modulos importados tardiamente durante um run guardam esta
    referencia e nao podem vazar o contexto do run anterior."""
    llm = _ORIGINAL(temperature, tier)
    ctx = _CURRENT
    return llm if ctx is None else LatencyInjectingLLM(llm, tier, ctx)


def install(ctx: LatencyContext) -> None:
    """Troca ``get_llm`` em todo modulo que o importou. Reversivel via ``uninstall``."""
    global _ORIGINAL, _CURRENT
    import llm_setup

    if _ORIGINAL is None:
        _ORIGINAL = llm_setup.get_llm
    _CURRENT = ctx
    for module in list(sys.modules.values()):
        try:
            current = getattr(module, "get_llm", None)
            if current is _ORIGINAL:
                _installed.append((module, _ORIGINAL))
                module.get_llm = _shim
        except Exception:
            continue


def uninstall() -> None:
    global _CURRENT
    _CURRENT = None
    while _installed:
        module, original = _installed.pop()
        try:
            module.get_llm = original
        except Exception:
            pass
