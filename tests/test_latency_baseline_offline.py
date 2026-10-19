"""SPEC-200 Etapa 5 — baseline offline repetivel (MockLLM + latencia injetada + relogio virtual)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playtest import latency_llm  # noqa: E402
from scripts import latency_baseline as lb  # noqa: E402


def _run(tmp_path, name, *, journeys="J1,J6", reps=2, seed=200, profile="typical"):
    rc = lb.main(["run", "--journeys", journeys, "--reps", str(reps), "--seed", str(seed),
                  "--profile", profile, "--mode", "virtual",
                  "--out-dir", str(tmp_path), "--run-id", name])
    assert rc == 0
    return tmp_path / name


def _summary(run_dir: Path) -> dict:
    return json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))


def test_injected_latency_recovered_in_phases(tmp_path):
    """flat-fast e sem jitter: a fase reflete exatamente a latencia injetada."""
    summary = _summary(_run(tmp_path, "ff", profile="flat-fast", journeys="J1"))
    phases = summary["journeys"]["J1_story_simple"]["phases"]
    assert phases["router"]["p50"] == 50          # 1 chamada CLASSIFY
    assert phases["narrator"]["p50"] == 100       # 1 chamada FAST
    block = summary["journeys"]["J1_story_simple"]
    # soma das fases == total (+-1 ms) em cada registro => tambem nos percentis agregados
    assert block["total"]["p50"] >= phases["router"]["p50"] + phases["narrator"]["p50"]
    assert summary["fingerprint"]["mode"] == "offline-virtual"
    assert summary["fingerprint"]["pseudo_streaming"] is True


def test_typical_profile_within_declared_jitter(tmp_path):
    summary = _summary(_run(tmp_path, "typ", journeys="J1", reps=3))
    narrator = summary["journeys"]["J1_story_simple"]["phases"]["narrator"]["p50"]
    assert 2000 <= narrator <= 3000               # FAST 2500 ms +-20%
    router = summary["journeys"]["J1_story_simple"]["phases"]["router"]["p50"]
    assert 240 <= router <= 360                   # CLASSIFY 300 ms +-20%


def test_records_sum_phases_to_total(tmp_path):
    run_dir = _run(tmp_path, "sum", journeys="J1", reps=2)
    rows = [json.loads(line) for line in
            (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows
    for row in rows:
        assert abs(sum(row["phase_ms"].values()) - row["total_ms"]) <= 1
        assert row["ack_server_ms"] <= row["ttfmc_server_ms"] <= row["ttlt_server_ms"]
        assert row["input_size"] in {"short", "medium", "long"}
        assert row["mode"] == "offline-virtual" and row["transport"] == "stream"


def test_same_seed_same_summary(tmp_path):
    a = _run(tmp_path, "a")
    b = _run(tmp_path, "b")
    digest = lambda d: hashlib.sha256((d / "summary.json").read_bytes()).hexdigest()  # noqa: E731
    assert digest(a) == digest(b)
    c = _run(tmp_path, "c", seed=201)
    assert digest(a) != digest(c)                 # outra seed => outro jitter


def test_fallback_once_profile_counts_fallbacks(tmp_path):
    typical = _summary(_run(tmp_path, "t", journeys="J1", profile="typical"))
    fallback = _summary(_run(tmp_path, "f", journeys="J1", profile="fallback-once"))
    assert typical["overall"]["llm_fallbacks_total"] == 0
    assert fallback["overall"]["llm_fallbacks_total"] > 0
    assert fallback["overall"]["llm_attempts_mean"] > typical["overall"]["llm_attempts_mean"]


def test_install_is_reversible():
    import llm_setup
    before = latency_llm._ORIGINAL or llm_setup.get_llm
    ctx = latency_llm.LatencyContext(profile="flat-fast", mode="virtual", clock=lambda: 0.0)
    latency_llm.install(ctx)
    try:
        assert llm_setup.get_llm is not before
    finally:
        latency_llm.uninstall()
    assert llm_setup.get_llm is before


def test_profile_unknown_rejected():
    with pytest.raises(ValueError):
        latency_llm.LatencyContext(profile="nope")


def _fake_summary(**fp):
    base = {"git_sha": "aaa", "mode": "offline-virtual", "profile": "typical",
            "execution_mode": "sequential", "python": "3.13", "pseudo_streaming": True,
            "journeys": ["J1"], "journeys_version": 1, "schema_version": 1}
    base.update(fp)
    block = {"ttfmc": {"p50": 1, "p95": 2}, "ttlt": {"p50": 1, "p95": 2},
             "total": {"p50": 1, "p95": 2}}
    return {"fingerprint": base, "journeys": {"J1": block}, "overall": block}


def test_compare_refuses_env_mismatch():
    a, b = _fake_summary(), _fake_summary(profile="slow-tail")
    with pytest.raises(SystemExit) as exc:
        lb.compare_runs(a, b, allow_mismatch=False)
    assert "profile" in str(exc.value)
    text = lb.compare_runs(a, b, allow_mismatch=True)
    assert "RESSALVA" in text.splitlines()[2]
    # git_sha diferente NAO e incompatibilidade (e a variavel do A/B)
    assert "RESSALVA" not in lb.compare_runs(a, _fake_summary(git_sha="bbb"), allow_mismatch=False)


def test_real_mode_refuses_without_caps(monkeypatch):
    built = []
    monkeypatch.setattr(lb, "execute", lambda *a, **k: built.append(1))
    monkeypatch.delenv(lb.REAL_ENV, raising=False)
    with pytest.raises(SystemExit) as exc:
        lb.main(["run", "--real", "--journeys", "J1", "--reps", "1"])
    message = str(exc.value)
    assert lb.REAL_ENV in message and "--max-requests" in message and "--max-cost" in message
    monkeypatch.setenv(lb.REAL_ENV, "1")
    with pytest.raises(SystemExit):                      # autorizado, mas sem tetos
        lb.main(["run", "--real", "--journeys", "J1", "--reps", "1"])
    with pytest.raises(SystemExit):
        lb.main(["run", "--real", "--max-requests", "10", "--journeys", "J1"])
    assert built == []                                   # nada foi construido/executado


def test_report_renders_ttft_note_and_strata(tmp_path):
    run_dir = _run(tmp_path, "rep", journeys="J1", reps=2)
    text = lb.render_report(_summary(run_dir))
    assert "TTFT = TTFMC (pseudo_streaming)" in text
    assert "short" in text and "long" in text
    assert "p95 indicativo" in text
    assert "git_sha" in text
