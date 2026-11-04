"""Leitores de ambiente compartilhados (SPEC-378 E2/E6)."""

from __future__ import annotations

import os


def env_choice(name: str, choices: tuple[str, ...] | frozenset[str], default: str) -> str:
    """Valor de ``name`` (strip + lower) se estiver em ``choices``; senao ``default``.

    Nao le ``config/flags.yaml``: o literal do nome da flag fica no chamador (gate de flags).
    """
    raw = os.getenv(name, default).strip().lower()
    return raw if raw in choices else default


def is_database_profile() -> bool:
    """Perfil runtime com banco (qualquer valor diferente de ``legacy``; ``""`` conta)."""
    return os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy"
