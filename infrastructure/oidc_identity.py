"""Verificador OIDC portável por UserInfo, sem dependência do Supabase.

O endpoint UserInfo do provedor é responsável por validar assinatura, expiração
e audience do access token. O domínio recebe apenas uma identidade estável.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

import httpx

from infrastructure.contracts import Principal, Unauthorized


class OidcIdentityProvider:
    def __init__(self, userinfo_url: str, issuer: str, *, timeout: float = 8.0) -> None:
        self.userinfo_url = userinfo_url.strip()
        self.issuer = issuer.rstrip("/")
        self.timeout = timeout
        if not self.userinfo_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise ValueError("OIDC UserInfo exige HTTPS ou loopback local")
        if not self.issuer.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise ValueError("OIDC issuer exige HTTPS ou loopback local")

    @staticmethod
    def _owner_id(issuer: str, subject: str) -> UUID:
        try:
            return UUID(subject)
        except (TypeError, ValueError):
            return uuid5(NAMESPACE_URL, f"{issuer}#{subject}")

    def verify(self, access_token: str | None) -> Principal:
        if not access_token:
            raise Unauthorized("token ausente")
        try:
            response = httpx.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise Unauthorized("provedor de identidade indisponível") from exc
        if response.status_code != 200:
            raise Unauthorized("token inválido")
        payload = response.json()
        subject = str(payload.get("sub") or "").strip()
        if not subject:
            raise Unauthorized("token sem subject")
        claimed_issuer = str(payload.get("iss") or self.issuer).rstrip("/")
        if claimed_issuer != self.issuer:
            raise Unauthorized("issuer inválido")
        return Principal(self._owner_id(self.issuer, subject), self.issuer, subject)

    # Password grant não faz parte do contrato OIDC portável. As rotas atuais
    # falham de modo explícito até a futura certificação cloud definir redirect/PKCE.
    def login(self, _email: str, _password: str):
        raise Unauthorized("login por senha indisponível no perfil OIDC")

    def signup(self, _email: str, _password: str):
        raise Unauthorized("cadastro por senha indisponível no perfil OIDC")

    def refresh(self, _refresh_token: str):
        raise Unauthorized("refresh gerenciado pelo provedor OIDC")

    def logout(self, _access_token: str) -> None:
        return None
