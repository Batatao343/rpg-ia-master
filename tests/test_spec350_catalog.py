"""SPEC-350 Etapa 4 — catálogo real de tramas de Nova Arcádia (onda 1)."""

from __future__ import annotations

import json
import os
import re
import unicodedata

import pytest

from services import content_validator as cv
from services import plot_threads as pt
from services.codex_loader import CODEX_DIR, parse_codex_file

NA = "nova_arcadia"
TEMPLATE_PHRASE = "fala por imagens concretas"
NEW_NPCS = 14
EXCLUDED_NA = {
    "npc_elaryin_historico", "npc_malagor", "npc_fehk", "npc_o_cego", "npc_o_corretor",
}
LORE_362 = (
    "npc_valerius npc_grum npc_velha_magda npc_doutor_silas_vane npc_comandante_thrace "
    "npc_lorde_vesperio_valante npc_mae_corva npc_mestre_fundidor_kald npc_arquimaga_sylvenne "
    "npc_pardal npc_lirio npc_lorde_oswin_conta_de_ouro npc_bors_martelo_partido "
    "npc_velha_netta npc_dama_vesperina npc_korvus npc_liane_chama_escondida "
    "npc_rato_de_ferro_tibb npc_benedita_a_parteira npc_ilsa npc_bertil "
    "npc_sennar_o_pregador_da_cicatriz"
).split()
MV = ["npc_mv_irena_prego_frio", "npc_mv_mara_do_setimo_sino", "npc_mv_teo_chamine"]
NAME_348 = ("ilsa", "bertil", "sennar", "benedita")


def _load(rel: str):
    with open(rel, encoding="utf-8") as f:
        return json.load(f)


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


@pytest.fixture(scope="module")
def data():
    return _load(pt.CATALOG_PATH)


def _docs():
    out = {}
    for root, _d, files in os.walk(CODEX_DIR):
        for fn in files:
            if fn.endswith(".md"):
                fm, body = parse_codex_file(os.path.join(root, fn))
                out[fm["id"]] = (fm, body)
    return out


def test_nova_arcadia_has_seven_threads_with_listed_members(data):
    threads = {t["id"]: t for t in data["threads"] if t["region_id"] == NA}
    assert set(threads) == {
        "tr_na_documento_da_legiao", "tr_na_o_que_o_lorde_trocou", "tr_na_corpos_marcados",
        "tr_na_aco_que_lembra", "tr_na_lista_de_fornalha", "tr_na_a_colecao", "tr_na_po_de_sonho",
    }
    for t in threads.values():
        assert len(t["portas"]) >= 3
        assert len({d["location_id"] for d in t["portas"]}) >= 2
        assert len({d["anchor_npc_id"] for d in t["portas"]}) == len(t["portas"])
    aco = threads["tr_na_aco_que_lembra"]
    assert {"npc_mv_irena_prego_frio", "npc_mv_teo_chamine"} <= set(aco["borda"])
    assert len(aco["portas"]) == 4
    assert "npc_ilsa" in threads["tr_na_documento_da_legiao"]["borda"]
    assert "npc_benedita_a_parteira" in threads["tr_na_corpos_marcados"]["borda"]


def test_po_de_sonho_has_an_elf_door_that_needs_no_prior_knowledge(data):
    thr = next(t for t in data["threads"] if t["id"] == "tr_na_po_de_sonho")
    assert "quebrados" in thr["factions"]
    door = thr["portas"][0]
    assert door["anchor_npc_id"] == "npc_tr_ysolt_fio_de_vidro"
    hook = _fold(door["hook_public"])
    assert "pele rachada" in hook
    for term in ("quebrado", "elaryin", "overdose", "licenca"):
        assert term not in hook
    ysolt = data["cast"]["npc_tr_ysolt_fio_de_vidro"]
    assert "elfico" in _fold(ysolt["desejo"]) or "elfica" in _fold(ysolt["desejo"])


