import os
from enum import Enum
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory

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


def get_llm(temperature: float = 0.1, tier: ModelTier = ModelTier.FAST):
    """Retorna uma instância configurada do Gemini ou um fallback resiliente."""
    model = "gemini-flash-latest" if tier == ModelTier.FAST else "gemini-pro-latest"
    # Fail-fast: sem retries automáticos. O erro mais comum (429 quota) NÃO é
    # transitório (limite diário), e o retry com backoff do langchain trava o
    # turno por minutos antes de cair no fallback. Cada nó já trata a exceção
    # (try/except -> fallback resiliente), então falhar rápido é melhor UX.
    max_retries = 0

    # Modo SIMULADO (dados fictícios jogáveis), sem rede, quando:
    #  - não há GOOGLE_API_KEY, ou
    #  - RPG_FORCE_MOCK=1 (testes determinísticos mesmo com chave — evita quota/rede).
    # Defina RPG_NO_MOCK=1 para forçar o fallback de erro puro (só vale sem chave).
    force_mock = bool(os.getenv("RPG_FORCE_MOCK"))
    if force_mock or not os.getenv("GOOGLE_API_KEY"):
        if os.getenv("RPG_NO_MOCK") and not force_mock:
            return FallbackLLM("O narrador está indisponível. Configure GOOGLE_API_KEY e tente novamente.")
        from mock_llm import MockLLM
        return MockLLM(temperature=temperature)

    try:
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
    except Exception as exc:  # noqa: BLE001 - captura falhas do provider
        print(
            "[LLM WARNING] Não foi possível inicializar o modelo Gemini. "
            "Defina GOOGLE_API_KEY e verifique a conexão."
        )
        print(f"[LLM WARNING] Detalhes: {exc}")
        return FallbackLLM("O narrador está indisponível. Configure GOOGLE_API_KEY e tente novamente.")

