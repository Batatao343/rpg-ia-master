"""MemoryStore PostgreSQL: fato bruto durável, vetor assíncrono e FTS fallback."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from typing import Any

from psycopg.types.json import Jsonb

from infrastructure.contracts import Conflict, MemoryDocument, MemoryQuery, MemoryWriteIntent
from infrastructure.postgres import PostgresPool
from services.memory_intents import intent_sha256, normalized_intent


Embedder = Callable[[str], Sequence[float]]
_VISIBILITY = {"public": 0, "hidden": 1, "secret": 2}


def vector_literal(values: Sequence[float], dimensions: int = 1024) -> str:
    if len(values) != dimensions:
        raise ValueError(f"embedding deve ter {dimensions} dimensões")
    return "[" + ",".join(format(float(value), ".9g") for value in values) + "]"


class PgVectorMemoryStore:
    def __init__(self, pool: PostgresPool, *, profile_id: str = "local-1024",
                 embedder: Embedder | None = None) -> None:
        self.pool = pool
        self.profile_id = profile_id
        self.embedder = embedder

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
                intent.document.document_id, owner_id, game_id, npc_id,
                intent.document.scope, intent.document.text, digest, Jsonb(metadata),
                metadata.get("provenance"), metadata.get("confidence"),
                metadata.get("source_id"), metadata.get("source_turn"),
                list(metadata.get("canonical_entity_ids", [])),
                metadata.get("visibility", "public"), intent.timeline_epoch,
                metadata.get("commit_version"), self.profile_id,
            ),
        ).fetchone()
        if row is None:
            existing = connection.execute(
                "select content,metadata,owner_id,game_id,npc_id,scope,timeline_epoch from app.memory_documents where id=%s",
                (intent.document.document_id,),
            ).fetchone()
            comparable = MemoryWriteIntent(
                MemoryDocument(intent.document.document_id, existing["content"], existing["scope"], dict(existing["metadata"])),
                intent.principal if existing["owner_id"] else None,
                existing["game_id"], existing["npc_id"], existing["timeline_epoch"],
            )
            # Repeating an identical fact on a later commit keeps the original
            # visibility boundary, not a new version that changes its identity.
            from dataclasses import replace
            comparison_metadata = dict(intent.document.metadata)
            comparison_metadata['commit_version'] = existing['metadata'].get('commit_version')
            if 'commit_version' not in existing['metadata']:
                comparison_metadata.pop('commit_version', None)
            identity_digest = intent_sha256(replace(intent,
                document=replace(intent.document, metadata=comparison_metadata)))
            if intent_sha256(comparable) != identity_digest:
                raise Conflict("memory_id reutilizado com conteúdo divergente")
            return
        connection.execute(
            """
            insert into app.jobs(id,owner_id,game_id,kind,dedupe_key,status,payload,max_attempts)
            values (gen_random_uuid(),%s,%s,'embed_memory',%s,'queued',%s,5)
            on conflict (kind,dedupe_key) do nothing
            """,
            (owner_id, game_id, intent.document.document_id,
             Jsonb({"memory_id": intent.document.document_id, "content_sha256": digest,
                    "profile_id": self.profile_id, "timeline_epoch": intent.timeline_epoch,
                    "commit_version": metadata.get('commit_version')})),
        )

    def set_embedding(self, document_id: str, values: Sequence[float], *, content_sha256: str) -> None:
        vector = vector_literal(values)
        with self.pool.connection() as connection, connection.transaction():
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
            if request.vector is not None and request.embedding_profile_id not in {None, self.profile_id}:
                raise ValueError("embedding_profile_id incompatível com o adapter")
            if request.vector is not None:
                vector = vector_literal(request.vector)
            elif self.embedder is not None:
                try:
                    vector = vector_literal(self.embedder(request.text))
                except Exception:
                    vector = None
            else:
                vector = None
            if vector:
                rows = connection.execute(
                    f"""select *,1-(embedding <=> %s::extensions.vector) as score
                    from app.memory_documents where {where} and embedding_status='ready'
                    order by embedding <=> %s::extensions.vector limit %s""",
                    [vector, *params, vector, request.k],
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
        return sorted(by_id.values(), key=lambda item: item.score or 0, reverse=True)[:request.k]

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
