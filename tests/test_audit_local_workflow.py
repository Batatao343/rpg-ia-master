"""SPEC-416 R9/R10: o pgTAP roda no audit-local antes do gate, sem esconder o resultado dele."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "audit-local.yml"


def _steps() -> list[dict]:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return data["jobs"]["infra-browser"]["steps"]


def _index(steps: list[dict], needle: str) -> int:
    return next(i for i, s in enumerate(steps) if needle in str(s.get("run", "")))


def test_audit_local_runs_pgtap() -> None:
    steps = _steps()
    start = _index(steps, "dev_stack.py start")
    pgtap = _index(steps, "dev_stack.py test-db")
    gate = _index(steps, "audit_local_gate.py")
    assert start < pgtap < gate
    assert steps[start]["id"] == "stack"
    cond = steps[gate]["if"]
    assert "!cancelled()" in cond
    assert "steps.stack.outcome == 'success'" in cond
    assert "continue-on-error" not in steps[pgtap], "o passo nasce bloqueante (D-416-2)"
