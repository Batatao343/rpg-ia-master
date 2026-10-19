"""A provider's uncertain result must never become a second paid request."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")


def test_uncertain_art_result_cannot_be_generated_again(monkeypatch):
    import workers.run_worker as module
    from infrastructure.contracts import Conflict
    from infrastructure.pgvector_memory import PgVectorMemoryStore

    status, calls = ["pending"], []
    generation_id, owner_id, game_id = uuid4(), uuid4(), uuid4()

    class Repository:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *_):
            return {"game_id": game_id, "status": status[0], "image_quote_id": uuid4()}

    class Finance:
        def __init__(self, *_):
            pass

        def dispatch(self, *_):
            if status[0] != "pending":
                raise Conflict("requires reconciliation")
            status[0] = "generating"
            return {}

        def hold_or_release(self, *_):
            status[0] = "failed"

    def generate(**kwargs):
        kwargs["admission"]()
        calls.append("provider")
        raise TimeoutError("provider may have produced an image")

    import services.image_quotes

    monkeypatch.setattr(services.image_quotes, "ImageQuoteRepository", Finance)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-local-key")
    monkeypatch.setattr(
        module,
        "get_runtime",
        lambda: SimpleNamespace(
            resources=[object()], memory_store=PgVectorMemoryStore(None), blob_store=object()
        ),
    )
    monkeypatch.setattr(module, "DynamicArtRepository", Repository)
    monkeypatch.setattr(module, "OpenAIImageGenerator", lambda key: object())
    monkeypatch.setattr(module, "generate_dynamic_art_job", generate)
    handler = module.build_handlers()["generate_dynamic_art"]
    payload = dict(
        generation={
            "generation_id": str(generation_id),
            "model": "fake",
            "profile_version": "test",
        },
        owner_id=str(owner_id),
        game_id=str(game_id),
        asset_id=str(uuid4()),
    )
    with pytest.raises(TimeoutError):
        handler(payload)
    with pytest.raises(Conflict):
        handler(payload)
    assert calls == ["provider"]
