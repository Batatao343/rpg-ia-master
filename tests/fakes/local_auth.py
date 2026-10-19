"""Synthetic confirmed users for browser and mutation audits against local GoTrue."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from scripts.start_local_api import _supabase_status


@lru_cache(maxsize=1)
def _local_admin() -> tuple[str, str]:
    status = _supabase_status()
    base = status["API_URL"].rstrip("/")
    parsed = urlsplit(base)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port != 55321
    ):
        raise RuntimeError("audit Auth admin requires local GoTrue on port 55321")
    return base, status["SERVICE_ROLE_KEY"]


def create_confirmed_user(email: str, password: str) -> UUID:
    base, key = _local_admin()
    response = httpx.post(
        f"{base}/auth/v1/admin/users",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        json={"email": email, "password": password, "email_confirm": True},
        timeout=10,
    )
    response.raise_for_status()
    return UUID(response.json()["id"])


def delete_confirmed_user(user_id: UUID) -> None:
    base, key = _local_admin()
    response = httpx.delete(
        f"{base}/auth/v1/admin/users/{user_id}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=10,
    )
    if response.status_code not in (200, 204, 404):
        response.raise_for_status()
