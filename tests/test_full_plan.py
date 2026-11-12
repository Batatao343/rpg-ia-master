"""SPEC-414 R1: planejamento e wrapper da suíte completa (`scripts/dev/full.sh`)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from scripts.dev import full_plan as fp

ROOT = Path(__file__).resolve().parents[1]


def test_pick_workers_table() -> None:
    assert fp.pick_workers(None, 8, None) == 2
    assert fp.pick_workers(2.9, 8, None) is None
    assert fp.pick_workers(3.0, 8, None) == 2
    assert fp.pick_workers(64.0, 4, None) == 4
    assert fp.pick_workers(64.0, 16, None) == fp.MAX_WORKERS
    seq = [fp.pick_workers(g / 2, 16, None) or 0 for g in range(6, 60)]
    assert seq == sorted(seq)
    assert fp.pick_workers(1.0, 8, "5") == 5
    assert fp.pick_workers(8.0, 8, "x") == fp.pick_workers(8.0, 8, None)


def test_crashed_ids_from_real_xdist_crash(tmp_path: Path) -> None:
    t = tmp_path / "test_boom.py"
    t.write_text(
        "import os\n\ndef test_ok():\n    pass\n\ndef test_exit():\n    os._exit(1)\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-n", "1", "-p", "no:cacheprovider", "-o", "addopts=",
         "--rootdir", str(tmp_path), "--basetemp", str(tmp_path / "bt"), str(t)],
        capture_output=True, text=True, encoding="utf-8", timeout=120, cwd=tmp_path,
    )  # fmt: skip
    ids = fp.crashed_ids(out.stdout)
    assert len(ids) == 1 and ids[0].endswith("test_boom.py::test_exit")


def test_verdict() -> None:
    a = ["t.py::a"]
    assert fp.verdict(a, a, 0) == 0
    assert fp.verdict(a + ["t.py::b"], a, 0) == 1
    assert fp.verdict(a, a, 1) == 1
    assert fp.verdict(["t.py::b"], [], None) == 1
    assert fp.verdict([], [], None) == 0
    many = [f"t.py::c{i}" for i in range(21)]
    assert fp.verdict(many, many, 0) == 1


FAKE = textwrap.dedent(
    """
    import os, sys
    mode, counter = os.environ["FAKE_MODE"], os.environ["FAKE_COUNT"]
    n = int(open(counter).read()) if os.path.exists(counter) else 0
    open(counter, "w").write(str(n + 1))
    if mode == "green":
        print("1 passed"); sys.exit(0)
    if mode == "plainfail":
        print("FAILED tests/t.py::test_b - assert 0"); sys.exit(1)
    if n == 0:
        print("FAILED tests/t.py::test_a - worker 'gw0' crashed while running 'tests/t.py::test_a'")
        sys.exit(1)
    sys.exit(0)
    """
)


def _full(tmp_path: Path, mode: str, **env: str) -> tuple[subprocess.CompletedProcess, int]:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash indisponível")
    fake = tmp_path / "fake.py"
    fake.write_text(FAKE, encoding="utf-8")
    counter = tmp_path / "count"
    e = {
        **os.environ,
        "FAKE_MODE": mode,
        "FAKE_COUNT": str(counter),
        "FULL_PYTEST": f'"{sys.executable}" "{fake}"'.replace("\\", "/"),
        "FULL_N": "2",
        "TMPDIR": str(tmp_path),
        **env,
    }
    out = subprocess.run(
        [bash, "scripts/dev/full.sh"], cwd=ROOT, env=e, capture_output=True, text=True,
        encoding="utf-8", timeout=120,
    )  # fmt: skip
    calls = int(counter.read_text()) if counter.exists() else 0
    return out, calls


def test_full_sh_propagates_rc_and_reruns_crash(tmp_path: Path) -> None:
    out, calls = _full(tmp_path, "crash")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "mortos=1" in out.stdout and calls == 2
    for sub in ("b", "c"):
        (tmp_path / sub).mkdir()
    out, calls = _full(tmp_path / "b", "plainfail")
    assert out.returncode == 1 and calls == 1
    out, calls = _full(tmp_path / "c", "green")
    assert out.returncode == 0 and "mortos=0" in out.stdout


def test_full_sh_refuses_below_floor(tmp_path: Path) -> None:
    out, calls = _full(tmp_path, "green", FULL_PLAN_FREE_GB="1.0", FULL_N="")
    assert out.returncode == 3 and calls == 0
