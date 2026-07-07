"""Spec roteamento-multi-provider — Etapa 1: infra de rotas + fallback.

Suíte 100% OFFLINE: providers são FAKE por monkeypatch em `llm_setup._build_client`
(o seam único de construção de client). Zero rede, zero chave real.

Convenção CRÍTICA testada aqui: quando TODOS os candidatos falham, o RoutedLLM
devolve um `AIMessage` (nunca levanta) — o guard `isinstance`/`try` do nó segue
obrigatório (o RoutedLLM não mascara isso).
"""
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

import llm_setup
from llm_setup import ModelTier, RoutedLLM, get_llm, set_llm_telemetry_hook


class _Tiny(BaseModel):
    value: str = "ok"


class _FakeClient:
    """Client falso: 'ok' devolve conteúdo/instância; 'raise' levanta no invoke."""

    def __init__(self, tag: str, behavior: str = "ok"):
        self.tag = tag
        self.behavior = behavior
        self._schema = None

    def with_structured_output(self, schema, *_a, **_k):
        self._schema = schema
        return self

    def bind_tools(self, *_a, **_k):
        return self

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, _input):
        if self.behavior == "raise":
            raise RuntimeError(f"{self.tag} boom")
        if self._schema is not None:
            return self._schema()
        return AIMessage(content=f"resposta de {self.tag}")

    def stream(self, _input):
        if self.behavior == "raise":
            raise RuntimeError(f"{self.tag} boom-stream")
        yield self.invoke(_input)


@pytest.fixture(autouse=True)
def _routing_env(monkeypatch):
    """Alcança o caminho ROUTES: sem mock forçado, sem provider legado, com >=1
    key presente (senão get_llm cai no MockLLM de zero-config). Cache limpo."""
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("RPG_ROUTES", raising=False)
    monkeypatch.delenv("RPG_NO_MOCK", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    llm_setup._CLIENT_CACHE.clear()
    set_llm_telemetry_hook(None)
    yield
    set_llm_telemetry_hook(None)
    llm_setup._CLIENT_CACHE.clear()


def _install_fakes(monkeypatch, mapping: dict):
    """mapping: provider -> 'ok' | 'raise' | 'nokey' (build levanta)."""
    calls = []

    def fake_build(provider, model, temperature):
        calls.append((provider, model, temperature))
        beh = mapping.get(provider, "ok")
        if beh == "nokey":
            raise ValueError(f"{provider} key ausente")
        return _FakeClient(provider, "raise" if beh == "raise" else "ok")

    monkeypatch.setattr(llm_setup, "_build_client", fake_build)
    return calls


# ---------------------------------------------------------------------------
# Enum + tabela
# ---------------------------------------------------------------------------
def test_classify_tier_existe():
    assert ModelTier.CLASSIFY.value == "classify"
    assert llm_setup.ROUTES.get(ModelTier.CLASSIFY), "ROUTES[CLASSIFY] não pode ser vazio"
    for tier in (ModelTier.CLASSIFY, ModelTier.FAST, ModelTier.SMART):
        assert llm_setup.ROUTES.get(tier), f"ROUTES[{tier}] vazio"


def test_get_llm_devolve_routed():
    llm = get_llm(tier=ModelTier.FAST)
    assert isinstance(llm, RoutedLLM)
    assert llm.candidates, "RoutedLLM sem candidatos"


# ---------------------------------------------------------------------------
# Fallback em tempo de invoke
# ---------------------------------------------------------------------------
def test_fallback_pula_candidato_que_levanta(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "raise", "p2": "ok"})
    eventos = []
    set_llm_telemetry_hook(lambda *a: eventos.append(a))

    routed = RoutedLLM(ModelTier.FAST, 0.1, [("p1", "m1"), ("p2", "m2")])
    res = routed.invoke([HumanMessage(content="oi")])

    assert res.content == "resposta de p2", "resposta deveria vir do 2º candidato"
    assert eventos, "hook de telemetria não disparou"
    provider, model, tier, latency_ms, fell_back = eventos[-1]
    assert provider == "p2" and model == "m2"
    assert tier == ModelTier.FAST
    assert isinstance(latency_ms, int) and latency_ms >= 0
    assert fell_back is True, "fell_back deveria ser True (2º candidato)"


