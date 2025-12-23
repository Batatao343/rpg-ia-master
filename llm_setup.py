from enum import Enum
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory

load_dotenv()


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
    max_retries = 3 if tier == ModelTier.FAST else 1

    try:
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            max_retries=max_retries,
            safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
        )
    except Exception as exc:  # noqa: BLE001 - captura falhas do provider
        print(
            "[LLM WARNING] Não foi possível inicializar o modelo Gemini. "
            "Defina GOOGLE_API_KEY e verifique a conexão."
        )
        print(f"[LLM WARNING] Detalhes: {exc}")
        return FallbackLLM("O narrador está indisponível. Configure GOOGLE_API_KEY e tente novamente.")

