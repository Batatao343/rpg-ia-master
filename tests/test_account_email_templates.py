"""Rendered email links match the browser fragment contract without URL logging."""
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit
import tomllib


def test_local_confirmation_and_recovery_links_use_fragment_only():
    config=tomllib.loads(Path("supabase/config.toml").read_text(encoding="utf-8"))
    assert config["auth"]["site_url"]=="http://localhost:5173"
    assert config["auth"]["email"]["enable_confirmations"] is True
    for kind,action in (("confirmation","verify"),("recovery","recovery")):
        template=Path(config["auth"]["email"]["template"][kind]["content_path"])
        content=template.read_text(encoding="utf-8")
        rendered=unescape(content.replace("{{ .SiteURL }}","http://localhost:5173")
                          .replace("{{ .TokenHash }}","hash-secret"))
        assert f'href="http://localhost:5173/#auth_action={action}&token_hash=hash-secret"' in rendered
        parsed=urlsplit(f"http://localhost:5173/#auth_action={action}&token_hash=hash-secret")
        assert parsed.query=="" and parsed.fragment.endswith("token_hash=hash-secret")
