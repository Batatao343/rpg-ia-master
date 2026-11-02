"""SPEC-368 R9/R10 - o script de metricas roda em 2 sementes e produz o schema esperado."""

from __future__ import annotations

import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    spec = importlib.util.spec_from_file_location(
        "metricas_epico_368", os.path.join(ROOT, "docs", "spec368", "metricas_epico.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R9_KEYS = {
    "conflitos",
    "rodadas",
    "cartas_por_rodada_media",
    "cartas_por_rodada_p50",
    "pct_rodadas_ge3_escolhas",
    "pct_rodadas_ge3_com_basico",
    "uso_cartas_da_mao_pct",
    "cartas_com_uso_acima_60",
    "p95_rodadas_conflito",
    "vitoria_pct",
    "timeout_pct",
}


def test_metricas_run_two_seeds_schema_and_determinism():
    mod = _load()
    kw = dict(r10=True, classes=["Sangromante"])
    a = mod.run([0, 1], [1], ["padrao"], 1, **kw)
    b = mod.run([0, 1], [1], ["padrao"], 1, **kw)
    assert a == b  # determinístico
    assert set(a) == {"r9", "r10"}
    assert set(a["r9"]["total"]) == R9_KEYS
    assert set(a["r9"]["por_postura"]["Sangromante"]) == R9_KEYS
    assert a["r9"]["total"]["conflitos"] == 2
    assert a["r10"]["total"]["off"]["conflitos"] == a["r10"]["total"]["on"]["conflitos"] == 2
    assert {"delta_dano", "delta_dano_pct", "dano_cai"} <= set(a["r10"]["total"])
    json.dumps(a)


def test_p95_is_nearest_rank():
    mod = _load()
    assert mod.p95([]) == 0.0
    assert mod.p95(list(range(1, 21))) == 19.0


def test_committed_json_has_the_agreed_shape():
    path = os.path.join(ROOT, "docs", "spec368", "metricas-0-19.json")
    data = json.load(open(path, encoding="utf-8"))
    assert data["meta"]["seeds"] == [0, 19]
    assert set(data["r9"]["total"]) == R9_KEYS
    assert data["r9"]["total"]["conflitos"] == 1800
    assert len(data["r9"]["por_postura"]) == 5
