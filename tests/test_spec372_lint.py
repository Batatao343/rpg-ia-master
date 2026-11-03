"""SPEC-372 Etapa 3 — forma de `tramas` e lint E19-E22."""

from __future__ import annotations

import json
from pathlib import Path

from services import fauna_lint as fl
from services import fauna_lint_tramas as ft
from services import plot_threads as pt

ROOT = Path(__file__).resolve().parent.parent
CORPOS = "tr_na_corpos_marcados"
REGION = "nova_arcadia"


def _thr() -> pt.PlotThread:
    return pt.thread(CORPOS)


def _refs(boss: set[str] = frozenset(), n: int = 10) -> fl.Refs:
    thr = _thr()
    nodes = frozenset(thr.locations)
    bestiary = {f"c{i}": {"name": f"criatura{i}", "regions": [REGION], "boss": False} for i in range(n)}
    for b in boss:
        bestiary[b] = {"name": b, "regions": [REGION], "boss": True}
    return fl.Refs(region=REGION, region_nodes=nodes, bestiary=bestiary)


def _entry(tramas, terr=None, sinais=None) -> dict:
    return {
        "ecologia": {"territorio": terr or []},
        "sinais": sinais or {},
        "tramas": tramas,
    }


def _run(crit: dict, refs: fl.Refs) -> list[str]:
    return ft.lint_tramas(crit, refs, {t.id: t for t in pt.catalog().threads})


def test_string_vira_tocada():
    assert ft.normalize_tramas(["a", {"id": "b", "desde": "revelada"}]) == [
        {"id": "a", "desde": "tocada"},
        {"id": "b", "desde": "revelada"},
    ]
    assert ft.tramas_form_ok(["a", {"id": "b", "desde": "tocada"}])
    assert not ft.tramas_form_ok([3])
    assert not ft.tramas_form_ok({"id": "a"})


def test_e19_trama_inexistente():
    errs = _run({"c0": _entry([{"id": "tr_nada", "desde": "tocada"}])}, _refs())
    assert any(e.startswith("E19 c0") for e in errs)


def test_e19_regiao_errada():
    refs = _refs()
    other = next((t for t in pt.catalog().threads if t.region_id != REGION), None)
    thr = _thr().model_copy(update={"id": "tr_x", "region_id": "outra"})
    errs = ft.lint_tramas(
        {"c0": _entry(["tr_x"])}, refs, {"tr_x": thr, **({other.id: other} if other else {})}
    )
    assert any(e.startswith("E19 c0") for e in errs)


def test_e20_boss_com_trama():
    refs = _refs(boss={"b0"})
    errs = _run({"b0": _entry([CORPOS])}, refs)
    assert any(e.startswith("E20 b0") for e in errs)


def test_e20_tres_tramas_e_desde_invalido():
    ids = [t.id for t in pt.threads_for_region(REGION)][:3]
    errs = _run({"c0": _entry(ids, terr=list(_thr().locations))}, _refs())
    assert any("E20 c0" in e and "max 2" in e for e in errs)
    errs = _run({"c0": _entry([{"id": CORPOS, "desde": "nunca"}], terr=list(_thr().locations))}, _refs())
    assert any("E20 c0" in e and "desde" in e for e in errs)


def test_e21_territorio_sem_locais():
    refs = fl.Refs(region=REGION, region_nodes=frozenset({"na_longe"}), bestiary={"c0": {}})
    errs = _run({"c0": _entry([CORPOS], terr=["na_longe"])}, refs)
    assert any(e.startswith("E21 c0") for e in errs)


def test_e21_teto_25():
    loc = list(_thr().locations)
    crit = {f"c{i}": _entry([CORPOS] if i < 3 else [], terr=loc) for i in range(10)}
    errs = _run(crit, _refs())
    assert any("E21:" in e and "25 %" in e for e in errs)
    crit = {f"c{i}": _entry([CORPOS] if i < 2 else [], terr=loc) for i in range(10)}
    assert not any("25 %" in e for e in _run(crit, _refs()))


def test_e22_assinatura_de_segredo():
    thr = pt.thread("tr_na_o_que_o_lorde_trocou")
    sinais = {"rumor": "ouviram falar de um pacto com valerius na noite"}
    errs = ft.lint_tramas(
        {"c0": _entry([thr.id], terr=list(thr.locations), sinais=sinais)},
        _refs(),
        {thr.id: thr},
    )
    assert any(e.startswith("E22 c0") for e in errs)


def test_e22_nome_do_core():
    thr = pt.thread("tr_na_o_que_o_lorde_trocou")
    sinais = {"rastro": "pegadas que levam a casa de Valerius"}
    errs = ft.lint_tramas(
        {"c0": _entry([thr.id], terr=list(thr.locations), sinais=sinais)},
        _refs(),
        {thr.id: thr},
    )
    assert any(e.startswith("E22 c0") for e in errs)


def test_sem_tramas_sem_erro():
    assert _run({"c0": _entry([]), "c1": _entry(None)}, _refs()) == []


def test_fauna_json_fresco():
    from scripts.fauna import build

    doc = json.loads((ROOT / "data" / "world" / "fauna.json").read_text(encoding="utf-8"))
    assert build.render(build.build_doc()) == build.render(doc)
