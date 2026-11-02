"""SPEC-350 P2-7 — o oráculo LEAK_PHRASES da SPEC-348 não pode ser afrouxado como dado.

As frases abaixo são a lista original da 348 (dobradas). `data/world/leak_phrases.json` pode
ganhar frases, nunca perder estas. Mudar este arquivo exige revisão independente.
"""

from __future__ import annotations

from services.leak_phrases import leak_phrases

FROZEN_348 = {
    "vibora": [
        "magda e a vibora",
        "a vibora (velha magda)",
        "(a vibora)",
        "lider da mao sombria",
        "magda/a vibora",
        "escritorio da mao sombria",
    ],
    "barril": [
        "testamento real",
        "testamento do antigo rei",
        "herdeiro ao trono",
        "herdeiro de ostmar",
    ],
    "corpos": [
        "vao para o doutor silas vane",
        "nao vao ao crematorio",
        "vende os marcados",
        "entrega os marcados",
    ],
    "praga": ["caixa de amostras", "criada em laboratorio", "cepa atual"],
}
MIN_FARO = 12


def test_frozen_348_phrases_are_still_present():
    cur = leak_phrases()
    for group, phrases in FROZEN_348.items():
        assert set(phrases) <= set(cur[group]), group
    assert len(cur["farol"]) >= MIN_FARO
    assert len(cur["arauto"]) >= 5 and len(cur["pacto"]) >= 5  # derivados de SECRET_SIGNATURES
