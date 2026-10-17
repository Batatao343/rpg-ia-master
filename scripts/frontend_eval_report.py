"""Normalize a Playwright JSON report into the frontend eval hard metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

# F30-F34 are reserved for the SPEC-210 map journeys (authored on a parallel branch).
JOURNEY_IDS = tuple(f"F{i:02d}" for i in (*range(1, 31), *range(35, 41)))
JOURNEY_COUNT = len(JOURNEY_IDS)
JOURNEY_RE = re.compile(r"^(F(?:0[1-9]|[1-9][0-9]))\s+")
# SPEC-212: jornada vertical J-V1 (stack real + MockLLM), um resultado por viewport desktop.
VERTICAL_IDS = tuple(f"V{i:02d}" for i in range(1, 10))
VERTICAL_RE = re.compile(r"^(V(?:0[1-9]))\s+")
VERTICAL_VIEWPORTS = ("desktop-1440", "desktop-1280")


def _specs(suites: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for suite in suites:
        yield from suite.get("specs", [])
        yield from _specs(suite.get("suites", []))


def _messages(report: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    for error in report.get("errors", []):
        messages.append(str(error.get("message") or error.get("stack") or error))
    for spec in _specs(report.get("suites", [])):
        for test in spec.get("tests", []):
            for result in test.get("results", []):
                error = result.get("error") or {}
                messages.append(str(error.get("message") or error.get("stack") or ""))
    return [message for message in messages if message]


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    journeys: dict[str, bool] = {}
    for spec in _specs(report.get("suites", [])):
        match = JOURNEY_RE.match(str(spec.get("title", "")))
        if not match:
            continue
        tests = spec.get("tests", [])
        results = [test.get("results", [])[-1] for test in tests if test.get("results")]
        journeys[match.group(1)] = bool(results) and all(result.get("status") == "passed" for result in results)

    messages = _messages(report)
    joined = "\n".join(messages)
    total = len(journeys)
    passed = sum(journeys.values())
    metrics = {
        "frontend_critical_journey_pass_rate": passed / total if total else 0.0,
        "frontend_uncaught_page_errors": joined.count("pageerror:"),
        "frontend_unexpected_console_errors": joined.count("console.error:"),
        "frontend_unexpected_failed_requests": joined.count("requestfailed:"),
        "frontend_unexpected_5xx_responses": len(re.findall(r"HTTP 5\d\d:", joined)),
        "frontend_horizontal_overflow_cases": 0 if journeys.get("F16") else 1,
        "frontend_a11y_serious_critical": joined.count("A11Y serious/critical:"),
    }
    complete = set(journeys) == set(JOURNEY_IDS)
    hard_pass = complete and metrics["frontend_critical_journey_pass_rate"] == 1.0 and all(
        value == 0 for key, value in metrics.items() if key != "frontend_critical_journey_pass_rate"
    )
    return {
        "schema_version": 1,
        "source": "playwright-json",
        "journeys": {"registered": JOURNEY_COUNT, "executed": total, "passed": passed, "results": journeys},
        "metrics": metrics,
        "hard_gates_passed": hard_pass,
    }


def summarize_vertical(report: dict[str, Any]) -> dict[str, Any]:
    """V01..V09 por projeto Playwright (viewport). Todo viewport exigido, todo passo `passed`."""

    by_project: dict[str, dict[str, bool]] = {}
    for spec in _specs(report.get("suites", [])):
        match = VERTICAL_RE.match(str(spec.get("title", "")))
        if not match:
            continue
        for test in spec.get("tests", []):
            results = test.get("results", [])
            passed = bool(results) and results[-1].get("status") == "passed"
            project = str(test.get("projectName") or "default")
            by_project.setdefault(project, {})[match.group(1)] = passed
    expected = {(project, step) for project in VERTICAL_VIEWPORTS for step in VERTICAL_IDS}
    seen = {(project, step) for project, steps in by_project.items() for step in steps}
    passed_n = sum(1 for project, steps in by_project.items() for ok in steps.values() if ok)
    rate = passed_n / len(expected)
    messages = "\n".join(_messages(report))
    complete = expected <= seen
    metrics = {
        "vertical_journey_pass_rate": rate,
        "frontend_uncaught_page_errors": messages.count("pageerror:"),
        "frontend_unexpected_console_errors": messages.count("console.error:"),
        "frontend_unexpected_failed_requests": messages.count("requestfailed:"),
        "frontend_unexpected_5xx_responses": len(re.findall(r"HTTP 5\d\d:", messages)),
    }
    hard_pass = complete and rate == 1.0 and all(
        value == 0 for key, value in metrics.items() if key != "vertical_journey_pass_rate")
    return {
        "schema_version": 1,
        "source": "playwright-json",
        "suite": "vertical",
        "journeys": {"registered": len(expected), "executed": len(seen & expected), "passed": passed_n,
                     "results": {p: by_project.get(p, {}) for p in VERTICAL_VIEWPORTS}},
        "metrics": metrics,
        "hard_gates_passed": hard_pass,
    }


def measurement_identity(root: Path) -> dict[str, str]:
    def digest(path: Path) -> str:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    git = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False
    )
    package = json.loads((root / "web/package.json").read_text(encoding="utf-8"))
    return {
        "product_sha": os.getenv("GITHUB_SHA") or git.stdout.strip(),
        "evaluator_version": "1.14.0",
        "metrics_registry_hash": digest(root / "evals/metrics-registry.yaml"),
        "journey_manifest_hash": digest(root / "web/e2e/critical-journeys.yaml"),
        "platform": platform.platform(),
        "browser": "chromium",
        "playwright": package["devDependencies"]["@playwright/test"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--suite", choices=("frontend", "vertical"), default="frontend")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    summary = summarize_vertical(report) if args.suite == "vertical" else summarize(report)
    summary["measurement_identity"] = measurement_identity(args.root.resolve())
    encoded = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 1 if args.check and not summary["hard_gates_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
