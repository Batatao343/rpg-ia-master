"""SPEC-222 R8/R10: terceiros declarados e retenção derivada do código."""
from __future__ import annotations

import re
from pathlib import Path

from infrastructure.account_lifecycle import RETAINED_WITH_REASON
from services.retention import RETENTION_RULES, retention_markdown

ROOT = Path(__file__).resolve().parents[1]
FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")


def test_retention_doc_is_generated_from_code():
    doc = (ROOT / "docs" / "spec222" / "retencao.md").read_text(encoding="utf-8")
    assert doc == retention_markdown(), "rode: uv run python scripts/gen_retention_doc.py"
    documented = set(re.findall(r"^\| `([a-z_]+)` \|", doc, flags=re.M))
    assert set(RETAINED_WITH_REASON) | set(RETENTION_RULES) <= documented


def test_index_html_has_no_external_font_hosts():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert not any(host in html for host in FONT_HOSTS)
    legal_renderer = (ROOT / "web" / "scripts" / "legal.mjs").read_text(encoding="utf-8")
    assert not any(host in legal_renderer for host in FONT_HOSTS)


def test_fonts_are_self_hosted_and_referenced():
    css = (ROOT / "web" / "src" / "fonts.css").read_text(encoding="utf-8")
    urls = re.findall(r"url\((/fonts/[^)]+\.woff2)\)", css)
    assert urls and not any(host in css for host in FONT_HOSTS)
    for url in set(urls):
        assert (ROOT / "web" / "public" / url.lstrip("/")).is_file(), url
    families = set(re.findall(r"font-family: '([^']+)'", css))
    assert {"Cinzel", "Cinzel Decorative", "EB Garamond"} <= families
    assert 'import "./fonts.css"' in (ROOT / "web" / "src" / "main.tsx").read_text(encoding="utf-8")


def test_csp_no_longer_allows_google_fonts():
    import api
    assert not any(host in api.CONTENT_SECURITY_POLICY for host in FONT_HOSTS)
    assert "font-src 'self' data:" in api.CONTENT_SECURITY_POLICY
