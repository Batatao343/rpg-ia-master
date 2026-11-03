"""SPEC-371 R13: bestiary_view/dossiê com o saber; golden `off` byte-idêntico."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services import discovery as disc
from services import dossiers
from services import fauna
from services import fauna_saber as fs

CID = "mon_arame_vivo"
GOLDEN = Path(__file__).parent / "fixtures" / "spec371_bestiary_view_off.json"


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA_SABER", "on")


def _rec(**kw) -> dict:
    base = {"seen": 2, "fought": 1, "defeated": 0, "first_seen_turn": 3}
    base.update(kw)
    return base


def test_view_fields_tier_2():
    rec = _rec(
        sinais_vistos=["rastro", "som"],
        telegrafos_vistos=["O arame abre os ganchos."],
        saber_revelado={"motivo": "sobreviveu", "turn": 4},
    )
    (view,) = disc.bestiary_view({CID: rec})
    assert view["tier"] == 2
    assert [s["tipo"] for s in view["sinais_vistos"]] == ["rastro", "som"]
    assert view["telegrafos_vistos"] == ["O arame abre os ganchos."]
    assert view["contra_jogo"].startswith("Manter distância")
    assert view["contra_jogo_motivo"] == "Aprendido ao aguentar o golpe preparado"


def test_nada_no_tier_1():
    rec = {
        "seen": 1,
        "sinais_vistos": ["rastro"],
        "saber_revelado": {"motivo": "estudada", "turn": 1},
    }
    (view,) = disc.bestiary_view({CID: rec})
    assert view["tier"] == 1
    assert not {"sinais_vistos", "contra_jogo", "telegrafos_vistos"} & set(view)


def test_texto_do_sinal_vem_do_fauna_json():
    rec = _rec(sinais_vistos=["rastro", "tipo_que_nao_existe"])
    (view,) = disc.bestiary_view({CID: rec})
    texto = fauna.entry(CID)["sinais"]["rastro"]
    assert view["sinais_vistos"] == [{"tipo": "rastro", "texto": texto}]


def test_contra_jogo_so_revelado():
    (view,) = disc.bestiary_view({CID: _rec(sinais_vistos=["rastro"])})
    assert "contra_jogo" not in view and "contra_jogo_motivo" not in view
    # revelado, mas sem fonte (legado): nada
    legado = {"enemy_rato_peste_anel_lama": _rec(saber_revelado={"motivo": "estudada", "turn": 2})}
    (v2,) = disc.bestiary_view(legado)
    assert "contra_jogo" not in v2


@pytest.mark.parametrize("motivo", fs.MOTIVOS)
def test_rotulo_do_motivo(motivo):
    (view,) = disc.bestiary_view({CID: _rec(saber_revelado={"motivo": motivo, "turn": 4})})
    assert view["contra_jogo_motivo"] == fs.MOTIVO_LABEL[motivo]


def test_bestiary_view_off_golden(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA_SABER", "off")
    gold = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert disc.bestiary_view(gold["bk"], gold["turn"]) == gold["view"]
    monkeypatch.delenv("RPG_FAUNA_SABER")
    assert disc.bestiary_view(gold["bk"], gold["turn"]) == gold["view"]


def test_dossie_repassa_campos():
    rec = _rec(
        sinais_vistos=["rastro"],
        telegrafos_vistos=["t"],
        saber_revelado={"motivo": "rastreada", "turn": 4},
    )
    (entry,) = disc.bestiary_view({CID: rec})
    entry = {**entry, "knowledge": {}, "notes": []}
    dossie = dossiers.creature_dossier(entry, {"bestiary_knowledge": {CID: rec}})
    assert dossie["sinais_vistos"][0]["tipo"] == "rastro"
    assert dossie["telegrafos_vistos"] == ["t"]
    assert dossie["contra_jogo_motivo"] == fs.MOTIVO_LABEL["rastreada"]


def test_dossie_off_sem_campos(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA_SABER", "off")
    rec = _rec(sinais_vistos=["rastro"], saber_revelado={"motivo": "rastreada", "turn": 4})
    (entry,) = disc.bestiary_view({CID: rec})
    dossie = dossiers.creature_dossier(
        {**entry, "knowledge": {}, "notes": []}, {"bestiary_knowledge": {CID: rec}}
    )
    assert not {"sinais_vistos", "contra_jogo", "telegrafos_vistos"} & set(dossie)
