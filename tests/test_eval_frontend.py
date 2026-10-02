from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from scripts.frontend_eval_report import summarize

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_frontend_manifest_and_playwright_suite_cover_f01_to_f16():
    manifest = yaml.safe_load((WEB / "e2e/critical-journeys.yaml").read_text(encoding="utf-8"))
    expected = [f"F{i:02d}" for i in range(1, 17)]
    assert [row["id"] for row in manifest["journeys"]] == expected
    assert all(row["hard"] for row in manifest["journeys"])
    source = (WEB / "e2e/critical-journeys.spec.ts").read_text(encoding="utf-8")
    assert re.findall(r'test\("(F\d{2}) ', source) == expected


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
    assert package["devDependencies"]["@playwright/test"] == "^1.55.1"
    assert package["devDependencies"]["@axe-core/playwright"] == "^4.10.2"
    visual = (WEB / "e2e/visual-surfaces.spec.ts").read_text(encoding="utf-8")
    assert 'process.platform !== "linux"' in visual
    assert "RPG_VISUAL_SNAPSHOTS" in visual


def test_frontend_metrics_are_blocking_and_have_hard_limits():
    registry = yaml.safe_load((ROOT / "evals/metrics-registry.yaml").read_text(encoding="utf-8"))["metrics"]
    names = {
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


def test_frontend_report_requires_all_sixteen_journeys():
    specs = []
    for number in range(1, 17):
        specs.append({"title": f"F{number:02d} fixture", "tests": [{"results": [{"status": "passed"}]}]})
    summary = summarize({"suites": [{"specs": specs}]})
    assert summary["hard_gates_passed"] is True
    assert summary["metrics"]["frontend_critical_journey_pass_rate"] == 1.0
    specs[-1]["tests"][0]["results"][0] = {
        "status": "failed", "error": {"message": "A11Y serious/critical: color-contrast"}
    }
    failed = summarize({"suites": [{"specs": specs}]})
    assert failed["hard_gates_passed"] is False
    assert failed["metrics"]["frontend_a11y_serious_critical"] == 1
