"""SPEC-417 R11: perfil Hypothesis determinístico dos testes de propriedade.

Mesmos ajustes de `tests/fakes/api_fuzz.py::fuzz_settings` (SPEC-338 R16), sem o teto por
variável de ambiente. `deadline=None`: com `-n 4`/`-n 6` e o OneDrive, prazo por exemplo é flake;
o teto real é o tempo por arquivo (SPEC-417 R14). Sem perfil global em `conftest.py`.
"""

from __future__ import annotations

from hypothesis import HealthCheck, settings


def deterministic_settings(*, max_examples: int) -> settings:
    return settings(
        max_examples=max_examples,
        derandomize=True,
        database=None,
        deadline=None,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.too_slow,
            HealthCheck.filter_too_much,
        ],
    )
