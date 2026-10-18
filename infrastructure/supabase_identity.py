"""Adapter mínimo do Supabase Auth via HTTP, injetável e sem SDK no browser."""

from __future__ import annotations
from infrastructure.db_roles import admin_connection

from datetime import UTC, datetime, timedelta
import base64
import hashlib
import json
import os
import threading
import time
from uuid import UUID

import httpx

from infrastructure.contracts import AuthUnavailable, Principal, Unauthorized
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
        self._verified: dict[str, tuple[Principal, float]] = {}   # SPEC-219 R7
        self._verified_lock = threading.Lock()

    def _headers(self, access_token: str | None = None) -> dict[str, str]:
        headers = {"apikey": self._key, "Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    def _request(self, op: str, method: str, url: str, *, public: str = "",
                 special: dict | None = None, ok: tuple = (200,), quiet: bool = False,
                 **kwargs) -> httpx.Response:
        """SPEC-245 R1: toda chamada ao GoTrue vira ``auth.upstream`` (op, status, error_code
        do catálogo fechado, duração, código público). Timeout/erro de rede => ``AuthUnavailable``
        (503), nunca 500. Nunca registra corpo, e-mail ou token."""
        from observability.auth_log import upstream_code
        from observability.telemetry import log_event
        started = time.monotonic()
        try:
            response = getattr(httpx, method)(url, **kwargs)
        except httpx.HTTPError as exc:
            log_event("auth", "upstream", level="error", op=op, upstream_status=0,
                      error_type=type(exc).__name__, public_code="auth_unavailable",
                      duration_ms=int((time.monotonic() - started) * 1000))
            raise AuthUnavailable("auth_unavailable") from None
        status = response.status_code
        fields: dict = {}
        if status in ok:
            level = "debug" if quiet else "info"
        else:
            code = self._gotrue_error(response)
            fields = {"upstream_code": upstream_code(code),
                      "public_code": (special or {}).get(code, public)}
            level = "error" if status >= 500 else "warning"
        log_event("auth", "upstream", level=level, op=op, upstream_status=status,
                  duration_ms=int((time.monotonic() - started) * 1000), **fields)
        return response

    @staticmethod
    def _tokens(payload: dict) -> SessionTokens:
        user_id = UUID(str((payload.get("user") or {})["id"]))
        return SessionTokens(
            str(payload["access_token"]), str(payload["refresh_token"]),
            datetime.now(UTC) + timedelta(seconds=int(payload.get("expires_in", 3600))),
            user_id,
        )

    @staticmethod
    def _gotrue_error(response: httpx.Response) -> str:
        """GoTrue ``error_code`` (``""`` se ausente/não-JSON). Nunca sai na resposta pública."""
        try:
            payload = response.json()
        except ValueError:
            return ""
        return str(payload.get("error_code") or "") if isinstance(payload, dict) else ""

    def login(self, email: str, password: str, *, captcha_token: str | None = None) -> SessionTokens:
        body = {"email": email, "password": password}
        if captcha_token is not None:
            body["gotrue_meta_security"] = {"captcha_token": captcha_token}
        response = self._request(
            "login", "post", f"{self.base_url}/auth/v1/token?grant_type=password",
            public="credentials_invalid",
            special={"email_not_confirmed": "email_not_confirmed", "captcha_failed": "captcha_invalid"},
            headers=self._headers(), json=body, timeout=self.timeout,
        )
        if response.status_code != 200:
            code = self._gotrue_error(response)
            if code == "email_not_confirmed":  # GoTrue só responde isso com a senha correta
                raise Unauthorized("email_not_confirmed")
            if code == "captcha_failed":
                raise Unauthorized("captcha_invalid")
            raise Unauthorized("credenciais inválidas")
        return self._tokens(response.json())

    def signup(self, email: str, password: str, *, captcha_token: str | None = None) -> SessionTokens | None:
        body = {"email": email, "password": password}
        if captcha_token is not None:
            body["gotrue_meta_security"] = {"captcha_token": captcha_token}
        response = self._request(
            "signup", "post", f"{self.base_url}/auth/v1/signup", ok=(200, 201),
            public="signup_failed", special={"captcha_failed": "captcha_invalid"},
            headers=self._headers(), json=body, timeout=self.timeout,
        )
        if response.status_code not in (200, 201):
            if self._gotrue_error(response) == "captcha_failed":
                raise Unauthorized("captcha_invalid")
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
        response = self._request(
            "recover" if recovery else "resend", "post", f"{self.base_url}/auth/v1/{endpoint}",
            ok=(200, 201, 202, 204), public="email_delivery_failed",
            special={"captcha_failed": "captcha_invalid"},
            headers=self._headers(), json=body, timeout=self.timeout)
        if response.status_code not in (200, 201, 202, 204):
            if self._gotrue_error(response) == "captcha_failed":
                raise Unauthorized("captcha_invalid")  # independe da conta: não enumera
            raise AuthEmailDeliveryError(f"{response.status_code // 100}xx")

    def verify_email(self, token_hash: str, *, recovery: bool = False) -> SessionTokens:
        response = self._request(
            "verify", "post", f"{self.base_url}/auth/v1/verify", public="link_invalid_or_expired",
            headers=self._headers(),
            json={"token_hash": token_hash, "type": "recovery" if recovery else "signup"},
            timeout=self.timeout)
        if response.status_code != 200:
            raise Unauthorized("link_invalid_or_expired")
        return self._tokens(response.json())

    def reset_password(self, token_hash: str, password: str) -> None:
        tokens = self.verify_email(token_hash, recovery=True)
        self.verify(tokens.access_token)  # Reject tombstones/revoked session before mutation.
        response = self._request(
            "reset", "put", f"{self.base_url}/auth/v1/user", public="password_reset_failed",
            headers=self._headers(tokens.access_token), json={"password": password},
            timeout=self.timeout)
        if response.status_code != 200:
            raise Unauthorized("password_reset_failed")
        self.logout(tokens.access_token)

    def reauthenticate(self, access_token: str, password: str, *, captcha_token: str | None = None) -> UUID:
        original = self.verify(access_token)
        response = self._request(
            "reauth_user", "get", f"{self.base_url}/auth/v1/user", public="credentials_invalid",
            headers=self._headers(access_token), timeout=self.timeout)
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
            self._request("reauth_logout", "post", f"{self.base_url}/auth/v1/logout?scope=local",
                          ok=(200, 204), quiet=True, headers=self._headers(tokens.access_token),
                          timeout=self.timeout)

    def delete_user(self, user_id: UUID) -> None:
        if not self._service_key:
            raise Unauthorized("lifecycle_unavailable")
        headers = {"apikey": self._service_key}
        if not self._service_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self._service_key}"
        response = self._request(
            "delete", "delete", f"{self.base_url}/auth/v1/admin/users/{user_id}",
            ok=(200, 204, 404), public="account_delete_pending", headers=headers, timeout=self.timeout)
        if response.status_code not in (200, 204, 404):
            raise Unauthorized("account_delete_pending")
        self._forget(user_id=user_id)

    def refresh(self, refresh_token: str) -> SessionTokens:
        response = self._request(
            "refresh", "post", f"{self.base_url}/auth/v1/token?grant_type=refresh_token",
            public="session_invalid", headers=self._headers(),
            json={"refresh_token": refresh_token}, timeout=self.timeout,
        )
        if response.status_code != 200:
            raise Unauthorized("sessão inválida")
        tokens = self._tokens(response.json())
        self._forget(user_id=tokens.user_id)
        return tokens

    def logout(self, access_token: str) -> None:
        response = self._request(
            "logout", "post", f"{self.base_url}/auth/v1/logout?scope=global", ok=(200, 204),
            public="session_invalid", headers=self._headers(access_token), timeout=self.timeout,
        )
        if response.status_code not in (200, 204):
            raise Unauthorized("sessão inválida")
        self._forget(access_token, self._cached_user(access_token))

    def _cached_user(self, access_token: str) -> UUID | None:
        with self._verified_lock:
            hit = self._verified.get(hashlib.sha256(access_token.encode()).hexdigest())
        return hit[0].user_id if hit else None

    def logout_via_refresh(self, refresh_token: str) -> bool:
        """SPEC-220 R1: access vencido => troca o refresh e revoga globalmente.

        Tolerante: refresh já rotacionado/revogado (401/404) devolve False sem exceção.
        """
        try:
            tokens = self.refresh(refresh_token)
            self.logout(tokens.access_token)
            return True
        except Unauthorized:
            return False

    def revoke_all(self, user_id: UUID) -> bool:
        """SPEC-220 R2 (D-A): apaga todas as sessões/refresh do owner no Auth.

        Usa a mesma função privilegiada da exclusão de conta (SPEC-190); o GoTrue
        não expõe logout-por-id na Admin API. Sem pool => False (R1 basta).
        """
        if self.pool is None:
            return False
        with admin_connection(self.pool) as db:
            # O pool real faz commit ao sair do contexto (psycopg_pool).
            db.execute("select app.runtime_revoke_auth(%s)", (user_id,))
        self._forget(user_id=user_id)
        return True

    # --- SPEC-219 R7: pre-validacao local + cache curto ------------------------------------
    CLOCK_SKEW_SECONDS = 60

    def _cache_ttl(self) -> float:
        try:
            return max(0.0, float(os.getenv("RPG_VERIFY_CACHE_SECONDS", "20")))
        except ValueError:
            return 20.0

    def _prevalidate(self, access_token: str) -> float:
        """Corta lixo SEM rede: 3 segmentos base64url, ``exp`` futuro (+skew), ``aud`` e ``iss``.
        A assinatura/revogacao continuam sendo decididas pelo GoTrue."""
        parts = access_token.split(".")
        if len(access_token) > 8192 or len(parts) != 3 or not all(parts):
            raise Unauthorized("token inválido", reason="bad_signature")
        try:
            encoded = parts[1]
            claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            exp = float(claims["exp"])
        except (ValueError, KeyError, TypeError, RecursionError):  # payload aninhado = lixo, nunca 500
            raise Unauthorized("token inválido", reason="bad_signature") from None
        if not isinstance(claims, dict):
            raise Unauthorized("token inválido", reason="bad_signature")
        if exp + self.CLOCK_SKEW_SECONDS < time.time():
            raise Unauthorized("token inválido", reason="expired")
        issuer = claims.get("iss")
        if claims.get("aud") != "authenticated" or not isinstance(issuer, str) \
                or not issuer.startswith(f"{self.base_url}/auth/v1"):
            raise Unauthorized("token inválido", reason="bad_aud_iss")
        return exp

    def _forget(self, access_token: str | None = None, user_id: UUID | None = None) -> None:
        with self._verified_lock:
            if access_token:
                self._verified.pop(hashlib.sha256(access_token.encode()).hexdigest(), None)
            if user_id is not None:
                for key in [k for k, (p, _) in self._verified.items() if p.user_id == user_id]:
                    del self._verified[key]

    def verify(self, access_token: str | None) -> Principal:
        if not access_token:
            raise Unauthorized("sessão ausente")
        exp = self._prevalidate(access_token)
        digest = hashlib.sha256(access_token.encode()).hexdigest()
        ttl = self._cache_ttl()
        principal = None
        if ttl:
            with self._verified_lock:
                hit = self._verified.get(digest)
            # Cache nunca estende a vida do token: so vale enquanto ``exp`` (sem skew) nao passou.
            if hit and time.monotonic() - hit[1] < ttl and exp > time.time():
                principal = hit[0]
        if principal is None:
            principal = self._verify_remote(access_token)       # so o GoTrue (assinatura/expiracao) e cacheado
            if ttl:
                with self._verified_lock:
                    if len(self._verified) > 2048:
                        self._verified.clear()
                    self._verified[digest] = (principal, time.monotonic())
        try:
            self._check_session(access_token, principal.user_id)   # banco local: revogacao e imediata
        except Unauthorized:
            self._forget(access_token)
            raise
        return principal

    def _check_session(self, access_token: str, user_id: UUID) -> None:
        if self.pool is None:
            return
        # Claims are only read AFTER Supabase validates the bearer. Metadata is never authorization.
        try:
            encoded = access_token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            session_id = UUID(claims["session_id"])
        except (ValueError, KeyError, IndexError, TypeError):
            raise Unauthorized("sessão inválida") from None
        with admin_connection(self.pool) as db:
            active = db.execute("select app.runtime_session_active(%s,%s) as ok",
                                (session_id, user_id)).fetchone()["ok"]
        if not active:
            raise Unauthorized("sessão revogada")

    def _verify_remote(self, access_token: str) -> Principal:
        response = self._request(
            "verify_token", "get", f"{self.base_url}/auth/v1/user", public="session_invalid",
            quiet=True, headers=self._headers(access_token), timeout=self.timeout,
        )
        if response.status_code != 200:
            raise Unauthorized("token inválido", reason="upstream_rejected")
        user_id = UUID(str(response.json()["id"]))
        return Principal(user_id, f"{self.base_url}/auth/v1", str(user_id))
