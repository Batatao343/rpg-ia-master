"""Adapter mínimo do Supabase Auth via HTTP, injetável e sem SDK no browser."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import base64
import json
from uuid import UUID

import httpx

from infrastructure.contracts import Principal, Unauthorized
from services.auth_sessions import SessionTokens


class AuthEmailDeliveryError(Exception):
    """Sanitized upstream delivery failure; never carries an address/body."""

    def __init__(self, status_class: str) -> None:
        self.status_class = status_class
        super().__init__("auth_email_delivery_failed")


class SupabaseIdentityProvider:
    def __init__(self, base_url: str, publishable_key: str, *, timeout: float = 8.0,
                 pool=None, service_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self._key = publishable_key
        self.timeout = timeout
        self.pool = pool
        self._service_key = service_key

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

    def login(self, email: str, password: str, *, captcha_token: str | None = None) -> SessionTokens:
        body = {"email": email, "password": password}
        if captcha_token is not None:
            body["gotrue_meta_security"] = {"captcha_token": captcha_token}
        response = httpx.post(
            f"{self.base_url}/auth/v1/token?grant_type=password",
            headers=self._headers(), json=body,
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise Unauthorized("credenciais inválidas")
        return self._tokens(response.json())

    def signup(self, email: str, password: str, *, captcha_token: str | None = None) -> SessionTokens | None:
        body = {"email": email, "password": password}
        if captcha_token is not None:
            body["gotrue_meta_security"] = {"captcha_token": captcha_token}
        response = httpx.post(
            f"{self.base_url}/auth/v1/signup", headers=self._headers(),
            json=body, timeout=self.timeout,
        )
        if response.status_code not in (200, 201):
            raise Unauthorized("não foi possível criar a conta")
        payload = response.json()
        if not payload.get("access_token"):
            return None
        return self._tokens(payload)

    def request_email(self, email: str, *, recovery: bool, captcha_token: str | None = None) -> None:
        endpoint = "recover" if recovery else "resend"
        body = {"email": email} if recovery else {"email": email, "type": "signup"}
        if captcha_token is not None:
            body["gotrue_meta_security"] = {"captcha_token": captcha_token}
        # Response is deliberately ignored: existence/confirmation/quota share a contract.
        response = httpx.post(f"{self.base_url}/auth/v1/{endpoint}", headers=self._headers(),
                              json=body, timeout=self.timeout)
        if response.status_code not in (200, 201, 202, 204):
            raise AuthEmailDeliveryError(f"{response.status_code // 100}xx")

    def verify_email(self, token_hash: str, *, recovery: bool = False) -> SessionTokens:
        response = httpx.post(f"{self.base_url}/auth/v1/verify", headers=self._headers(),
                              json={"token_hash": token_hash, "type": "recovery" if recovery else "signup"},
                              timeout=self.timeout)
        if response.status_code != 200:
            raise Unauthorized("link_invalid_or_expired")
        return self._tokens(response.json())

    def reset_password(self, token_hash: str, password: str) -> None:
        tokens = self.verify_email(token_hash, recovery=True)
        self.verify(tokens.access_token)  # Reject tombstones/revoked session before mutation.
        response = httpx.put(f"{self.base_url}/auth/v1/user", headers=self._headers(tokens.access_token),
                             json={"password": password}, timeout=self.timeout)
        if response.status_code != 200:
            raise Unauthorized("password_reset_failed")
        self.logout(tokens.access_token)

    def reauthenticate(self, access_token: str, password: str, *, captcha_token: str | None = None) -> UUID:
        original = self.verify(access_token)
        response = httpx.get(f"{self.base_url}/auth/v1/user", headers=self._headers(access_token), timeout=self.timeout)
        email = response.json().get("email") if response.status_code == 200 else None
        if not email:
            raise Unauthorized("credenciais inválidas")
        tokens = self.login(email, password, captcha_token=captcha_token)
        try:
            if tokens.user_id != original.user_id:
                raise Unauthorized("credenciais inválidas")
            return original.user_id
        finally:
            # Remove only the temporary password-grant session, retain current session.
            httpx.post(f"{self.base_url}/auth/v1/logout?scope=local", headers=self._headers(tokens.access_token), timeout=self.timeout)

    def delete_user(self, user_id: UUID) -> None:
        if not self._service_key:
            raise Unauthorized("lifecycle_unavailable")
        headers = {"apikey": self._service_key}
        if not self._service_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self._service_key}"
        response = httpx.delete(f"{self.base_url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=self.timeout)
        if response.status_code not in (200, 204, 404):
            raise Unauthorized("account_delete_pending")

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
            f"{self.base_url}/auth/v1/logout?scope=global", headers=self._headers(access_token),
            timeout=self.timeout,
        )
        if response.status_code not in (200, 204):
            raise Unauthorized("sessão inválida")

    def verify(self, access_token: str | None) -> Principal:
        if not access_token:
            raise Unauthorized("sessão ausente")
        response = httpx.get(
            f"{self.base_url}/auth/v1/user", headers=self._headers(access_token),
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise Unauthorized("token inválido")
        user_id = UUID(str(response.json()["id"]))
        if self.pool is not None:
            # Claims are only read AFTER Supabase validates the bearer. Metadata is never authorization.
            try:
                encoded = access_token.split(".")[1]
                claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
                session_id = UUID(claims["session_id"])
            except (ValueError, KeyError, IndexError, TypeError):
                raise Unauthorized("sessão inválida") from None
            with self.pool.connection() as db:
                active = db.execute("select app.runtime_session_active(%s,%s) as ok",
                                    (session_id, user_id)).fetchone()["ok"]
            if not active:
                raise Unauthorized("sessão revogada")
        return Principal(user_id, f"{self.base_url}/auth/v1", str(user_id))
