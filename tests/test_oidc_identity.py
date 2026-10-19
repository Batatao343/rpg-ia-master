"""SPEC-220 R6: OIDC valida JWT localmente via JWKS (fail-closed)."""

from __future__ import annotations

import base64
import json
import time
from uuid import UUID

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from infrastructure.contracts import Unauthorized
from infrastructure.oidc_identity import OidcIdentityProvider
from infrastructure.runtime import RuntimeConfig

ISS = "https://identity.example"
AUD = "rpg-api"
JWKS = "https://identity.example/jwks"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _n(value: int, size: int | None = None) -> str:
    return _b64(value.to_bytes(size or (value.bit_length() + 7) // 8, "big"))


@pytest.fixture(scope="module")
def keys():
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ec_key = ec.generate_private_key(ec.SECP256R1())
    rn, en = rsa_key.public_key().public_numbers(), ec_key.public_key().public_numbers()
    jwks = {
        "keys": [
            {"kty": "RSA", "kid": "r1", "alg": "RS256", "use": "sig", "n": _n(rn.n), "e": _n(rn.e)},
            {"kty": "EC", "kid": "e1", "crv": "P-256", "x": _n(en.x, 32), "y": _n(en.y, 32)},
        ]
    }
    return rsa_key, ec_key, jwks


def _token(keys, *, alg="RS256", kid="r1", **overrides):
    rsa_key, ec_key, _ = keys
    now = int(time.time())
    body = {"iss": ISS, "aud": AUD, "sub": "external-user", "exp": now + 300, "iat": now}
    for key, value in overrides.items():
        if value is None:
            body.pop(key, None)
        else:
            body[key] = value
    head = _b64(json.dumps({"alg": alg, "kid": kid, "typ": "JWT"}).encode())
    payload = _b64(json.dumps(body).encode())
    signing = f"{head}.{payload}".encode()
    if alg == "RS256":
        sig = rsa_key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
    elif alg == "ES256":
        r, s = decode_dss_signature(ec_key.sign(signing, ec.ECDSA(hashes.SHA256())))
        sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    else:
        sig = b""
    return f"{head}.{payload}.{_b64(sig)}"


@pytest.fixture
def provider(keys, monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        assert url == JWKS
        return httpx.Response(200, json=keys[2])

    monkeypatch.setattr(httpx, "get", fake_get)
    p = OidcIdentityProvider("", ISS, jwks_url=JWKS, audience=AUD, timeout=3)
    p.calls = calls
    return p


def test_valid_rs256_and_es256_map_stable_principal(provider, keys):
    first = provider.verify(_token(keys))
    second = provider.verify(_token(keys, alg="ES256", kid="e1"))
    assert isinstance(first.user_id, UUID) and first == second
    assert first.subject == "external-user"
    assert provider.calls == [JWKS]  # JWKS em cache


@pytest.mark.parametrize(
    "case",
    [
        {"aud": "other-api"},
        {"iss": None},
        {"iss": "https://evil.example"},
        {"email_verified": False},
        {"exp": int(time.time()) - 3600},
        {"nbf": int(time.time()) + 3600},
        {"sub": None},
        {"exp": None},
    ],
)
def test_rejects_bad_claims(provider, keys, case):
    with pytest.raises(Unauthorized):
        provider.verify(_token(keys, **case))


def test_azp_can_carry_audience(provider, keys):
    assert provider.verify(_token(keys, aud="account", azp=AUD)).subject == "external-user"


@pytest.mark.parametrize("alg", ["none", "HS256"])
def test_rejects_none_and_hmac_algorithms(provider, keys, alg):
    with pytest.raises(Unauthorized):
        provider.verify(_token(keys, alg=alg))


def test_rejects_tampered_signature_unknown_kid_and_garbage(provider, keys):
    token = _token(keys)
    head, _payload, sig = token.split(".")
    forged = _b64(json.dumps({"iss": ISS, "aud": AUD, "sub": "admin", "exp": 9999999999}).encode())
    for bad in (f"{head}.{forged}.{sig}", _token(keys, kid="unknown"), "a.b", "", "x.y.z"):
        with pytest.raises(Unauthorized):
            provider.verify(bad)


def test_userinfo_only_complements_and_must_match_subject(keys, monkeypatch):
    def fake_get(url, **kwargs):
        if url == JWKS:
            return httpx.Response(200, json=keys[2])
        return httpx.Response(200, json={"sub": "someone-else"})

    monkeypatch.setattr(httpx, "get", fake_get)
    p = OidcIdentityProvider("https://identity.example/userinfo", ISS, jwks_url=JWKS, audience=AUD)
    with pytest.raises(Unauthorized):
        p.verify(_token(keys))


def test_fail_closed_without_jwks_or_audience_and_http_remote():
    with pytest.raises(ValueError, match="RPG_OIDC_JWKS_URL"):
        OidcIdentityProvider("", ISS, audience=AUD)
    with pytest.raises(ValueError, match="RPG_OIDC_AUDIENCE"):
        OidcIdentityProvider("", ISS, jwks_url=JWKS)
    with pytest.raises(ValueError, match="HTTPS"):
        OidcIdentityProvider("", ISS, jwks_url="http://identity.example/jwks", audience=AUD)
    with pytest.raises(ValueError, match="HTTPS"):
        OidcIdentityProvider("http://identity.example/userinfo", ISS, jwks_url=JWKS, audience=AUD)


def test_password_grant_stays_unavailable(provider):
    with pytest.raises(Unauthorized, match="senha"):
        provider.login("a@example.com", "secret")


def test_runtime_config_requires_issuer_jwks_and_audience():
    base = {
        "RPG_RUNTIME_PROFILE": "portable",
        "DATABASE_URL": "postgresql://localhost/postgres",
        "RPG_OIDC_ISSUER": ISS,
    }
    for missing in ({}, {"RPG_OIDC_JWKS_URL": JWKS}, {"RPG_OIDC_AUDIENCE": AUD}):
        with pytest.raises(ValueError, match="RPG_OIDC_JWKS_URL"):
            RuntimeConfig.from_env({**base, **missing})
    config = RuntimeConfig.from_env({**base, "RPG_OIDC_JWKS_URL": JWKS, "RPG_OIDC_AUDIENCE": AUD})
    assert (config.oidc_jwks_url, config.oidc_audience) == (JWKS, AUD)


def test_unknown_kid_flood_refetches_jwks_at_most_once_per_cooldown(provider, keys):
    """Revisão Sol: kid desconhecido não pode virar amplificação de requests ao IdP."""
    provider.verify(_token(keys))
    for _ in range(20):
        with pytest.raises(Unauthorized):
            provider.verify(_token(keys, kid=f"rot-{_}"))
    assert len(provider.calls) <= 2


@pytest.mark.parametrize("value", ["nan", "inf", True, "9999999999"])
def test_rejects_non_numeric_or_non_finite_time_claims(provider, keys, value):
    with pytest.raises(Unauthorized):
        provider.verify(_token(keys, exp=value))
    with pytest.raises(Unauthorized):
        provider.verify(_token(keys, nbf=value if value is not True else True))
