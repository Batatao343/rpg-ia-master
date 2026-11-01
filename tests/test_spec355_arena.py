"""SPEC-355 R45: artefatos da arena (0-19 ajuste, 20-99 confirmacao) e faixas por Postura."""

from __future__ import annotations

import json
from pathlib import Path

from services import cards

D = Path(__file__).resolve().parents[1] / "docs" / "spec355"
# Excecoes pendentes registradas em SPEC-355 §9 (decisao do dono): ficam abaixo do piso de 45 %.
EXCECOES_PISO = {"Arcanista Cinzento"}


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


def test_emboscada_realista_gravada():
    real = _load("arena-emboscada-20-99.json")["posturas"]
    assert set(real) == set(_load("arena-confirmacao.json")["posturas"])
    for cls, subs in real.items():
        assert 0.0 < subs["todas"]["realista"]["total"] <= 1.0, cls
