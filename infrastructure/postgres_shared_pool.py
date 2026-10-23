"""postgres_shared_pool.py — `app.shared_pool` (SPEC-297 R3/R19/R31).

Perfis local/portable/hosted/hosted-supabase. Leituras e insert pela conexão do request
(RLS `rpg_api`: só `promoted` + linhas do próprio owner; insert só `held`/`local_only`);
mudança de `status`, claim do job e contadores globais pela conexão de sistema (R19).

`due()` faz um CLAIM por lease: `for update skip locked` + `promote_after = now + 15 min`
numa só instrução, então dois workers nunca avaliam a mesma entrada (R18). Entrada cujo
worker morreu volta a ficar elegível quando o lease expira.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from infrastructure.shared_pool_store import _check_immutable
from services.shared_pool_models import PoolNamespace, PoolStatus, SharedPoolEntry

_COLUMNS = (
    "entry_id, namespace, status, region_id, name, name_fold, name_origin, document, legend, "
    "seed, seed_signature, origin_owner_id, origin_game_id, input_shingles, embedding_profile, "
    "embedding::text as embedding, created_at, promote_after, attempts, evaluation, "
    "evaluated_at, duplicate_of, veto_reason, version"
)
_UPDATABLE = frozenset(
    {
        "status",
        "evaluation",
        "evaluated_at",
        "attempts",
        "promote_after",
        "duplicate_of",
        "veto_reason",
        "embedding",
        "embedding_profile",
        "origin_owner_id",
        "origin_game_id",
        "input_shingles",
    }
)
_JSON_FIELDS = frozenset({"evaluation"})
LEASE_MINUTES = 15
EMBEDDING_DIMENSIONS = 1024


def _vector_literal(values: list[float] | None) -> str | None:
    if not values or len(values) != EMBEDDING_DIMENSIONS:
        return None  # dimensão diferente do pgvector: sem embedding (dedupe lexical)
    return "[" + ",".join(repr(float(x)) for x in values) + "]"


def _row_to_entry(row: dict[str, Any]) -> SharedPoolEntry:
    data = dict(row)
    emb = data.get("embedding")
    data["embedding"] = json.loads(emb) if isinstance(emb, str) else emb
    data["input_shingles"] = list(data.get("input_shingles") or [])
    return SharedPoolEntry.model_validate(data)


class PostgresSharedPoolStore:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    def _admin(self):
        from infrastructure.db_roles import admin_connection

        return admin_connection(self.pool)

    def insert(self, entry: SharedPoolEntry) -> None:
        from psycopg.types.json import Jsonb

        with self.pool.connection() as db:
            db.execute(
                """
                insert into app.shared_pool
                  (entry_id, namespace, status, region_id, name, name_fold, name_origin, document,
                   legend, seed, seed_signature, origin_owner_id, origin_game_id, input_shingles,
                   embedding_profile, created_at, promote_after, attempts, version)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    entry.entry_id,
                    entry.namespace.value,
                    entry.status.value,
                    entry.region_id,
                    entry.name,
                    entry.name_fold,
                    entry.name_origin,
                    Jsonb(entry.document),
                    entry.legend,
                    Jsonb(entry.seed.model_dump()) if entry.seed else None,
                    entry.seed_signature,
                    entry.origin_owner_id,
                    entry.origin_game_id,
                    list(entry.input_shingles),
                    entry.embedding_profile,
                    entry.created_at,
                    entry.promote_after,
                    entry.attempts,
                    entry.version,
                ),
            )

    def get(self, entry_id: str) -> SharedPoolEntry | None:
        with self.pool.connection() as db:
            row = db.execute(
                f"select {_COLUMNS} from app.shared_pool where entry_id=%s", (entry_id,)
            ).fetchone()
        return _row_to_entry(row) if row else None

    def update(self, entry_id: str, fields: dict[str, Any]) -> SharedPoolEntry:
        from psycopg.types.json import Jsonb

        # Conteúdo (document/name/legend/seed) NUNCA é atualizável por esta porta.
        unknown = set(fields) - _UPDATABLE
        if unknown:
            raise ValueError(f"campos não atualizáveis: {sorted(unknown)}")
        with self._admin() as db, db.transaction():
            row = db.execute(
                f"select {_COLUMNS} from app.shared_pool where entry_id=%s for update",
                (entry_id,),
            ).fetchone()
            if row is None:
                raise KeyError(entry_id)
            _check_immutable(_row_to_entry(row), fields)
            sets, values = [], []
            for key, value in fields.items():
                if key == "embedding":
                    sets.append("embedding=%s::extensions.vector")
                    values.append(_vector_literal(value))
                elif key in _JSON_FIELDS:
                    sets.append(f"{key}=%s")
                    values.append(Jsonb(value) if value is not None else None)
                else:
                    sets.append(f"{key}=%s")
                    values.append(value.value if hasattr(value, "value") else value)
            if sets:
                db.execute(
                    f"update app.shared_pool set {', '.join(sets)} where entry_id=%s",
                    (*values, entry_id),
                )
            fresh = db.execute(
                f"select {_COLUMNS} from app.shared_pool where entry_id=%s", (entry_id,)
            ).fetchone()
        return _row_to_entry(fresh)

    def select(
        self,
        *,
        namespace: PoolNamespace | None = None,
        statuses: Iterable[PoolStatus] | None = None,
        region_id: str | None = None,
        name_fold: str | None = None,
        seed_signature: str | None = None,
        origin_game_id: str | None = None,
        limit: int | None = None,
    ) -> list[SharedPoolEntry]:
        where: list[str] = ["true"]
        values: list[Any] = []
        if namespace is not None:
            where.append("namespace=%s")
            values.append(namespace.value)
        if statuses is not None:
            where.append("status = any(%s)")
            values.append([s.value for s in statuses])
        if region_id is not None:
            where.append("region_id=%s")
            values.append(region_id)
        if name_fold is not None:
            where.append("name_fold=%s")
            values.append(name_fold)
        if seed_signature is not None:
            where.append("seed_signature=%s")
            values.append(seed_signature)
        if origin_game_id is not None:
            where.append("origin_game_id=%s")
            values.append(origin_game_id)
        sql = (
            f"select {_COLUMNS} from app.shared_pool where {' and '.join(where)} "
            "order by created_at, entry_id"
        )
        if limit is not None:
            sql += " limit %s"
            values.append(int(limit))
        with self.pool.connection() as db:
            rows = db.execute(sql, tuple(values)).fetchall()
        return [_row_to_entry(r) for r in rows]

    def due(self, now: datetime, limit: int) -> list[SharedPoolEntry]:
        with self._admin() as db, db.transaction():
            rows = db.execute(
                f"""
                update app.shared_pool set promote_after = %s + make_interval(mins => %s)
                 where entry_id in (
                   select entry_id from app.shared_pool
                    where status = 'held' and promote_after <= %s
                    order by created_at, entry_id
                    limit %s for update skip locked)
             returning {_COLUMNS}
                """,
                (now, LEASE_MINUTES, now, max(0, int(limit))),
            ).fetchall()
        return sorted((_row_to_entry(r) for r in rows), key=lambda e: (e.created_at, e.entry_id))

    def count_submissions(self, owner_id: UUID | None, since: datetime) -> int:
        with self.pool.connection() as db:
            row = db.execute(
                """select count(*) as n from app.shared_pool
                    where origin_owner_id is not distinct from %s and created_at >= %s
                      and status <> 'local_only'""",
                (owner_id, since),
            ).fetchone()
        return int(row["n"])

    def count_evaluated(self, since: datetime) -> int:
        with self._admin() as db:
            row = db.execute(
                "select count(*) as n from app.shared_pool where evaluated_at >= %s", (since,)
            ).fetchone()
        return int(row["n"])

    @staticmethod
    def erase_owner(db: Any, owner: UUID) -> None:
        """R31/D3: apaga held/local_only/rejected e DESVINCULA o resto (promoted/vetoed/retired).

        Roda dentro da transação de exclusão de conta (`account_lifecycle.finish`)."""
        db.execute(
            "delete from app.shared_pool where origin_owner_id=%s "
            "and status in ('held','local_only','rejected')",
            (owner,),
        )
        db.execute(
            "update app.shared_pool set origin_owner_id=null, origin_game_id=null, "
            "input_shingles='{}' where origin_owner_id=%s",
            (owner,),
        )
