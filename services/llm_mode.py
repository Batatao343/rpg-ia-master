"""SPEC-408: resolvedor puro do modo do LLM (mock | fallback | legacy | routes).

Única fonte da decisão: `get_llm`, `is_simulated` e `llm_mode` (em `llm_setup`)
derivam daqui. Só lê `os.environ`; não instancia LLM, não loga, não importa `llm_setup`.
"""

import os
from collections.abc import Callable, Iterable
from typing import NamedTuple


class LlmMode(NamedTuple):
    kind: str  # mock | fallback | legacy | routes
    provider: str = ""  # normalizado; em kind == "legacy" e em unknown_provider
    reason: str = ""  # force_mock | legacy_gemini_no_key | unknown_provider | no_keys | ""


def resolve_mode(key_envs: Iterable[str], is_known_provider: Callable[[str], bool]) -> LlmMode:
    """Ordem: RPG_FORCE_MOCK -> LLM_PROVIDER -> sem chave -> rotas."""
    no_mock = bool(os.getenv("RPG_NO_MOCK"))
    sem_chave = "fallback" if no_mock else "mock"
    if os.getenv("RPG_FORCE_MOCK"):
        return LlmMode("mock", reason="force_mock")
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider:
        if provider == "gemini" and not os.getenv("GOOGLE_API_KEY"):
            return LlmMode(sem_chave, reason="legacy_gemini_no_key")
        if not is_known_provider(provider):
            return LlmMode("fallback", provider, "unknown_provider")
        return LlmMode("legacy", provider)
    if not any(os.getenv(env) for env in key_envs):
        return LlmMode(sem_chave, reason="no_keys")
    return LlmMode("routes")
