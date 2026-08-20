from __future__ import annotations

import hashlib
from io import BytesIO
from uuid import uuid4

import pytest

from infrastructure.contracts import BlobMetadata, Conflict
from infrastructure.s3_blob import S3BlobStore


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.last_put = None

    def put_object(self, **kwargs):
        self.last_put = kwargs
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = bytes(kwargs["Body"])

    def get_object(self, **kwargs):
        return {"Body": BytesIO(self.objects[(kwargs["Bucket"], kwargs["Key"])])}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        return f"https://s3.example/{Params['Bucket']}/{Params['Key']}?expires={ExpiresIn}"

    def delete_object(self, **kwargs):
        self.objects.pop((kwargs["Bucket"], kwargs["Key"]), None)


def test_s3_obedece_contrato_blob_e_preserva_metadata_scoped():
    client = FakeS3()
    store = S3BlobStore(client, "private")
    payload = b"webp-fixture"
    owner_id, game_id = uuid4(), uuid4()
    metadata = BlobMetadata(
        owner_id, game_id, "image/webp", hashlib.sha256(payload).hexdigest(),
        "npc_portrait", len(payload),
    )
    ref = store.put("users/a/art.webp", BytesIO(payload), metadata)
    assert store.open(ref.key).read() == payload
    assert client.last_put["Metadata"]["owner-id"] == str(owner_id)
    assert client.last_put["Metadata"]["game-id"] == str(game_id)
    assert "expires=60" in store.signed_url(ref.key, 60)
    assert store.delete(ref.key)


def test_s3_recusa_hash_e_expiracao_invalidos():
    store = S3BlobStore(FakeS3(), "private")
    with pytest.raises(Conflict):
        store.put(
            "x", BytesIO(b"x"),
            BlobMetadata(uuid4(), uuid4(), "image/webp", "0" * 64, "test", 1),
        )
    with pytest.raises(ValueError):
        store.signed_url("x", 0)
