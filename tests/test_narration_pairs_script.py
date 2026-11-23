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


def _cases() -> list[dict]:
    return json.loads(CASES.read_text(encoding="utf-8"))


def _boom(*_a, **_k):
    raise AssertionError("chamada real de LLM no teste do pacote de pares")


def test_world_pulse_llm_is_neutralised(monkeypatch):
    """P2-1: com o LLM do mundo explodindo, o run --mock ainda gera os 10 pares (sem chamar)."""
    import llm_setup
    from agents import world_simulator

    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")  # caminho `simulate_world`, que chamaria LLM
    monkeypatch.setattr(world_simulator, "get_llm", _boom)
    monkeypatch.setattr(llm_setup, "get_llm", _boom)
    result = np_.run(_cases(), np_._FakeNarrator())
    assert len(result["pairs"]) == 10
    assert result["calls"] == 20  # 10 casos x 2 bracos, so o narrador


def test_zero_llm_calls_outside_narrator(monkeypatch):
    import llm_setup
    from agents import storyteller as st

    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")  # caminho `simulate_world`, que chamaria LLM
    monkeypatch.setattr(llm_setup, "get_llm", _boom)
    budget = {"calls": 0, "foreign": 0}
    counted = np_._CountingLLM(np_._FakeNarrator(), budget)
    with np_._llm_guard(counted, budget):
        assert st.get_llm() is counted  # o narrador recebe o proxy contado
        with pytest.raises(RuntimeError):
            llm_setup.get_llm()  # qualquer outro ponto de LLM levanta e e contado
    assert budget["foreign"] == 1
    result = np_.run(_cases(), np_._FakeNarrator())
    assert result["calls"] == 20


def test_budget_refuses_before_any_call(tmp_path):
    class _Spy(np_._FakeNarrator):
        n = 0

        def invoke(self, *a, **k):
            _Spy.n += 1
            return super().invoke(*a, **k)

    with pytest.raises(SystemExit, match="previsto 40"):
        np_.run(_cases(), _Spy(), samples=2)
    assert _Spy.n == 0
    with pytest.raises(SystemExit, match="previsto"):
        np_.main(["--cases", str(CASES), "--out", str(tmp_path / "x"), "--mock", "--samples", "2"])
    assert not (tmp_path / "x.md").exists()


def test_pairs_carry_input_hash_and_fail_on_divergence(tmp_path, monkeypatch):
    out = tmp_path / "pares"
    assert np_.main(["--cases", str(CASES), "--out", str(out), "--mock"]) == 0
    data = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert all(len(p["input_hash"]) == 16 for p in data["pairs"])
    seq = iter(range(1000))
    monkeypatch.setattr(np_, "prompt_fingerprint", lambda _m: str(next(seq)))
    with pytest.raises(SystemExit, match="divergem"):
        np_.run(_cases(), np_._FakeNarrator())


def test_fingerprint_ignores_only_size_lines():
    a = ["x\n- Responda em 2 a 3 parágrafos.\nfim"]
    b = [
        "x\n- Responda em 2 a 3 parágrafos, salvo quando TAMANHO DA RESPOSTA, abaixo\n"
        "    - TAMANHO DA RESPOSTA: 1\nfim"
    ]
    assert np_.prompt_fingerprint(a) == np_.prompt_fingerprint(b)
    assert np_.prompt_fingerprint(a) != np_.prompt_fingerprint(["y\nfim"])
