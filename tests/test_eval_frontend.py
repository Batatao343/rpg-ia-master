from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from scripts.frontend_eval_report import (
    JOURNEY_IDS, MOBILE_IDS, MOBILE_VIEWPORTS, VERTICAL_IDS, VERTICAL_VIEWPORTS,
    summarize, summarize_mobile, summarize_vertical,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_frontend_manifest_and_playwright_suite_cover_every_registered_journey():
    manifest = yaml.safe_load((WEB / "e2e/critical-journeys.yaml").read_text(encoding="utf-8"))
    expected = list(JOURNEY_IDS)
    rows = manifest["journeys"]
    assert manifest["schema_version"] == 2
    assert [row["id"] for row in rows if row.get("suite", "frontend") == "frontend"] == expected
    assert all(row["hard"] for row in rows)
    source = (WEB / "e2e/critical-journeys.spec.ts").read_text(encoding="utf-8")
    assert re.findall(r'test\("(F\d{2}) ', source) == expected


def test_vertical_manifest_and_spec_cover_v01_to_v09_on_both_desktop_viewports():
    manifest = yaml.safe_load((WEB / "e2e/critical-journeys.yaml").read_text(encoding="utf-8"))
    vertical = [row for row in manifest["journeys"] if row.get("suite") == "vertical"]
    assert [row["id"] for row in vertical] == list(VERTICAL_IDS)
    assert all(row["hard"] and row["viewports"] == ["1440x900", "1280x800"] for row in vertical)
    source = (WEB / "e2e/vertical-journey.spec.ts").read_text(encoding="utf-8")
    titles = re.findall(r'test\("(V\d{2}) (\w+)"', source)
    assert [(i, n) for i, n in titles] == [(row["id"], row["name"]) for row in vertical]
    assert "waitForTimeout(" not in (WEB / "e2e/vertical-support.ts").read_text(encoding="utf-8")
    # A régua é o oráculo Python: a jornada só observa e entrega o trace.
    assert "evals.gameplay_scan" in (WEB / "e2e/vertical-support.ts").read_text(encoding="utf-8")


def test_mobile_manifest_and_spec_cover_m01_to_m07_on_both_mobile_viewports():
    manifest = yaml.safe_load((WEB / "e2e/critical-journeys.yaml").read_text(encoding="utf-8"))
    mobile = [row for row in manifest["journeys"] if row.get("suite") == "mobile"]
    assert [row["id"] for row in mobile] == list(MOBILE_IDS)
    assert all(row["hard"] and row["viewports"] == ["320x568", "390x844"] for row in mobile)
    source = (WEB / "e2e/mobile-single-pane.spec.ts").read_text(encoding="utf-8")
    titles = re.findall(r'test\("(M\d{2}) (\w+)"', source)
    assert titles == [(row["id"], row["name"]) for row in mobile]
    # SPEC-216 R7: toque, nunca hover/drag; sem sleep fixo.
    assert not re.search(r"\.hover\(|dragTo\(|waitForTimeout\(", source)
    config = (WEB / "playwright.config.ts").read_text(encoding="utf-8")
    assert '"mobile-320"' in config and '"mobile-390"' in config and "mobile-single-pane" in config
    # F/V não podem enxergar as jornadas M (e vice-versa): conjuntos disjuntos.
    assert not set(MOBILE_IDS) & (set(JOURNEY_IDS) | set(VERTICAL_IDS))


def _mobile_specs(failed: tuple[str, str] | None = None, drop: str | None = None) -> dict:
    specs = []
    for step in MOBILE_IDS:
        tests = []
        for project in MOBILE_VIEWPORTS:
            if project == drop:
                continue
            status = "failed" if failed == (project, step) else "passed"
            tests.append({"projectName": project, "results": [{"status": status}]})
        specs.append({"title": f"{step} fixture", "tests": tests})
    return {"suites": [{"specs": specs}]}


def test_mobile_report_requires_every_journey_on_both_viewports():
    ok = summarize_mobile(_mobile_specs())
    assert ok["hard_gates_passed"] is True
    assert ok["journeys"]["registered"] == 14
    assert ok["metrics"]["mobile_journey_pass_rate"] == 1.0
    assert summarize_mobile(_mobile_specs(failed=("mobile-320", "M05")))["hard_gates_passed"] is False
    assert summarize_mobile(_mobile_specs(drop="mobile-390"))["hard_gates_passed"] is False
    assert summarize(_mobile_specs())["journeys"]["executed"] == 0
    assert summarize_vertical(_mobile_specs())["journeys"]["passed"] == 0


def _vertical_specs(failed: tuple[str, str] | None = None, drop: str | None = None) -> dict:
    specs = []
    for step in VERTICAL_IDS:
        tests = []
        for project in VERTICAL_VIEWPORTS:
            if project == drop:
                continue
            status = "failed" if failed == (project, step) else "passed"
            tests.append({"projectName": project, "results": [{"status": status}]})
        specs.append({"title": f"{step} fixture", "tests": tests})
    return {"suites": [{"specs": specs}]}


def test_vertical_report_requires_every_step_on_both_viewports():
    ok = summarize_vertical(_vertical_specs())
    assert ok["hard_gates_passed"] is True
    assert ok["journeys"]["registered"] == 18
    assert ok["metrics"]["vertical_journey_pass_rate"] == 1.0
    assert summarize_vertical(_vertical_specs(failed=("desktop-1280", "V09")))["hard_gates_passed"] is False
    assert summarize_vertical(_vertical_specs(drop="desktop-1280"))["hard_gates_passed"] is False
    # Os passos V não entram no relatório F (e vice-versa).
    assert summarize(_vertical_specs())["journeys"]["executed"] == 0


def test_frontend_suite_has_every_hard_gate_and_no_fixed_sleep():
    source = (WEB / "e2e/fixtures.ts").read_text(encoding="utf-8")
    journeys = (WEB / "e2e/critical-journeys.spec.ts").read_text(encoding="utf-8")
    for contract in ("pageerror", 'message.type() === "error"', "response.status() >= 500", "requestfailed"):
        assert contract in source
    assert "AxeBuilder" in journeys
    assert "scrollWidth <= document.documentElement.clientWidth" in journeys
    assert "waitForTimeout(" not in source + journeys
    for viewport in ("320, height: 568", "390, height: 844", "768, height: 1024", "1440, height: 900"):
        assert viewport in journeys


def test_frontend_toolchain_and_visual_snapshot_are_pinned():
    package = json.loads((WEB / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["test:e2e"] == "playwright test"
    assert package["devDependencies"]["@playwright/test"] == "^1.64.1"
    assert package["devDependencies"]["@axe-core/playwright"] == "^4.10.2"
    visual = (WEB / "e2e/visual-surfaces.spec.ts").read_text(encoding="utf-8")
    assert 'process.platform !== "linux"' in visual
    assert "RPG_VISUAL_SNAPSHOTS" in visual


def test_frontend_metrics_are_blocking_and_have_hard_limits():
    registry = yaml.safe_load((ROOT / "evals/metrics-registry.yaml").read_text(encoding="utf-8"))["metrics"]
    names = {
        "vertical_journey_pass_rate",
        "mobile_journey_pass_rate",
        "frontend_critical_journey_pass_rate",
        "frontend_uncaught_page_errors",
        "frontend_unexpected_console_errors",
        "frontend_unexpected_failed_requests",
        "frontend_unexpected_5xx_responses",
        "frontend_horizontal_overflow_cases",
        "frontend_a11y_serious_critical",
    }
    assert names <= registry.keys()
    assert all(registry[name]["blocking"] and "hard_limit" in registry[name] for name in names)


def test_frontend_report_requires_every_registered_journey():
    specs = []
    for journey_id in JOURNEY_IDS:
        specs.append({"title": f"{journey_id} fixture", "tests": [{"results": [{"status": "passed"}]}]})
    summary = summarize({"suites": [{"specs": specs}]})
    assert summary["hard_gates_passed"] is True
    assert summary["metrics"]["frontend_critical_journey_pass_rate"] == 1.0
    assert summary["journeys"]["registered"] == len(JOURNEY_IDS) == 36
    missing = summarize({"suites": [{"specs": specs[:30]}]})
    assert missing["hard_gates_passed"] is False
    specs[-1]["tests"][0]["results"][0] = {
        "status": "failed", "error": {"message": "A11Y serious/critical: color-contrast"}
    }
    failed = summarize({"suites": [{"specs": specs}]})
    assert failed["hard_gates_passed"] is False
    assert failed["metrics"]["frontend_a11y_serious_critical"] == 1
