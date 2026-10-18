"""Entrypoint explícito da Vercel Function (SPEC-192).

Não usar `main.py` (exporta o grafo LangGraph como `app`). Este módulo é
apontado por `[tool.vercel] entrypoint` no pyproject.toml e por `functions`
no vercel.json.
"""

from infrastructure.runtime import apply_serverless_defaults

apply_serverless_defaults()

from observability.logging_setup import configure_logging

configure_logging()

from api import app  # noqa: E402,F401  (FastAPI instance exigida pela Vercel)
