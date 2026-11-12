"""SPEC-414 R4: `env.sh` escolhe o venv do principal em worktree; `wt.sh new` avisa em stderr.

Os caminhos são comparados normalizados (`_norm`): o Git Bash devolve `/c/...` e o Python
`C:\\...`, e `cygpath` nem sempre existe fora do Windows.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(not (BASH and GIT), reason="bash/git indisponíveis")


def _norm(p: str | Path) -> str:
    s = str(p).strip().replace("\\", "/").rstrip("/").lower()
    return re.sub(r"^/([a-z])/", r"\1:/", s)


def _git(cwd: Path, *args: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}  # fmt: skip
    subprocess.run([GIT, *args], cwd=cwd, check=True, capture_output=True, env=env)


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    (main / "scripts" / "dev").mkdir(parents=True)
    for name in ("env.sh", "wt.sh"):
        shutil.copy(ROOT / "scripts" / "dev" / name, main / "scripts" / "dev" / name)
    (main / "uv.lock").write_text("lock-a\n", encoding="utf-8")
    _git(main, "init", "-q", "-b", "main")
    _git(main, "add", ".")
    _git(main, "commit", "-qm", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt), "main")
    return main, wt


def _env_out(cwd: Path, **env: str) -> subprocess.CompletedProcess:
    base = {k: v for k, v in os.environ.items() if k != "UV_PROJECT_ENVIRONMENT"}
    return subprocess.run(
        [BASH, "-c", '. scripts/dev/env.sh; echo "${UV_PROJECT_ENVIRONMENT:-}"'],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", env={**base, **env},
    )  # fmt: skip


def test_worktree_prefers_main_venv_even_with_own(repo: tuple[Path, Path]) -> None:
    main, wt = repo
    (main / ".venv").mkdir()
    (wt / ".venv").mkdir()
    out = _env_out(wt)
    assert _norm(out.stdout.strip().splitlines()[-1]) == _norm(main / ".venv")
    assert "ignorando" in out.stderr


def test_worktree_with_different_lock_keeps_own_env(repo: tuple[Path, Path]) -> None:
    main, wt = repo
    (main / ".venv").mkdir()
    (wt / "uv.lock").write_text("lock-b\n", encoding="utf-8")
    out = _env_out(wt)
    assert out.stdout.strip() == ""
    assert "uv sync --all-extras" in out.stderr


def test_main_checkout_and_explicit_env_untouched(repo: tuple[Path, Path]) -> None:
    main, wt = repo
    (main / ".venv").mkdir()
    assert _env_out(main).stdout.strip() == ""
    assert _env_out(wt, UV_PROJECT_ENVIRONMENT="/x").stdout.strip() == "/x"


def test_wt_new_warns_on_stderr_only(repo: tuple[Path, Path], tmp_path: Path) -> None:
    main, _wt = repo
    root = tmp_path / "wts"
    env = {**os.environ, "RPG_WT_ROOT": str(root)}

    def run(n: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [BASH, "scripts/dev/wt.sh", "new", n], cwd=main, capture_output=True, text=True,
            encoding="utf-8", env=env,
        )  # fmt: skip

    first = run("998")
    assert first.returncode == 0, first.stderr
    assert len(first.stdout.strip().splitlines()) == 1
    assert _norm(first.stdout).endswith("rpg-spec-998")
    assert "uv sync --all-extras" in first.stderr
    (main / ".venv").mkdir()
    second = run("999")
    assert second.returncode == 0, second.stderr
    assert len(second.stdout.strip().splitlines()) == 1
    assert "não rode `uv sync`" in second.stderr
