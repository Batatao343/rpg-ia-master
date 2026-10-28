"""SPEC-352: registro compartilhado de retratos de criatura (canonical owner de `app.creature_portraits`).

Nenhum outro modulo faz `insert/update/delete` nessa tabela (teste de grep). Sem LLM e sem provider de
imagem aqui: a geracao passa pela porta `ImageGenerator` no worker.

Chaves (`creature_art.portrait_key`):
- `tipo:{bestiary_id}` / `tipo:gen:*` / `npc:{entity_id}`  -> visibilidade `shared`;
- `tipo:bst:{entry}` / `unico:bst:{entry}:*`               -> `pool` (visivel a todos so se promovida);
- `unico:{game_id}:*`                                       -> `game` (so o jogo de origem).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Literal
from uuid import UUID

from psycopg.types.json import Jsonb

from infrastructure.contracts import Conflict
from infrastructure.db_roles import admin_connection

PortraitStatus = Literal["pending", "ready", "failed", "retired"]
PortraitVisibility = Literal["shared", "pool", "game"]

_DEAD_GENERATION = ("failed", "failed_retryable", "refused", "superseded", "rejected_quality")
_LIVE_GENERATION = ("pending", "generating", "ready")


class CreaturePortraitTaken(Conflict):
    """A chave ja esta `pending`/`ready` (outro jogador pagou primeiro)."""


def visibility_for(portrait_key: str) -> PortraitVisibility:
    if portrait_key.startswith(("tipo:bst:", "unico:bst:")):
        return "pool"
    if portrait_key.startswith("unico:"):
        return "game"
    return "shared"


def scope_for(portrait_key: str) -> str:
    head = portrait_key.partition(":")[0]
    if head not in {"tipo", "unico", "npc"}:
        raise ValueError("portrait_key invalida")
    return head


def pool_entry_for(portrait_key: str) -> str | None:
    for prefix in ("tipo:bst:", "unico:bst:"):
        if portrait_key.startswith(prefix):
            return portrait_key[len(prefix) :].split(":", 1)[0] or None
    return None


def key_hash(portrait_key: str) -> str:
    """Hash curto da chave: a chave de bucket nao expoe `game_id` de `unico:{game}`."""
    return hashlib.sha256(portrait_key.encode()).hexdigest()[:12]


def effective_status(row: Mapping[str, Any], generation_status: str | None) -> PortraitStatus:
    """`pending` cuja geracao esta morta (ou sumiu) conta como `failed` (R3)."""
    status = str(row.get("status") or "failed")
    if status == "pending" and (generation_status is None or generation_status in _DEAD_GENERATION):
        return "failed"
    return status  # type: ignore[return-value]


def effective_visible(
    row: Mapping[str, Any],
    *,
    game_id: str,
    pool_status: str | None = None,
    npc_known: bool = True,
) -> bool:
    """Visibilidade efetiva calculada na leitura (R4)."""
    key = str(row.get("portrait_key") or "")
    visibility = str(row.get("visibility") or visibility_for(key))
    mine = str(row.get("origin_game_id") or "") == str(game_id)
    if visibility == "game":
        return mine
    if visibility == "pool":
        return pool_status == "promoted" or (mine and pool_status not in {"rejected", "vetoed"})
    if key.startswith("npc:"):
        return npc_known
    return True


class SnapshotRegistry:
    """Leitura em lote de uma resposta: satisfaz o Protocol `PortraitRegistry` (`get`) da SPEC-347."""

    def __init__(
        self,
        rows: Mapping[str, dict[str, Any]] | None = None,
        *,
        sign: Callable[[str, str], str | None] | None = None,
    ) -> None:
        self.rows = dict(rows or {})
        self.sign = sign

    def get(self, portrait_key: str) -> dict[str, Any] | None:
        return self.rows.get(portrait_key)


class PostgresPortraitRegistry:
    def __init__(self, pool) -> None:
        self.pool = pool

    # --- leitura -------------------------------------------------------------------------
    def get_many(
        self,
        keys: Sequence[str],
        *,
        game_id: str,
        npc_known: Iterable[str] = (),
    ) -> dict[str, dict[str, Any]]:
        """Uma query por chamada; ja filtrado por status efetivo (R3) e visibilidade (R4)."""
        wanted = sorted({key for key in keys if key})
        if not wanted:
            return {}
        known = set(npc_known)
        with admin_connection(self.pool) as connection:
            rows = connection.execute(
                """select p.*, g.status as generation_status, sp.status as pool_status
                from app.creature_portraits p
                left join app.art_generations g on g.generation_id = p.generation_id
                left join app.shared_pool sp on sp.entry_id = p.pool_entry_id
                where p.portrait_key = any(%s) and p.status in ('pending','ready')""",
                (wanted,),
            ).fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            data = dict(row)
            if effective_status(data, data.get("generation_status")) not in {"pending", "ready"}:
                continue
            if not effective_visible(
                data,
                game_id=game_id,
                pool_status=data.get("pool_status"),
                npc_known=data["portrait_key"] in known,
            ):
                continue
            data["origin_game_id"] = str(data["origin_game_id"]) if data["origin_game_id"] else None
            result[data["portrait_key"]] = {
                key: data.get(key)
                for key in (
                    "portrait_key",
                    "status",
                    "visibility",
                    "origin_game_id",
                    "store",
                    "object_keys",
                )
            }
        return result

    def get(
        self, portrait_key: str
    ) -> dict[str, Any] | None:  # Protocol da 347 (sem jogo: so shared)
        return self.get_many([portrait_key], game_id="", npc_known=[portrait_key]).get(portrait_key)

    # --- escrita (todas dentro da transacao do chamador) ---------------------------------
    @staticmethod
    def claim(
        connection,
        *,
        portrait_key: str,
        scope: str,
        pool_entry_id: str | None,
        origin_owner_id: UUID,
        origin_game_id: UUID,
        generation_id: UUID,
    ) -> dict[str, Any]:
        """nada -> pending; failed/retired (ou pending de geracao morta) -> pending. O PK e o arbitro."""
        row = connection.execute(
            """insert into app.creature_portraits as cp
            (portrait_key,scope,status,generation_id,visibility,pool_entry_id,
             origin_owner_id,origin_game_id)
            values (%s,%s,'pending',%s,%s,%s,%s,%s)
            on conflict (portrait_key) do update set
              status='pending', generation_id=excluded.generation_id, scope=excluded.scope,
              visibility=excluded.visibility, pool_entry_id=excluded.pool_entry_id,
              origin_owner_id=excluded.origin_owner_id, origin_game_id=excluded.origin_game_id,
              store=null, object_keys='{}'::jsonb, sha256='{}'::jsonb, error_code=null,
              updated_at=now(), version=cp.version+1
            where cp.status in ('failed','retired')
               or (cp.status='pending' and not exists (
                    select 1 from app.art_generations g
                    where g.generation_id=cp.generation_id and g.status = any(%s)))
            returning *""",
            (
                portrait_key,
                scope,
                generation_id,
                visibility_for(portrait_key),
                pool_entry_id,
                origin_owner_id,
                origin_game_id,
                list(_LIVE_GENERATION),
            ),
        ).fetchone()
        if row is None:
            raise CreaturePortraitTaken("retrato ja gerado ou em geracao")
        return dict(row)

    @staticmethod
    def mark_ready(
        connection,
        *,
        generation_id: UUID,
        store: Literal["shared", "private"],
        object_keys: Mapping[str, str],
        sha256: Mapping[str, str],
    ) -> bool:
        result = connection.execute(
            """update app.creature_portraits set status='ready', store=%s, object_keys=%s,
            sha256=%s, error_code=null, updated_at=now(), version=version+1
            where generation_id=%s and status='pending'""",
            (store, Jsonb(dict(object_keys)), Jsonb(dict(sha256)), generation_id),
        )
        return result.rowcount == 1

    @staticmethod
    def mark_failed(connection, *, generation_id: UUID, error_code: str) -> bool:
        result = connection.execute(
            """update app.creature_portraits set status='failed', error_code=%s, updated_at=now(),
            version=version+1 where generation_id=%s and status='pending'""",
            (error_code[:100], generation_id),
        )
        return result.rowcount == 1

    def promote_store(self, *, portrait_key: str, object_keys: Mapping[str, str]) -> bool:
        """`private` -> `shared` (uma vez; o trigger recusa qualquer outra reescrita)."""
        with admin_connection(self.pool) as connection, connection.transaction():
            result = connection.execute(
                """update app.creature_portraits set store='shared', object_keys=%s,
                updated_at=now(), version=version+1
                where portrait_key=%s and status='ready' and store='private'""",
                (Jsonb(dict(object_keys)), portrait_key),
            )
            return result.rowcount == 1

    def retire(self, *, portrait_key: str, reason: str) -> list[str]:
        """ready -> retired (operador). Devolve as object keys COMPARTILHADAS a apagar."""
        with admin_connection(self.pool) as connection, connection.transaction():
            row = connection.execute(
                "select * from app.creature_portraits where portrait_key=%s for update",
                (portrait_key,),
            ).fetchone()
            if not row or row["status"] != "ready":
                raise Conflict("retrato nao esta pronto")
            connection.execute(
                """update app.creature_portraits set status='retired', error_code=%s,
                updated_at=now(), version=version+1 where portrait_key=%s""",
                (("retired:" + reason)[:100], portrait_key),
            )
            keys = [str(v) for v in (row["object_keys"] or {}).values()]
            return keys if row["store"] == "shared" else []

    @staticmethod
    def erase_owner(db, owner: UUID) -> list[str]:
        """R14: apaga `game`/pending/privadas do dono; desvincula as `ready` compartilhadas.

        Devolve as object keys compartilhadas das linhas apagadas (o chamador as remove do store)."""
        keys = [
            str(v)
            for row in db.execute(
                """delete from app.creature_portraits where origin_owner_id=%s and (
                     visibility='game' or status in ('pending','failed') or store='private')
                returning object_keys, store, status""",
                (owner,),
            ).fetchall()
            if row["store"] == "shared"
            for v in (row["object_keys"] or {}).values()
        ]
        db.execute(
            """update app.creature_portraits set origin_owner_id=null, origin_game_id=null
            where origin_owner_id=%s""",
            (owner,),
        )
        return keys

    @staticmethod
    def delete_game(db, game_id: UUID) -> list[str]:
        """R14: apaga as linhas `game` do jogo (as demais ficam). Devolve keys compartilhadas."""
        return [
            str(v)
            for row in db.execute(
                """delete from app.creature_portraits where origin_game_id=%s
                and visibility='game' returning object_keys, store""",
                (game_id,),
            ).fetchall()
            if row["store"] == "shared"
            for v in (row["object_keys"] or {}).values()
        ]

    @staticmethod
    def export_rows(db, owner: UUID) -> list[dict[str, Any]]:
        """Exportacao de conta: so chave, escopo, status e datas (sem object keys)."""
        return [
            dict(row)
            for row in db.execute(
                """select portrait_key,scope,status,created_at,updated_at
                from app.creature_portraits where origin_owner_id=%s""",
                (owner,),
            ).fetchall()
        ]


def purge_game_portraits(connection, owner_id: UUID, game_id: UUID) -> None:
    """R14: no caminho de exclusao de jogo (mesma transacao). Apaga as linhas `game` do jogo e agenda
    a remocao dos objetos compartilhados; as demais linhas ficam (valem para todos)."""
    from infrastructure.db_roles import system_scope

    if not connection.execute("select to_regclass('app.creature_portraits') as r").fetchone()["r"]:
        return
    with system_scope(connection):
        keys = PostgresPortraitRegistry.delete_game(connection, game_id)
    if keys:
        from workers.blob_purge_jobs import enqueue_shared_art_purge

        enqueue_shared_art_purge(connection, owner_id, keys)
