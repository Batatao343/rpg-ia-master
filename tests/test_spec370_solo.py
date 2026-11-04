"""SPEC-370 (dono, 03/11): em regiao de 1 no raiz, presenca nova anuncia antes de virar luta."""

from __future__ import annotations

import pytest

import world_utils as wu
from services import fauna


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")


def _presence(region: str, cid: str, shown=()) -> dict:
    return {
        "pid": "p1",
        "creature_id": cid,
        "region_id": region,
        "locais": ["x"],
        "sinais_mostrados": list(shown),
    }


def _res(cid: str, presence: dict) -> dict:
    return wu._fauna_encounter({}, {"id": cid}, presence, {})


def _first(antecedencia: str, region: str) -> str:
    return next(
        c
        for c, e in fauna.load().items()
        if e["regiao"] == region and (e.get("sinais") or {}).get("antecedencia") == antecedencia
    )


def test_anuncia_so_em_regiao_de_1_no():
    assert fauna.anuncia_presenca_nova("ophidia") is True
    assert fauna.anuncia_presenca_nova("nova_arcadia") is False
    assert fauna.anuncia_presenca_nova("skallgard") is False


@pytest.mark.parametrize("ante", ["cedo", "imediato"])
def test_ophidia_presenca_sem_sinal_converte(on, ante):
    cid = _first(ante, "ophidia")
    assert _res(cid, _presence("ophidia", cid)).get("fauna_convert") is True


def test_ophidia_presenca_com_sinal_pode_virar_luta(on):
    cid = _first("cedo", "ophidia")
    assert not _res(cid, _presence("ophidia", cid, shown=["rastro"])).get("fauna_convert")


def test_outras_regioes_inalteradas(on):
    for region in ("nova_arcadia", "skallgard"):
        for ante in ("cedo", "imediato"):
            cid = _first(ante, region)
            assert not _res(cid, _presence(region, cid)).get("fauna_convert"), (region, ante)


def test_e9_mede_o_bloco_inteiro():
    """H-02: o E9 recusa sinal que estoura 60 tokens no bloco, mesmo abaixo de 160 caracteres."""
    from tests.test_spec370_suprime import _entry, _errs, _refs

    longo = "palavra " * 19  # 152 caracteres: passa nos 160, mas o bloco passa de 240
    e = _entry()
    e["sinais"] = {"antecedencia": "cedo", "rastro": longo.strip()}
    crit = {"A": e, "B": _entry(), "C": _entry(), "D": _entry()}
    assert any("tokens no bloco" in x for x in _errs(crit, _refs(), "E9"))
