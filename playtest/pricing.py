"""playtest/pricing.py — estimativa de custo (USD) por invoke de LLM.

O hook de telemetria do roteamento entrega `(provider, model, tier, latency_ms,
fell_back)` — NÃO tokens. Custo é, portanto, ESTIMADO: um número fixo de tokens
por invoke (heurística) × preço por milhão de tokens do modelo. Suficiente p/
comparar campanhas e proteger o bolso no `--real` (spec 5.3 R6); nunca é fatura
oficial. MockLLM não dispara o hook → custo 0.

Preços (USD por 1M tokens, in/out) — tabela curada, editável sem deploy. Modelo
desconhecido cai no default conservador.
"""
from __future__ import annotations

from typing import List

# (preço_in, preço_out) em USD por 1_000_000 tokens.
PRICE_PER_MTOK = {
    # Groq (free tier no jogo; preço listado p/ referência)
    "openai/gpt-oss-20b": (0.10, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    # Gemini
    "gemini-flash-lite-latest": (0.10, 0.40),
    "gemini-flash-latest": (0.30, 2.50),
    "gemini-pro-latest": (1.25, 10.0),
    # Pagos (assumem quando têm saldo)
    "MiniMax-M2.5": (0.30, 1.20),
    "qwen-max": (1.60, 6.40),
    # DeepSeek V4 (cache miss; tabela oficial em 2026-07-24).
    "deepseek-v4-flash": (0.14, 0.28),
    "deepseek-v4-pro": (0.435, 0.87),
    "claude-sonnet-5": (3.00, 15.0),
}
_DEFAULT_PRICE = (1.00, 3.00)

# Heurística de tokens por invoke (contexto + saída típicos de 1 turno do jogo).
_EST_TOKENS_IN = 1200
_EST_TOKENS_OUT = 400


def estimate_cost(model: str, tokens_in: int = _EST_TOKENS_IN,
                  tokens_out: int = _EST_TOKENS_OUT) -> float:
    """Custo estimado (USD) de 1 invoke do modelo."""
    price_in, price_out = PRICE_PER_MTOK.get(model or "", _DEFAULT_PRICE)
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000.0


def turn_cost(llm_events: List[dict]) -> float:
    """Soma o custo estimado de todos os invokes de LLM de um turno."""
    return sum(estimate_cost(e.get("model", "")) for e in llm_events)
