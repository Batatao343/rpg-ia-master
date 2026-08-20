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
from llm_setup import (
    ModelTier,
    RoutedLLM,
    get_llm,
    set_llm_attempt_telemetry_hook,
    set_llm_telemetry_hook,
)


class _Tiny(BaseModel):
    value: str = "ok"


class _FakeClient:
    """Client falso: 'ok' devolve conteúdo/instância; 'raise' levanta no invoke."""

    def __init__(self, tag: str, behavior: str = "ok"):
        self.tag = tag
        self.behavior = behavior
        self._schema = None
        self._include_raw = False

    def with_structured_output(self, schema, *_a, **_k):
        self._schema = schema
        self._include_raw = bool(_k.get("include_raw"))
        return self

    def bind_tools(self, *_a, **_k):
        return self

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, _input):
        if self.behavior == "raise":
            raise RuntimeError(f"{self.tag} boom")
        if self.behavior == "payment":
            raise RuntimeError("402 Payment Required: insufficient balance")
        if self.behavior == "none":
            return None
        if self.behavior == "wrong":
            return AIMessage(content=f"structured invalido de {self.tag}")
        if self._schema is not None:
            if self._include_raw:
                if self.behavior == "raw_error":
                    return {
                        "raw": AIMessage(content="raw"),
                        "parsed": self._schema(),
                        "parsing_error": ValueError("parse falhou"),
                    }
                if self.behavior == "raw_wrong":
                    return {
                        "raw": AIMessage(content="raw"),
                        "parsed": AIMessage(content="tipo errado"),
                        "parsing_error": None,
                    }
                return {
                    "raw": AIMessage(content="raw"),
                    "parsed": self._schema(),
                    "parsing_error": None,
                }
            return self._schema()
        return AIMessage(content=f"resposta de {self.tag}")

    def stream(self, _input):
        if self.behavior == "raise":
            raise RuntimeError(f"{self.tag} boom-stream")
        if self.behavior == "yield_raise":
            yield AIMessage(content=f"parcial de {self.tag}")
            raise RuntimeError(f"{self.tag} boom-midstream")
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
    llm_setup.reset_llm_circuit_breakers()
    set_llm_telemetry_hook(None)
    set_llm_attempt_telemetry_hook(None)
    yield
    set_llm_telemetry_hook(None)
    set_llm_attempt_telemetry_hook(None)
    llm_setup._CLIENT_CACHE.clear()
    llm_setup.reset_llm_circuit_breakers()


def _install_fakes(monkeypatch, mapping: dict):
    """mapping: provider -> 'ok' | 'raise' | 'nokey' (build levanta)."""
    calls = []

    def fake_build(provider, model, temperature):
        calls.append((provider, model, temperature))
        beh = mapping.get(provider, "ok")
        if beh == "nokey":
            raise ValueError(f"{provider} key ausente")
        return _FakeClient(provider, beh)

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


def test_deepseek_usa_identificador_v4_nao_alias_descontinuado():
    for tier in (ModelTier.CLASSIFY, ModelTier.FAST, ModelTier.SMART):
        deepseek = [model for provider, model in llm_setup.ROUTES[tier]
                    if provider == "deepseek"]
        assert deepseek == ["deepseek-v4-flash"]
        assert "deepseek-chat" not in deepseek


def test_fast_usa_modelo_groq_disponivel():
    groq = [model for provider, model in llm_setup.ROUTES[ModelTier.FAST]
            if provider == "groq"]
    assert groq == ["openai/gpt-oss-120b"]
    assert "llama-3.3-70b-versatile" not in groq


def test_deepseek_v4_desliga_thinking_e_aplica_timeout(monkeypatch):
    import langchain_openai

    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12.5")

    llm_setup._build_openai("deepseek", 0.0, "deepseek-v4-flash")

    assert captured["timeout"] == 12.5
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}


