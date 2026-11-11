"""SPEC-408: get_llm, is_simulated e llm_mode derivam do mesmo resolvedor (teste-tabela)."""

import itertools

import pytest

import llm_setup

_PROVIDERS = [None, "gemini", " Gemini ", "ollama", "foo"]
_KEYS = [None, "GOOGLE_API_KEY", "GROQ_API_KEY"]


def _env(monkeypatch, force, no_mock, provider, key):
    for var in ("RPG_FORCE_MOCK", "RPG_NO_MOCK", "LLM_PROVIDER", "RPG_ROUTES"):
        monkeypatch.delenv(var, raising=False)
    for var in set(llm_setup.PROVIDER_KEY_ENV.values()):
        monkeypatch.delenv(var, raising=False)
    if force:
        monkeypatch.setenv("RPG_FORCE_MOCK", "1")
    if no_mock:
        monkeypatch.setenv("RPG_NO_MOCK", "1")
    if provider:
        monkeypatch.setenv("LLM_PROVIDER", provider)
    if key:
        monkeypatch.setenv(key, "fake")
    llm_setup._ANNOUNCED.clear()


def _expected(force, no_mock, provider, key):
    """Oraculo independente: (tipo do LLM, llm_mode, simulated)."""
    p = (provider or "").strip().lower()
    if force:
        return "MockLLM", "mock", True
    if p == "gemini" and key != "GOOGLE_API_KEY" or (not p and key is None):
        return ("FallbackLLM", "fallback", False) if no_mock else ("MockLLM", "mock", True)
    if p and p not in ("gemini", "ollama", "openai", "openai_compat"):
        return "FallbackLLM", "fallback", False
    return "RoutedLLM", f"legacy:{p}" if p else "routes", False


@pytest.mark.parametrize(
    ("force", "no_mock", "provider", "key"),
    list(itertools.product([False, True], [False, True], _PROVIDERS, _KEYS)),
)
def test_get_llm_is_simulated_e_llm_mode_concordam(monkeypatch, force, no_mock, provider, key):
    _env(monkeypatch, force, no_mock, provider, key)
    kind, mode, simulated = _expected(force, no_mock, provider, key)
    assert type(llm_setup.get_llm()).__name__ == kind
    assert llm_setup.llm_mode() == mode
    assert llm_setup.is_simulated() is simulated


def test_provider_desconhecido_vira_fallback(monkeypatch):
    _env(monkeypatch, False, False, "foo", None)
    assert llm_setup.llm_mode() == "fallback"


# --- resolvedor puro (sem llm_setup) ---------------------------------------


def _resolve(monkeypatch, force, no_mock, provider, key):
    from services.llm_mode import resolve_mode

    _env(monkeypatch, force, no_mock, provider, key)
    return resolve_mode(
        set(llm_setup.PROVIDER_KEY_ENV.values()),
        lambda p: llm_setup._legacy_model(p, llm_setup.ModelTier.FAST) is not None,
    )


@pytest.mark.parametrize(
    ("args", "kind", "provider", "reason"),
    [
        ((True, False, None, None), "mock", "", "force_mock"),
        ((False, False, "gemini", None), "mock", "", "legacy_gemini_no_key"),
        ((False, True, "gemini", None), "fallback", "", "legacy_gemini_no_key"),
        ((False, False, " Gemini ", "GOOGLE_API_KEY"), "legacy", "gemini", ""),
        ((False, False, "foo", None), "fallback", "", "unknown_provider"),
        ((False, False, None, None), "mock", "", "no_keys"),
        ((False, True, None, None), "fallback", "", "no_keys"),
        ((False, False, None, "GROQ_API_KEY"), "routes", "", ""),
    ],
)
def test_resolve_mode(monkeypatch, args, kind, provider, reason):
    m = _resolve(monkeypatch, *args)
    assert (m.kind, m.provider, m.reason) == (kind, provider, reason)


def test_predicado_de_provider_conhecido_paridade():
    for p in (*llm_setup.PROVIDER_KEY_ENV, "ollama", "openai", "openai_compat", "foo"):
        known = llm_setup._legacy_model(p, llm_setup.ModelTier.FAST) is not None
        assert known == (p in ("gemini", "ollama", "openai", "openai_compat"))
