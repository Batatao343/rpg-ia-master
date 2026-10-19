"""Workspace tooling contracts (docs/melhorias_workspace): skills, agents, scripts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.dev import eval_publish

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("qa", "wrap-up", "spec-new", "spec-land", "estado", "reindex", "eval-publish",
          "staging-deploy", "status-dono")
AGENTS = ("spec-executor", "spec-reviewer", "spec-author", "code-locator", "audit-reader", "ci-watcher")


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path} lacks frontmatter"
    return dict(line.split(": ", 1) for line in match.group(1).splitlines() if ": " in line)


@pytest.mark.parametrize("name", SKILLS)
def test_versioned_skills_have_frontmatter_and_no_hardcoded_checkout(name: str) -> None:
    path = ROOT / ".claude/skills" / name / "SKILL.md"
    meta = _frontmatter(path)
    assert meta["name"] == name and meta["description"]
    assert "Trabalho/rpg-ia-master" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", AGENTS)
def test_agent_types_pin_a_model(name: str) -> None:
    meta = _frontmatter(ROOT / ".claude/agents" / f"{name}.md")
    assert meta["name"] == name
    assert meta["model"] in {"haiku", "sonnet", "opus"}


def test_settings_json_is_valid_and_hook_is_checkout_relative() -> None:
    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    command = settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
    assert "$CLAUDE_PROJECT_DIR" in command and "Trabalho" not in command
    assert settings["env"]["PYTHONUTF8"] == "1"


def test_eval_publish_prints_owner_approval_command() -> None:
    command = eval_publish.approval_command("o/r", "123", "456")
    assert command.startswith("gh api -X POST repos/o/r/actions/runs/123/pending_deployments")
    assert "environment_ids[]=456" in command and "state=approved" in command
