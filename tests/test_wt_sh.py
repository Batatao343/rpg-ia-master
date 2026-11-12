"""SPEC-415 R3/R10: `wt.sh` real em repositorio temporario (sync/land/ci com land_check)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="precisa de bash")

SPEC_BODY = "# SPEC-999 - t\n\n> **Status:** `in-progress`\n> **Risco:** `baixo`\n"


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return out.stdout.strip()


def _wt(repo: Path, wt_root: Path, *args: str, **env: str) -> subprocess.CompletedProcess:
    import os

    full = {
        **os.environ,
        "RPG_WT_ROOT": wt_root.as_posix(),
        "RPG_LAND_SKIP": "ram",
        "RPG_WT_PUSH": "",
        **env,
    }
    return subprocess.run(
        [BASH, "scripts/dev/wt.sh", *args],
        cwd=repo,
        env=full,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "principal"
    (main / "scripts" / "dev").mkdir(parents=True)
    (main / "specs").mkdir()
    (main / "docs").mkdir()
    for name in (
        "wt.sh",
        "land_check.sh",
        "land_check.py",
        "baseline_growth.py",
        "weak_tests.py",
        "red_green.py",
    ):
        if (
            ROOT / "scripts" / "dev" / name
        ).exists():  # na main (sem land_check) o teste fica vermelho de verdade
            shutil.copy(ROOT / "scripts" / "dev" / name, main / "scripts" / "dev" / name)
    (main / "scripts" / "check_handoff_names.py").write_text(
        (ROOT / "scripts" / "check_handoff_names.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (main / "scripts" / "dev" / "py.sh").write_text(
        f'#!/usr/bin/env bash\nexec "{Path(sys.executable).as_posix()}" "$@"\n', encoding="utf-8"
    )
    (main / "scripts" / "spec_index.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (main / "specs" / "SPEC-999-t.md").write_text(SPEC_BODY, encoding="utf-8")
    (main / "specs" / "index.yaml").write_text("specs: []\n", encoding="utf-8")
    (main / "docs" / "x.md").write_text("um\n", encoding="utf-8")
    _git(tmp_path, "init", "-q", "-b", "main", str(main))
    _git(main, "add", "-A")
    _git(main, "commit", "-q", "-m", "init")
    return main, tmp_path / "wt"


def _branch_changes_x(main: Path, wt_root: Path) -> None:
    assert _wt(main, wt_root, "new", "999").returncode == 0
    wt = wt_root / "rpg-spec-999"
    (wt / "docs" / "x.md").write_text("dois\n", encoding="utf-8")
    _git(wt, "commit", "-qam", "muda x")


def test_sync_fails_on_collision_with_dirty_main(repo: tuple[Path, Path]) -> None:
    main, root = repo
    _branch_changes_x(main, root)
    (main / "docs" / "x.md").write_text("sujo\n", encoding="utf-8")
    out = _wt(main, root, "sync", "999")
    assert out.returncode == 1, out.stdout + out.stderr
    assert "docs/x.md" in out.stdout


def test_land_refuses_ff_on_collision(repo: tuple[Path, Path]) -> None:
    main, root = repo
    _branch_changes_x(main, root)
    before = _git(main, "rev-parse", "main")
    (main / "docs" / "x.md").write_text("sujo\n", encoding="utf-8")
    out = _wt(main, root, "land", "999")
    assert out.returncode == 1
    assert "FAIL collision" in out.stdout
    assert _git(main, "rev-parse", "main") == before


def test_sync_clean_passes(repo: tuple[Path, Path]) -> None:
    main, root = repo
    _branch_changes_x(main, root)
    out = _wt(main, root, "sync", "999")
    assert out.returncode == 0, out.stdout + out.stderr


def test_land_clean_fast_forwards(repo: tuple[Path, Path]) -> None:
    main, root = repo
    _branch_changes_x(main, root)
    out = _wt(main, root, "land", "999")
    assert out.returncode == 0, out.stdout + out.stderr
    assert (main / "docs" / "x.md").read_text(encoding="utf-8") == "dois\n"


def test_ci_is_off_without_env(repo: tuple[Path, Path]) -> None:
    main, root = repo
    _branch_changes_x(main, root)
    out = _wt(main, root, "ci", "999")
    assert out.returncode == 3
    assert "desligado" in out.stderr


def test_ci_rejects_non_spec_target(repo: tuple[Path, Path]) -> None:
    main, root = repo
    out = _wt(main, root, "ci", "main", RPG_WT_PUSH="1")
    assert out.returncode == 2
    assert "spec-NNN" in out.stderr
