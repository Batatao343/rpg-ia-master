import os
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory

load_dotenv()


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


def get_llm(temperature=0.1):
    """Retorna uma instância configurada do Gemini ou um fallback resiliente."""
    try:
        return ChatGoogleGenerativeAI(
            model="gemini-pro-latest",
            temperature=temperature,
            max_retries=3,
            safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
        )
    except Exception as exc:  # noqa: BLE001 - captura falhas do provider
        print(
            "[LLM WARNING] Não foi possível inicializar o modelo Gemini. "
            "Defina GOOGLE_API_KEY e verifique a conexão."
        )
        print(f"[LLM WARNING] Detalhes: {exc}")
        return FallbackLLM("O narrador está indisponível. Configure GOOGLE_API_KEY e tente novamente.")