def test_deepseek_timeout_curto_por_padrao(monkeypatch):
    import langchain_openai

    captured = {}
    monkeypatch.setattr(
        langchain_openai, "ChatOpenAI",
        lambda **kwargs: captured.update(kwargs) or object(),
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "11")

    llm_setup._build_openai("deepseek", 0.0, "deepseek-v4-flash")

    assert captured["timeout"] == 11.0


def test_timeout_global_tambem_alcanca_anthropic_e_gemini(monkeypatch):
    import langchain_anthropic
    import langchain_google_genai

    anthropic_kwargs = {}
    gemini_kwargs = {}
    monkeypatch.setattr(
        langchain_anthropic, "ChatAnthropic",
        lambda **kwargs: anthropic_kwargs.update(kwargs) or object(),
    )
    monkeypatch.setattr(
        langchain_google_genai, "ChatGoogleGenerativeAI",
        lambda **kwargs: gemini_kwargs.update(kwargs) or object(),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "7.5")

    llm_setup._build_anthropic(0.0, "claude-sonnet-5")
    llm_setup._build_gemini(0.0, "gemini-flash-latest")

    assert anthropic_kwargs["timeout"] == 7.5
    assert gemini_kwargs["request_timeout"] == 7.5


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


def test_falha_permanente_abre_circuito_ate_reset(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "payment", "p2": "ok"})
    attempts = []
    set_llm_attempt_telemetry_hook(attempts.append)
    routed = RoutedLLM(ModelTier.FAST, 0.1, [("p1", "m1"), ("p2", "m2")])

    assert routed.invoke([HumanMessage(content="primeira")]).content == "resposta de p2"
    assert [event.outcome for event in attempts] == ["invoke_error", "success"]

    attempts.clear()
    assert routed.invoke([HumanMessage(content="segunda")]).content == "resposta de p2"
    assert [event.outcome for event in attempts] == ["circuit_open", "success"]
    assert "402" in (attempts[0].error or "")

    llm_setup.reset_llm_circuit_breakers()
    attempts.clear()
    routed.invoke([HumanMessage(content="terceira")])
    assert attempts[0].outcome == "invoke_error"


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


@pytest.mark.parametrize("invalid_behavior", ["none", "wrong"])
def test_structured_output_invalido_tenta_proximo_provider(
        monkeypatch, invalid_behavior):
    _install_fakes(monkeypatch, {"p1": invalid_behavior, "p2": "ok"})
    tentativas = []
    sucessos_legados = []
    set_llm_attempt_telemetry_hook(tentativas.append)
    set_llm_telemetry_hook(lambda *args: sucessos_legados.append(args))

    engine = RoutedLLM(
        ModelTier.CLASSIFY, 0.0, [("p1", "m1"), ("p2", "m2")]
    ).with_structured_output(_Tiny)
    res = engine.invoke([HumanMessage(content="classifique")])

    assert isinstance(res, _Tiny)
    assert [event.outcome for event in tentativas] == [
        "invalid_structured", "success",
    ]
    assert tentativas[0].structured is True
    assert tentativas[1].fell_back is True
    assert [args[0] for args in sucessos_legados] == ["p2"], (
        "hook legado continua representando apenas sucesso validado"
    )


def test_structured_include_raw_exige_parsed_tipado_e_sem_erro(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "raw_error", "p2": "ok"})
    tentativas = []
    set_llm_attempt_telemetry_hook(tentativas.append)

    engine = RoutedLLM(
        ModelTier.CLASSIFY, 0.0, [("p1", "m1"), ("p2", "m2")]
    ).with_structured_output(_Tiny, include_raw=True)
    res = engine.invoke([HumanMessage(content="classifique")])

    assert isinstance(res, dict)
    assert isinstance(res["parsed"], _Tiny)
    assert res["parsing_error"] is None
    assert [event.outcome for event in tentativas] == [
        "invalid_structured", "success",
    ]


