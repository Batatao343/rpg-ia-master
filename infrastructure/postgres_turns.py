"""Coordenação distribuída de mutações e rate limit em Postgres."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from infrastructure.contracts import (
    Conflict,
    LeaseHeld,
    NotFound,
    OperationClaim,
    Principal,
    RateLimitDecision,
    StaleVersion,
)
from infrastructure.postgres import PostgresPool
from services.usage_metering import UsageEvent


class PostgresTurnCoordinator:
    def __init__(self, pool: PostgresPool, *, lease_seconds: int = 180) -> None:
        self.pool = pool
        self.lease_seconds = lease_seconds

    def claim(
        self,
        principal: Principal,
        operation_id: UUID,
        *,
        game_id: UUID | None,
        kind: str,
        request_hash: str,
        base_version: int | None,
    ) -> OperationClaim:
        token = uuid4()
        interval = timedelta(seconds=self.lease_seconds)
        with self.pool.connection() as connection, connection.transaction():
            game = None
            # Global lock order for game-scoped operations: game -> operation.
            # Inserting an operation takes a FK lock on games; doing the insert
            # first lets two contenders each hold a shared FK lock and then
            # deadlock while upgrading to FOR UPDATE.
            if game_id is not None:
                game = connection.execute(
                    "select * from app.games where id=%s and owner_id=%s for update",
                    (game_id, principal.user_id),
                ).fetchone()
                if not game:
                    raise NotFound("campanha não encontrada")
                if base_version is not None and int(game["version"]) != int(base_version):
                    raise StaleVersion("versão base da operação divergiu")
                if game["active_operation_id"] not in (None, operation_id):
                    fresh = connection.execute(
                        "select coalesce(%s > now(),false) as fresh",
                        (game["active_lease_until"],),
                    ).fetchone()["fresh"]
                    if fresh:
                        raise LeaseHeld("game_busy")
            inserted = connection.execute(
                """
                insert into app.operations
                  (id,owner_id,game_id,kind,status,base_game_version,lease_token,
                   lease_until,heartbeat_at,request_sha256)
                values (%s,%s,%s,%s,'running',%s,%s,now()+%s,now(),%s)
                on conflict do nothing
                returning id
                """,
                (
                    operation_id, principal.user_id, game_id, kind, base_version,
                    token, interval, request_hash,
                ),
            ).fetchone()
            existing = connection.execute(
                "select * from app.operations where id=%s for update",
                (operation_id,),
            ).fetchone()
            if not existing or existing["owner_id"] != principal.user_id:
                raise Conflict("idempotency key indisponível")
            if not inserted:
                if existing["request_sha256"] != request_hash:
                    raise Conflict("idempotency key reutilizada com request divergente")
                if (existing["game_id"] != game_id or existing["kind"] != kind
                        or existing["base_game_version"] != base_version):
                    raise Conflict("idempotency key reutilizada com operação divergente")
                if existing["status"] == "completed":
                    raise Conflict("operation_completed")
                if existing["status"] == "running" and existing["lease_until"] is not None:
                    fresh = connection.execute(
                        "select %s > now() as fresh", (existing["lease_until"],),
                    ).fetchone()["fresh"]
                    if fresh:
                        raise LeaseHeld("operation_in_progress")
                connection.execute(
                    """
                    update app.operations set status='running',lease_token=%s,
                      lease_until=now()+%s,heartbeat_at=now(),error_code=null
                    where id=%s
                    """,
                    (token, interval, operation_id),
                )
            if game_id is not None:
                connection.execute(
                    """
                    update app.games set active_operation_id=%s,active_lease_token=%s,
                      active_lease_until=now()+%s where id=%s and owner_id=%s
                    """,
                    (operation_id, token, interval, game_id, principal.user_id),
                )
        return OperationClaim(operation_id, token, game_id, base_version, request_hash)

    def commit_game(
        self,
        principal: Principal,
        claim: OperationClaim,
        state: dict[str, Any],
        *,
        receipt: Mapping[str, Any],
        input_sha256: str,
        latency_ms: int,
        llm_cost_usd: Decimal | float,
        checkpoint: bool = False,
        record_turn: bool = True,
        usage_events: Sequence[UsageEvent] = (),
    ) -> tuple[int, dict[str, Any]]:
        """Confirma jogo, eventos, turno e recibo sob o mesmo fencing token.

        O grafo já terminou quando este método abre a conexão; portanto nenhuma
        chamada de LLM acontece dentro da transação.
        """
        if claim.game_id is None or claim.base_version is None:
            raise ValueError("commit de turno exige game_id e versão base")
        from infrastructure.postgres import PostgresGameStore

        document, digest, projection = PostgresGameStore._prepare(state)
        if UUID(str(document["game_id"])) != claim.game_id:
            raise Conflict("game_id do documento divergiu")
        with self.pool.connection() as connection, connection.transaction():
            previous = connection.execute(
                'select state from app.games where id=%s and owner_id=%s for update',
                (claim.game_id, principal.user_id),
            ).fetchone()
            operation = connection.execute(
                """select status,lease_token,base_game_version from app.operations
                where id=%s and owner_id=%s for update""",
                (claim.operation_id, principal.user_id),
            ).fetchone()
            if (not operation or operation["status"] != "running"
                    or operation["lease_token"] != claim.lease_token):
                raise LeaseHeld("fencing token inválido")
            old_epoch = int(((previous or {}).get('state', {}).get('continuity') or {}).get('timeline_epoch', 0))
            new_epoch = int((document.get('continuity') or {}).get('timeline_epoch', 0))
            if new_epoch > old_epoch:
                from services.restore_effects import restore_effects
                restore_effects(connection, principal=principal, game_id=claim.game_id,
                               document=document)
            row = connection.execute(
                """update app.games set
                  schema_version=%s,version=version+1,state=%s,state_sha256=%s,
                  status=%s,player_name=%s,class_name=%s,player_level=%s,
                  location_name=%s,world_day=%s,game_over=%s,combat_simulation=%s,
                  updated_at=now(),last_action_at=now()
                where id=%s and owner_id=%s and version=%s
                  and active_operation_id=%s and active_lease_token=%s
                returning version""",
                (
                    int(document["schema_version"]), Jsonb(document), digest,
                    projection["status"], projection["player_name"],
                    projection["class_name"], projection["player_level"],
                    projection["location_name"], projection["world_day"],
                    projection["game_over"], projection["combat_simulation"],
                    claim.game_id, principal.user_id, claim.base_version,
                    claim.operation_id, claim.lease_token,
                ),
            ).fetchone()
            if not row:
                raise StaleVersion("versão/lease do jogo divergiu no commit")
            committed_version = int(row["version"])
            from services.turn_effects import current_effects
            from infrastructure.pgvector_memory import PgVectorMemoryStore
            effects = current_effects()
            if effects is not None:
                effects.flush(connection, memory_store=PgVectorMemoryStore(self.pool),
                    principal=principal, game_id=claim.game_id,
                    epoch=int((document.get('continuity') or {}).get('timeline_epoch', 0)),
                    version=committed_version)
            PostgresGameStore._insert_events(
                connection, principal.user_id, claim.game_id, document,
            )
            world = document.get("world") or {}
            continuity = document.get("continuity") or {}
            if checkpoint:
                connection.execute(
                    """insert into app.game_checkpoints
                      (game_id,owner_id,game_version,canonical_turn,timeline_epoch,
                       memory_commit_version,state,state_sha256)
                    values(%s,%s,%s,%s,%s,%s,%s,%s)
                    on conflict(game_id) do update set
                      owner_id=excluded.owner_id,game_version=excluded.game_version,
                      canonical_turn=excluded.canonical_turn,
                      timeline_epoch=excluded.timeline_epoch,
                      memory_commit_version=excluded.memory_commit_version,
                      state=excluded.state,state_sha256=excluded.state_sha256,
                      created_at=now()""",
                    (
                        claim.game_id, principal.user_id, committed_version,
                        int(world.get("turn_count", 0) or 0),
                        int(continuity.get("timeline_epoch", 0) or 0),
                        committed_version,
                        Jsonb(document), digest,
                    ),
                )
            if record_turn:
                sequence = committed_version
                connection.execute(
                    """insert into app.turns
                  (operation_id,game_id,owner_id,sequence,timeline_epoch,route,
                   input_sha256,state_version_before,state_version_after,latency_ms,llm_cost_usd)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        claim.operation_id, claim.game_id, principal.user_id, sequence,
                        int(continuity.get("timeline_epoch", 0) or 0),
                        str(document.get("next") or ""), input_sha256,
                        claim.base_version, committed_version, max(0, int(latency_ms)),
                        max(Decimal("0"), Decimal(str(llm_cost_usd))),
                    ),
                )
            if usage_events:
                from infrastructure.usage_events import append_usage_events
                append_usage_events(
                    connection, owner_id=principal.user_id,
                    operation_id=claim.operation_id, game_id=claim.game_id,
                    events=usage_events,
                )
            persisted_receipt = dict(receipt)
            persisted_receipt["committed_version"] = committed_version
            connection.execute(
                """update app.operations set status='completed',
                  committed_game_version=%s,receipt=%s,lease_token=null,
                  lease_until=null,finished_at=now()
                where id=%s and status='running' and lease_token=%s""",
                (committed_version, Jsonb(persisted_receipt),
                 claim.operation_id, claim.lease_token),
            )
            connection.execute(
                """update app.games set active_operation_id=null,
                  active_lease_token=null,active_lease_until=null
                where id=%s and active_operation_id=%s and active_lease_token=%s""",
                (claim.game_id, claim.operation_id, claim.lease_token),
            )
        return committed_version, persisted_receipt

    def commit_create(
        self, principal: Principal, claim: OperationClaim, state: dict[str, Any],
        *, receipt: Mapping[str, Any], checkpoint: bool = True,
    ) -> tuple[int, dict[str, Any]]:
        """Cria campanha, eventos, checkpoint inicial e recibo atomicamente."""
        if claim.game_id is not None or claim.base_version is not None:
            raise ValueError("operação de criação não aceita jogo/versão base")
        from infrastructure.postgres import PostgresGameStore

        document, digest, projection = PostgresGameStore._prepare(state)
        game_id = UUID(str(document["game_id"]))
        with self.pool.connection() as connection, connection.transaction():
            operation = connection.execute(
                """select status,lease_token from app.operations
                where id=%s and owner_id=%s for update""",
                (claim.operation_id, principal.user_id),
            ).fetchone()
            if (not operation or operation["status"] != "running"
                    or operation["lease_token"] != claim.lease_token):
                raise LeaseHeld("fencing token inválido")
            row = connection.execute(
                """insert into app.games
                  (id,owner_id,schema_version,state,state_sha256,status,player_name,
                   class_name,player_level,location_name,world_day,game_over,combat_simulation)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                returning version""",
                (
                    game_id, principal.user_id, int(document["schema_version"]),
                    Jsonb(document), digest, projection["status"],
                    projection["player_name"], projection["class_name"],
                    projection["player_level"], projection["location_name"],
                    projection["world_day"], projection["game_over"],
                    projection["combat_simulation"],
                ),
            ).fetchone()
            version = int(row["version"])
            from services.turn_effects import current_effects
            from infrastructure.pgvector_memory import PgVectorMemoryStore
            effects = current_effects()
            if effects is not None:
                effects.flush(connection, memory_store=PgVectorMemoryStore(self.pool),
                    principal=principal, game_id=game_id,
                    epoch=int((document.get('continuity') or {}).get('timeline_epoch', 0)),
                    version=version)
            PostgresGameStore._insert_events(connection, principal.user_id, game_id, document)
            if checkpoint:
                world = document.get("world") or {}
                continuity = document.get("continuity") or {}
                connection.execute(
                    """insert into app.game_checkpoints
                      (game_id,owner_id,game_version,canonical_turn,timeline_epoch,
                       memory_commit_version,state,state_sha256)
                    values(%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (game_id, principal.user_id, version,
                     int(world.get("turn_count", 0) or 0),
                     int(continuity.get("timeline_epoch", 0) or 0),
                     version, Jsonb(document), digest),
                )
            persisted_receipt = dict(receipt)
            persisted_receipt["committed_version"] = version
            connection.execute(
                """update app.operations set game_id=%s,status='completed',
                  committed_game_version=%s,receipt=%s,lease_token=null,
                  lease_until=null,finished_at=now()
                where id=%s and owner_id=%s and lease_token=%s""",
                (game_id, version, Jsonb(persisted_receipt), claim.operation_id,
                 principal.user_id, claim.lease_token),
            )
        return version, persisted_receipt

    def commit_delete(
        self, principal: Principal, claim: OperationClaim, game_id: UUID,
        *, receipt: Mapping[str, Any],
    ) -> dict[str, Any]:
        if claim.game_id is not None:
            raise ValueError("delete usa operação desacoplada para preservar o recibo")
        with self.pool.connection() as connection, connection.transaction():
            operation = connection.execute(
                """select status,lease_token from app.operations
                where id=%s and owner_id=%s for update""",
                (claim.operation_id, principal.user_id),
            ).fetchone()
            if (not operation or operation["status"] != "running"
                    or operation["lease_token"] != claim.lease_token):
                raise LeaseHeld("fencing token inválido")
            deleted = connection.execute(
                "delete from app.games where id=%s and owner_id=%s",
                (game_id, principal.user_id),
            )
            if deleted.rowcount != 1:
                raise NotFound("campanha não encontrada")
            persisted = dict(receipt)
            connection.execute(
                """update app.operations set status='completed',receipt=%s,
                  lease_token=null,lease_until=null,finished_at=now()
                where id=%s and owner_id=%s and lease_token=%s""",
                (Jsonb(persisted), claim.operation_id, principal.user_id,
                 claim.lease_token),
            )
        return persisted

    def receipt(self, principal: Principal, operation_id: UUID, *,
                game_id: UUID | None = None, kind: str | None = None,
                request_hash: str | None = None) -> dict[str, Any] | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "select status,receipt,game_id,kind,request_sha256 from app.operations where id=%s and owner_id=%s",
                (operation_id, principal.user_id),
            ).fetchone()
            if not row:
                return None
            if kind is not None:
                # Creation acquires an ID before a campaign exists; completion
                # fills game_id. Kind/hash still bind that initial request.
                if (row['kind'] != kind or row['request_sha256'] != request_hash
                        or (kind != 'new_game' and row['game_id'] != game_id)):
                    raise Conflict('operation_request_mismatch')
            return row["receipt"] if row["status"] == "completed" else None

    def heartbeat(self, claim: OperationClaim) -> None:
        interval = timedelta(seconds=self.lease_seconds)
        with self.pool.connection() as connection, connection.transaction():
            if claim.game_id is not None:
                connection.execute(
                    "select id from app.games where id=%s for update", (claim.game_id,),
                ).fetchone()
            result = connection.execute(
                """
                update app.operations set lease_until=now()+%s,heartbeat_at=now()
                where id=%s and status='running' and lease_token=%s
                """,
                (interval, claim.operation_id, claim.lease_token),
            )
            if result.rowcount != 1:
                raise LeaseHeld("fencing token inválido")
            if claim.game_id is not None:
                connection.execute(
                    """
                    update app.games set active_lease_until=now()+%s
                    where id=%s and active_operation_id=%s and active_lease_token=%s
                    """,
                    (interval, claim.game_id, claim.operation_id, claim.lease_token),
                )

    def complete(self, claim: OperationClaim, *, committed_version: int | None,
                 receipt: Mapping[str, Any]) -> dict[str, Any]:
        with self.pool.connection() as connection, connection.transaction():
            if claim.game_id is not None:
                connection.execute(
                    "select id from app.games where id=%s for update", (claim.game_id,),
                ).fetchone()
            result = connection.execute(
                """
                update app.operations set status='completed',committed_game_version=%s,
                  receipt=%s,lease_token=null,lease_until=null,finished_at=now()
                where id=%s and status='running' and lease_token=%s
                """,
                (committed_version, Jsonb(dict(receipt)), claim.operation_id, claim.lease_token),
            )
            if result.rowcount != 1:
                raise LeaseHeld("worker atrasado não pode confirmar")
            if claim.game_id is not None:
                connection.execute(
                    """
                    update app.games set active_operation_id=null,active_lease_token=null,
                      active_lease_until=null where id=%s and active_operation_id=%s
                      and active_lease_token=%s
                    """,
                    (claim.game_id, claim.operation_id, claim.lease_token),
                )
        return dict(receipt)

    def fail(self, claim: OperationClaim, error_code: str) -> None:
        with self.pool.connection() as connection, connection.transaction():
            if claim.game_id is not None:
                connection.execute(
                    "select id from app.games where id=%s for update", (claim.game_id,),
                ).fetchone()
            result = connection.execute(
                """
                update app.operations set status='failed',error_code=%s,lease_token=null,
                  lease_until=null,finished_at=now()
                where id=%s and status='running' and lease_token=%s
                """,
                (error_code[:100], claim.operation_id, claim.lease_token),
            )
            if result.rowcount != 1:
                raise LeaseHeld("fencing token inválido")
            if claim.game_id is not None:
                connection.execute(
                    """
                    update app.games set active_operation_id=null,active_lease_token=null,
                      active_lease_until=null where id=%s and active_operation_id=%s
                      and active_lease_token=%s
                    """,
                    (claim.game_id, claim.operation_id, claim.lease_token),
                )


class PostgresRateLimiter:
    def __init__(self, pool: PostgresPool) -> None:
        self.pool = pool

    def consume(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit e window_seconds precisam ser positivos")
        interval = timedelta(seconds=window_seconds)
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """
                insert into app.rate_limit_buckets
                  (bucket_key,window_started_at,window_seconds,request_count)
                values (%s,now(),%s,1)
                on conflict (bucket_key) do update set
                  window_started_at = case
                    when app.rate_limit_buckets.window_started_at + %s <= now()
                    then now() else app.rate_limit_buckets.window_started_at end,
                  window_seconds = excluded.window_seconds,
                  request_count = case
                    when app.rate_limit_buckets.window_started_at + %s <= now()
                    then 1 else app.rate_limit_buckets.request_count + 1 end,
                  updated_at=now()
                returning request_count,
                  greatest(0,extract(epoch from window_started_at + %s - now()))::integer
                    as retry_after
                """,
                (key, window_seconds, interval, interval, interval),
            ).fetchone()
        count = int(row["request_count"])
        return RateLimitDecision(count <= limit, max(0, limit - count),
                                 int(row["retry_after"]) if count > limit else 0)
