"""SPEC-386: hooks do Claude Code (guarda de leitura/pytest, ruff por edição, tamanho de sessão)."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"


def _run(hook: str, payload: dict | str) -> dict | None:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    out = subprocess.run(
        [sys.executable, "-I", str(HOOKS / hook)],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout) if out.stdout.strip() else None


def _denied(result: dict | None) -> bool:
    return bool(result) and result["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.fixture
def big(tmp_path: Path) -> Path:
    p = tmp_path / "big.md"
    p.write_text("x" * 50_000, encoding="utf-8")
    return p


@pytest.fixture
def small(tmp_path: Path) -> Path:
    p = tmp_path / "small.md"
    p.write_text("x" * 100, encoding="utf-8")
    return p


def _read(path: Path, **extra) -> dict:
    return {
        "tool_name": "Read",
        "tool_input": {"file_path": str(path), **extra},
        "cwd": str(path.parent),
    }


def _sh(cmd: str, cwd: Path, agent: bool = False, tool: str = "Bash") -> dict:
    data = {"tool_name": tool, "tool_input": {"command": cmd}, "cwd": str(cwd)}
    if agent:
        data["agent_id"] = "a1"
    return data


def test_read_big_without_limit_is_denied(big: Path) -> None:
    assert _denied(_run("guard_tools.py", _read(big)))


def test_read_big_with_limit_or_small_is_allowed(big: Path, small: Path) -> None:
    assert _run("guard_tools.py", _read(big, offset=1, limit=50)) is None
    assert _run("guard_tools.py", _read(small)) is None


def test_read_image_is_allowed(tmp_path: Path) -> None:
    img = tmp_path / "shot.png"
    img.write_bytes(b"\0" * 60_000)
    assert _run("guard_tools.py", _read(img)) is None


def test_read_transcript_is_denied(tmp_path: Path) -> None:
    p = tmp_path / ".claude" / "projects" / "x" / "s.jsonl"
    p.parent.mkdir(parents=True)
    p.write_text("{}", encoding="utf-8")
    assert _denied(_run("guard_tools.py", _read(p, limit=5)))


@pytest.mark.parametrize(
    "cmd",
    [
        "cat big.md",
        "cd sub && cat ../big.md",
        "cat small.md big.md",
        "Get-Content big.md",
        "WINPATH",
    ],
)
def test_cat_big_file_is_denied(big: Path, cmd: str) -> None:
    (big.parent / "sub").mkdir(exist_ok=True)
    if cmd == "WINPATH":
        cmd = f"cat {big}"  # C:\...\big.md sem aspas
    tool = "PowerShell" if cmd.startswith("Get-") else "Bash"
    assert _denied(_run("guard_tools.py", _sh(cmd, big.parent, tool=tool)))


@pytest.mark.parametrize(
    "cmd",
    [
        "cat big.md | head -20",
        "cat small.md",
        "cat > out.txt <<'EOF'\nhi\nEOF",
        "Get-Content big.md -TotalCount 20",
        "sed -n '1,20p' big.md",
        "cat big.md | grep x",
    ],
)
def test_capped_or_small_reads_are_allowed(big: Path, small: Path, cmd: str) -> None:
    tool = "PowerShell" if cmd.startswith("Get-") else "Bash"
    assert _run("guard_tools.py", _sh(cmd, big.parent, tool=tool)) is None


@pytest.mark.parametrize("flag", ["-n auto", "-n 4", "--numprocesses=auto", "-nauto", "-n=auto"])
def test_subagent_heavy_pytest_is_denied(tmp_path: Path, flag: str) -> None:
    assert _denied(
        _run("guard_tools.py", _sh(f"uv run pytest {flag} tests/", tmp_path, agent=True))
    )


@pytest.mark.parametrize(
    "cmd",
    [
        "bash scripts/dev/pt.sh tests/ -n 4",
        "bash scripts/dev/py.sh -m pytest -n auto",
        "PYTHONUTF8=1 uv run --frozen python -m pytest --numprocesses 4",
        "cd sub && uv run pytest -nauto | tail -n 5",
    ],
)
def test_subagent_heavy_pytest_forms_are_denied(tmp_path: Path, cmd: str) -> None:
    assert _denied(_run("guard_tools.py", _sh(cmd, tmp_path, agent=True)))


@pytest.mark.parametrize(
    "cmd",
    [
        "sed -n 80,200p tests/x.py | grep pytest",
        "git log -n 5 --grep pytest",
        "uv run pytest tests/x.py | tail -n 40",
        "echo pytest && head -n 50 README.md",
    ],
)
def test_subagent_non_pytest_dash_n_is_allowed(tmp_path: Path, cmd: str) -> None:
    assert _run("guard_tools.py", _sh(cmd, tmp_path, agent=True)) is None


def test_subagent_cannot_run_full_suite(tmp_path: Path) -> None:
    cmd = "bash scripts/dev/full.sh"
    assert _denied(_run("guard_tools.py", _sh(cmd, tmp_path, agent=True)))
    assert _run("guard_tools.py", _sh(cmd, tmp_path, agent=False)) is None


def _agent(subagent_type: object, prompt: object, tool: str = "Agent") -> dict:
    ti: dict = {"prompt": prompt}
    if subagent_type is not None:
        ti["subagent_type"] = subagent_type
    return {"tool_name": tool, "tool_input": ti, "cwd": "."}


@pytest.mark.parametrize("stype", [None, "", "general-purpose", "claude", "General-Purpose"])
def test_agent_without_type_needs_reason(stype: str | None) -> None:
    denied = _run("guard_tools.py", _agent(stype, "faça x"))
    assert _denied(denied)
    assert "Motivo sem tipo:" in denied["hookSpecificOutput"]["permissionDecisionReason"]
    ok = "SPEC-1\nMotivo sem tipo: precisa de web e edição juntos\nfim"
    assert _run("guard_tools.py", _agent(stype, ok)) is None
    assert _denied(_run("guard_tools.py", _agent(stype, "Motivo sem tipo: ok")))
    late = "x Motivo sem tipo: precisa de web e edição"
    assert _denied(_run("guard_tools.py", _agent(stype, late)))


@pytest.mark.parametrize(
    "stype",
    ["spec-executor", "code-locator", "Explore", "Plan", "claude-code-guide", "tipo-novo"],
)
@pytest.mark.parametrize("tool", ["Agent", "Task"])
def test_agent_typed_or_builtin_is_free(stype: str, tool: str) -> None:
    assert _run("guard_tools.py", _agent(stype, "faça x", tool)) is None


def test_agent_guard_never_crashes() -> None:
    bad = {"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose"}}
    assert _denied(_run("guard_tools.py", bad))  # sem prompt: sem marcador
    assert _denied(_run("guard_tools.py", _agent("general-purpose", 42)))
    assert _run("guard_tools.py", {"tool_name": "Agent", "tool_input": "texto"}) is None


def test_pytest_light_or_coordinator_is_allowed(tmp_path: Path) -> None:
    assert (
        _run("guard_tools.py", _sh("uv run pytest -n 2 tests/x.py", tmp_path, agent=True)) is None
    )
    assert _run("guard_tools.py", _sh("uv run pytest -n auto", tmp_path, agent=False)) is None
    cmd = "uv run pytest -n 2 tests | tail -n 40"
    assert _run("guard_tools.py", _sh(cmd, tmp_path, agent=True)) is None


def test_guard_never_crashes_on_garbage() -> None:
    assert _run("guard_tools.py", "not json") is None
    assert (
        _run(
            "guard_tools.py", {"tool_name": "Bash", "tool_input": {"command": "cat 'unterminated"}}
        )
        is None
    )


def test_ruff_hook_ignores_non_python_and_outside_repo(tmp_path: Path) -> None:
    md = tmp_path / "a.md"
    md.write_text("x", encoding="utf-8")
    assert _run("ruff_after_edit.py", {"tool_input": {"file_path": str(md)}}) is None
    py = tmp_path / "a.py"
    py.write_text("x=1\n", encoding="utf-8")
    assert _run("ruff_after_edit.py", {"tool_input": {"file_path": str(py)}}) is None
    assert py.read_text(encoding="utf-8") == "x=1\n"  # sem pyproject com [tool.ruff]: intocado


def test_ruff_hook_formats_and_reports(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.ruff]\nline-length = 100\n[tool.ruff.lint]\nselect = ["F"]\n'
    )
    py = tmp_path / "m.py"
    py.write_text("import os\nx=1\nprint(undefined_name)\n", encoding="utf-8")
    result = _run("ruff_after_edit.py", {"tool_input": {"file_path": str(py)}})
    text = py.read_text(encoding="utf-8")
    if "x = 1" not in text:
        pytest.skip("ruff indisponível neste ambiente")
    assert "import os" in text  # F401 não é auto-removido
    assert result and "F821" in result["hookSpecificOutput"]["additionalContext"]


def _transcript(tmp_path: Path, tokens: int) -> Path:
    t = tmp_path / "s.jsonl"
    line = {
        "type": "assistant",
        "message": {"usage": {"input_tokens": 5, "cache_read_input_tokens": tokens}},
    }
    t.write_text(json.dumps({"type": "user"}) + "\n" + json.dumps(line) + "\n", encoding="utf-8")
    return t


def test_context_size_warns_once_per_step(tmp_path: Path) -> None:
    sid = f"t-{uuid.uuid4().hex}"
    big = {"transcript_path": str(_transcript(tmp_path, 400_000)), "session_id": sid}
    first = _run("context_size.py", big)
    assert first and "400 K" in first["systemMessage"]
    assert _run("context_size.py", big) is None  # mesmo patamar: não repete


def test_context_size_points_to_handoff_file(tmp_path: Path) -> None:
    """SPEC-415 R23: o aviso diz onde gravar o handoff."""
    import datetime

    sid = f"t-{uuid.uuid4().hex}"
    big = {"transcript_path": str(_transcript(tmp_path, 400_000)), "session_id": sid}
    msg = _run("context_size.py", big)["systemMessage"]
    assert "/estado --handoff" in msg
    assert f".tmp/handoff-{datetime.date.today().isoformat()}.md" in msg


def test_context_size_quiet_when_small_or_subagent(tmp_path: Path) -> None:
    t = str(_transcript(tmp_path, 100_000))
    assert _run("context_size.py", {"transcript_path": t, "session_id": uuid.uuid4().hex}) is None
    t2 = str(_transcript(tmp_path, 900_000))
    assert (
        _run(
            "context_size.py",
            {"transcript_path": t2, "session_id": uuid.uuid4().hex, "agent_id": "a"},
        )
        is None
    )


def test_settings_register_every_hook_checkout_relative() -> None:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [
        h["command"] for groups in settings["hooks"].values() for g in groups for h in g["hooks"]
    ]
    for script in (
        "guard_tools.py",
        "ruff_after_edit.py",
        "context_size.py",
        "reindex-reminder.js",
    ):
        cmd = next(c for c in commands if script in c)
        assert "$CLAUDE_PROJECT_DIR/.claude/hooks/" in cmd and "Trabalho" not in cmd
        assert (HOOKS / script).is_file()
    guard = next(
        g
        for groups in settings["hooks"].values()
        for g in groups
        if any("guard_tools.py" in h["command"] for h in g["hooks"])
    )
    assert {"Agent", "Task"} <= set(guard["matcher"].split("|"))


def test_ruff_hook_skips_protected_eval_paths(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
    py = tmp_path / "evals" / "core" / "x.py"
    py.parent.mkdir(parents=True)
    py.write_text("x=1\n", encoding="utf-8")
    assert _run("ruff_after_edit.py", {"tool_input": {"file_path": str(py)}}) is None
    assert py.read_text(encoding="utf-8") == "x=1\n"


def test_ruff_hook_skips_files_listed_in_protected_paths(tmp_path: Path) -> None:
    """Revisão SPEC-388 P2-3: avaliador protegido fora de `evals/` também não é reescrito."""
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
    (tmp_path / "evals").mkdir()
    (tmp_path / "evals" / "protected-paths.txt").write_text(
        "# congelados\nscripts/fauna/eval.py\n", encoding="utf-8"
    )
    py = tmp_path / "scripts" / "fauna" / "eval.py"
    py.parent.mkdir(parents=True)
    py.write_text("x=1\n", encoding="utf-8")
    assert _run("ruff_after_edit.py", {"tool_input": {"file_path": str(py)}}) is None
    assert py.read_text(encoding="utf-8") == "x=1\n"
