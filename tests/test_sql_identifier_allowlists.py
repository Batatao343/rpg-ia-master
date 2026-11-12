"""SPEC-411 R4b: as allowlists que sustentam identificadores SQL interpolados em f-string.

O ruff nao liga S608 (29 falsos positivos); o que de fato impede injecao e que o fragmento
interpolado venha de um conjunto fechado de identificadores. Este teste trava esses conjuntos:
mudar um deles exige mudar o teste de proposito (revisao consciente).
"""

from __future__ import annotations

import re

import pytest

from infrastructure import account_lifecycle as al
from infrastructure.postgres_shared_pool import _UPDATABLE

IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")

KNOWN_UPDATABLE = {
    "attempts",
    "duplicate_of",
    "embedding",
    "embedding_profile",
    "evaluated_at",
    "evaluation",
    "input_shingles",
    "origin_game_id",
    "origin_owner_id",
    "promote_after",
    "status",
    "veto_reason",
}


def test_shared_pool_updatable_columns_are_the_known_closed_set() -> None:
    assert set(_UPDATABLE) == KNOWN_UPDATABLE
    assert all(IDENT.fullmatch(name) for name in _UPDATABLE)


@pytest.mark.parametrize("name", ["PRIVATE_TABLES", "FINANCIAL_TABLES", "EXPORT_TABLES"])
def test_account_lifecycle_tables_are_plain_identifiers_without_duplicates(name: str) -> None:
    tables = getattr(al, name)
    assert tables, name
    assert all(isinstance(t, str) and IDENT.fullmatch(t) for t in tables)
    assert len(set(tables)) == len(tables)


def test_export_tables_are_private_plus_financial_plus_play_purchases() -> None:
    expected = set(al.PRIVATE_TABLES) | set(al.FINANCIAL_TABLES) | {"google_play_purchases"}
    assert set(al.EXPORT_TABLES) == expected
