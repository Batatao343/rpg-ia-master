"""SPEC-353 etapa 4: nucleo da dica com cabeca generica e contagem da entrada."""

from __future__ import annotations

import pytest

from services import encounter_manifest as em
from services import prose_guard


@pytest.mark.parametrize(
    ("hint", "core", "generic"),
    [
        ("a criatura além das estacas", "criatura", True),
        ("a criatura da fenda", "criatura", True),
        ("o vulto atrás do muro", "vulto", True),
        ("o bandido da estrada", "bandido da estrada", False),
        ("o bandido mais próximo", "bandido", False),
    ],
)
def test_hint_core_generic_head_with_locative(hint, core, generic):
    assert em.hint_core(hint) == core
    assert em.is_generic_hint(hint) is generic


def _manifest(n_active: int, label: str = "Bandido") -> dict:
    return {
        "participants": [
            {"participant_id": f"e{i}", "species_label": label, "status": "ativo"}
            for i in range(n_active)
        ]
    }


def test_count_drift_flags_larger_numeral():
    flags = prose_guard.count_drift("Três bandidos surgem da névoa.", _manifest(2))
    assert flags and flags[0]["claimed"] == 3 and flags[0]["active"] == 2


def test_count_drift_ok_when_equal_or_smaller():
    assert not prose_guard.count_drift("Dois bandidos surgem.", _manifest(2))
    assert not prose_guard.count_drift("Um bandido surge.", _manifest(2))


def test_count_drift_sentence_is_deterministic():
    flags = prose_guard.count_drift("três bandidos avançam", _manifest(2))
    sentence = prose_guard.reconcile_count_sentence(flags)
    assert sentence == "Só dois Bandidos avançam contra você; o resto some na sombra."
