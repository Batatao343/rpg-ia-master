"""Adapter mínimo do Supabase Auth via HTTP, injetável e sem SDK no browser."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx

from infrastructure.contracts import Principal, Unauthorized
from services.auth_sessions import SessionTokens


class SupabaseIdentityProvider:
    def __init__(self, base_url: str, publishable_key: str, *, timeout: float = 8.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._key = publishable_key
        self.timeout = timeout

    def _headers(self, access_token: str | None = None) -> dict[str, str]:
        headers = {"apikey": self._key, "Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    @staticmethod
    def _tokens(payload: dict) -> SessionTokens:
        user_id = UUID(str((payload.get("user") or {})["id"]))
        return SessionTokens(
            str(payload["access_token"]), str(payload["refresh_token"]),
            datetime.now(UTC) + timedelta(seconds=int(payload.get("expires_in", 3600))),
            user_id,
        )

    def login(self, email: str, password: str) -> SessionTokens:
        response = httpx.post(
            f"{self.base_url}/auth/v1/token?grant_type=password",
            headers=self._headers(), json={"email": email, "password": password},
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise Unauthorized("credenciais inválidas")
        return self._tokens(response.json())

    def signup(self, email: str, password: str) -> SessionTokens:
        response = httpx.post(
            f"{self.base_url}/auth/v1/signup", headers=self._headers(),
            json={"email": email, "password": password}, timeout=self.timeout,
        )
        if response.status_code not in (200, 201):
            raise Unauthorized("não foi possível criar a conta")
        payload = response.json()
        if not payload.get("access_token"):
            raise Unauthorized("confirme o e-mail antes de entrar")
        return self._tokens(payload)

    def refresh(self, refresh_token: str) -> SessionTokens:
        response = httpx.post(
            f"{self.base_url}/auth/v1/token?grant_type=refresh_token",
            headers=self._headers(), json={"refresh_token": refresh_token}, timeout=self.timeout,
        )
        if response.status_code != 200:
            raise Unauthorized("sessão inválida")
        return self._tokens(response.json())

    def logout(self, access_token: str) -> None:
        response = httpx.post(
            f"{self.base_url}/auth/v1/logout", headers=self._headers(access_token),
            timeout=self.timeout,
        )
        if response.status_code not in (200, 204):
            raise Unauthorized("sessão inválida")

    def verify(self, access_token: str) -> Principal:
        response = httpx.get(
            f"{self.base_url}/auth/v1/user", headers=self._headers(access_token),
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise Unauthorized("token inválido")
        user_id = UUID(str(response.json()["id"]))
        return Principal(user_id, f"{self.base_url}/auth/v1", str(user_id))
