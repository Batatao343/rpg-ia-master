"""SPEC-317 R11 — importar a API não carrega SDKs de provider, PIL nem uvicorn."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_HEAVY = ("langchain_anthropic", "langchain_google_genai", "ollama", "PIL", "uvicorn")


def test_importing_api_does_not_load_provider_sdks():
    code = (
        "import sys, api\n"
        f"bad = [m for m in {_HEAVY!r} if m in sys.modules]\n"
        "assert not bad, bad\n"
        "assert 'langchain_community.document_loaders' not in sys.modules\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "RPG_FORCE_MOCK": "1", "PYTHONUTF8": "1"},
    )
    assert result.returncode == 0, result.stderr[-800:]
