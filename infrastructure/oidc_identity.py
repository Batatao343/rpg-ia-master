"""Verificador OIDC portável (SPEC-220 R6): JWT validado localmente via JWKS.

O access token é um JWT assinado (RS256/ES256) e é verificado aqui: assinatura
pela JWKS do provedor (cache 10 min), ``iss`` exato, ``aud``/``azp`` contendo a
audience configurada, ``exp``/``nbf`` e ``email_verified`` quando presente.
``alg=none``/``HS*`` são recusados. UserInfo, se configurado, só complementa
(o ``sub`` precisa coincidir). Nenhuma dependência nova: só ``cryptography``.
"""

from __future__ import annotations

import base64
import json
import math
import threading
import time
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from infrastructure.contracts import Principal, Unauthorized

ALLOWED_ALGS = {"RS256", "ES256"}
JWKS_TTL_SECONDS = 600
CLOCK_SKEW_SECONDS = 60
JWKS_FORCE_COOLDOWN_SECONDS = 60  # kid desconhecido não amplifica requests ao IdP


def _b64(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _int(segment: str) -> int:
    return int.from_bytes(_b64(segment), "big")


def _safe_url(url: str, label: str) -> str:
    url = url.strip()
    if not url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        raise ValueError(f"OIDC {label} exige HTTPS ou loopback local")
    return url


class OidcIdentityProvider:
    def __init__(self, userinfo_url: str, issuer: str, *, jwks_url: str = "", audience: str = "",
                 timeout: float = 8.0, clock=time.time) -> None:
        self.issuer = _safe_url(issuer, "issuer").rstrip("/")
        self.userinfo_url = _safe_url(userinfo_url, "UserInfo") if userinfo_url.strip() else ""
        if not jwks_url.strip() or not audience.strip():
            raise ValueError("OIDC exige RPG_OIDC_JWKS_URL e RPG_OIDC_AUDIENCE (fail-closed)")
        self.jwks_url = _safe_url(jwks_url, "JWKS")
        self.audience = audience.strip()
        self.timeout = timeout
        self._clock = clock
        self._keys: dict[str, dict] = {}
        self._fetched_at = float("-inf")
        self._forced_at = float("-inf")
        self._lock = threading.Lock()

    @staticmethod
    def _owner_id(issuer: str, subject: str) -> UUID:
        try:
            return UUID(subject)
        except (TypeError, ValueError):
            return uuid5(NAMESPACE_URL, f"{issuer}#{subject}")

    def _jwks(self, *, force: bool = False) -> dict[str, dict]:
        with self._lock:
            if force:
                if self._clock() - self._forced_at < JWKS_FORCE_COOLDOWN_SECONDS:
                    return self._keys
                self._forced_at = self._clock()
            if force or self._clock() - self._fetched_at >= JWKS_TTL_SECONDS:
                try:
                    response = httpx.get(self.jwks_url, timeout=self.timeout)
                    keys = response.json().get("keys", []) if response.status_code == 200 else None
                except (httpx.HTTPError, ValueError, AttributeError):
                    keys = None
                if not isinstance(keys, list):
                    raise Unauthorized("provedor de identidade indisponível")
                self._keys = {str(k.get("kid", "")): k for k in keys if isinstance(k, dict)}
                self._fetched_at = self._clock()
            return self._keys

    def _key_for(self, kid: str) -> dict:
        key = self._jwks().get(kid)
        if key is None:  # rotação de chave no IdP: um refetch, depois falha
            key = self._jwks(force=True).get(kid)
        if key is None:
            raise Unauthorized("token inválido")
        return key

    @staticmethod
    def _check_signature(alg: str, jwk: dict, signing_input: bytes, signature: bytes) -> None:
        try:
            if alg == "RS256" and jwk.get("kty") == "RSA":
                public = rsa.RSAPublicNumbers(_int(jwk["e"]), _int(jwk["n"])).public_key()
                public.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
                return
            if alg == "ES256" and jwk.get("kty") == "EC" and jwk.get("crv") == "P-256":
                if len(signature) != 64:
                    raise Unauthorized("token inválido")
                public = ec.EllipticCurvePublicNumbers(
                    _int(jwk["x"]), _int(jwk["y"]), ec.SECP256R1()).public_key()
                der = encode_dss_signature(int.from_bytes(signature[:32], "big"),
                                           int.from_bytes(signature[32:], "big"))
                public.verify(der, signing_input, ec.ECDSA(hashes.SHA256()))
                return
        except (InvalidSignature, KeyError, ValueError, TypeError):
            raise Unauthorized("token inválido") from None
        raise Unauthorized("token inválido")

    def _claims(self, token: str) -> dict:
        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
            header = json.loads(_b64(header_b64))
            claims = json.loads(_b64(payload_b64))
            signature = _b64(signature_b64)
        except (ValueError, TypeError):
            raise Unauthorized("token inválido") from None
        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise Unauthorized("token inválido")
        alg = header.get("alg")
        if alg not in ALLOWED_ALGS:  # recusa none/HS*/qualquer outro
            raise Unauthorized("token inválido")
        jwk = self._key_for(str(header.get("kid", "")))
        if jwk.get("alg") not in (None, alg) or jwk.get("use") not in (None, "sig"):
            raise Unauthorized("token inválido")
        self._check_signature(alg, jwk, f"{header_b64}.{payload_b64}".encode(), signature)
        return claims

    def verify(self, access_token: str | None) -> Principal:
        if not access_token:
            raise Unauthorized("token ausente")
        claims = self._claims(access_token)
        now = self._clock()
        if str(claims.get("iss") or "").rstrip("/") != self.issuer:
            raise Unauthorized("token inválido")  # iss obrigatório e exato
        audiences = claims.get("aud")
        audiences = [audiences] if isinstance(audiences, str) else (
            audiences if isinstance(audiences, list) else [])
        if self.audience not in audiences and claims.get("azp") != self.audience:
            raise Unauthorized("token inválido")
        exp, nbf = claims.get("exp"), claims.get("nbf", now)
        for value in (exp, nbf):  # NumericDate: número finito, nunca bool/string
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise Unauthorized("token inválido")
        if exp <= now - CLOCK_SKEW_SECONDS or nbf > now + CLOCK_SKEW_SECONDS:
            raise Unauthorized("token inválido")
        if "email_verified" in claims and claims["email_verified"] is not True:
            raise Unauthorized("token inválido")
        subject = str(claims.get("sub") or "").strip()
        if not subject:
            raise Unauthorized("token sem subject")
        if self.userinfo_url:
            self._userinfo_matches(access_token, subject)
        return Principal(self._owner_id(self.issuer, subject), self.issuer, subject)

    def _userinfo_matches(self, access_token: str, subject: str) -> None:
        try:
            response = httpx.get(self.userinfo_url, headers={"Authorization": f"Bearer {access_token}"},
                                 timeout=self.timeout)
            payload = response.json() if response.status_code == 200 else {}
        except (httpx.HTTPError, ValueError) as exc:
            raise Unauthorized("provedor de identidade indisponível") from exc
        if not isinstance(payload, dict) or str(payload.get("sub") or "") != subject:
            raise Unauthorized("token inválido")

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
