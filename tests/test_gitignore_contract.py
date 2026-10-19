"""SPEC-225 R1: .gitignore cobre segredos locais preventivos e não ignora o template."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

MUST_IGNORE = [
    ".env.local",
    ".env.production",
    ".env.production.local",
    "x.keystore",
    "k.jks",
    "google-services.json",
    "backend-service-account-prod.json",
    "server.pem",
    "server.key",
    "cert.p12",
    "cert.pfx",
    "keystore.properties",
    "signing.properties",
]
MUST_TRACK = [".env.example"]


def _git_ignored(name: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", name], cwd=ROOT, capture_output=True
    )
    if result.returncode not in (0, 1):
        pytest.skip("git indisponível para check-ignore")
    return result.returncode == 0


@pytest.mark.skipif(shutil.which("git") is None, reason="precisa de git")
@pytest.mark.parametrize("name", MUST_IGNORE)
def test_secret_like_files_are_ignored(name):
    assert _git_ignored(name), f"{name} deveria ser ignorado pelo .gitignore"


@pytest.mark.skipif(shutil.which("git") is None, reason="precisa de git")
@pytest.mark.parametrize("name", MUST_TRACK)
def test_templates_are_not_ignored(name):
    assert not _git_ignored(name), f"{name} é template versionado e não pode ser ignorado"
