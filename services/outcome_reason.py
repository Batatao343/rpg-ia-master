"""SPEC-398 R3: motivo aditivo do desfecho (`outcome` segue `defeat`, D-398-1).

Objetivo de cena falho com o herói de pé fecha como `defeat` (SPEC-331 R5); o campo
`outcome_reason: "objective_failed"` diz por quê. Save antigo sem o campo segue como hoje."""

from __future__ import annotations

OBJECTIVE_FAILED = "objective_failed"


def is_objective_failed(outcome: str | None, objective_result: str | None, player: dict) -> bool:
    return (
        outcome == "defeat"
        and objective_result == "falhou"
        and bool((player or {}).get("conscious", True))
    )


def mark(meta: dict, outcome: str | None, scene: dict | None, player: dict) -> None:
    """Grava (ou limpa) `outcome_reason` no combate, antes de `_finish_encounter`."""
    result = (scene or {}).get("objetivo_resultado")
    if is_objective_failed(outcome, result, player):
        meta["outcome_reason"] = OBJECTIVE_FAILED
    else:
        meta.pop("outcome_reason", None)
