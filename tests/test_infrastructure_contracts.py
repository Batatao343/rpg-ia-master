from __future__ import annotations

import hashlib
import io
from uuid import uuid4

import pytest

from infrastructure.contracts import BlobMetadata, JobRequest, Principal, StaleVersion
from infrastructure.local_adapters import (
    FileBlobStore,
    FileGameStore,
    InlineJobQueue,
    JsonRuntimeCatalogStore,
    LegacyRuntimeCatalogStore,
)


def _principal():
    user_id = uuid4()
    return Principal(user_id, "test", str(user_id), local=True)


def test_file_game_store_isola_owner_e_usa_versao_otimista(tmp_path):
    store = FileGameStore(tmp_path / "games", schema_version=7)
    owner = _principal()
    other = _principal()
    game_id = uuid4()

    created = store.create(owner, {"game_id": str(game_id), "gold": 10})
    assert created.version == 1
    assert store.get(other, game_id) is None
    assert store.list(other) == []

    saved = store.save(owner, game_id, 1, {"game_id": str(game_id), "gold": 8})
    assert saved.version == 2
    with pytest.raises(StaleVersion):
        store.save(owner, game_id, 1, {"game_id": str(game_id), "gold": 99})
    assert store.get(owner, game_id).state["gold"] == 8
    assert not store.delete(other, game_id)
    assert store.delete(owner, game_id)


def test_runtime_catalog_valida_e_isola_escopos(tmp_path):
    store = JsonRuntimeCatalogStore(tmp_path / "catalog.json")
    owner = uuid4()
    game = uuid4()
    store.put("npc", "n1", {"name": "A"}, scope="game", owner_id=owner, game_id=game)
    assert store.get("npc", "n1", owner_id=owner, game_id=game) == {"name": "A"}
    assert store.get("npc", "n1", owner_id=uuid4(), game_id=game) is None
    with pytest.raises(ValueError):
        store.put("npc", "n2", {}, scope="game", owner_id=None, game_id=game)


def test_legacy_catalog_preserva_arquivos_globais_e_isola_conhecimento(tmp_path):
    store = LegacyRuntimeCatalogStore(lambda: tmp_path)
    store.put(
        "npc_template", "n1", {"name": "A"},
        scope="global", owner_id=None, game_id=None,
    )
    assert (tmp_path / "npc_database.json").exists()
    owner_a, owner_b, game = uuid4(), uuid4(), uuid4()
    store.put(
        "bestiary_knowledge", "wolf", {"seen": True},
        scope="game", owner_id=owner_a, game_id=game,
    )
    assert store.get(
        "bestiary_knowledge", "wolf", owner_id=owner_b, game_id=game,
    ) is None


def test_blob_store_rejeita_traversal_hash_divergente_e_isola_raiz(tmp_path):
    store = FileBlobStore(tmp_path / "blobs")
    owner, game = uuid4(), uuid4()
    payload = b"valoria"
    digest = hashlib.sha256(payload).hexdigest()
    metadata = BlobMetadata(owner, game, "image/png", digest, "test", len(payload))
    ref = store.put("users/a/test.bin", io.BytesIO(payload), metadata)
    assert ref.sha256 == digest
    with store.open(ref.key) as handle:
        assert handle.read() == payload
    with pytest.raises(ValueError):
        store.put("../escape", io.BytesIO(payload), metadata)
    bad = BlobMetadata(owner, game, "image/png", "0" * 64, "test", len(payload))
    with pytest.raises(Exception):
        store.put("bad.bin", io.BytesIO(payload), bad)


def test_fila_inline_deduplica_e_aplica_teto_de_tentativas():
    queue = InlineJobQueue()
    request = JobRequest("embed", "same", {"id": 1}, max_attempts=2)
    job_id = queue.enqueue(request)
    assert queue.enqueue(request) == job_id
    first = queue.lease("w1", {"embed"}, 1)[0]
    queue.fail(first.job_id, first.lease_token, "timeout")
    second = queue.lease("w2", {"embed"}, 1)[0]
    queue.fail(second.job_id, second.lease_token, "timeout")
    assert queue.lease("w3", {"embed"}, 1) == []
