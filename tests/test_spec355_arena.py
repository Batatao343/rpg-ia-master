"""SPEC-355 R45: artefatos da arena (0-19 ajuste, 20-99 confirmacao) e faixas por Postura."""

from __future__ import annotations

import json
from pathlib import Path

from services import cards

D = Path(__file__).resolve().parents[1] / "docs" / "spec355"
# Excecao de piso do Arcanista: SPEC-362 (pacote de 3 Cartas) subiu 0-19 de 44,4 para 46,5 % e a confirmacao 20-99 deu 44,8 %; fica abaixo de 45 % (decisao do coordenador 02/11).
# Destino: follow-up (raio_cinza de volta ao pool, +2,3 pp medido) remove esta linha; leitura do artefato novo em tests/test_spec362_arcanista.py.
EXCECOES_PISO = {"Arcanista Cinzento"}
# Teto de 75 % por subclasse na leitura padrao. Excecoes = valor medido, registrado em §9 para o dono
# (341 aceitou avaro 75,2 / silencioso 76,6; o R11/R12 empurrou o silencioso a 78,7 nas 0-19).
EXCECOES_TETO = {
    "arena-final.json": {
        ("Sangromante", "todas"): 0.754,
        ("Sangromante", "silencioso"): 0.787,
    },
    "arena-confirmacao.json": {
        ("Sangromante", "todas"): 0.752,
        ("Sangromante", "avaro"): 0.776,
        ("Sangromante", "silencioso"): 0.768,
    },
}


def _load(name: str) -> dict:
    return json.loads((D / name).read_text(encoding="utf-8"))


def test_versoes_batem_com_catalogo():
    for name in ("arena-final.json", "arena-confirmacao.json"):
        for cid, v in _load(name)["versoes"].items():
            assert int((cards.get_card(cid) or {}).get("versao", 1) or 1) == v, (name, cid)


def test_no_maximo_4_cartas_alteradas():
    for name in ("arena-final.json", "arena-confirmacao.json"):
        assert len(_load(name)["versoes"]) <= 4


def test_faixas_por_postura():
    for name in ("arena-final.json", "arena-confirmacao.json"):
        for cls, subs in _load(name)["posturas"].items():
            total = subs["todas"]["total"]
            assert total <= 0.85, (name, cls)
            if cls not in EXCECOES_PISO:
                assert total >= 0.45, (name, cls, total)


def test_teto_padrao_por_subclasse():
    for name in ("arena-final.json", "arena-confirmacao.json"):
        for cls, subs in _load(name)["posturas"].items():
            for sub, cell in subs.items():
                limit = EXCECOES_TETO[name].get((cls, sub), 0.75)
                assert cell["padrao"] <= limit + 1e-9, (name, cls, sub, cell["padrao"])
    # a lista de excecoes nao pode ter folga: cada uma e um valor realmente medido
    for name, table in EXCECOES_TETO.items():
        posturas = _load(name)["posturas"]
        for (cls, sub), value in table.items():
            assert abs(posturas[cls][sub]["padrao"] - value) < 1e-9, (name, cls, sub)


def test_emboscada_realista_gravada():
    real = _load("arena-emboscada-20-99.json")["posturas"]
    assert set(real) == set(_load("arena-confirmacao.json")["posturas"])
    for cls, subs in real.items():
        assert 0.0 < subs["todas"]["realista"]["total"] <= 1.0, cls
