"""SPEC-197 R3: legal pages are served by the app (static, CSP-compatible, RASCUNHO visible)."""
from pathlib import Path

import pytest

DIST = Path(__file__).resolve().parents[1] / "web" / "dist"


@pytest.mark.skipif(not (DIST / "privacidade" / "index.html").exists(), reason="web build ausente")
@pytest.mark.parametrize("slug", ["privacidade", "termos", "reembolso", "suporte"])
def test_legal_page_served_with_csp_and_draft_banner(slug):
    from fastapi.testclient import TestClient
    import api
    r = TestClient(api.app).get(f"/{slug}/")
    assert r.status_code == 200 and "RASCUNHO" in r.text
    assert "<script" not in r.text.lower()
    assert "script-src 'self'" in r.headers.get("content-security-policy", "")
