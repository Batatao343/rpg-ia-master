"""Deterministic contract for SPEC-164's operational AGENTS router."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agents_routes_specs_evals_and_model_handoffs() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    required = (
        "specs/index.yaml",
        "project_index/domains.yaml",
        "source permanece a verdade",
        "specs/SPEC-NNN-<slug>.md",
        "registro correspondente em `specs/index.yaml`",
        "12_MODEL_EXECUTION_POLICY.md",
        "deterministic-first",
        "canonical owner",
        "MODEL_HANDOFF_REQUIRED",
        "handoffs/SPEC-xxx-<model>-review.md",
        "Luna",
        "Terra",
        "Sol",
        "Astra",
    )
    assert all(fragment in text for fragment in required)
    assert "specs/<nome>.md" not in text


def test_agents_keeps_long_runs_strictly_opt_in() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "Long-runs, campanhas de 100/200 turnos" in text
    assert "pedido explícito do usuário" in text
    assert "baseline, release e regressão não constituem permissão" in text
