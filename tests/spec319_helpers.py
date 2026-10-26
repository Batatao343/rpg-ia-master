"""SPEC-319: provider falso com streaming de tool call (deltas de argumentos)."""

from __future__ import annotations

import json
import time

from langchain_core.messages import AIMessage, AIMessageChunk

import llm_setup
from llm_setup import ModelTier, RoutedLLM


def tool_args(narrative: str, **extra) -> str:
    return json.dumps({"narrative": narrative, **extra}, ensure_ascii=False)


def slices(raw: str, size: int = 6) -> list[str]:
    return [raw[i : i + size] for i in range(0, len(raw), size)]


class FakeStreamClient:
    """`bind_tools(...).stream(...)` emitindo `tool_call_chunks` como os providers OpenAI-compat."""

    def __init__(
        self,
        deltas: list[str],
        *,
        fail_after: int | None = None,
        fail_before: bool = False,
        first_delay: float = 0.0,
        gap: float = 0.0,
    ) -> None:
        self.deltas = deltas
        self.fail_after = fail_after
        self.fail_before = fail_before
        self.first_delay = first_delay
        self.gap = gap
        self.calls = 0
        self.bound = None

    def bind_tools(self, tools, **kwargs):
        self.bound = (tools, kwargs)
        return self

    def stream(self, _input):
        self.calls += 1
        if self.fail_before:
            raise RuntimeError("boom before first chunk")
        if self.first_delay:
            time.sleep(self.first_delay)
        for i, delta in enumerate(self.deltas):
            if self.fail_after is not None and i >= self.fail_after:
                raise RuntimeError("boom mid stream")
            if i and self.gap:
                time.sleep(self.gap)
            yield AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {
                        "name": "StoryUpdate" if i == 0 else None,
                        "args": delta,
                        "id": None,
                        "index": 0,
                    }
                ],
            )


def install(monkeypatch, clients: dict[str, FakeStreamClient]) -> None:
    llm_setup.reset_llm_circuit_breakers()
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda p, m, t: clients[p])


def routed(candidates, tier: ModelTier = ModelTier.FAST) -> RoutedLLM:
    return RoutedLLM(tier, 0.7, list(candidates))


def is_error_message(result: object) -> bool:
    return isinstance(result, AIMessage)
