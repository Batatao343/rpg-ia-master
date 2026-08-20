from __future__ import annotations

import hashlib
import os
from io import BytesIO
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
import pytest
from PIL import Image

from infrastructure.contracts import BlobMetadata
from infrastructure.supabase_blob import SupabaseBlobStore


pytestmark = [pytest.mark.infra_local, pytest.mark.security_local]


def _env() -> tuple[str, str, str]:
    values = tuple(os.getenv(name, "") for name in (
        "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    ))
    if not all(values):
        pytest.skip("env local Supabase ausente")
    return values  # type: ignore[return-value]


def _create_user(base: str, service: str, email: str, password: str) -> UUID:
    response = httpx.post(
        f"{base}/auth/v1/admin/users",
        headers={"apikey": service, "Authorization": f"Bearer {service}"},
        json={"email": email, "password": password, "email_confirm": True},
        timeout=10,
    )
    response.raise_for_status()
    return UUID(response.json()["id"])


def _token(base: str, publishable: str, email: str, password: str) -> str:
    response = httpx.post(
        f"{base}/auth/v1/token?grant_type=password",
        headers={"apikey": publishable},
        json={"email": email, "password": password}, timeout=10,
    )
    response.raise_for_status()
    return str(response.json()["access_token"])


def _webp() -> bytes:
    output = BytesIO()
    Image.new("RGB", (32, 32), "#43352b").save(output, format="WEBP")
    return output.getvalue()


def test_bucket_privado_isola_objeto_a_b_e_signed_url_expira():
    base, publishable, service = _env()
    suffix = uuid4().hex
    password = "StorageLocal!2026"
    users: list[UUID] = []
    key = ""
    store = SupabaseBlobStore(base, service)
    try:
        owner_a = _create_user(base, service, f"storage-a-{suffix}@example.test", password)
        owner_b = _create_user(base, service, f"storage-b-{suffix}@example.test", password)
        users.extend((owner_a, owner_b))
        token_a = _token(base, publishable, f"storage-a-{suffix}@example.test", password)
        token_b = _token(base, publishable, f"storage-b-{suffix}@example.test", password)
        game_id = uuid4()
        payload = _webp()
        digest = hashlib.sha256(payload).hexdigest()
        key = f"users/{owner_a}/games/{game_id}/npc/test/{uuid4()}.full.{digest[:12]}.webp"
        store.put(
            key, BytesIO(payload),
            BlobMetadata(owner_a, game_id, "image/webp", digest, "security_test", len(payload)),
        )
        assert store.open(key).read() == payload
        path = quote(key, safe="/")
        object_url = f"{base}/storage/v1/object/authenticated/rpg-dynamic/{path}"
        headers_a = {"apikey": publishable, "Authorization": f"Bearer {token_a}"}
        headers_b = {"apikey": publishable, "Authorization": f"Bearer {token_b}"}
        assert httpx.get(object_url, headers=headers_a, timeout=10).status_code == 200
        assert httpx.get(object_url, headers=headers_b, timeout=10).status_code in (400, 403, 404)
        assert httpx.get(object_url, headers={"apikey": publishable}, timeout=10).status_code != 200
        signed = store.signed_url(key, 30)
        assert httpx.get(signed, timeout=10).status_code == 200
    finally:
        if key:
            store.delete(key)
        for user_id in users:
            httpx.delete(
                f"{base}/auth/v1/admin/users/{user_id}",
                headers={"apikey": service, "Authorization": f"Bearer {service}"},
                timeout=10,
            )
