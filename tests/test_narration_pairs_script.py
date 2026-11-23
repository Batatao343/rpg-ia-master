"""SPEC-428 R12: script do pacote de pares (`scripts/dev/narration_pairs.py`)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "docs" / "spec428" / "pares_casos.json"

sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import narration_pairs as np_  # noqa: E402


def test_committed_cases_match_generator():
    assert json.loads(CASES.read_text(encoding="utf-8")) == np_.build_cases()


def test_mock_run_makes_ten_pairs_with_expected_classes(tmp_path, monkeypatch):
    from services import narration_size as ns

    seen: list[str] = []
    real = ns.classify

    def spy(t):
        seen.append(real(t))
        return seen[-1]

    monkeypatch.setattr(ns, "classify", spy)
    out = tmp_path / "pares"
    rc = np_.main(["--cases", str(CASES), "--out", str(out), "--mock"])
    assert rc == 0
    data = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert len(data["pairs"]) == 10
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    # `on` classifica 1x por caso (o `off` nao loga nem classifica)
    assert seen == [c["expected_class"] for c in cases]
    assert out.with_suffix(".md").read_text(encoding="utf-8").count("### on") == 10


def test_json_has_only_counts(tmp_path):
    out = tmp_path / "pares"
    assert np_.main(["--cases", str(CASES), "--out", str(out), "--mock"]) == 0
    raw = out.with_suffix(".json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert "text" not in raw and "git_sha" in data
    for pair in data["pairs"]:
        assert set(pair["off"]["counts"]) == {"chars", "paragraphs", "option_lines"}


def test_refuses_without_key_and_without_mock(tmp_path, monkeypatch):
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.setattr("llm_setup.get_llm", lambda *a, **k: type("M", (), {"is_mock": True})())
    with pytest.raises(SystemExit, match="sem chave"):
        np_.main(["--cases", str(CASES), "--out", str(tmp_path / "x")])
    assert not (tmp_path / "x.md").exists()


def test_refuses_with_force_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_FORCE_MOCK", "1")
    with pytest.raises(SystemExit, match="RPG_FORCE_MOCK"):
        np_.main(["--cases", str(CASES), "--out", str(tmp_path / "x")])


def test_call_budget_aborts():
    class _L:
        def with_structured_output(self, *a, **k):
            return self

        def invoke(self, *a, **k):
            return None

    counted = np_._CountingLLM(_L(), {"calls": np_.MAX_CALLS})
    with pytest.raises(SystemExit):
        counted.with_structured_output(None).invoke([])
