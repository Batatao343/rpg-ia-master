"""RuntimeCatalogStore Postgres com escopos e versionamento explícitos."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from infrastructure.contracts import Conflict, validate_scope
from infrastructure.postgres import PostgresPool
from services.game_serialization import document_sha256


class PostgresRuntimeCatalogStore:
    def __init__(self, pool: PostgresPool) -> None:
        self.pool = pool

    @staticmethod
    def _where(owner_id: UUID | None, game_id: UUID | None) -> tuple[str, tuple[Any, ...]]:
        if game_id is not None:
            return "scope='game' and owner_id=%s and game_id=%s", (owner_id, game_id)
        if owner_id is not None:
            return "scope='user' and owner_id=%s and game_id is null", (owner_id,)
        return "scope='global' and owner_id is null and game_id is null", ()

    def get(self, namespace: str, key: str, *, owner_id: UUID | None,
            game_id: UUID | None) -> dict[str, Any] | None:
        where, values = self._where(owner_id, game_id)
        with self.pool.connection() as connection:
            row = connection.execute(
                f"select document from app.runtime_catalog where namespace=%s and item_key=%s and {where}",
                (namespace, key, *values),
            ).fetchone()
            return deepcopy(row["document"]) if row else None

    def list(self, namespace: str, *, owner_id: UUID | None,
             game_id: UUID | None) -> dict[str, dict[str, Any]]:
        where, values = self._where(owner_id, game_id)
        with self.pool.connection() as connection:
            rows = connection.execute(
                f"select item_key, document from app.runtime_catalog where namespace=%s and {where}",
                (namespace, *values),
            ).fetchall()
            return {row["item_key"]: deepcopy(row["document"]) for row in rows}

    def put(self, namespace: str, key: str, value: dict[str, Any], *, scope: str,
            owner_id: UUID | None, game_id: UUID | None) -> None:
        validate_scope(scope, owner_id, game_id)  # type: ignore[arg-type]
        digest = document_sha256(value)
        where, values = self._where(owner_id, game_id)
        with self.pool.connection() as connection, connection.transaction():
            current = connection.execute(
                f"select id, document_sha256 from app.runtime_catalog where namespace=%s and item_key=%s and {where} for update",
                (namespace, key, *values),
            ).fetchone()
            if current:
                connection.execute(
                    """
                    update app.runtime_catalog set document=%s, document_sha256=%s,
                      version=version+1, updated_at=now() where id=%s
                    """,
                    (Jsonb(value), digest, current["id"]),
                )
                return
            connection.execute(
                """
                insert into app.runtime_catalog
                  (namespace,item_key,scope,owner_id,game_id,document,document_sha256)
                values (%s,%s,%s,%s,%s,%s,%s)
                """,
                (namespace, key, scope, owner_id, game_id, Jsonb(value), digest),
            )
