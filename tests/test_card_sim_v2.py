"""SPEC-358: protocolo ``lote-v2`` do sim.py e prova de equivalência do v1."""

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gold():
    return _load_path(
        "gerar_golden_v1_358", os.path.join(ROOT, "docs", "spec358", "gerar_golden_v1.py")
    )


@pytest.fixture(scope="module")
def sim():
    return _load_path("cards_sim_358", os.path.join(ROOT, "scripts", "cards", "sim.py"))


def test_v1_reproduz_golden(gold, sim):
    with open(gold.GOLDEN, encoding="utf-8") as f:
        golden = json.load(f)
    atual = gold.compute(sim)
    assert atual["simulate_batch"] == golden["simulate_batch"]
    assert atual["simulate_protocolo_lote"] == golden["simulate_protocolo_lote"]
    assert atual["main"] == golden["main"]
