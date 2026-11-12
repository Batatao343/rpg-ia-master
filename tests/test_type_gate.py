"""SPEC-418: gate de tipos (basedpyright). Puros na suite default; `types_e2e` roda o checador."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path

import pytest
import yaml

from scripts.dev import type_gate as tg

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "dev" / "type_gate.py"

UNGUARDED = """\
from pydantic import BaseModel

from llm_setup import ModelTier, get_llm


class Cena(BaseModel):
    titulo: str


def f() -> str:
    r = get_llm(0.1, ModelTier.FAST).with_structured_output(Cena).invoke("x")
    return r.titulo
"""

GUARDED = UNGUARDED.replace(
    "    return r.titulo", "    if isinstance(r, Cena):\n        return r.titulo\n    return ''"
)

SELF_CONTAINED = """\
from langchain_core.messages import AIMessage


class Fallback:
    def with_structured_output(self, *a: object) -> "Fallback":
        return self

    def invoke(self, x: object) -> AIMessage:
        return AIMessage(content="")


def f() -> object:
    return Fallback().with_structured_output(dict).invoke("x").titulo
"""


def _entries(**kw: int) -> Counter:
    return Counter({tuple(k.split("__")): n for k, n in kw.items()})


# Funcoes puras, R20


def test_entries_reads_checker_baseline_format() -> None:
    data = {
        "files": {
            "./services/a.py": [{"code": "reportCallIssue"}, {"code": "reportCallIssue"}],
            "./state.py": [{"code": "reportReturnType"}],
        }
    }
    assert tg.entries(data) == Counter(
        {("services/a.py", "reportCallIssue"): 2, ("state.py", "reportReturnType"): 1}
    )
    assert tg.entries({}) == Counter()


def test_slack_flags_fixed_entries_only() -> None:
    base = _entries(a__r1=2, b__r2=1)
    assert tg.slack(base, base) == []
    msgs = tg.slack(base, _entries(a__r1=1, b__r2=1))
    assert len(msgs) == 1
    assert "baseline folgada: a r1 2 -> 1" in msgs[0]
    assert "--tighten" in msgs[0]
    assert tg.slack(base, _entries(a__r1=2)) != []  # arquivo apagado


def test_is_shrink_only_rejects_any_new_entry() -> None:
    old = _entries(a__r1=2, b__r2=1)
    assert tg.is_shrink_only(old, _entries(a__r1=1))
    assert tg.is_shrink_only(old, old)
    assert not tg.is_shrink_only(old, _entries(a__r1=3))
    assert not tg.is_shrink_only(old, _entries(c__r9=1))


def test_growth_against_base() -> None:
    base = _entries(a__r1=2)
    assert tg.growth(base, base) == []
    assert tg.growth(base, _entries(a__r1=1)) == []
    out = tg.growth(base, _entries(a__r1=3, z__r2=1))
    assert len(out) == 2
    assert any("a r1 2 -> 3" in m for m in out)


def test_needs_check_filters_changed_files() -> None:
    assert not tg.needs_check(["docs/a.md", "web/src/x.tsx", "specs/SPEC-1.md"])
    assert tg.needs_check(["docs/a.md", "api.py"])  # .py fora do escopo tambem
    assert tg.needs_check(["pyproject.toml"])
    assert tg.needs_check(["uv.lock"])
    assert tg.needs_check([".basedpyright/baseline.json"])
    assert not tg.needs_check([])


def test_land_line_format() -> None:
    assert tg.land_line("OK", "nada a checar") == "OK types: nada a checar"
    assert tg.land_line("FAIL", "2 erros novos").startswith("FAIL types: ")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8",
    )  # fmt: skip


def _repo_with_change(tmp_path: Path, filename: str) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "README.md").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    _git(tmp_path, "checkout", "-q", "-b", "feat")
    (tmp_path / filename).write_text(
        "x = 1\n" if filename.endswith(".py") else "b\n", encoding="utf-8"
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "change")
    return tmp_path


def test_land_prints_ok_when_diff_is_not_python(tmp_path: Path, capsys) -> None:
    repo = _repo_with_change(tmp_path, "notas.md")
    assert tg.main(["--land", "--base", "main", "--repo", str(repo)]) == 0
    assert capsys.readouterr().out.strip() == "OK types: nada a checar"


def test_land_warns_when_checker_missing(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _repo_with_change(tmp_path, "mod.py")
    monkeypatch.setattr(tg, "checker_installed", lambda: False)
    assert tg.main(["--land", "--base", "main", "--repo", str(repo)]) == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("WARN types:")
    assert "basedpyright" in out


def test_land_fails_when_baseline_grew(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _repo_with_change(tmp_path, "mod.py")
    (repo / ".basedpyright").mkdir()
    base = '{"files": {"./a.py": [{"code": "reportCallIssue"}]}}'
    _git(repo, "checkout", "-q", "main")
    (repo / ".basedpyright" / "baseline.json").write_text(base, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")
    _git(repo, "checkout", "-q", "feat")
    _git(repo, "merge", "-q", "main", "-m", "m")
    grown = '{"files": {"./a.py": [{"code": "reportCallIssue"}, {"code": "reportCallIssue"}]}}'
    (repo / ".basedpyright" / "baseline.json").write_text(grown, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "grow")
    monkeypatch.setattr(tg, "checker_installed", lambda: True)
    assert tg.main(["--land", "--base", "main", "--repo", str(repo)]) == 1
    assert capsys.readouterr().out.startswith("FAIL types: 1 entrada(s): baseline cresceu")


def test_update_requires_reason(tmp_path: Path) -> None:
    assert tg.cmd_update(tmp_path, "  ") == 2


def test_basedpyright_config_matches_spec() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    cfg = data["tool"]["basedpyright"]
    assert "persistence.py" in cfg["include"] and "state.py" in cfg["include"]
    assert "infrastructure" in cfg["include"]
    assert cfg["pythonPlatform"] == "Linux"
    assert cfg["pythonVersion"] == "3.13"
    assert cfg["typeCheckingMode"] == "standard"
    for rule in (
        "reportOptionalMemberAccess", "reportAttributeAccessIssue", "reportCallIssue",
        "reportArgumentType", "reportReturnType", "reportOptionalSubscript",
        "reportPossiblyUnboundVariable", "reportIgnoreCommentWithoutRule",
    ):  # fmt: skip
        assert cfg[rule] == "error", rule
    dev = data["dependency-groups"]["dev"]
    pins = [d for d in dev if d.startswith("basedpyright")]
    assert len(pins) == 1 and pins[0].startswith("basedpyright==")
    assert "types_e2e" in data["tool"]["pytest"]["ini_options"]["addopts"]
    assert any(m.startswith("types_e2e:") for m in data["tool"]["pytest"]["ini_options"]["markers"])


def test_ci_has_types_job() -> None:
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "validate.yml").read_text("utf-8"))
    job = wf["jobs"]["types"]
    assert "docs_only" in job["if"]
    assert job["needs"] == "scope"
    assert job["continue-on-error"] is True  # calibracao (R17): o coordenador remove depois
    runs = " ".join(s.get("run", "") for s in job["steps"])
    assert "type_gate.py --check" in runs
    assert "uv sync --all-extras" in runs


# Rodam o checador de verdade, R19


def _gate_files(tmp_path: Path, source: str) -> subprocess.CompletedProcess:
    f = tmp_path / "mod_probe.py"
    f.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(GATE), "--files", str(f)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=600,
    )  # fmt: skip


@pytest.mark.types_e2e
def test_unguarded_structured_output_is_rejected(tmp_path: Path) -> None:
    out = _gate_files(tmp_path, UNGUARDED)
    assert out.returncode == 1, out.stdout + out.stderr
    lines = [ln for ln in out.stdout.splitlines() if "reportAttributeAccessIssue" in ln]
    assert any(":12 " in ln and "AIMessage" in ln for ln in lines), out.stdout


@pytest.mark.types_e2e
def test_guarded_structured_output_passes(tmp_path: Path) -> None:
    out = _gate_files(tmp_path, GUARDED)
    assert out.returncode == 0, out.stdout + out.stderr


@pytest.mark.types_e2e
def test_self_contained_fallback_pattern_is_rejected(tmp_path: Path) -> None:
    out = _gate_files(tmp_path, SELF_CONTAINED)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "reportAttributeAccessIssue" in out.stdout
    assert "AIMessage" in out.stdout


@pytest.mark.types_e2e
def test_bare_type_ignore_is_rejected(tmp_path: Path) -> None:
    out = _gate_files(tmp_path, 'x: int = "a"  # type: ignore\n')
    assert out.returncode == 1, out.stdout + out.stderr
    assert "reportIgnoreCommentWithoutRule" in out.stdout