def test_primeiro_candidato_ok_nao_e_fallback(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "ok"})
    eventos = []
    set_llm_telemetry_hook(lambda *a: eventos.append(a))

    routed = RoutedLLM(ModelTier.FAST, 0.1, [("p1", "m1"), ("p2", "m2")])
    res = routed.invoke([HumanMessage(content="oi")])

    assert res.content == "resposta de p1"
    assert eventos[-1][4] is False, "1º candidato não é fallback"


def test_todos_falham_devolve_aimessage(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "raise", "p2": "raise"})
    routed = RoutedLLM(ModelTier.SMART, 0.1, [("p1", "m1"), ("p2", "m2")])
    res = routed.invoke([HumanMessage(content="oi")])
    # NUNCA levanta — devolve AIMessage (convenção CRÍTICA)
    assert isinstance(res, AIMessage)
    # conteúdo vazio: sites de narração plain-invoke caem no fallback determinístico
    assert res.content == ""


def test_with_structured_output_todos_falham_nao_e_instancia(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "raise", "p2": "raise"})
    routed = RoutedLLM(ModelTier.CLASSIFY, 0.0, [("p1", "m1"), ("p2", "m2")])
    engine = routed.with_structured_output(_Tiny)
    res = engine.invoke([HumanMessage(content="classifique")])
    assert not isinstance(res, _Tiny), "guard do nó ainda é necessário"
    assert isinstance(res, AIMessage)


def test_structured_output_sucesso_devolve_instancia(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "ok"})
    routed = RoutedLLM(ModelTier.CLASSIFY, 0.0, [("p1", "m1")])
    engine = routed.with_structured_output(_Tiny)
    res = engine.invoke([HumanMessage(content="classifique")])
    assert isinstance(res, _Tiny)
    assert res.value == "ok"


def test_key_ausente_pula_provider(monkeypatch):
    calls = _install_fakes(monkeypatch, {"p1": "nokey", "p2": "ok"})
    routed = RoutedLLM(ModelTier.FAST, 0.1, [("p1", "m1"), ("p2", "m2")])
    res = routed.invoke([HumanMessage(content="oi")])
    assert res.content == "resposta de p2"
    assert ("p1", "m1", 0.1) in calls, "build do p1 foi tentado (e falhou por key)"


def test_build_cacheado(monkeypatch):
    calls = _install_fakes(monkeypatch, {"p1": "ok"})
    routed = RoutedLLM(ModelTier.FAST, 0.1, [("p1", "m1")])
    routed.invoke([HumanMessage(content="1")])
    routed.invoke([HumanMessage(content="2")])
    builds = [c for c in calls if c == ("p1", "m1", 0.1)]
    assert len(builds) == 1, f"cache falhou: {len(builds)} builds do mesmo candidato"


def test_stream_fallback(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "raise", "p2": "ok"})
    routed = RoutedLLM(ModelTier.FAST, 0.1, [("p1", "m1"), ("p2", "m2")])
    chunks = list(routed.stream([HumanMessage(content="oi")]))
    assert chunks and chunks[-1].content == "resposta de p2"


def test_import_error_pula_candidato(monkeypatch):
    """Dep faltando (ImportError no build) ⇒ candidato pulado, chain continua (R4/R5).
    É o mecanismo exato do Anthropic sem `--extra anthropic`."""

    def fake_build(provider, model, temperature):
        if provider == "anthropic":
            raise ImportError("langchain-anthropic não instalado")
        return _FakeClient(provider, "ok")

    monkeypatch.setattr(llm_setup, "_build_client", fake_build)
    routed = RoutedLLM(ModelTier.SMART, 0.1, [("anthropic", "claude-x"), ("groq", "kimi")])
    res = routed.invoke([HumanMessage(content="oi")])
    assert res.content == "resposta de groq"


class _RecFake(_FakeClient):
    """Registra os kwargs de with_structured_output para inspeção."""
    def __init__(self, tag, sink):
        super().__init__(tag, "ok")
        self._sink = sink

    def with_structured_output(self, schema, *a, **k):
        self._sink["kwargs"] = dict(k)
        return super().with_structured_output(schema, *a, **k)


