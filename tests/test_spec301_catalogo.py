"""SPEC-301 Etapa 1 — catálogo curado e lint (R1/R9)."""

from __future__ import annotations

import json

import pytest

import gamedata
from services import content_validator as cv
from services import faction_membership as fm
from services import graph_resolver as gr
from services.faction_membership_lint import PERK_TYPES, lint_faction_membership


def _lint_args() -> dict:
    ents = gr.load_entities()
    merchants = json.loads(open("data/merchants.json", encoding="utf-8").read())
    return {
        "faction_ids": set(gamedata.FACTIONS),
        "location_ids": {loc["id"] for loc in gamedata.WORLD_MAP["locations"]},
        "npc_ids": {k for k, v in ents.items() if v.get("type") == "npc"},
        "item_ids": set(gamedata.ARTIFACTS_DB),
        "merchant_location_ids": {m["location_id"] for m in merchants.values()},
    }


def test_catalogo_cobre_as_19_faccoes():
    cat = fm.load_catalog()
    assert set(cat) == set(gamedata.FACTIONS)
    assert len(cat) == 19


def test_faccao_nao_sem_ranks():
    closed = [fid for fid, row in fm.load_catalog().items() if row["accepts"] == "nao"]
    assert closed  # as fechadas existem (Mercadores de Escravos entre elas)
    assert "mercadores_escravos_pradaria" in closed
    for fid in closed:
        assert set(fm.load_catalog()[fid]) == {"accepts"}


def test_devoradores_de_sol_so_origem_zhur():
    row = fm.load_catalog()["tribos_devoradores_sol"]
    assert row["accepts"] == "condicional"
    assert row["requirements"]["origins_allowed"] == ["deserto_zhur"]


def test_ids_de_local_npc_item_rival_existem():
    assert lint_faction_membership(fm.load_catalog(), **_lint_args()) == []


def test_perk_tipo_fechado():
    cat = json.loads(json.dumps(fm.load_catalog()))
    cat["legiao_ferro"]["perks_by_rank"]["0"] = [{"type": "voar"}]
    problems = lint_faction_membership(cat, **_lint_args())
    assert any("perk de tipo desconhecido" in p for p in problems)
    for row in fm.load_catalog().values():
        for perks in (row.get("perks_by_rank") or {}).values():
            assert all(p["type"] in PERK_TYPES for p in perks)


def test_templates_minimos_por_faccao_aceitante():
    ids = set(gamedata.FACTIONS)
    for fid, row in fm.load_catalog().items():
        if row["accepts"] == "nao":
            continue
        kinds = [t["kind"] for t in row["mission_templates"]]
        assert kinds.count("apoio") >= 2, fid
        sabs = [t for t in row["mission_templates"] if t["kind"] == "sabotagem"]
        assert sabs and all(t["target_faction_id"] in ids for t in sabs), fid


def test_ultima_patente_nao_e_lider():
    leaders = {}
    for edge in gr.resolve_edges(None, edge_type="leads"):
        leaders.setdefault(edge["target"], set()).add(
            (gr.get_entity(edge["source"]) or {}).get("name", "")
        )
    for fid, row in fm.load_catalog().items():
        if row["accepts"] == "nao":
            continue
        top = row["ranks"][-1]["name"]
        assert top not in leaders.get(fid, set()), fid
        assert 3 <= len(row["ranks"]) <= 5


def test_ids_de_patente_unicos_e_merito_crescente():
    for fid, row in fm.load_catalog().items():
        if row["accepts"] == "nao":
            continue
        merits = [r["merit"] for r in row["ranks"]]
        assert merits == sorted(merits) and merits[0] == 0, fid
        assert len({r["id"] for r in row["ranks"]}) == len(row["ranks"])


def test_lint_reporta_erro_em_catalogo_corrompido():
    cat = json.loads(json.dumps(fm.load_catalog()))
    cat["tribos_devoradores_sol"]["ranks"] = []  # aceita membro sem patentes
    cat["bandos_orc_saidas_baixas"]["ranks"] = [{"id": "x"}]  # 'nao' com ranks
    cat["legiao_ferro"]["hq_location_ids"] = ["lugar_que_nao_existe"]
    cat["legiao_ferro"]["rivals"] = ["nao_e_faccao"]
    cat["legiao_ferro"]["recruiter_npc_ids"] = ["npc_fantasma"]
    cat["legiao_ferro"]["quartermaster"] = {"item_fantasma": 0}
    problems = " | ".join(lint_faction_membership(cat, **_lint_args()))
    for needle in (
        "ranks deve ter de 3 a 5",
        "não pode ter ranks",
        "hq fora do mapa",
        "não é fação",
        "recrutador fora do grafo",
        "item do intendente fora de artifacts",
    ):
        assert needle in problems, needle


def test_lint_validate_content_exit_nonzero(tmp_path, monkeypatch):
    bad = json.loads(json.dumps(fm.load_catalog()))
    bad["legiao_ferro"]["hq_location_ids"] = ["lugar_que_nao_existe"]
    path = tmp_path / "faction_membership.json"
    path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    findings = cv.validate_faction_membership(str(path))
    assert findings and all(f.severity == "error" for f in findings)
    monkeypatch.setattr(cv, "FACTION_MEMBERSHIP_PATH", str(path))
    from scripts import validate_content

    assert validate_content.main() == 1


def test_lint_real_passa():
    assert cv.validate_faction_membership() == []


@pytest.mark.parametrize("fid", sorted(gamedata.FACTIONS))
def test_missao_template_aponta_para_local_do_mapa(fid):
    from services import faction_missions

    if fm.load_catalog()[fid]["accepts"] != "nao":
        assert faction_missions.mission_locations_exist(fid)
