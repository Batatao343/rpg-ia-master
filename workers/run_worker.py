"""Worker local/portátil para embeddings, crônica e arte dinâmica."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.openai_images import OpenAIImageGenerator
from infrastructure.pgvector_memory import PgVectorMemoryStore
from infrastructure.runtime import get_runtime
from services.chronicle_repository import ChronicleRepository
from services.dynamic_art import DynamicArtRepository
from workers.chronicle_jobs import compress_chronicle_job
from workers.dynamic_art_jobs import generate_dynamic_art_job
from workers.embedding_jobs import embed_memory_job
from workers.job_worker import JobWorker


def build_handlers():
    runtime = get_runtime()
    if not runtime.resources:
        raise RuntimeError("worker durável exige runtime Postgres")
    pool = runtime.resources[0]
    if not isinstance(runtime.memory_store, PgVectorMemoryStore):
        raise RuntimeError("worker durável exige PgVectorMemoryStore")

    def generate(payload: dict) -> dict:
        generation = dict(payload["generation"])
        generation_id = UUID(str(generation["generation_id"]))
        repository = DynamicArtRepository(
            pool, model=generation["model"],
            profile_version=generation["profile_version"],
        )
        try:
            if not repository.begin(generation_id):
                return {"status": "already_ready", "generation_id": str(generation_id)}
            result = generate_dynamic_art_job(
                generator=OpenAIImageGenerator(os.environ["OPENAI_API_KEY"]),
                blob_store=runtime.blob_store, generation=generation,
                owner_id=UUID(str(payload["owner_id"])),
                game_id=UUID(str(payload["game_id"])),
                asset_id=UUID(str(payload["asset_id"])),
            )
            repository.complete(
                generation_id, asset_id=UUID(str(payload["asset_id"])), result=result,
            )
            return result
        except Exception as exc:
            repository.fail(generation_id, type(exc).__name__)
            raise

    def embed(payload: dict) -> dict:
        import rag
        embeddings = rag.get_embeddings()
        if embeddings is None:
            raise RuntimeError("provider de embedding indisponível")

        def query(text: str):
            values = embeddings.embed_query(text)
            if len(values) != 1024:
                raise ValueError(f"embedding incompatível: {len(values)} dimensões")
            return values

        return embed_memory_job(runtime.memory_store, payload, query)

    def compress(payload: dict) -> dict:
        digest = compress_chronicle_job(payload)
        ChronicleRepository(pool, runtime.memory_store).complete(payload, digest)
        return {"status": digest["status"], "source_hash": digest["source_hash"]}

    return {
        "generate_dynamic_art": generate,
        "embed_memory": embed,
        "compress_chronicle": compress,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-id", default="local-worker-1")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    worker = JobWorker(get_runtime().job_queue, build_handlers(), worker_id=args.worker_id)
    while True:
        processed = worker.run_once(limit=10)
        if args.once:
            return 0
        if processed == 0:
            time.sleep(0.5)


if __name__ == "__main__":
    raise SystemExit(main())
