"""SPEC-382: golden de nos (storyteller, combate, stream, campanhas) para a refatoracao pura.

O fixture (`tests/fixtures/spec382_node_golden.json`) foi gravado na Etapa 1, ANTES de qualquer
extracao (`SPEC382_REGEN=1`, serial, so vale nessa etapa). `SPEC382_DUMP=<pasta>` grava o texto
normalizado de cada parte para diff de depuracao.

Antes da Etapa 3 (Sol P2-1) o golden ganhou os casos diretos de `run_round`
(`spec382_round_cases.py`) e o modo `strict` (partes `calls` e `order`, sensiveis a ordem de
fases e de chaves) nos casos de rodada e de combate; as cinco partes antigas nao mudaram.
Mutacoes de controle: `docs/spec382/golden-etapa3.md`.
"""

from __future__ import annotations

import os

import pytest

from tests import spec382_node_cases as cases
from tests import spec382_round_cases as round_cases
from tests.spec382_node_golden import Recorder, load_golden, save_golden

ALL_CASES = {
    **cases.STORY_CASES,
    **cases.COMBAT_CASES,
    **cases.STREAM_CASES,
    **cases.CAMPAIGN_CASES,
    **round_cases.ROUND_CASES,
}
STRICT = {*cases.COMBAT_CASES, *round_cases.ROUND_CASES}


def _check(name: str, digest: dict) -> None:
    if os.getenv("SPEC382_REGEN") == "1":
        data = load_golden()
        data[name] = digest
        save_golden(data)
        pytest.skip("golden regravado")
    golden = load_golden()
    assert name in golden, f"caso sem golden: {name}"
    assert digest == golden[name], f"divergiu: {name} (use SPEC382_DUMP=<pasta> para diff)"


def _run(name: str, monkeypatch, tmp_path) -> None:
    rec = Recorder(monkeypatch, tmp_path, strict=name in STRICT)
    try:
        ALL_CASES[name](rec)
        digest = rec.digest(name)
    finally:
        rec.close()
    _check(name, digest)


@pytest.mark.parametrize("name", sorted(cases.STORY_CASES))
def test_storyteller_cases(name, monkeypatch, tmp_path):
    _run(name, monkeypatch, tmp_path)


@pytest.mark.parametrize("name", sorted(cases.COMBAT_CASES))
def test_combat_cases(name, monkeypatch, tmp_path):
    _run(name, monkeypatch, tmp_path)


@pytest.mark.parametrize("name", sorted(cases.STREAM_CASES))
def test_stream_cases(name, monkeypatch, tmp_path):
    _run(name, monkeypatch, tmp_path)


@pytest.mark.parametrize("name", sorted(cases.CAMPAIGN_CASES))
def test_campaign_fingerprints(name, monkeypatch, tmp_path):
    _run(name, monkeypatch, tmp_path)


@pytest.mark.parametrize("name", sorted(round_cases.ROUND_CASES))
def test_round_cases(name, monkeypatch, tmp_path):
    _run(name, monkeypatch, tmp_path)
