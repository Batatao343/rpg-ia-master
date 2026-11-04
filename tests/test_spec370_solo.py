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
    assert fauna.solo_region("ophidia") is True
    assert fauna.solo_region("nova_arcadia") is False
    assert fauna.solo_region("skallgard") is False


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


@pytest.mark.parametrize("ante", ["cedo", "imediato"])
def test_regra_solo_vale_com_anuncia_global_ligado(on, monkeypatch, ante):
    """P2-3 (Sol): ligar `ANUNCIA_PRESENCA_NOVA` nao pode exigir `cedo` em Ophidia."""
    monkeypatch.setitem(fauna._config(), "ANUNCIA_PRESENCA_NOVA", True)
    cid = _first(ante, "ophidia")
    assert _res(cid, _presence("ophidia", cid)).get("fauna_convert") is True
    # nas outras regioes a constante global continua valendo so para `cedo`
    na_cedo, na_imed = _first("cedo", "nova_arcadia"), _first("imediato", "nova_arcadia")
    assert _res(na_cedo, _presence("nova_arcadia", na_cedo)).get("fauna_convert") is True
    assert not _res(na_imed, _presence("nova_arcadia", na_imed)).get("fauna_convert")