def test_fourteen_new_npcs_have_public_secret_extra_edges_agenda_cast(data):
    new = sorted(k for k, v in data["cast"].items() if v["fonte"] == "spec350")
    assert len(new) == NEW_NPCS
    extra = _load("data/graph/entities_extra.json")
    edges = _load("data/graph/edges.json")
    agendas = _load("data/world/npc_world.json")["agenda_by_npc"]
    docs = _docs()
    for nid in new:
        fm, _body = docs[nid]
        assert fm["visibility"] == "public" and fm.get("curated") is True
        assert os.path.exists(os.path.join(CODEX_DIR, "npcs", "tramas", f"{nid}.md"))
        sfm, _ = docs[data["cast"][nid]["segredo_doc_id"]]
        assert sfm["visibility"] == "hidden" and sfm["type"] == "npc_secret"
        assert nid in extra and extra[nid]["type"] == "npc"
        assert any(e["source"] == nid and e["type"] == "located_in" for e in edges)
        assert nid in agendas
        in_thread = [t for t in data["threads"] if nid in t["borda"] or nid in t["core"]]
        assert in_thread, nid
    names = {_fold(extra[n]["name"]) for n in new}
    assert not any(any(x in n for x in NAME_348) for n in names)  # R14


def test_rute_is_a_real_npc_and_daily_life_text_is_untouched(data):
    assert "npc_tr_rute_corvo_veterana" in data["cast"]
    with open("lore_nova/daily_life.txt", encoding="utf-8") as f:
        assert "Rute, Corvo Veterana" in f.read()


def test_mundo_vivo_na_promoted_without_template_line(data):
    docs = _docs()
    for nid in MV:
        fm, body = docs[nid]
        assert TEMPLATE_PHRASE not in body
        assert nid in data["cast"] and data["cast"][nid]["segredo_doc_id"] in docs
    others = [i for i in docs if i.startswith("npc_mv_") and i not in MV]
    assert any(TEMPLATE_PHRASE in docs[i][1] for i in others)  # os outros 33 ficam como estão


def test_every_na_named_npc_in_cast_or_excluded(data):
    for nid in LORE_362:
        assert nid in data["cast"], nid
    for nid in EXCLUDED_NA:
        assert nid in data["excluded"] and data["excluded"][nid]
        assert nid not in data["cast"]


def test_348_npcs_reused_not_redefined(data):
    for nid in ("npc_ilsa", "npc_bertil", "npc_sennar_o_pregador_da_cicatriz", "npc_benedita_a_parteira"):
        assert data["cast"][nid]["fonte"].startswith("lore_nova/npcs.txt:")
    assert not [n for n in data["cast"] if n.startswith("npc_tr_") and any(x in n for x in NAME_348)]


def test_region_coverage_nova_arcadia(data):
    wave = next(w for w in data["waves"] if NA in w["regions"])
    if wave["status"] != "done":
        pytest.skip("onda 1 ainda não fechada")
    threads = [t for t in data["threads"] if t["region_id"] == NA]
    assert len(threads) >= 5


def test_waves_cover_the_twelve_regions(data):
    covered = [r for w in data["waves"] for r in w["regions"]]
    origins = [r["id"] for r in _load("data/origins.json")["regions"]]
    assert sorted(covered) == sorted(origins)


def test_door_hooks_are_third_person_and_short(data):
    for t in data["threads"]:
        for d in t["portas"]:
            assert len(d["hook_public"]) <= 220
            assert not re.search(r"\bvoc[eê]\b", _fold(d["hook_public"]))


def test_repo_lint_has_no_plot_errors():
    from services.leak_phrases import all_phrases

    assert all_phrases(), "LEAK_PHRASES não carregou"
    assert [f for f in cv.validate_plot_threads() if f.severity == "error"] == []


def test_catalog_loads_in_runtime_and_region_cast_is_complete(monkeypatch):
    monkeypatch.setenv("RPG_PLOT_THREADS", "on")
    pt.clear_cache()
    try:
        cat = pt.catalog()
        assert len(cat.threads) == 7 and len(cat.cast) >= 36
        assert len(pt.plot_doors(NA)) == 22
        assert len(pt.plot_doors(NA, postura="Corruptor")) == 22
        assert pt.plot_doors(NA, postura="Corruptor")[0].id.startswith("tr_na_a_colecao")
        assert set(pt.region_cast(NA)) == set(cat.cast)
    finally:
        pt.clear_cache()
