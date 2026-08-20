from __future__ import annotations

import json

from scripts.readiness_report import GATES, build_report, record_gate


def test_readiness_exige_g0_g7_e_produz_json_markdown(tmp_path):
    gates = tmp_path / "gates"
    output = tmp_path / "report"
    for gate in GATES:
        record_gate(
            gates, gate, status="passed", command=f"run {gate}",
            evidence=f"{gate} green",
        )
    report = build_report(gates, output)
    assert report["ready_local"] is True
    assert json.loads((output / "readiness-local.json").read_text())["pending"] == []
    assert "READY" in (output / "readiness-local.md").read_text()


def test_readiness_falha_com_gate_ausente_e_redige_evidencia(tmp_path):
    record_gate(
        tmp_path, "G0", status="passed", command="pytest",
        evidence="Bearer secret.jwt.token hero@example.com",
    )
    raw = (tmp_path / "g0.json").read_text()
    assert "secret.jwt" not in raw and "hero@example.com" not in raw
    report = build_report(tmp_path, tmp_path / "report")
    assert report["ready_local"] is False
    assert "G1" in report["pending"]
