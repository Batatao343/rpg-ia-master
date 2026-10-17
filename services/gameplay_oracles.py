"""SPEC-212 §3.2: nomes de contrato dos oraculos do gate de gameplay.

Os oraculos moram na regua (`evals/evaluators/gameplay_gate.py`, Etapa 0, protegida).
Este modulo e so o mapa nome-da-spec -> oraculo, para o orquestrador e para quem
precisar chamar um oraculo isolado sem copiar logica. Cada funcao devolve a lista de
classes de problema (vazia = ok). Nao reimplementar: a paridade e testada.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _gate():
    from evals.evaluators import gameplay_gate
    return gameplay_gate


def no_duplicate_turns(data: Mapping[str, Any]) -> list[str]:
    return _gate().turn_problems(data)


def no_unrevealed_secret(data: Mapping[str, Any]) -> list[str]:
    return _gate().secret_problems(data)


def xp_not_in_prose(data: Mapping[str, Any]) -> list[str]:
    return _gate().xp_problems(data)


def latency_present(data: Mapping[str, Any]) -> list[str]:
    return _gate().latency_problems(data)


def speaker_matches(data: Mapping[str, Any]) -> list[str]:
    return _gate().speaker_problems(data)


def roster_stable(data: Mapping[str, Any]) -> list[str]:
    return _gate().roster_problems(data)


def scan_trace(trace: Mapping[str, Any]) -> dict[str, Any]:
    """Veredito completo de um trace J-V1 (todos os oraculos + baseline de latencia)."""
    return _gate().scan_trace(trace)
