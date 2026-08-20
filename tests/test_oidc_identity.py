from __future__ import annotations

from uuid import UUID

import httpx
import pytest

from infrastructure.contracts import Unauthorized
from infrastructure.oidc_identity import OidcIdentityProvider


def test_oidc_userinfo_valida_token_e_mapeia_subject_nao_uuid(monkeypatch):
    def fake_get(url, *, headers, timeout):
        assert url == "https://identity.example/userinfo"
        assert headers == {"Authorization": "Bearer good"}
        assert timeout == 3
        return httpx.Response(200, json={"sub": "external-user", "iss": "https://identity.example"})

    monkeypatch.setattr(httpx, "get", fake_get)
    provider = OidcIdentityProvider(
        "https://identity.example/userinfo", "https://identity.example", timeout=3,
    )
    first = provider.verify("good")
    second = provider.verify("good")
    assert isinstance(first.user_id, UUID)
    assert first == second
    assert first.subject == "external-user"


def test_oidc_rejeita_status_subject_e_issuer_invalidos(monkeypatch):
    provider = OidcIdentityProvider(
        "https://identity.example/userinfo", "https://identity.example",
    )
    fixtures = [
        httpx.Response(401),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"sub": "u", "iss": "https://evil.example"}),
    ]
    for response in fixtures:
        monkeypatch.setattr(httpx, "get", lambda *_args, **_kwargs: response)
        with pytest.raises(Unauthorized):
            provider.verify("bad")


def test_oidc_recusa_http_remoto_e_password_grant():
    with pytest.raises(ValueError, match="HTTPS"):
        OidcIdentityProvider("http://identity.example/userinfo", "https://identity.example")
    provider = OidcIdentityProvider(
        "https://identity.example/userinfo", "https://identity.example",
    )
    with pytest.raises(Unauthorized, match="senha"):
        provider.login("a@example.com", "secret")
