"""SPEC-416 R29: relatório de crescimento de baselines contra um ref git."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.dev import baseline_growth as bg


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


def _repo(tmp_path: Path, files: dict[str, int]) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "size_budget.json").write_text(
        json.dumps({"files": {}, "functions": files}), encoding="utf-8"
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def _write(root: Path, functions: dict[str, int]) -> None:
    (root / "tests" / "size_budget.json").write_text(
        json.dumps({"files": {}, "functions": functions}), encoding="utf-8"
    )


def test_crescimento_lista_subida_e_chave_nova(tmp_path):
    root = _repo(tmp_path, {"a.py::f": 110, "b.py::g": 120})
    _write(root, {"a.py::f": 115, "b.py::g": 120, "c.py::h": 105})
    found = bg.report(root, "main")
    assert len(found) == 2
    assert any("subiu functions::a.py::f 110 -> 115" in line for line in found)
    assert any("chave nova functions::c.py::h" in line for line in found)


def test_so_descida_nao_reclama(tmp_path):
    root = _repo(tmp_path, {"a.py::f": 110})
    _write(root, {"a.py::f": 105})
    assert bg.report(root, "main") == []


def test_arquivo_ausente_na_base_conta_como_vazio(tmp_path):
    root = _repo(tmp_path, {})
    (root / "ruff-baseline-counts.json").write_text(
        json.dumps({"counts": {"x.py": {"BLE001": 2}}}), encoding="utf-8"
    )
    assert bg.report(root, "main") == [
        "ruff-baseline-counts.json: chave nova counts::x.py::BLE001 (2)"
    ]
