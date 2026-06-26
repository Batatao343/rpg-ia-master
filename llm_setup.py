import os
from enum import Enum
from typing import TYPE_CHECKING
from dotenv import load_dotenv
from langchain_core.messages import AIMessage

if TYPE_CHECKING:
    from langchain_core.language_model import BaseLanguageModel

load_dotenv(override=True)  # .env é a fonte canônica da key (sobrepõe env var do SO)


class ModelTier(Enum):
    FAST = "fast"
    SMART = "smart"


class FallbackLLM:
    """Retorno seguro quando o provider não pode ser inicializado."""

    def __init__(self, error_message: str):
        self.error_message = error_message
        self.is_fallback = True

    def bind_tools(self, *_args, **_kwargs):
        return self

    def with_structured_output(self, *_args, **_kwargs):
        return self

    def with_retry(self, *_args, **_kwargs):
        return self

    def invoke(self, _input):
        return AIMessage(content=self.error_message)

    def stream(self, _input):
        """Yield single AIMessage for compatibility with streaming calls."""
        yield self.invoke(_input)


def _build_gemini(temperature: float, tier: ModelTier) -> "BaseLanguageModel":
    """Constrói ChatGoogleGenerativeAI com settings de segurança customizados."""
    from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory

    model = "gemini-flash-latest" if tier == ModelTier.FAST else "gemini-pro-latest"
    max_retries = 0  # Fail-fast: 429 quota não é transitório

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        max_retries=max_retries,
        safety_settings={
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        }
    )


def _build_ollama(temperature: float, tier: ModelTier) -> "BaseLanguageModel":
    """Constrói ChatOllama para LLM local via Ollama."""
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        raise ImportError(
            "langchain-ollama não está instalado. "
            "Instale com: uv sync --extra ollama"
        )

    models = {
        ModelTier.FAST: os.getenv("OLLAMA_MODEL_FAST", "llama3.2"),
        ModelTier.SMART: os.getenv("OLLAMA_MODEL_SMART", "llama3.1"),
    }
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    return ChatOllama(
        model=models[tier],
        base_url=base_url,
        temperature=temperature,
    )


def _build_openai(temperature: float, tier: ModelTier) -> "BaseLanguageModel":
    """Constrói ChatOpenAI para OpenAI ou compatíveis (Qwen, LM Studio, etc.)."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ImportError(
            "langchain-openai não está instalado. "
            "Instale com: uv sync --extra openai"
        )

    models = {
        ModelTier.FAST: os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini"),
        ModelTier.SMART: os.getenv("OPENAI_MODEL_SMART", "gpt-4o"),
    }
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL") or None

    if not api_key:
        raise ValueError("OPENAI_API_KEY não configurada")

    return ChatOpenAI(
        model=models[tier],
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_retries=0,
    )


_PROVIDERS = {
    "gemini": _build_gemini,
    "ollama": _build_ollama,
    "openai": _build_openai,
    "openai_compat": _build_openai,  # mesmo builder, usa OPENAI_BASE_URL customizado
}


def get_llm(temperature: float = 0.1, tier: ModelTier = ModelTier.FAST):
    """Retorna uma instância LLM configurada ou fallback resiliente.

    Suporta múltiplos providers (Gemini, Ollama, OpenAI) via LLM_PROVIDER env var.
    Modo simulado (MockLLM) ativado por RPG_FORCE_MOCK=1 ou quando key está faltando.
    """
    force_mock = bool(os.getenv("RPG_FORCE_MOCK"))
    provider_name = os.getenv("LLM_PROVIDER", "gemini").lower()

    # Modo SIMULADO: MockLLM com dados fictícios (jogável sem chave/rede)
    if force_mock:
        from mock_llm import MockLLM
        return MockLLM(temperature=temperature)

    # Gemini: requer chave obrigatoriamente
    if provider_name == "gemini":
        if not os.getenv("GOOGLE_API_KEY"):
            if os.getenv("RPG_NO_MOCK"):
                return FallbackLLM("GOOGLE_API_KEY não configurada")
            from mock_llm import MockLLM
            return MockLLM(temperature=temperature)

    # Resolver provider
    builder = _PROVIDERS.get(provider_name)
    if not builder:
        available = ", ".join(_PROVIDERS.keys())
        return FallbackLLM(
            f"Provider desconhecido: {provider_name!r}. Disponíveis: {available}"
        )

    try:
        return builder(temperature, tier)
    except ImportError as e:
        return FallbackLLM(f"Dependência faltando: {e}")
    except Exception as exc:
        print(f"[LLM WARNING] Falha ao inicializar {provider_name}: {exc}")
        return FallbackLLM(f"Falha ao inicializar {provider_name}: {exc}")

