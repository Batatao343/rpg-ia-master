"""Registro durável e idempotente de gerações antes da chamada ao provider."""

from __future__ import annotations

from contextlib import nullcontext

import hashlib
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from psycopg.types.json import Jsonb

from infrastructure.contracts import Conflict, Principal
from infrastructure.postgres import PostgresPool
from services.art_brief import ArtBrief, render_image_prompt
from services.art_triggers import ArtGenerationRequest


class DynamicArtRepository:
    def __init__(self, pool: PostgresPool, *, model: str, profile_version: str) -> None:
        self.pool = pool
        self.model = model
        self.profile_version = profile_version

    def reserve(self, principal: Principal, game_id: UUID, *, timeline_epoch: int,
                generation_id: UUID, request: ArtGenerationRequest, brief: ArtBrief, connection=None) -> dict[str, Any]:
        prompt = render_image_prompt(brief)
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        anchor_hash = hashlib.sha256("\n".join(brief["reference_asset_ids"]).encode()).hexdigest()
        scope = self.pool.connection() if connection is None else nullcontext(connection)
        with scope as connection, connection.transaction():
            row = connection.execute(
                """insert into app.art_generations
                (generation_id,owner_id,game_id,timeline_epoch,arc_instance_id,trigger_kind,
                 trigger_instance_id,subject_type,subject_id,status,model,profile_version,
                 prompt_hash,anchor_hash,private_brief)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s,%s,%s,%s,%s)
                on conflict(game_id,timeline_epoch,trigger_kind,trigger_instance_id,profile_version)
                do nothing returning *""",
                (generation_id, principal.user_id, game_id, timeline_epoch,
                 request.arc_instance_id, request.trigger_kind, request.trigger_instance_id,
                 request.subject_type, request.subject_id, self.model, self.profile_version,
                 prompt_hash, anchor_hash, Jsonb(dict(brief))),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    """select * from app.art_generations where game_id=%s and timeline_epoch=%s
                    and trigger_kind=%s and trigger_instance_id=%s and profile_version=%s""",
                    (game_id, timeline_epoch, request.trigger_kind,
                     request.trigger_instance_id, self.profile_version),
                ).fetchone()
                if row["prompt_hash"] != prompt_hash:
                    raise Conflict("gatilho de arte reutilizado com brief divergente")
            return dict(row)

    def get(self, principal: Principal, generation_id: UUID) -> dict[str, Any] | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                """select g.*, not exists (
                    select 1 from app.jobs j where j.kind='generate_dynamic_art'
                    and j.dedupe_key='art:' || g.generation_id::text
                    and j.status='running' and j.lease_until > now()
                ) as worker_inactive
                from app.art_generations g where generation_id=%s and owner_id=%s""",
                (generation_id, principal.user_id),
            ).fetchone()
            return dict(row) if row else None

    def begin(self, generation_id: UUID) -> bool:
        """Claim a generation once; ``False`` means it already completed."""
        with self.pool.connection() as connection, connection.transaction():
            result = connection.execute(
                """update app.art_generations set status='generating',
                attempt_count=least(3,attempt_count+1),updated_at=now()
                where generation_id=%s and status in ('pending','failed_retryable')""",
                (generation_id,),
            )
            if result.rowcount == 1:
                return True
            if result.rowcount != 1:
                row = connection.execute(
                    "select status from app.art_generations where generation_id=%s",
                    (generation_id,),
                ).fetchone()
                if row and row["status"] == "ready":
                    return False
                if not row or row["status"] != "ready":
                    raise Conflict("geração não está disponível para execução")
        return False

    def set_quality(self, principal: Principal, generation_id: UUID, *, approved: bool) -> None:
        with self.pool.connection() as connection, connection.transaction():
            result = connection.execute(
                """update app.art_generations set status=%s,updated_at=now()
                where generation_id=%s and owner_id=%s and status in ('ready','rejected_quality')""",
                ("ready" if approved else "rejected_quality",
                 generation_id, principal.user_id),
            )
            if result.rowcount != 1:
                raise Conflict("geração não está pronta para avaliação")

    @staticmethod
    def _record_usage(connection, generation: dict, *, model: str,
                      usage: dict) -> dict:
        from infrastructure.usage_events import append_usage_events
        from services.usage_metering import normalize_attempts, safe_provider_usage

        generation_id = generation["generation_id"]
        safe_usage = safe_provider_usage(usage, image_generated=True)
        connection.execute(
            """insert into app.operations
              (id,owner_id,game_id,kind,status,request_sha256,finished_at)
            values (%s,%s,%s,'art','completed',%s,now())
            on conflict (id) do nothing""",
            (generation_id, generation["owner_id"], generation["game_id"],
             generation["prompt_hash"]),
        )
        operation = connection.execute(
            """select kind,request_sha256 from app.operations
            where id=%s and owner_id=%s and game_id=%s""",
            (generation_id, generation["owner_id"], generation["game_id"]),
        ).fetchone()
        if (not operation or operation["kind"] != "art"
                or operation["request_sha256"] != generation["prompt_hash"]):
            raise Conflict("operação de imagem divergiu")
        usage_events = normalize_attempts([{
            "provider": "openai", "model": model,
            "outcome": "success", "network_attempted": True, "usage": safe_usage,
        }], operation_id=generation_id, component="image", category="image")
        append_usage_events(
            connection, owner_id=generation["owner_id"],
            operation_id=generation_id, game_id=generation["game_id"],
            events=usage_events,
        )
        connection.execute(
            """update app.art_generations set usage_json=%s,updated_at=now()
            where generation_id=%s""",
            (Jsonb(safe_usage), generation_id),
        )
        return safe_usage

    def record_usage(self, generation_id: UUID, *, model: str, usage: dict) -> None:
        """Commit provider usage before image processing or blob I/O can fail."""
        from services.job_fence import require_job_fence

        with self.pool.connection() as connection, connection.transaction():
            require_job_fence(connection)
            generation = connection.execute(
                "select * from app.art_generations where generation_id=%s for update",
                (generation_id,),
            ).fetchone()
            if not generation or generation["status"] != "generating":
                raise Conflict("geração não encontrada")
            self._record_usage(connection, generation, model=model, usage=usage)

    def complete(self, generation_id: UUID, *, asset_id: UUID,
                 result: dict[str, Any]) -> None:
        variants = list(result.get("variants") or [])
        with self.pool.connection() as connection, connection.transaction():
            from services.job_fence import require_job_fence

            require_job_fence(connection)
            generation = connection.execute(
                "select * from app.art_generations where generation_id=%s for update",
                (generation_id,),
            ).fetchone()
            if not generation or generation['status'] != 'generating':
                raise Conflict("geração não encontrada")
            safe_usage = self._record_usage(
                connection, generation,
                model=result.get("model") or generation["model"],
                usage=result.get("usage") or {},
            )
            display_asset_id = None
            for variant in variants:
                row_id = uuid5(NAMESPACE_URL, f"{asset_id}:{variant['variant']}")
                if variant["variant"] == "full":
                    display_asset_id = row_id
                connection.execute(
                    """insert into app.assets
                    (id,owner_id,game_id,entity_id,asset_kind,variant,status,visibility,
                     bucket,object_key,mime_type,bytes,width,height,sha256,source_provider,
                     source_model,prompt_sha256,ready_at)
                    values(%s,%s,%s,%s,%s,%s,'ready','public','rpg-dynamic',%s,%s,%s,%s,%s,%s,
                           'openai',%s,%s,now()) on conflict(object_key) do nothing""",
                    (row_id, generation["owner_id"], generation["game_id"],
                     generation["subject_id"],
                     "epic" if generation["subject_type"] == "scene" else generation["subject_type"],
                     variant["variant"], variant["key"], variant["mime_type"],
                     variant["bytes"], variant["width"], variant["height"], variant["sha256"],
                     result.get("model"), generation["prompt_hash"]),
                )
            connection.execute(
                """update app.art_generations set status='ready',asset_id=%s,
                usage_json=%s,updated_at=now() where generation_id=%s""",
                (display_asset_id, Jsonb(safe_usage), generation_id),
            )

    def fail(self, generation_id: UUID, error_code: str, *, retryable: bool = True) -> None:
        with self.pool.connection() as connection, connection.transaction():
            from services.job_fence import require_job_fence

            require_job_fence(connection)
            connection.execute(
                """update app.art_generations set
                status=%s,error_code=%s,updated_at=now()
                where generation_id=%s and status='generating'""",
                ("failed_retryable" if retryable else "failed", error_code[:100], generation_id),
            )

    def assets(self, principal: Principal, generation_id: UUID) -> list[dict[str, Any]]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                """select a.id,a.variant,a.object_key,a.mime_type,a.bytes,
                         a.width,a.height,a.sha256
                from app.assets a join app.art_generations g
                  on g.game_id=a.game_id and g.subject_id=a.entity_id
                where g.generation_id=%s and g.owner_id=%s and a.status='ready'
                  and a.prompt_sha256=g.prompt_hash and a.source_model=g.model
                order by a.variant""",
                (generation_id, principal.user_id),
            ).fetchall()
            return [dict(row) for row in rows]
