"""SPEC-349 Etapa 2: curadoria do legado (data/bestiario/curadoria_legado.yaml)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from services import bestiary_lint as bl

ROOT = Path(__file__).resolve().parents[1]
CUR = yaml.safe_load((ROOT / "data/bestiario/curadoria_legado.yaml").read_text(encoding="utf-8"))
BEST = json.loads((ROOT / "data/bestiary.json").read_text(encoding="utf-8"))
SNAP = json.loads(
    (ROOT / "tests/fixtures/spec349_legado_snapshot.json").read_text(encoding="utf-8")
)
# SPEC-348 D8 edita a descrição da Víbora.
DESC_EXCECAO = {"enemy_boss_vibora"}


def test_todas_classificadas():
    assert len(SNAP) == 124
    assert set(CUR) == set(SNAP)
    for cid, e in CUR.items():
        assert e["classe"] in {"valoria", "generico"}, cid
        assert e["subclasse"] in {"unico", "conceitual", "generico"}, cid
        assert e["motivo"].strip() and e["evidencia"].strip() and e["revisor"].strip(), cid
        assert e["regiao_onda"], cid


def test_evidencias_resolvem():
    for cid, e in CUR.items():
        ev = e["evidencia"]
        m = re.match(r"^((?:lore_nova|data)/[^\s:]+):(\d+)", ev)
        if m:
            assert bl._ref_ok(f"{m.group(1)}:{m.group(2)}"), (cid, ev)
        else:
            assert re.search(r"\d+ hits? ", ev) or ev.startswith("0 hits"), (cid, ev)


def test_generico_tem_destino():
    for cid, e in CUR.items():
        assert (e["classe"] == "generico") == (e["destino"] != "manter"), cid
        assert (
            e["destino"] == "manter"
            or e["destino"] == "reinventar"
            or e["destino"].startswith("adotar:")
        )
        assert (e["classe"] == "generico") == (e["subclasse"] == "generico"), cid


def test_valoria_intocada():
    for cid, e in CUR.items():
        if e["classe"] != "valoria":
            continue
        assert cid in BEST, f"{cid} apagada"
        snap = SNAP[cid]
        assert BEST[cid]["id"] == cid
        assert BEST[cid]["name"] == snap["name"], cid
        if cid not in DESC_EXCECAO:
            assert BEST[cid]["description"] == snap["description"], cid


def test_snapshot_bate_com_bestiario_original_nos_campos_de_slot():
    # genéricos ainda não reinventados (Etapa 6): campos de slot nunca mudam
    for cid, snap in SNAP.items():
        cre = BEST[cid]
        for campo in (
            "categoria",
            "arquetipo",
            "virtudes",
            "max_vitalidade",
            "ferimento_espacos",
            "regions",
            "faction",
        ):
            assert cre.get(campo) == snap[campo], (cid, campo)


def test_adotado_aponta_codex_fisico():
    adotados = {
        cid: e["destino"].split(":", 1)[1]
        for cid, e in CUR.items()
        if e["destino"].startswith("adotar:")
    }
    assert (
        len(adotados) == 4
    )  # coordenador 28/10: Brasa Profunda e Polvo dos Destroços viraram reinvenção
    for cid, doc_id in adotados.items():
        path = ROOT / "data/codex/monsters" / f"{doc_id}.md"
        assert path.is_file(), (cid, doc_id)
        assert doc_id not in BEST, "adotada não pode ter ficha mecânica prévia (D4)"
        body = path.read_text(encoding="utf-8")
        # físico: nenhum termo conceitual. O U9 completo (>= 3 partes) vale na ficha da
        # Etapa 4, que escreve anatomia própria (vários docs do Codex não citam partes).
        assert not bl.checar_fisico(body, minimo=0), (cid, bl.checar_fisico(body, minimo=0))


@pytest.mark.parametrize("cid", [c for c, e in CUR.items() if e["destino"] == "reinventar"])
def test_reinventar_tem_nome_proibido_ou_motivo(cid):
    assert CUR[cid]["motivo"]
