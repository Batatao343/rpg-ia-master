"""BlobStore S3 compatível opcional; boto3 só é exigido pela factory."""

from __future__ import annotations

import hashlib
from io import BytesIO

from infrastructure.contracts import BlobMetadata, BlobRef, Conflict


class S3BlobStore:
    def __init__(self, client, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    @staticmethod
    def _metric(operation: str, success: bool = True) -> None:
        from observability.metrics import metrics
        from observability.telemetry import span
        outcome = "ok" if success else "error"
        metrics.increment(
            "rpg_blob_operations_total",
            {"operation": operation, "outcome": outcome},
        )
        with span("blob.operation", operation=operation, outcome=outcome):
            pass

    def put(self, key, payload, metadata: BlobMetadata) -> BlobRef:
        data = payload.read()
        digest = hashlib.sha256(data).hexdigest()
        if digest != metadata.sha256:
            self._metric("put", False)
            raise Conflict("hash do blob divergiu")
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data,
            ContentType=metadata.content_type,
            Metadata={
                "owner-id": str(metadata.owner_id),
                "game-id": str(metadata.game_id),
                "sha256": digest,
                "purpose": metadata.purpose[:100],
            },
        )
        self._metric("put")
        return BlobRef(key, digest, len(data), metadata.content_type)

    def open(self, key):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        self._metric("open")
        return BytesIO(response["Body"].read())

    def signed_url(self, key: str, expires_seconds: int) -> str:
        if not 1 <= expires_seconds <= 3600:
            raise ValueError("expiração deve estar entre 1 e 3600 segundos")
        signed = self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )
        self._metric("sign")
        return signed

    def delete(self, key: str) -> bool:
        self.client.delete_object(Bucket=self.bucket, Key=key)
        self._metric("delete")
        return True
