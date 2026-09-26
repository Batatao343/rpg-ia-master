"""Persistência derivada da crônica no perfil Postgres.

Entradas raw continuam no GameState. Esta projeção guarda somente digests e
documentos de busca, sempre escopados por owner/campanha/epoch.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from infrastructure.contracts import (
    MemoryDocument,
    MemoryQuery,
    MemoryWriteIntent,
    Principal,
)
from infrastructure.pgvector_memory import PgVectorMemoryStore
from infrastructure.postgres import PostgresPool
from services.chronicle import ensure_chronicle_ids
from services.chronicle_compression import PROFILE_VERSION, chapter_source_hash, should_compress
from services.chronicle_search import ChronicleCandidate


class ChronicleRepository:
    def __init__(self, pool: PostgresPool, memory: PgVectorMemoryStore) -> None:
        self.pool = pool
        self.memory = memory

    @staticmethod
    def _epoch(state: dict[str, Any]) -> int:
        return int((state.get("continuity") or {}).get("timeline_epoch", 0) or 0)

    def enqueue_due(self, principal: Principal, state: dict[str, Any]) -> int:
        game_id = UUID(str(state["game_id"]))
        epoch = self._epoch(state)
        chapters = ensure_chronicle_ids(
            state.get("chronicle") or [], game_id=str(game_id),
        )
        queued = 0
        for index, chapter in enumerate(chapters):
            closed = index < len(chapters) - 1
            if not should_compress(chapter, closed=closed):
                continue
            source_hash = chapter_source_hash(chapter)
            dedupe = f"{game_id}:{epoch}:{chapter['chapter_id']}:{source_hash}:{PROFILE_VERSION}"
            with self.pool.connection() as connection, connection.transaction():
                row = connection.execute(
                    """insert into app.chronicle_digests
                      (owner_id,game_id,timeline_epoch,chapter_id,source_hash,
                       profile_version,status,digest)
                    values(%s,%s,%s,%s,%s,%s,'pending','{}'::jsonb)
                    on conflict(game_id,timeline_epoch,chapter_id,source_hash,profile_version)
                    do nothing returning id""",
                    (principal.user_id, game_id, epoch, chapter["chapter_id"],
                     source_hash, PROFILE_VERSION),
                ).fetchone()
                if not row:
                    continue
                connection.execute(
                    """insert into app.jobs
                      (id,owner_id,game_id,kind,dedupe_key,status,payload,max_attempts)
                    values(%s,%s,%s,'compress_chronicle',%s,'queued',%s,3)
                    on conflict(kind,dedupe_key) do nothing""",
                    (
                        uuid4(), principal.user_id, game_id, dedupe,
                        Jsonb({
                            "owner_id": str(principal.user_id), "game_id": str(game_id),
                            "timeline_epoch": epoch, "chapter": chapter,
                            "source_hash": source_hash,
                        }),
                    ),
                )
                queued += 1
        return queued

    def complete(self, payload: dict[str, Any], digest: dict[str, Any]) -> None:
        owner_id = UUID(str(payload["owner_id"]))
        game_id = UUID(str(payload["game_id"]))
        epoch = int(payload["timeline_epoch"])
        chapter = ensure_chronicle_ids([payload["chapter"]], game_id=str(game_id))[0]
        source_hash = str(payload["source_hash"])
        if chapter_source_hash(chapter) != source_hash:
            raise ValueError("source hash da crônica divergiu")
        status = str(digest.get("status") or "extractive_fallback")
        with self.pool.connection() as connection, connection.transaction():
            from services.job_fence import require_job_fence

            game = connection.execute(
                'select state,version from app.games where id=%s and owner_id=%s for update',
                (game_id, owner_id),
            ).fetchone()
            if not game or self._epoch(game['state']) != epoch:
                raise ValueError("chronicle timeline was superseded")
            require_job_fence(connection)
            result = connection.execute(
                """update app.chronicle_digests set status=%s,digest=%s
                where owner_id=%s and game_id=%s and timeline_epoch=%s
                  and chapter_id=%s and source_hash=%s and profile_version=%s""",
                (status, Jsonb(digest), owner_id, game_id, epoch,
                 chapter["chapter_id"], source_hash, PROFILE_VERSION),
            )
            if result.rowcount != 1:
                raise ValueError("reserva de digest não encontrada")
            principal = Principal(owner_id, "worker", str(owner_id))
            common = {
                "chapter_id": chapter["chapter_id"], "visibility": "public",
                "source_hash": source_hash,
                "commit_version": game["version"],
            }
            for entry in chapter.get("entries") or []:
                self.memory.stage_on(connection, MemoryWriteIntent(
                    MemoryDocument(
                        f"chronicle:{game_id}:{epoch}:entry:{entry['entry_id']}",
                        str(entry.get("text", "")), "chronicle",
                        {**common, "source_kind": "entry",
                         "domain_document_id": entry["entry_id"],
                         "entry_id": entry["entry_id"], "event_id": entry.get("event_id"),
                         "from_turn": int(entry.get("turn", 0) or 0),
                         "to_turn": int(entry.get("turn", 0) or 0)},
                    ),
                    principal, game_id, timeline_epoch=epoch,
                ))
            self.memory.stage_on(connection, MemoryWriteIntent(
                MemoryDocument(
                    f"chronicle:{game_id}:{epoch}:digest:{chapter['chapter_id']}:{source_hash}",
                    str(digest.get("summary", "")), "chronicle",
                    {**common, "source_kind": "digest",
                     "domain_document_id": f"{chapter['chapter_id']}:digest",
                     "from_turn": int(digest.get("from_turn", 0) or 0),
                     "to_turn": int(digest.get("to_turn", 0) or 0)},
                ),
                principal, game_id, timeline_epoch=epoch,
            ))

    def overlay(self, principal: Principal, state: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(state)
        game_id = UUID(str(result["game_id"]))
        epoch = self._epoch(result)
        chapters = ensure_chronicle_ids(
            result.get("chronicle") or [], game_id=str(game_id),
        )
        with self.pool.connection() as connection:
            rows = connection.execute(
                """select chapter_id,source_hash,digest from app.chronicle_digests
                where owner_id=%s and game_id=%s and timeline_epoch=%s
                  and status in ('ready','extractive_fallback')
                order by created_at desc""",
                (principal.user_id, game_id, epoch),
            ).fetchall()
        by_key = {(row["chapter_id"], row["source_hash"]): dict(row["digest"])
                  for row in rows}
        for chapter in chapters:
            digest = by_key.get((chapter["chapter_id"], chapter_source_hash(chapter)))
            if digest:
                chapter["digest"] = digest
        result["chronicle"] = chapters
        return result

    def semantic_candidates(
        self, principal: Principal, game_id: UUID, query: str, *, top_k: int,
    ) -> list[ChronicleCandidate]:
        docs = self.memory.query(MemoryQuery(
            query, "chronicle", principal=principal, game_id=game_id, k=top_k,
        ))
        candidates = []
        for doc in docs:
            if doc.metadata.get("retrieval") != "semantic":
                continue
            candidates.append(ChronicleCandidate(
                str(doc.metadata.get("domain_document_id") or doc.document_id),
                str(doc.metadata.get("chapter_id") or ""),
                str(doc.metadata.get("source_kind") or "entry"),
                float(doc.score or 0.0),
            ))
        return candidates
