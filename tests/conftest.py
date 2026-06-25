"""Config de testes: força o modo simulado (MockLLM) para a suíte ser
determinística e offline — independente de haver GOOGLE_API_KEY no ambiente
(evita falhas por quota/rede). O comportamento de jogo real não muda."""
import os

# Precisa estar setado antes de qualquer chamada a get_llm() nos nós do grafo.
os.environ.setdefault("RPG_FORCE_MOCK", "1")
