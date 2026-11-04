"""SPEC-369 R11 - testes de META, escritos pela Fase A ANTES do produto (autor de eval).

Leem os artefatos da Fase B (`docs/spec369/final-0-19.json`, `passos-0-19.json`) e da Fase C
(`docs/spec369/confirmacao.json`), todos no formato de `docs/spec369/metricas_369.py` (uma chave
por subcomando), e reprovam enquanto as metas do R13-R20/R22 nao forem cumpridas.

Artefato ausente -> ``pytest.xfail`` (vermelho esperado, sem quebrar a suite default).
Para ver a falha real: ``bash scripts/dev/pt.sh tests/test_spec369_metas.py --runxfail``.
Os limiares (``LIMIARES``) so mudam por decisao do dono, em commit separado de autor de eval.
A Fase B NAO edita este arquivo (R1).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

D = Path(__file__).resolve().parents[1] / "docs" / "spec369"

# D-369-3 (defaults aprovados sob "manda bala"; o gate R9c do dono pode trocar, so por autor de eval)
LIMIARES = {
    "cartas_rodada_total_min": 2.00,  # R13
    "cartas_rodada_postura_min": 1.90,  # R13
    "uso_alto": 0.60,  # R14(a)
    "p95_total_max": 10.0,  # R15
    "p95_postura_max": 12.0,  # R15
    "timeout_postura_max_pct": 1.0,  # R15
    "pressagio_razao_faixa_cego_max": 0.95,  # R16 primaria (D-369-2)
    "faixa_vitoria_pct": (45.0, 85.0),  # R16, R19(c), R20
    "emboscada_corruptor_min": 0.45,  # R17
    "sangromante_max_pp": 2.0,  # R19(b), D-369-8
    "queda_postura_max_pp": 5.0,  # R19(d)
    "familia_delta_max_pp": 10.0,  # R20, D-369-7
    "max_cartas_heroi": 8,  # R18
    "max_passos_por_carta": 2,  # R18
    "max_cartas_inimigo_por_familia": 2,  # R18(d)
}
FORA_DA_META_R14 = {"sangromante"}  # R4(a): Sangromante e excecao aceita


def _load(name: str) -> dict | list:
    path = D / name
    if not path.exists():
        pytest.xfail(f"{name} ausente: artefato da Fase B/C ainda nao existe (R11)")
    return json.loads(path.read_text(encoding="utf-8"))


def _base() -> dict:
    return json.loads((D / "base-0-19.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# checagens (devolvem a lista de violacoes; vazia = meta cumprida)
# --------------------------------------------------------------------------
def r13(data: dict) -> list[str]:
    r9 = data["base"]["r9"]
    bad = []
    if r9["total"]["cartas_por_rodada_media"] < LIMIARES["cartas_rodada_total_min"]:
        bad.append(f"total {r9['total']['cartas_por_rodada_media']}")
    for cls, v in r9["por_postura"].items():
        if v["cartas_por_rodada_media"] < LIMIARES["cartas_rodada_postura_min"]:
            bad.append(f"{cls} {v['cartas_por_rodada_media']}")
    return bad


def r14(data: dict) -> list[str]:
    bad = []
    for cid, r in data["uso"]["cartas"].items():
        if r["categoria"] in FORA_DA_META_R14:
            continue
        if r["categoria"] == "onda" and r["uso"] > LIMIARES["uso_alto"]:
            bad.append(f"(a) {cid} uso {r['uso']}")
        if "dominante" in r["bandeiras_v2"]:
            bad.append(f"(b) {cid} delta {r['delta_pp_v2']}")
    return bad


def r15(data: dict) -> list[str]:
    r9 = data["base"]["r9"]
    bad = []
    if r9["total"]["p95_rodadas_conflito"] > LIMIARES["p95_total_max"]:
        bad.append(f"p95 total {r9['total']['p95_rodadas_conflito']}")
    for cls, v in r9["por_postura"].items():
        if v["p95_rodadas_conflito"] > LIMIARES["p95_postura_max"]:
            bad.append(f"{cls} p95 {v['p95_rodadas_conflito']}")
        if v["timeout_pct"] > LIMIARES["timeout_postura_max_pct"]:
            bad.append(f"{cls} timeout {v['timeout_pct']}")
    return bad


def r16(data: dict) -> list[str]:
    bloco = data["pressagio"]["conhecida"]["decks_on"]
    lo, hi = LIMIARES["faixa_vitoria_pct"]
    bad = []
    if bloco["razao_faixa_cego"] > LIMIARES["pressagio_razao_faixa_cego_max"]:
        bad.append(f"on-faixa/on-cego {bloco['razao_faixa_cego']}")
    if not lo <= bloco["on-faixa"]["vitoria_pct"] <= hi:
        bad.append(f"vitoria on-faixa {bloco['on-faixa']['vitoria_pct']}")
    return bad


def r17(data: dict) -> list[str]:
    """Piso do Corruptor na emboscada realista com o credito D-369-6 (`realista_369`).
    "Nenhuma outra Postura muda" vale no commit do B2 (antes do B3 mexer em basicas) e e
    conferido no registro B2 de `passos-0-19.json` pela revisao, nao no artefato final."""
    total = data["emboscada"]["posturas"]["Corruptor"]["todas"]["realista_369"]["total"]
    return [] if total >= LIMIARES["emboscada_corruptor_min"] else [f"Corruptor {total}"]


def r19(data: dict, base: dict | None) -> list[str]:
    g = data["posturas"]["guarda_r19"]
    bad = [f"(a) {x}" for x in g["postura_fora_45_85"] + g["padrao_acima_75"]]
    if not g["arcanista_todas_ge_45"]:
        bad.append("(a) Arcanista todas < 45 %")
    lo, hi = LIMIARES["faixa_vitoria_pct"]
    vit = data["base"]["r9"]["total"]["vitoria_pct"]
    if not lo <= vit <= hi:
        bad.append(f"(c) vitoria base {vit}")
    if base is not None:
        ref = base["posturas"]["guarda_r19"]["totais"]
        for cls, total in g["totais"].items():
            if cls == "Sangromante" and (total - ref[cls]) * 100 > LIMIARES["sangromante_max_pp"]:
                bad.append(f"(b) Sangromante {ref[cls]} -> {total}")
            if (ref[cls] - total) * 100 > LIMIARES["queda_postura_max_pp"]:
                bad.append(f"(d) {cls} {ref[cls]} -> {total}")
    return bad


def r20(data: dict, alvo: list[str]) -> list[str]:
    lo, hi = LIMIARES["faixa_vitoria_pct"]
    bad = []
    for key in alvo:
        cell = data["familias"]["cells"][key]
        on = cell["on"]["win"] * 100
        if not lo <= on <= hi or abs(cell["delta_pp"]) > LIMIARES["familia_delta_max_pp"]:
            bad.append(f"{key} on {on:.1f} delta {cell['delta_pp']}")
    return bad


# --------------------------------------------------------------------------
# Fase B (sementes 0-19 / familias 0-7)
# --------------------------------------------------------------------------
def test_r13_cartas_por_rodada():
    assert r13(_load("final-0-19.json")) == []


def test_r14_dominancia():
    assert r14(_load("final-0-19.json")) == []


def test_r15_duracao():
    assert r15(_load("final-0-19.json")) == []


def test_r16_pressagio_valor_da_informacao():
    assert r16(_load("final-0-19.json")) == []


def test_r17_emboscada_corruptor():
    assert r17(_load("final-0-19.json")) == []


def test_r19_guardas_globais():
    assert r19(_load("final-0-19.json"), _base()) == []


def test_r20_familias():
    assert r20(_load("final-0-19.json"), _base()["familias"]["celulas_alvo"]) == []


def test_r18_limites_de_passos():
    """``passos-0-19.json``: lista (ou ``{"passos": [...]}``) de ``{bloco, carta|constante, ...}``;
    passos de inimigo (B6) trazem ``familia``. Passo revertido tambem conta (R18)."""
    raw = _load("passos-0-19.json")
    passos = raw["passos"] if isinstance(raw, dict) else raw
    heroi: dict[str, int] = {}
    inimigo: dict[str, set[str]] = {}
    for p in passos:
        if not p.get("carta"):
            continue
        if p.get("bloco") == "B6":
            inimigo.setdefault(p["familia"], set()).add(p["carta"])
        else:
            heroi[p["carta"]] = heroi.get(p["carta"], 0) + 1
    assert len(heroi) <= LIMIARES["max_cartas_heroi"], sorted(heroi)
    assert all(n <= LIMIARES["max_passos_por_carta"] for n in heroi.values()), heroi
    assert all(len(v) <= LIMIARES["max_cartas_inimigo_por_familia"] for v in inimigo.values())


# --------------------------------------------------------------------------
# Fase C (R22: uma vez, sementes 260-339 / familias 260-267, sem reajuste)
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "check",
    ["r13", "r14", "r15", "r16", "r17", "r19", "r20"],
)
def test_r22_confirmacao(check):
    data = _load("confirmacao.json")
    assert data["base"]["meta"]["seeds"] == [260, 339]
    assert data["familias"]["meta"]["seeds"] == [260, 267]
    fns = {
        "r13": lambda: r13(data),
        "r14": lambda: r14(data),
        "r15": lambda: r15(data),
        "r16": lambda: r16(data),
        "r17": lambda: r17(data),
        "r19": lambda: r19(data, None),  # (a) e (c)
        "r20": lambda: r20(data, _base()["familias"]["celulas_alvo"]),
    }
    assert fns[check]() == []
