"""SPEC-225 R2/R3/R4: workflows com permissions mínimas, sem pull_request_target e actions pinadas por SHA."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
SHA_USES = re.compile(r"^\s*-?\s*uses:\s*[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}\s+#\s*v\d")
ANY_USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_declares_top_level_permissions(path):
    data = _load(path)
    assert "permissions" in data, f"{path.name} sem bloco permissions no topo"
    assert data["permissions"] is not None


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_never_uses_pull_request_target(path):
    assert "pull_request_target" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_external_actions_are_pinned_by_sha_with_tag_comment(path):
    bad = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ANY_USES.match(line)
        if not match or match.group(1).startswith("./") or match.group(1).startswith("docker://"):
            continue
        if not SHA_USES.match(line):
            bad.append(line.strip())
    assert not bad, f"actions sem pin por SHA: {bad}"


def test_eval_protected_first_checkout_does_not_persist_credentials():
    data = _load(ROOT / ".github" / "workflows" / "eval-protected.yml")
    for job in data["jobs"].values():
        first = next(
            s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout")
        )
        assert first.get("with", {}).get("persist-credentials") is False
