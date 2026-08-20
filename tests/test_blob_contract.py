from __future__ import annotations

import hashlib
from io import BytesIO
from uuid import uuid4

import pytest

from infrastructure.contracts import BlobMetadata, Conflict
from infrastructure.file_blob import FileBlobStore


def test_file_blob_contract_e_isolamento(tmp_path):
    store = FileBlobStore(tmp_path)
    payload = b"valoria"
    digest = hashlib.sha256(payload).hexdigest()
    owner, game = uuid4(), uuid4()
    metadata = BlobMetadata(owner, game, "image/webp", digest, "npc")
    ref = store.put(f"users/{owner}/games/{game}/npc/a.webp", BytesIO(payload), metadata)
    assert store.open(ref.key).read() == payload
    assert store.signed_url(ref.key, 30).startswith("file:")
    assert store.delete(ref.key) and not store.delete(ref.key)


def test_file_blob_recusa_traversal_e_hash(tmp_path):
    store = FileBlobStore(tmp_path)
    metadata = BlobMetadata(uuid4(), uuid4(), "image/webp", "0" * 64, "npc")
    with pytest.raises((ValueError, Conflict)):
        store.put("../escape.webp", BytesIO(b"x"), metadata)
