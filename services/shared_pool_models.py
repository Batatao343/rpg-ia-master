"""shared_pool_models.py — schemas do pool compartilhado (SPEC-297 §3).

Só tipos e constantes puras (sem I/O), para que store, validadores e serviço
importem sem ciclo. Os números mecânicos NUNCA vêm de `document`: o motor
recalcula (R27/§3).
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from services.npc_seed import NpcSeed


class PoolNamespace(StrEnum):
    NPC = "npc_template"
    CREATURE = "bestiary_template"
    ARTIFACT = "custom_artifact"
    LOCATION = "location"


class PoolStatus(StrEnum):
    HELD = "held"
    LOCAL_ONLY = "local_only"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    VETOED = "vetoed"
    RETIRED = "retired"


# Allowlists de `document` por namespace (§3). R23 para NPC.
DOCUMENT_ALLOWLIST: dict[PoolNamespace, frozenset[str]] = {
    PoolNamespace.NPC: frozenset(
        {
            "id",
            "name",
            "role",
            "persona",
            "appearance",
            "attributes",
            "initial_relationship",
            "race_id",
            "origin_region_id",
            "faction_id",
            "profession_id",
            "legend",
            "pool_entry_id",
        }
    ),
    PoolNamespace.CREATURE: frozenset(
        {
            "id",
            "name",
            "description",
            "categoria",
            "arquetipo",
            "estilo_ataque",
            "nome_ataque",
            "region_tags",
        }
    ),
    PoolNamespace.ARTIFACT: frozenset(
        {"id", "name", "description", "type", "rarity", "unique", "stackable"}
    ),
    PoolNamespace.LOCATION: frozenset(
        {"id", "name", "description", "parent_location_id", "region", "tags"}
    ),
}

# Campos de texto livre varridos pelos validadores (com teto de tamanho, R14).
TEXT_LIMITS: dict[str, int] = {
    "name": 60,
    "persona": 600,
    "appearance": 300,
    "legend": 160,
    "role": 60,
    "description": 600,
}


class SharedPoolEntry(BaseModel):
    entry_id: str
    namespace: PoolNamespace
    status: PoolStatus
    region_id: str
    name: str = Field(max_length=60)
    name_fold: str
    name_origin: Literal["narrator", "player", "engine"]
    document: dict
    legend: str = Field("", max_length=160)
    seed: NpcSeed | None = None
    seed_signature: str = ""
    origin_owner_id: UUID | None = None
    origin_game_id: str | None = None
    input_shingles: list[str] = Field(default_factory=list, max_length=200)
    embedding_profile: str | None = None
    embedding: list[float] | None = None  # preenchido na promoção (dedupe de entradas futuras)
    created_at: datetime
    promote_after: datetime
    attempts: int = 0
    evaluation: dict | None = None
    evaluated_at: datetime | None = None
    duplicate_of: str | None = None
    veto_reason: str | None = None
    version: int = 1


class PoolCriterion(BaseModel):
    ok: bool
    reason: str = Field("", max_length=200)


class PoolEvaluation(BaseModel):
    lore: PoolCriterion
    uniqueness: PoolCriterion
    content: PoolCriterion
    pii: PoolCriterion
    injection: PoolCriterion

    def all_ok(self) -> bool:
        return all(
            getattr(self, key).ok for key in ("lore", "uniqueness", "content", "pii", "injection")
        )


def fold_name(text: object) -> str:
    """Nome dobrado: sem acento, casefold, espaços colapsados."""
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()
    return " ".join(stripped.split())