def test_plain_invoke_nao_rejeita_none(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "none", "p2": "ok"})
    tentativas = []
    set_llm_attempt_telemetry_hook(tentativas.append)

    res = RoutedLLM(
        ModelTier.FAST, 0.1, [("p1", "m1"), ("p2", "m2")]
    ).invoke([HumanMessage(content="oi")])

    assert res is None, "pos-condicao vale somente para structured output Pydantic"
    assert [event.outcome for event in tentativas] == ["success"]
    assert tentativas[0].structured is False


def test_hook_de_tentativas_observa_build_e_invoke_falhos(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "nokey", "p2": "raise", "p3": "ok"})
    tentativas = []
    set_llm_attempt_telemetry_hook(tentativas.append)

    res = RoutedLLM(
        ModelTier.FAST, 0.1,
        [("p1", "m1"), ("p2", "m2"), ("p3", "m3")],
    ).invoke([HumanMessage(content="oi")])

    assert res.content == "resposta de p3"
    assert [event.outcome for event in tentativas] == [
        "build_error", "invoke_error", "success",
    ]
    assert tentativas[0].provider == "p1"
    assert tentativas[0].attempt_index == 0
    assert tentativas[0].error
    assert tentativas[-1].attempt_index == 2
    assert tentativas[-1].fell_back is True


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
    tentativas = []
    set_llm_attempt_telemetry_hook(tentativas.append)
    routed = RoutedLLM(ModelTier.FAST, 0.1, [("p1", "m1"), ("p2", "m2")])
    chunks = list(routed.stream([HumanMessage(content="oi")]))
    assert chunks and chunks[-1].content == "resposta de p2"
    assert [event.outcome for event in tentativas] == ["stream_error", "success"]
    assert tentativas[-1].fell_back is True


def test_stream_so_emite_sucesso_depois_de_esgotar_iterador(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "ok"})
    tentativas = []
    sucessos_legados = []
    set_llm_attempt_telemetry_hook(tentativas.append)
    set_llm_telemetry_hook(lambda *args: sucessos_legados.append(args))
    routed = RoutedLLM(ModelTier.FAST, 0.1, [("p1", "m1")])

    stream = routed.stream([HumanMessage(content="oi")])
    first = next(stream)

    assert first.content == "resposta de p1"
    assert tentativas == []
    assert sucessos_legados == []

    assert list(stream) == []
    assert [event.outcome for event in tentativas] == ["success"]
    assert len(sucessos_legados) == 1


def test_stream_yield_depois_erro_nao_emite_falso_sucesso(monkeypatch):
    _install_fakes(monkeypatch, {"p1": "yield_raise", "p2": "ok"})
    tentativas = []
    sucessos_legados = []
    set_llm_attempt_telemetry_hook(tentativas.append)
    set_llm_telemetry_hook(lambda *args: sucessos_legados.append(args))
    routed = RoutedLLM(ModelTier.FAST, 0.1, [("p1", "m1"), ("p2", "m2")])

    chunks = list(routed.stream([HumanMessage(content="oi")]))

    assert [chunk.content for chunk in chunks] == ["parcial de p1"]
    assert [event.outcome for event in tentativas] == ["stream_error"]
    assert tentativas[0].error == "p1 boom-midstream"
    assert sucessos_legados == []


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


def test_openai_compat_structured_adiciona_instrucao_apos_ai_message(monkeypatch):
    seen = {}

    class RecordingClient(_FakeClient):
        def invoke(self, input):
            seen["input"] = input
            return super().invoke(input)

    monkeypatch.setattr(
        llm_setup, "_build_client",
        lambda p, m, t: RecordingClient(p),
    )
    original = [
        HumanMessage(content="pedido"),
        AIMessage(content="contexto narrativo"),
    ]

    result = RoutedLLM(
        ModelTier.SMART, 0.1, [("groq", "m")],
    ).with_structured_output(_Tiny).invoke(original)

    assert isinstance(result, _Tiny)
    assert original[-1].content == "contexto narrativo"
    assert isinstance(seen["input"][-1], HumanMessage)
    assert "saída estruturada" in seen["input"][-1].content


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
