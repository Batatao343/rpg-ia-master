"""Perfis de rota e controle de capacidade exclusivos do playtest real."""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Mapping, Optional

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from llm_setup import ModelTier


_ROUTES_DIR = Path(__file__).with_name("routes")
_PROFILE_FILES = {
    "deepseek-paid": _ROUTES_DIR / "deepseek_paid.json",
    "groq-free": _ROUTES_DIR / "groq_free.json",
}


class ProviderPreflightError(RuntimeError):
    pass


class _PreflightResponse(BaseModel):
    status: str


def get_routes_profile(name: str) -> dict[str, list[list[str]]]:
    path = _PROFILE_FILES.get(str(name or ""))
    if path is None:
        raise KeyError(f"perfil de rotas desconhecido: {name!r}")
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


@contextmanager
def activated_routes_profile(name: Optional[str]) -> Iterator[None]:
    previous = os.environ.get("RPG_ROUTES")
    if name:
        path = _PROFILE_FILES.get(name)
        if path is None:
            raise KeyError(f"perfil de rotas desconhecido: {name!r}")
        os.environ["RPG_ROUTES"] = str(path.resolve())
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("RPG_ROUTES", None)
        else:
            os.environ["RPG_ROUTES"] = previous


class ProviderPacer:
    """Espaça sucessos Groq 120b sem alterar retry/fallback do motor."""

    def __init__(
        self,
        min_interval_seconds: float = 0.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval_seconds = max(0.0, float(min_interval_seconds or 0.0))
        self._sleep = sleeper

    def observe(self, event: object) -> None:
        if self.min_interval_seconds <= 0:
            return
        if isinstance(event, Mapping):
            provider = str(event.get("provider") or "")
            model = str(event.get("model") or "")
            status = str(event.get("status") or event.get("outcome") or "")
        else:
            provider = str(getattr(event, "provider", "") or "")
            model = str(getattr(event, "model", "") or "")
            status = str(
                getattr(event, "status", None)
                or getattr(event, "outcome", "")
                or ""
            )
        network_attempt = status in {
            "success", "invoke_error", "invalid_structured", "stream_error",
        }
        if provider != "groq" or model != "openai/gpt-oss-120b" or not network_attempt:
            return
        # O hook roda imediatamente após a tentativa; aguardar aqui garante que
        # a PRÓXIMA chamada 120b não forme burst acima do TPM.
        self._sleep(self.min_interval_seconds)


def preflight_real_routes(*, min_groq_interval_seconds: float = 0.0) -> dict:
    """Prova structured output real nos três tiers antes de criar a matriz."""
    import llm_setup

    pacer = ProviderPacer(min_groq_interval_seconds)
    events: list[dict] = []

    def hook(event: object) -> None:
        events.append({
            "provider": str(getattr(event, "provider", "") or ""),
            "model": str(getattr(event, "model", "") or ""),
            "tier": str(getattr(getattr(event, "tier", ""), "value", getattr(event, "tier", ""))),
            "status": str(getattr(event, "outcome", "") or ""),
        })
        pacer.observe(event)

    llm_setup.reset_llm_circuit_breakers()
    llm_setup.set_llm_attempt_telemetry_hook(hook)
    passed: list[str] = []
    try:
        for tier in (ModelTier.CLASSIFY, ModelTier.FAST, ModelTier.SMART):
            messages = [HumanMessage(content="Retorne status READY.")]
            if tier == ModelTier.SMART:
                messages = [
                    HumanMessage(content="Prepare uma resposta estruturada."),
                    AIMessage(content="Contexto de prefill para contrato SMART."),
                ]
            result = llm_setup.get_llm(
                temperature=0.0, tier=tier,
            ).with_structured_output(_PreflightResponse).invoke(messages)
            if not isinstance(result, _PreflightResponse):
                raise ProviderPreflightError(
                    f"tier {tier.value} sem structured output real"
                )
            passed.append(tier.value)
    finally:
        llm_setup.set_llm_attempt_telemetry_hook(None)
    return {"tiers": passed, "events": events}
