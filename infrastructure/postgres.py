"""Pool e GameStore Postgres síncronos, sem transações durante chamadas LLM."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Iterator
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from infrastructure.contracts import Conflict, NotFound, Principal, StaleVersion, StoredGame
from services.game_serialization import (
    deserialize_game_state,
    document_sha256,
    event_document,
    game_projection,
    serialize_game_state,
)

try:
    from psycopg import Connection
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - erro acionável no extra opcional
    Connection = Any  # type: ignore[assignment,misc]
    ConnectionPool = None  # type: ignore[assignment,misc]
    Jsonb = None  # type: ignore[assignment,misc]
    dict_row = None  # type: ignore[assignment]


class PostgresPool:
    def __init__(self, dsn: str, *, min_size: int = 0, max_size: int = 4,
                 timeout: float = 5.0, transaction_pooler: bool = False):
        if ConnectionPool is None:
            raise RuntimeError("instale o extra postgres: uv sync --extra postgres")
        kwargs: dict[str, Any] = {"row_factory": dict_row, "connect_timeout": 5}
        if transaction_pooler:
            # Supavisor transaction mode cannot preserve prepared/session state.
            # Keep verify-full if already requested; never downgrade TLS.
            sslmodes = parse_qs(urlsplit(dsn).query).get("sslmode", [])
            kwargs["sslmode"] = "verify-full" if "verify-full" in sslmodes else "require"
            kwargs["prepare_threshold"] = None
        else:
            kwargs["options"] = "-c statement_timeout=15000 -c lock_timeout=5000"
        self._transaction_pooler = transaction_pooler
        self._pool = ConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            kwargs=kwargs,
            open=True,
        )

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        with self._pool.connection() as connection:
            if self._transaction_pooler:
                # SET LOCAL lives only for this transaction; the serverless
                # transaction pooler must not retain session settings.
                connection.execute("SET LOCAL statement_timeout = 15000")
                connection.execute("SET LOCAL lock_timeout = 5000")
            yield connection

    def close(self) -> None:
        self._pool.close()


def _stored(row: dict[str, Any]) -> StoredGame:
    return StoredGame(
        game_id=row["id"],
        owner_id=row["owner_id"],
        schema_version=int(row["schema_version"]),
        version=int(row["version"]),
        state=deserialize_game_state(row["state"]),
        updated_at=row["updated_at"],
    )


class PostgresGameStore:
    def __init__(self, pool: PostgresPool) -> None:
        self.pool = pool

    @staticmethod
    def _prepare(state: dict[str, Any]) -> tuple[dict[str, Any], str, dict[str, Any]]:
        document = serialize_game_state(state)
        return document, document_sha256(document), game_projection(document)

    @staticmethod
    def _insert_events(connection: Connection, owner_id: UUID, game_id: UUID,
                       document: dict[str, Any]) -> None:
        for raw in document.get("event_log", []) or []:
            if not isinstance(raw, dict) or not raw.get("event_id"):
                continue
            event = event_document(raw)
            digest = document_sha256(event)
            row = connection.execute(
                """
                insert into app.game_events
                  (game_id, owner_id, event_id, turn, event_type, payload, source, event_sha256)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (game_id, event_id) do nothing
                returning event_sha256
                """,
                (
                    game_id, owner_id, event["event_id"], event["turn"],
                    event["event_type"], Jsonb(event["payload"]), event["source"], digest,
                ),
            ).fetchone()
            if row is None:
                existing = connection.execute(
                    "select event_sha256 from app.game_events where game_id=%s and event_id=%s",
                    (game_id, event["event_id"]),
                ).fetchone()
                if not existing or existing["event_sha256"] != digest:
                    raise Conflict("event_id já existe com payload divergente")

    def create(self, principal: Principal, state: dict[str, Any]) -> StoredGame:
        game_id = UUID(str(state["game_id"]))
        document, digest, projection = self._prepare(state)
        with self.pool.connection() as connection, connection.transaction():
            try:
                row = connection.execute(
                    """
                    insert into app.games
                      (id, owner_id, schema_version, state, state_sha256, status,
                       player_name, class_name, player_level, location_name, world_day,
                       game_over, combat_simulation)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    returning *
                    """,
                    (
                        game_id, principal.user_id, int(document["schema_version"]),
                        Jsonb(document), digest, projection["status"], projection["player_name"],
                        projection["class_name"], projection["player_level"],
                        projection["location_name"], projection["world_day"],
                        projection["game_over"], projection["combat_simulation"],
                    ),
                ).fetchone()
            except Exception as exc:
                if getattr(exc, "sqlstate", "") == "23505":
                    raise Conflict("game_id já existe") from exc
                raise
            self._insert_events(connection, principal.user_id, game_id, document)
            return _stored(row)

    def get(self, principal: Principal, game_id: UUID) -> StoredGame | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "select * from app.games where id=%s and owner_id=%s",
                (game_id, principal.user_id),
            ).fetchone()
            return _stored(row) if row else None

    def list(self, principal: Principal) -> list[StoredGame]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "select * from app.games where owner_id=%s order by updated_at desc",
                (principal.user_id,),
            ).fetchall()
            return [_stored(row) for row in rows]

    def save(self, principal: Principal, game_id: UUID, expected_version: int,
             state: dict[str, Any]) -> StoredGame:
        document, digest, projection = self._prepare(state)
        if UUID(str(document["game_id"])) != game_id:
            raise Conflict("game_id do documento divergiu")
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """
                update app.games set
                  schema_version=%s, version=version+1, state=%s, state_sha256=%s,
                  status=%s, player_name=%s, class_name=%s, player_level=%s,
                  location_name=%s, world_day=%s, game_over=%s, combat_simulation=%s,
                  updated_at=now(), last_action_at=now()
                where id=%s and owner_id=%s and version=%s
                returning *
                """,
                (
                    int(document["schema_version"]), Jsonb(document), digest,
                    projection["status"], projection["player_name"], projection["class_name"],
                    projection["player_level"], projection["location_name"],
                    projection["world_day"], projection["game_over"],
                    projection["combat_simulation"], game_id, principal.user_id,
                    expected_version,
                ),
            ).fetchone()
            if row is None:
                exists = connection.execute(
                    "select version from app.games where id=%s and owner_id=%s",
                    (game_id, principal.user_id),
                ).fetchone()
                if exists:
                    raise StaleVersion("versão confirmada divergiu")
                raise NotFound("campanha não encontrada")
            self._insert_events(connection, principal.user_id, game_id, document)
            return _stored(row)

    def delete(self, principal: Principal, game_id: UUID) -> bool:
        with self.pool.connection() as connection, connection.transaction():
            result = connection.execute(
                "delete from app.games where id=%s and owner_id=%s",
                (game_id, principal.user_id),
            )
            return result.rowcount == 1

    def save_checkpoint(self, principal: Principal, stored: StoredGame,
                        state: dict[str, Any], *, memory_commit_version: int = 0) -> None:
        document = serialize_game_state(state)
        world = document.get("world") or {}
        continuity = document.get("continuity") or {}
        with self.pool.connection() as connection, connection.transaction():
            result = connection.execute(
                "select 1 from app.games where id=%s and owner_id=%s and version=%s",
                (stored.game_id, principal.user_id, stored.version),
            ).fetchone()
            if not result:
                raise StaleVersion("checkpoint não corresponde à versão confirmada")
            connection.execute(
                """
                insert into app.game_checkpoints
                  (game_id, owner_id, game_version, canonical_turn, timeline_epoch,
                   memory_commit_version, state, state_sha256)
                values (%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (game_id) do update set
                  owner_id=excluded.owner_id, game_version=excluded.game_version,
                  canonical_turn=excluded.canonical_turn,
                  timeline_epoch=excluded.timeline_epoch,
                  memory_commit_version=excluded.memory_commit_version,
                  state=excluded.state, state_sha256=excluded.state_sha256,
                  created_at=now()
                """,
                (
                    stored.game_id, principal.user_id, stored.version,
                    int(world.get("turn_count", 0) or 0),
                    int(continuity.get("timeline_epoch", 0) or 0), memory_commit_version,
                    Jsonb(document), document_sha256(document),
                ),
            )

    def get_checkpoint(self, principal: Principal, game_id: UUID) -> dict[str, Any] | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "select state from app.game_checkpoints where game_id=%s and owner_id=%s",
                (game_id, principal.user_id),
            ).fetchone()
            return deserialize_game_state(row["state"]) if row else None
