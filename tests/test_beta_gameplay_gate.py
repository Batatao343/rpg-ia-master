"""SPEC-212 Etapa 2: orquestrador e formato de evidencia (offline, Deps injetavel)."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import beta_gameplay_gate as gate
from scripts.beta_gameplay_gate import Result

OK_SUMMARY = {"journeys": {"passed": 36, "executed": 36, "registered": 36}, "hard_gates_passed": True}
OK_VERTICAL = {"journeys": {"passed": 18, "registered": 18,
                            "results": {"desktop-1440": {f"V0{i}": True for i in range(1, 10)},
                                        "desktop-1280": {f"V0{i}": True for i in range(1, 10)}}},
               "hard_gates_passed": True}


def _results(**over):
    base = [Result("a", "pass"), Result("b", "pass")]
    return base + [Result(n, s) for n, s in over.items()]


def test_report_ok_requires_zero_dirty():
    clean = gate.build_report(_results(), sha="a" * 40, dirty=[], strict=True)
    assert clean["ok"] and clean["dirty_files"] == 0 and clean["failing"] == []
    dirty = gate.build_report(_results(), sha="a" * 40, dirty=["api.py"], strict=True)
    assert not dirty["ok"] and dirty["dirty_files"] == 1 and "clean_tree" in dirty["failing"]


def test_not_provisioned_blocks_in_strict():
    results = _results(c="not_provisioned")
    assert gate.build_report(results, sha="x", dirty=[], strict=True)["failing"] == ["c"]
    assert gate.build_report(results, sha="x", dirty=[], strict=False)["ok"]


def test_report_schema_matches_checklist_style():
    report = gate.build_report(_results(), sha="b" * 40, dirty=[], strict=False)
    assert {"schema", "gate", "sha", "dirty_files", "ok", "failing", "viewports", "results"} <= set(report)
    assert report["viewports"] == ["1440x900", "1280x800"]
    assert set(report["results"][0]) == {"name", "status", "blocking", "detail"}


def test_failing_lists_blocking_only():
    results = [Result("hard", "fail"), Result("soft", "fail", blocking=False), Result("ok", "pass")]
    assert gate.build_report(results, sha="x", dirty=[], strict=True)["failing"] == ["hard"]


KI_HEADER = "| ID | Descrição | Prioridade | Impacto | Classificação | Status |\n|---|---|---|---|---|---|\n"


def test_known_issues_blocker_fails():
    text = KI_HEADER + "| KI-1 | x | P1 | R5 | bloqueia beta | aberto |\n"
    assert gate.check_known_issues(text).status == "fail"
    text = KI_HEADER + "| KI-1 | x | P1 | R5 | aceitável no beta | aberto |\n"
    assert gate.check_known_issues(text).status == "fail"      # P0/P1 com impacto em R1-R9 reprova
    text = KI_HEADER + "| KI-1 | x | P2 | UX | aceitável no beta | aberto |\n| KI-2 | y | P1 | R5 | bloqueia beta | fechado |\n"
    result = gate.check_known_issues(text)
    assert result.status == "pass" and result.detail["blocking_open"] == 0


def test_known_issues_missing_or_empty():
    assert gate.check_known_issues(None).status == "not_provisioned"
    assert gate.check_known_issues("sem tabela").status == "fail"


def test_journeys_need_both_viewports():
    assert gate.check_journeys({"desktop-1440": OK_SUMMARY, "desktop-1280": None}).status == "not_provisioned"
    assert gate.check_journeys({"desktop-1440": OK_SUMMARY, "desktop-1280": OK_SUMMARY}).status == "pass"
    bad = {**OK_SUMMARY, "hard_gates_passed": False}
    assert gate.check_journeys({"desktop-1440": OK_SUMMARY, "desktop-1280": bad}).status == "fail"


def test_vertical_check():
    assert gate.check_vertical(None).status == "not_provisioned"
    assert gate.check_vertical(OK_VERTICAL).status == "pass"
    assert gate.check_vertical({**OK_VERTICAL, "hard_gates_passed": False}).status == "fail"


def test_oracles_use_ruler_scan_and_report_per_oracle():
    trace = {"turns": {"turns": [{"action_id": "a1"}]}, "secrets": {"surfaces": {"s": "x"}},
             "a11y": {"tabs": []}, "latency": {"turns": []}}

    def scan(t):
        return {"ok": False, "problems": {"turns": ["turns:duplicate"]}, "baseline": {}}

    results = {r.name: r for r in gate.check_oracles({"desktop-1440": trace, "desktop-1280": trace}, scan)}
    assert results["no_duplicate_turns"].status == "fail"
    assert results["console_clean"].status == "pass"
    missing = gate.check_oracles({"desktop-1440": trace, "desktop-1280": None}, scan)
    assert {r.status for r in missing} == {"not_provisioned"}


def test_main_reuse_without_reports_is_not_provisioned_and_exit_1(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, **kw):
        calls.append(args)
        return (0, "abc123\n") if args[:2] == ["git", "rev-parse"] else (0, "")

    deps = gate.Deps(run=fake_run, exists=lambda p: False)
    monkeypatch.setattr(gate, "RESULTS", tmp_path)
    monkeypatch.setattr(gate, "REPORTS", tmp_path)
    code = gate.main(["--strict", "--reuse", "--evidence-dir", str(tmp_path / "ev")], deps)
    assert code == 1
    written = json.loads(next((tmp_path / "ev").glob("gameplay-gate-*.json")).read_text(encoding="utf-8"))
    assert written["ok"] is False and written["sha"] == "abc123"
    assert all(r["status"] == "not_provisioned" for r in written["results"])
    assert not any(a[1:2] == ["playwright"] for a in calls)   # --reuse nunca executa o navegador


def test_markdown_has_latency_baseline():
    res = Result("latency_present", "pass", {"baseline": {"desktop-1440": {
        "turns": 14, "ttfmc_ms": {"p50": 10, "p95": 20}, "ttlt_ms": {"p50": 30, "p95": 40}}}})
    md = gate.to_markdown(gate.build_report([res], sha="c" * 40, dirty=[], strict=False))
    assert "TTFMC p50/p95 10/20" in md


# --- revisao Sol (independente) -----------------------------------------------------------------------


def test_known_issues_status_is_fail_closed():
    """So `fechado` fecha: status ambiguo ("em andamento", vazio) conta como aberto."""
    for status in ("em andamento", "parcial", "", "reaberto"):
        text = KI_HEADER + f"| KI-1 | x | P2 | UX | bloqueia beta | {status} |\n"
        assert gate.check_known_issues(text).status == "fail", status
    text = KI_HEADER + "| KI-1 | x | P1 | R5 | bloqueia beta | Fechado — corrigido |\n"
    assert gate.check_known_issues(text).status == "pass"


def test_previous_reports_are_cleared_before_a_fresh_run(tmp_path):
    """Relatorio/trace de execucao anterior nunca pode virar evidencia do SHA atual."""
    reports, results = tmp_path / "reports", tmp_path / "results"
    (results / "vertical").mkdir(parents=True)
    reports.mkdir()
    stale = [reports / "gate-f-desktop-1440.json", reports / "gate-f-desktop-1280.json",
             reports / "gate-vertical.json", results / "vertical" / "vertical-trace-1440x900.json",
             results / "vertical" / "vertical-trace-1280x800.json"]
    for path in stale:
        path.write_text("{}", encoding="utf-8")
    keep = reports / "gate-api.log"
    keep.write_text("log", encoding="utf-8")
    gate.clear_previous(reports, results)
    assert not any(p.exists() for p in stale)
    assert keep.exists()
    f, v, traces = gate.collect(gate.Deps(), reports, results)
    assert v is None and not any(f.values()) and not any(traces.values())


def test_strict_reuse_never_certifies(tmp_path, monkeypatch):
    deps = gate.Deps(run=lambda args, **kw: (0, "abc\n") if args[:2] == ["git", "rev-parse"] else (0, ""),
                     exists=lambda p: False)
    monkeypatch.setattr(gate, "RESULTS", tmp_path)
    monkeypatch.setattr(gate, "REPORTS", tmp_path)
    gate.main(["--strict", "--reuse", "--evidence-dir", str(tmp_path / "ev")], deps)
    written = json.loads(next((tmp_path / "ev").glob("gameplay-gate-*.json")).read_text(encoding="utf-8"))
    assert "fresh_run" in written["failing"]
