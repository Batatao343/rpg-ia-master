"""SPEC-213 modo B: aplica a projeção derivada do arquivista (``project_archive``).

O job nasce na MESMA transação do commit do turno (outbox, R9b). O handler lê o
documento commitado, executa o derivado FORA de qualquer transação (LLM) e
publica com compare-and-set: a versão do jogo não pode ter mudado, nenhuma
operação com lease vigente pode estar ativa e o fencing token do job é exigido
no commit (``require_job_fence``). Conflito → ``ProjectionStale`` (retry com
backoff; o próximo turno, dentro da própria cerca, drena se ainda pendente).
"""
from __future__ import annotations

from typing import Any, Callable, Optional
from uuid import UUID

from infrastructure.db_roles import admin_connection


class ProjectionStale(RuntimeError):
    """CAS perdeu para um turno/mutação mais novo; a fila reagenda (R5)."""

    error_code = "projection_stale"


class ProjectionRetry(RuntimeError):
    """Derivado falhou (status ``failed`` já publicado); retry com backoff (R12)."""

    error_code = "projection_failed"


def apply_projection(pool, payload: dict[str, Any], *,
                     executor: Optional[Callable[[dict, dict], dict]] = None,
                     memory_store: Any = None) -> dict[str, Any]:
    from infrastructure.contracts import Principal
    from infrastructure.postgres import PostgresGameStore
    from infrastructure.request_context import principal_scope
    from services import projections
    from services.game_serialization import deserialize_game_state
    from services.job_fence import require_job_fence
    from services.turn_effects import effect_scope

    owner_id, game_id = UUID(str(payload["owner_id"])), UUID(str(payload["game_id"]))
    action_id, epoch = str(payload["action_id"]), int(payload["epoch"])
    with admin_connection(pool) as connection:
        row = connection.execute(
            """select version,state,active_operation_id,
              coalesce(active_lease_until > now(), false) as busy
            from app.games where id=%s and owner_id=%s""",
            (game_id, owner_id),
        ).fetchone()
    if not row:
        return {"status": "gone"}
    if row["active_operation_id"] is not None and row["busy"]:
        # Um turno está com a cerca do jogo e drena a pendência dentro dela (R10):
        # não gasta LLM numa projeção que perderia o CAS.
        raise ProjectionStale("jogo com operação ativa")
    version = int(row["version"])
    state = deserialize_game_state(row["state"])
    plan = projections.normalize_plan(state.get("pending_derived"))
    if plan is None or plan["action_id"] != action_id or plan["epoch"] != epoch:
        # Já drenada (pré-turno/API) ou de outra época (R7b): nada a aplicar.
        return {"status": "superseded"}
    principal = Principal(owner_id, "projection-worker", str(owner_id))
    with principal_scope(principal), effect_scope() as effects:
        drained = projections.run_pending(state, executor=executor)
        entry = drained["projection_state"]["summary"]
        document, digest, view = PostgresGameStore._prepare(drained)
        with admin_connection(pool) as connection, connection.transaction():
            require_job_fence(connection)
            current = connection.execute(
                """select version,active_operation_id,
                  coalesce(active_lease_until > now(), false) as busy
                from app.games where id=%s and owner_id=%s for update""",
                (game_id, owner_id),
            ).fetchone()
            if (not current or int(current["version"]) != version
                    or (current["active_operation_id"] is not None and current["busy"])):
                raise ProjectionStale("versão/operação do jogo mudou")
            updated = connection.execute(
                """update app.games set
                  schema_version=%s,version=version+1,state=%s,state_sha256=%s,
                  status=%s,player_name=%s,class_name=%s,player_level=%s,
                  location_name=%s,world_day=%s,game_over=%s,combat_simulation=%s,
                  updated_at=now()
                where id=%s and owner_id=%s and version=%s
                returning version""",
                _game_update_params(document, digest, view, game_id, owner_id, version),
            ).fetchone()
            if not updated:
                raise ProjectionStale("versão do jogo mudou no commit")
            new_version = int(updated["version"])
            if entry["status"] in ("completed", "stale"):
                if memory_store is None:
                    from infrastructure.pgvector_memory import (
                        PgVectorMemoryStore,
                        configured_profile_id,
                    )
                    memory_store = PgVectorMemoryStore(pool, profile_id=configured_profile_id())
                effects.flush(connection, memory_store=memory_store, principal=principal,
                              game_id=game_id, epoch=epoch, version=new_version)
    if drained.get("pending_derived") is not None:
        # Falha retentável já registrada no documento (attempts/last_error_code):
        # a fila reagenda com backoff (R12).
        raise ProjectionRetry(entry.get("last_error_code") or "exception")
    return {"status": entry["status"], "projected_version": entry["projected_version"],
            "game_version": new_version}


def make_handler(pool, memory_store=None) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Handler ``project_archive`` com o uso de LLM registrado sob o job (SPEC-182)."""

    def project(payload: dict[str, Any]) -> dict[str, Any]:
        from infrastructure.usage_events import append_projection_job_attempt
        from llm_setup import llm_attempt_scope
        from services.job_fence import current_job

        job = current_job()
        attempts: list[dict] = []
        capture_errors: list[Exception] = []

        def capture(event) -> None:
            attempts.append({
                "provider": event.provider, "model": event.model,
                "outcome": event.outcome,
                "network_attempted": event.outcome not in {"build_error", "circuit_open"},
                "usage": dict(event.usage) if event.usage else None,
            })
            if job is not None:
                try:
                    append_projection_job_attempt(pool, job, attempts)
                except Exception as exc:
                    capture_errors.append(exc)

        with llm_attempt_scope(capture):
            result = apply_projection(pool, payload, memory_store=memory_store)
        if capture_errors:
            raise capture_errors[0]
        return result

    return project


def _game_update_params(document, digest, view, game_id, owner_id, version):
    from psycopg.types.json import Jsonb
    return (
        int(document["schema_version"]), Jsonb(document), digest,
        view["status"], view["player_name"], view["class_name"], view["player_level"],
        view["location_name"], view["world_day"], view["game_over"],
        view["combat_simulation"], game_id, owner_id, version,
    )
