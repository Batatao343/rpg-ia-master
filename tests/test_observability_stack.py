from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from observability.metrics import LABELS


def test_metrics_endpoint_prometheus_sem_ids_ou_payloads():
    import api
    response = TestClient(api.app).get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "game_id" not in response.text and "owner_id" not in response.text


def test_dashboard_alertas_e_compose_sao_configs_reais():
    dashboard = json.loads(Path(
        "observability/dashboards/valoria-local.json"
    ).read_text(encoding="utf-8"))
    assert dashboard["schemaVersion"] >= 39
    assert all(panel.get("targets") for panel in dashboard["panels"])
    alerts = yaml.safe_load(Path(
        "observability/alerts/local.yml"
    ).read_text(encoding="utf-8"))
    assert alerts["groups"][0]["rules"]
    assert {rule["alert"] for rule in alerts["groups"][0]["rules"]} == {
        "TurnErrorRate", "TurnP95High", "OperationLeaseExpired", "JobBacklogOld",
        "RagFailure", "DbPoolWaiting", "BackupStale",
    }
    compose = yaml.safe_load(Path("infra/observability.compose.yml").read_text())
    assert set(compose["services"]) == {
        "prometheus", "grafana", "otel-collector", "tempo",
    }


def test_alertas_nao_referenciam_metricas_orfas():
    alerts = yaml.safe_load(Path("observability/alerts/local.yml").read_text(encoding="utf-8"))
    expressions = "\n".join(
        str(rule["expr"])
        for group in alerts["groups"]
        for rule in group["rules"]
    )
    referenced = set(__import__("re").findall(r"\b(rpg_[a-z0-9_]+)\b", expressions))
    base_names = {
        next((name for name in LABELS if metric in {
            name, f"{name}_count", f"{name}_sum", f"{name}_max", f"{name}_p95",
        }), metric)
        for metric in referenced
    }
    assert base_names <= set(LABELS)
    fixtures = yaml.safe_load(Path(
        "observability/alerts/local.test.yml"
    ).read_text(encoding="utf-8"))
    assert {case["name"] for case in fixtures["tests"]} == {
        "readiness-alerts-fire", "readiness-alerts-resolve",
    }
