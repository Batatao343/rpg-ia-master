import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory

load_dotenv()

def get_llm(temperature=0.1):
    """Retorna uma instância configurada do Gemini."""
    return ChatGoogleGenerativeAI(
        model="gemini-pro-latest", 
        temperature=temperature,
        max_retries=3,
        safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
    )
