from __future__ import annotations

from uuid import uuid4

import pytest

from infrastructure.contracts import Principal, Unauthorized
from services.auth_sessions import CsrfSigner, cookie_settings, principal_from_session, validate_mutation_request


pytestmark = pytest.mark.security_local


def test_csrf_exige_cookie_header_assinados_e_origin_permitida():
    signer = CsrfSigner("x" * 32)
    token = signer.issue()
    validate_mutation_request(
        cookie_token=token, header_token=token, origin="http://127.0.0.1:5173/path",
        allowed_origins={"http://127.0.0.1:5173"}, signer=signer,
    )
    for changed in ({"header_token": "nope"}, {"origin": "https://evil.invalid"}):
        values = dict(cookie_token=token, header_token=token, origin="http://127.0.0.1:5173")
        values.update(changed)
        with pytest.raises(Unauthorized):
            validate_mutation_request(allowed_origins={"http://127.0.0.1:5173"}, signer=signer, **values)


def test_cookies_de_sessao_sao_httponly_e_refresh_strict():
    access = cookie_settings(secure=True)
    refresh = cookie_settings(secure=True, refresh=True)
    assert access["httponly"] is True and access["samesite"] == "lax"
    assert refresh["httponly"] is True and refresh["samesite"] == "strict"
    assert refresh["path"] == "/auth/refresh"


def test_principal_verificado_nao_aceita_subject_divergente():
    user_id = uuid4()
    class Fake:
        def verify(self, _token):
            return Principal(user_id, "test", str(uuid4()))
    with pytest.raises(Unauthorized):
        principal_from_session(Fake(), "secret")
