"""BlobStore para Supabase Storage, usado somente pelo backend."""

from __future__ import annotations

import hashlib
from io import BytesIO
from urllib.parse import quote

import httpx

from infrastructure.contracts import BlobMetadata, BlobRef, Conflict, NotFound


class SupabaseBlobStore:
    def __init__(self, base_url: str, service_key: str, *, bucket: str = "rpg-dynamic",
                 timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._key = service_key
        self.bucket = bucket
        self.timeout = timeout

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        headers = {"apikey": self._key, "Authorization": f"Bearer {self._key}"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    @staticmethod
    def _metric(operation: str, success: bool) -> None:
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
        path = quote(key.strip("/"), safe="/")
        response = httpx.post(
            f"{self.base_url}/storage/v1/object/{self.bucket}/{path}",
            headers={**self._headers(metadata.content_type), "x-upsert": "false"},
            content=data, timeout=self.timeout,
        )
        success = response.status_code in (200, 201)
        self._metric("put", success)
        if not success:
            raise Conflict("upload do blob falhou")
        return BlobRef(key, digest, len(data), metadata.content_type)

    def open(self, key):
        path = quote(key.strip("/"), safe="/")
        response = httpx.get(
            f"{self.base_url}/storage/v1/object/authenticated/{self.bucket}/{path}",
            headers=self._headers(), timeout=self.timeout,
        )
        success = response.status_code == 200
        self._metric("open", success)
        if not success:
            raise NotFound("blob não encontrado")
        return BytesIO(response.content)

    def signed_url(self, key: str, expires_seconds: int) -> str:
        if not 1 <= expires_seconds <= 3600:
            raise ValueError("expiração deve estar entre 1 e 3600 segundos")
        path = quote(key.strip("/"), safe="/")
        response = httpx.post(
            f"{self.base_url}/storage/v1/object/sign/{self.bucket}/{path}",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={"expiresIn": expires_seconds}, timeout=self.timeout,
        )
        success = response.status_code == 200
        self._metric("sign", success)
        if not success:
            raise NotFound("blob não encontrado")
        signed = response.json()["signedURL"]
        return signed if signed.startswith("http") else f"{self.base_url}/storage/v1{signed}"

    def delete(self, key: str) -> bool:
        response = httpx.request(
            "DELETE", f"{self.base_url}/storage/v1/object/{self.bucket}",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={"prefixes": [key.strip("/")]}, timeout=self.timeout,
        )
        success = response.status_code in (200, 204)
        self._metric("delete", success)
        return success
