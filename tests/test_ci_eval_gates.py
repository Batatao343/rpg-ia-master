from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import yaml

from scripts.ci_eval_scope import classify
from scripts.post_deploy_smoke import run as run_post_deploy
from scripts.run_llm_contract_gate import ContractBudget, ContractBudgetExceeded
from scripts.validate_holdout_aggregate import validate as validate_holdout
from scripts.verify_protected_eval_change import verify

ROOT = Path(__file__).resolve().parents[1]


def test_change_scope_selects_backend_frontend_and_protected_jobs():
    protected = ROOT / "evals/protected-paths.txt"
    backend = classify(["agents/router.py"], protected)
    frontend = classify([r"web\src\App.tsx"], protected)
    ruler = classify(["evals/evaluators/exact.py"], protected)
    docs = classify(["README.md"], protected)

    assert backend["backend"] is True and backend["frontend"] is False
    assert frontend["frontend"] is True
    assert ruler["backend"] is True and ruler["protected"] is True
    assert docs["backend"] is False and docs["frontend"] is False
    assert all(row["long_run"] is False for row in (backend, frontend, ruler, docs))


def test_protected_change_requires_explicit_guarded_approval():
    manifest = {"protected": True, "protected_files": ["evals/evaluators/exact.py"]}
    with pytest.raises(PermissionError, match="eval-governance"):
        verify(manifest, "")
    verify(manifest, "true")
    verify({"protected": False, "protected_files": []}, "")


def test_private_holdout_contract_accepts_only_redacted_aggregates():
    good = {
        "schema_version": 1,
        "product_sha": "abcdef1",
        "evaluator_version": "1.6.0",
        "dataset_hash": "sha256:" + "a" * 64,
        "case_count": 10,
        "metrics": {"route_accuracy": 0.9},
    }
    validate_holdout(good)
    with pytest.raises(ValueError, match="case-level"):
        validate_holdout({**good, "cases": [{"input": "secret"}]})
    with pytest.raises(ValueError, match="numeric"):
        validate_holdout({**good, "metrics": {"route_accuracy": "pass"}})


def test_post_deploy_smoke_is_read_only_and_checks_sha():
    requested: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append((request.method, request.url.path))
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "online", "git_sha": "abcdef123456"})
        return httpx.Response(200, json={})

    result = run_post_deploy(
        "https://rpg.example.test",
        "abcdef1",
        transport=httpx.MockTransport(handler),
    )
    assert result["mode"] == "read-only"
    assert requested == [
        ("GET", "/health"),
        ("GET", "/auth/config"),
        ("GET", "/data/options"),
        ("GET", "/data/map"),
    ]
    with pytest.raises(RuntimeError, match="SHA mismatch"):
        run_post_deploy(
            "https://rpg.example.test", "fffffff", transport=httpx.MockTransport(handler)
        )


def test_ci_workflows_are_fail_closed_selective_and_have_artifacts():
    gates = (ROOT / ".github/workflows/eval-gates.yml").read_text(encoding="utf-8")
    protected = (ROOT / ".github/workflows/eval-protected.yml").read_text(encoding="utf-8")
    deploy = (ROOT / ".github/workflows/post-deploy-smoke.yml").read_text(encoding="utf-8")
    for source in (gates, protected, deploy):
        yaml.load(source, Loader=yaml.BaseLoader)
        assert "continue-on-error" not in source
        assert "if-no-files-found: ignore" not in source
    assert "needs.scope.outputs.backend == 'true'" in gates
    assert "needs.scope.outputs.frontend == 'true'" in gates
    assert "environment: eval-governance" in gates
    assert "verify_protected_eval_change.py" in gates
    assert "frontend_eval_report.py" in gates
    assert "--turns 100" not in gates and "--turns 200" not in gates and "--real" not in gates
    assert "workflow_dispatch:" in protected and "environment: eval-provider" in protected
    assert "run_llm_contract_gate.py" in protected
    assert "--max-requests 20 --max-cost-usd 0.20" in protected
    assert "readiness_artifacts/provider/manifest.json" in protected
    assert "environment: eval-holdout" in protected and "validate_holdout_aggregate.py" in protected
    assert "workflow_dispatch:" in deploy and "post_deploy_smoke.py" in deploy


def test_real_provider_budget_blocks_before_an_excess_request_or_cost():
    budget = ContractBudget(max_requests=2, max_cost_usd=1.0)
    budget.reserve("gemini")
    budget.reserve("gemini")
    with pytest.raises(ContractBudgetExceeded, match="request cap"):
        budget.reserve("gemini")

    one_request = ContractBudget(max_requests=5, max_cost_usd=0.000001)
    with pytest.raises(ContractBudgetExceeded, match="cost cap"):
        one_request.reserve("gemini")
    assert one_request.requests_started == 0


def test_frontend_artifact_carries_compatible_measurement_identity():
    from scripts.frontend_eval_report import measurement_identity

    identity = measurement_identity(ROOT)
    assert identity["product_sha"]
    assert identity["evaluator_version"] == "1.6.0"
    assert identity["metrics_registry_hash"].startswith("sha256:")
    assert identity["journey_manifest_hash"].startswith("sha256:")
    assert identity["browser"] == "chromium"


def test_health_exposes_deploy_identity(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GIT_SHA", "abcdef123")
    from api import health_check

    assert health_check()["git_sha"] == "abcdef123"
