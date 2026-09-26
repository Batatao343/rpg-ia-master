"""A provider's uncertain result must never become a second paid request."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip('psycopg')


def test_uncertain_art_result_cannot_be_generated_again(monkeypatch):
    from infrastructure.contracts import Conflict
    from infrastructure.pgvector_memory import PgVectorMemoryStore
    import workers.run_worker as module

    status, calls = ['pending'], []
    class Repository:
        def __init__(self, *args, **kwargs):
            pass
        def begin(self, _):
            if status[0] != 'pending':
                raise Conflict('requires reconciliation')
            status[0] = 'generating'
            return True
        def fail(self, _, code, *, retryable):
            assert code == 'external_result_uncertain'
            assert not retryable
            status[0] = 'failed'

    def generate(**kwargs):
        calls.append('provider')
        raise TimeoutError('provider may have produced an image')

    monkeypatch.setenv('OPENAI_API_KEY', 'fake-local-key')
    monkeypatch.setattr(module, 'get_runtime', lambda: SimpleNamespace(
        resources=[object()], memory_store=PgVectorMemoryStore(None), blob_store=object()))
    monkeypatch.setattr(module, 'DynamicArtRepository', Repository)
    monkeypatch.setattr(module, 'OpenAIImageGenerator', lambda key: object())
    monkeypatch.setattr(module, 'generate_dynamic_art_job', generate)
    handler = module.build_handlers()['generate_dynamic_art']
    payload = dict(generation={'generation_id': str(uuid4()), 'model': 'fake', 'profile_version': 'test'},
                   owner_id=str(uuid4()), game_id=str(uuid4()), asset_id=str(uuid4()))
    with pytest.raises(TimeoutError):
        handler(payload)
    with pytest.raises(Conflict):
        handler(payload)
    assert calls == ['provider']
