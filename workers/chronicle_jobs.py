"""Handlers da crônica avançada, fora do turno."""

from services.chronicle_compression import compress_chapter


def compress_chronicle_job(payload: dict, *, llm=None) -> dict:
    chapter = payload.get("chapter")
    if not isinstance(chapter, dict):
        raise ValueError("job sem capítulo")
    return compress_chapter(chapter, llm=llm)
