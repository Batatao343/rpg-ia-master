"""MemoryStore PostgreSQL: fato bruto durável, vetor assíncrono e FTS fallback."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from typing import Any

from psycopg.types.json import Jsonb

from infrastructure.contracts import Conflict, MemoryDocument, MemoryQuery, MemoryWriteIntent
from infrastructure.db_roles import admin_connection
from infrastructure.postgres import PostgresPool
from services.memory_intents import intent_sha256, normalized_intent

Embedder = Callable[[str], Sequence[float]]
_VISIBILITY = {"public": 0, "hidden": 1, "secret": 2}


def vector_literal(values: Sequence[float], dimensions: int = 1024) -> str:
    if len(values) != dimensions:
        raise ValueError(f"embedding deve ter {dimensions} dimensões")
    return "[" + ",".join(format(float(value), ".9g") for value in values) + "]"


def configured_profile_id() -> str:
    """Perfil de embedding do provider configurado (SPEC-234 R9).

    Fonte única para TODO adapter pgvector do processo (turno, worker, consulta):
    staging com um perfil e `set_embedding`/consulta com outro deixaria o
    documento órfão (Conflict no worker, nunca recuperado semanticamente).
    """
    try:
        import rag

        return rag.embedding_profile_id()
    except Exception as exc:  # pragma: no cover - rag indisponível: perfil legado
        from observability.telemetry import log_event

        log_event(
            "vector",
            "profile_fallback",
            level="warning",
            error_type=type(exc).__name__,
            profile="local-1024",
        )
        return "local-1024"


class PgVectorMemoryStore:
    def __init__(
        self,
        pool: PostgresPool,
        *,
        profile_id: str = "local-1024",
        embedder: Embedder | None = None,
        dimensions: int = 1024,
    ) -> None:
        if dimensions != 1024:  # SPEC-234 R9: coluna vector(1024)
            raise ValueError(f"pgvector exige 1024 dimensões, recebido {dimensions}")
        self.pool = pool
        self.profile_id = profile_id
        self.embedder = embedder
        self.dimensions = dimensions
        self._profile_ready = False

    def _insert_profile(self, connection) -> None:
        provider, _, rest = self.profile_id.partition("-")
        connection.execute(
            """insert into app.embedding_profiles(id,provider,model,dimensions,status,activated_at)
            values (%s,%s,%s,%s,'active',now()) on conflict (id) do nothing""",
            (self.profile_id, provider, rest, self.dimensions),
        )

    def _ensure_profile(self, connection) -> None:
        """Garante a linha de `app.embedding_profiles` do perfil configurado."""
        if self._profile_ready or self.profile_id == "local-1024":
            return
        # SPEC-224: a role de request (`rpg_api`) so le `embedding_profiles`. Normalmente a linha ja
        # existe (boot: `ensure_profile()` com credencial de sistema); se faltar, o insert e feito
        # numa conexao de sistema propria (autonoma), nunca na conexao escopada ao owner.
        if connection.execute(
            "select 1 from app.embedding_profiles where id=%s", (self.profile_id,)
        ).fetchone():
            self._profile_ready = True
            return
        if getattr(self.pool, "_request_rls", False):
            with admin_connection(self.pool) as system, system.transaction():
                self._insert_profile(system)
        else:
            self._insert_profile(connection)
        self._profile_ready = True

    def ensure_profile(self) -> None:
        """Cria o perfil de embedding com credencial de sistema (boot/worker)."""
        if self.profile_id == "local-1024":
            return
        with admin_connection(self.pool) as connection, connection.transaction():
            self._insert_profile(connection)
        self._profile_ready = True

    def migrate_legacy_profile(self, legacy: str = "local-1024") -> int:
        """Migra documentos do perfil legado para o perfil do provider (idempotente).

        Os vetores existentes foram gerados pelo provider configurado, entao o
        rename preserva embeddings 'ready'. Devolve quantas linhas mudaram.
        """
        if self.profile_id == legacy:
            return 0
        with admin_connection(self.pool) as connection, connection.transaction():
            self._insert_profile(connection)
            self._profile_ready = True
            result = connection.execute(
                "update app.memory_documents set embedding_profile_id=%s where embedding_profile_id=%s",
                (self.profile_id, legacy),
            )
            return int(getattr(result, "rowcount", 0) or 0)

    @staticmethod
    def _scope_values(intent: MemoryWriteIntent) -> tuple[Any, Any, Any]:
        scope = intent.document.scope
        if scope in {"lore", "rules"}:
            if intent.principal or intent.game_id or intent.npc_id:
                raise ValueError("memória global não recebe owner/game/npc")
            return None, None, None
        if not intent.principal or not intent.game_id:
            raise ValueError("memória privada exige principal e game_id")
        if scope == "npc" and not intent.npc_id:
            raise ValueError("memória NPC exige npc_id")
        if scope != "npc" and intent.npc_id:
            raise ValueError("npc_id só é válido no scope npc")
        return intent.principal.user_id, intent.game_id, intent.npc_id

    def stage(self, intent: MemoryWriteIntent) -> None:
        from services.turn_effects import current_effects

        effects = current_effects()
        if effects is not None:
            effects.memory.add(intent)
            return
        with self.pool.connection() as connection, connection.transaction():
            self.stage_on(connection, intent)

    def stage_on(self, connection, intent: MemoryWriteIntent) -> None:
        intent = normalized_intent(intent)
        self._ensure_profile(connection)
        owner_id, game_id, npc_id = self._scope_values(intent)
        metadata = intent.document.metadata
        digest = hashlib.sha256(intent.document.text.encode("utf-8")).hexdigest()
        identity_digest = intent_sha256(intent)
        row = connection.execute(
            """
            insert into app.memory_documents
              (id,owner_id,game_id,npc_id,scope,content,content_sha256,metadata,
               provenance,confidence,source_id,source_turn,canonical_entity_ids,
               visibility,timeline_epoch,commit_version,embedding_profile_id)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (id) do nothing returning id
            """,
            (
                intent.document.document_id,
                owner_id,
                game_id,
                npc_id,
                intent.document.scope,
                intent.document.text,
                digest,
                Jsonb(metadata),
                metadata.get("provenance"),
                metadata.get("confidence"),
                metadata.get("source_id"),
                metadata.get("source_turn"),
                list(metadata.get("canonical_entity_ids", [])),
                metadata.get("visibility", "public"),
                intent.timeline_epoch,
                metadata.get("commit_version"),
                self.profile_id,
            ),
        ).fetchone()
        if row is None:
            existing = connection.execute(
                "select content,metadata,owner_id,game_id,npc_id,scope,timeline_epoch,embedding_status from app.memory_documents where id=%s",
                (intent.document.document_id,),
            ).fetchone()
            comparable = MemoryWriteIntent(
                MemoryDocument(
                    intent.document.document_id,
                    existing["content"],
                    existing["scope"],
                    dict(existing["metadata"]),
                ),
                intent.principal if existing["owner_id"] else None,
                existing["game_id"],
                existing["npc_id"],
                existing["timeline_epoch"],
            )
            # Repeating an identical fact on a later commit keeps the original
            # visibility boundary, not a new version that changes its identity.
            from dataclasses import replace

            comparison_metadata = dict(intent.document.metadata)
            comparison_metadata["commit_version"] = existing["metadata"].get("commit_version")
            if "commit_version" not in existing["metadata"]:
                comparison_metadata.pop("commit_version", None)
            identity_digest = intent_sha256(
                replace(intent, document=replace(intent.document, metadata=comparison_metadata))
            )
            if intent_sha256(comparable) != identity_digest:
                raise Conflict("memory_id reutilizado com conteúdo divergente")
            if existing["embedding_status"] == "pending":
                # SPEC-236 R9: a dead embedding job would leave the fact lexical-only forever.
                from infrastructure.postgres_jobs import revive_dead_job

                revive_dead_job(connection, "embed_memory", intent.document.document_id)
            return
        connection.execute(
            """
            insert into app.jobs(id,owner_id,game_id,kind,dedupe_key,status,payload,max_attempts)
            values (gen_random_uuid(),%s,%s,'embed_memory',%s,'queued',%s,5)
            on conflict (kind,dedupe_key) do nothing
            """,
            (
                owner_id,
                game_id,
                intent.document.document_id,
                Jsonb(
                    {
                        "memory_id": intent.document.document_id,
                        "content_sha256": digest,
                        "profile_id": self.profile_id,
                        "timeline_epoch": intent.timeline_epoch,
                        "commit_version": metadata.get("commit_version"),
                    }
                ),
            ),
        )

    def set_embedding(
        self, document_id: str, values: Sequence[float], *, content_sha256: str
    ) -> None:
        vector = vector_literal(values)
        with admin_connection(self.pool) as connection, connection.transaction():
            result = connection.execute(
                """
                update app.memory_documents set embedding=%s::extensions.vector,
                  embedding_status='ready'
                where id=%s and content_sha256=%s and embedding_profile_id=%s
                  and discarded_at is null
                """,
                (vector, document_id, content_sha256, self.profile_id),
            )
            if result.rowcount != 1:
                raise Conflict("documento/hash/profile divergente")

    @staticmethod
    def _filters(request: MemoryQuery) -> tuple[str, list[Any]]:
        clauses = ["scope=%s", "discarded_at is null", "embedding_status <> 'discarded'"]
        params: list[Any] = [request.scope]
        if request.scope not in {"lore", "rules"}:
            if not request.principal or not request.game_id:
                raise ValueError("query privada exige principal e game_id")
            clauses.extend(["owner_id=%s", "game_id=%s"])
            params.extend([request.principal.user_id, request.game_id])
        if request.scope == "npc":
            if not request.npc_id:
                raise ValueError("query NPC exige npc_id")
            clauses.append("npc_id=%s")
            params.append(request.npc_id)
        clauses.append("case visibility when 'public' then 0 when 'hidden' then 1 else 2 end <= %s")
        params.append(_VISIBILITY[request.max_visibility])
        return " and ".join(clauses), params

    @staticmethod
    def _document(row: dict[str, Any], score: float | None) -> MemoryDocument:
        metadata = dict(row["metadata"])
        metadata.setdefault("visibility", row["visibility"])
        metadata.setdefault("embedding_status", row["embedding_status"])
        return MemoryDocument(row["id"], row["content"], row["scope"], metadata, score)

    def query(self, request: MemoryQuery) -> list[MemoryDocument]:
        where, params = self._filters(request)
        by_id: dict[str, MemoryDocument] = {}
        with self.pool.connection() as connection:
            if request.vector is not None and request.embedding_profile_id not in {
                None,
                self.profile_id,
            }:
                raise ValueError("embedding_profile_id incompatível com o adapter")
            if request.vector is not None:
                vector = vector_literal(request.vector)
            elif self.embedder is not None:
                try:
                    vector = vector_literal(self.embedder(request.text))
                except Exception as exc:
                    from observability.telemetry import log_event

                    log_event(
                        "vector",
                        "semantic_degraded",
                        level="warning",
                        error_type=type(exc).__name__,
                    )
                    vector = None
            else:
                vector = None
            if vector:
                rows = connection.execute(
                    f"""select *,1-(embedding <=> %s::extensions.vector) as score
                    from app.memory_documents where {where} and embedding_status='ready'
                      and embedding_profile_id=%s
                    order by embedding <=> %s::extensions.vector limit %s""",
                    [vector, *params, self.profile_id, vector, request.k],
                ).fetchall()
                for row in rows:
                    document = self._document(row, float(row["score"]))
                    document.metadata["retrieval"] = "semantic"
                    by_id[row["id"]] = document
            if request.text.strip():
                rows = connection.execute(
                    f"""select *,ts_rank(search_text,websearch_to_tsquery('simple',%s)) as score
                    from app.memory_documents where {where}
                      and search_text @@ websearch_to_tsquery('simple',%s)
                    order by score desc,created_at desc limit %s""",
                    [request.text, *params, request.text, request.k],
                ).fetchall()
                for row in rows:
                    document = self._document(row, float(row["score"]))
                    document.metadata["retrieval"] = "lexical"
                    by_id.setdefault(row["id"], document)
        return sorted(by_id.values(), key=lambda item: item.score or 0, reverse=True)[: request.k]

    def discard_after(self, *, game_id, timeline_epoch: int, commit_version: int) -> int:
        with self.pool.connection() as connection, connection.transaction():
            result = connection.execute(
                """update app.memory_documents set embedding_status='discarded',discarded_at=now()
                where game_id=%s and discarded_at is null and
                  (timeline_epoch > %s or (timeline_epoch=%s and commit_version > %s))""",
                (game_id, timeline_epoch, timeline_epoch, commit_version),
            )
            connection.execute(
                """update app.jobs set status='cancelled',updated_at=now()
                where game_id=%s and kind='embed_memory' and status in ('queued','retry')
                  and (payload->>'memory_id') in
                    (select id from app.memory_documents where game_id=%s and discarded_at is not null)""",
                (game_id, game_id),
            )
            return result.rowcount
