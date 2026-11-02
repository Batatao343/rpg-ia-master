"""SPEC-360 R28: eval deterministico da fauna viva (M1-M7), congelado na Etapa 1.

Protegido (D6, `evals/protected-paths.txt`): quem otimiza o produto nao edita este arquivo
nem `scripts/fauna/eval.py`. Limiares literais abaixo (D4).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_eval():
    spec = importlib.util.spec_from_file_location(
        "spec360_eval", ROOT / "scripts" / "fauna" / "eval.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def result():
    ev = _load_eval()
    return ev.run(20, 60)


def test_limiares_congelados():
    ev = _load_eval()
    assert ev.M1_MIN_PRECEDIDO == 0.70
    assert ev.M1_MIN_APROXIMACAO == 1.00
    assert ev.M2_MAX_RATIO_FORA == 0.35
    assert ev.M3_MIN_PRESA_SOBE == 1.5
    assert ev.M3_MAX_PREDADOR_CAI == 0.6
    assert ev.M4_MIN_TERRITORIO == 0.80
    assert (ev.M5_MIN_DELTA, ev.M5_MAX_DELTA) == (-0.20, 0.05)
    assert ev.M6_MAX_VAZAMENTOS == 0
    assert (ev.DEFAULT_SEEDS, ev.DEFAULT_DAYS) == (20, 60)


def test_m1_sinal_antes_e_aproximacao(result):
    m = result["metrics"]
    assert result["on"]["combats_with_entry"] > 0
    assert m["M1_precedido"] >= 0.70, m
    assert m["M1_aproximacao"] >= 1.00, m


def test_m2_horario(result):
    assert result["dist"]["m2"], "nenhuma criatura com horario restrito"
    assert result["metrics"]["M2_pior_razao"] <= 0.35, result["dist"]["m2"]


def test_m3_cadeia_alimentar(result):
    assert result["dist"]["m3_up"] and result["dist"]["m3_down"]
    assert result["metrics"]["M3_presa_sobe_min"] >= 1.5, result["dist"]["m3_up"]
    assert result["metrics"]["M3_predador_cai_max"] <= 0.6, result["dist"]["m3_down"]


def test_m4_territorio(result):
    assert result["metrics"]["M4_territorio"] >= 0.80, result["metrics"]


def test_m5_quantidade(result):
    assert result["off"]["fauna_combats"] > 0
    assert result["off"]["triggers"] == result["on"]["triggers"]  # R9: so QUEM, nunca QUANTOS
    assert -0.20 <= result["metrics"]["M5_delta"] <= 0.05, result["rates"]


def test_m6_vazamento(result):
    assert result["metrics"]["M6_vazamentos"] == 0, result["leak_samples"]
    assert result["on"]["texts"] > 0


def test_m7_determinismo():
    ev = _load_eval()
    a = ev.render(ev.run(3, 12))
    b = ev.render(ev.run(3, 12))
    assert a == b