def test_openai_compat_injeta_function_calling(monkeypatch):
    """Groq/compat: RoutedLLM força method=function_calling (strict json_schema
    rejeita dict aberto tipo StoryUpdate)."""
    sink = {}
    monkeypatch.setattr(llm_setup, "_build_client", lambda p, m, t: _RecFake(p, sink))
    RoutedLLM(ModelTier.FAST, 0.1, [("groq", "m")]).with_structured_output(_Tiny).invoke(
        [HumanMessage(content="x")])
    assert sink["kwargs"].get("method") == "function_calling"


def test_gemini_nao_recebe_function_calling(monkeypatch):
    """Gemini/Anthropic NÃO são forçados (têm structured output nativo próprio)."""
    sink = {}
    monkeypatch.setattr(llm_setup, "_build_client", lambda p, m, t: _RecFake(p, sink))
    RoutedLLM(ModelTier.FAST, 0.1, [("gemini", "m")]).with_structured_output(_Tiny).invoke(
        [HumanMessage(content="x")])
    assert "method" not in sink["kwargs"]


def test_method_explicito_nao_e_sobrescrito(monkeypatch):
    """Se o call site já escolheu um method, o RoutedLLM respeita."""
    sink = {}
    monkeypatch.setattr(llm_setup, "_build_client", lambda p, m, t: _RecFake(p, sink))
    RoutedLLM(ModelTier.FAST, 0.1, [("groq", "m")]).with_structured_output(
        _Tiny, method="json_mode").invoke([HumanMessage(content="x")])
    assert sink["kwargs"].get("method") == "json_mode"


def test_anthropic_pulado_sem_dep():
    """_build_anthropic sem a dep levanta ImportError (⇒ candidato pulado no RoutedLLM)."""
    try:
        import langchain_anthropic  # noqa: F401
        pytest.skip("langchain-anthropic instalado — caso SEM dep não aplicável")
    except ImportError:
        pass
    with pytest.raises(ImportError):
        llm_setup._build_anthropic(0.1, "claude-sonnet-5")


# ---------------------------------------------------------------------------
# Overrides de env (R8)
# ---------------------------------------------------------------------------
def test_force_mock_curto_circuita(monkeypatch):
    monkeypatch.setenv("RPG_FORCE_MOCK", "1")
    llm = get_llm(tier=ModelTier.FAST)
    assert getattr(llm, "is_mock", False), "RPG_FORCE_MOCK deveria devolver MockLLM"


def test_llm_provider_legado_forca_provider_unico(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    llm = get_llm(tier=ModelTier.SMART)
    assert isinstance(llm, RoutedLLM)
    assert len(llm.candidates) == 1, "provider legado = 1 candidato só"
    assert llm.candidates[0][0] == "ollama", "ignorou ROUTES, usou ollama"


def test_rpg_routes_override(monkeypatch, tmp_path):
    rotas = {
        "classify": [["glm", "glm-x"], ["gemini", "gemini-flash-lite-latest"]],
        "fast": [["minimax", "m-fast"]],
        "smart": [["anthropic", "claude-x"]],
    }
    p = tmp_path / "rotas.json"
    p.write_text(json.dumps(rotas), encoding="utf-8")
    monkeypatch.setenv("RPG_ROUTES", str(p))

    llm = get_llm(tier=ModelTier.CLASSIFY)
    assert llm.candidates == [("glm", "glm-x"), ("gemini", "gemini-flash-lite-latest")]
    assert get_llm(tier=ModelTier.SMART).candidates == [("anthropic", "claude-x")]


def test_zero_config_cai_no_mock(monkeypatch):
    """Sem NENHUMA key e sem RPG_NO_MOCK → MockLLM (newcomer roda sem configurar)."""
    for env in set(llm_setup.PROVIDER_KEY_ENV.values()):
        monkeypatch.delenv(env, raising=False)
    llm = get_llm(tier=ModelTier.FAST)
    assert getattr(llm, "is_mock", False), "zero-config deveria cair no MockLLM"


def test_zero_config_com_no_mock_e_fallback(monkeypatch):
    """RPG_NO_MOCK sem key → FallbackLLM (não MockLLM)."""
    for env in set(llm_setup.PROVIDER_KEY_ENV.values()):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("RPG_NO_MOCK", "1")
    llm = get_llm(tier=ModelTier.FAST)
    assert getattr(llm, "is_fallback", False), "RPG_NO_MOCK sem key → FallbackLLM"
