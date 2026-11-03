"""SPEC-372 R15: eval deterministico das criaturas de trama (T1-T8), congelado na Etapa 1.

Protegido (D10, `evals/protected-paths.txt`): quem otimiza o produto nao edita este arquivo
nem `scripts/fauna/eval_tramas.py`. Limiares e estagios esperados literais abaixo.

Antes das ligacoes autoradas (Etapa 4) T1-T3 sao `xfail(strict=True)` ("sem ligacao
autorada"); T4-T8 ja rodam: T7 verde desde ja; T8 vermelho ate a Etapa 2 (`plot_stage`);
T1-T6 dependem do contrato do motor (Etapa 5) e dao erro de setup ate la.
Os testes `test_avaliador_*` conferem o proprio avaliador (known-good/known-bad), sem produto.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_eval():
    spec = importlib.util.spec_from_file_location(
        "spec372_eval", ROOT / "scripts" / "fauna" / "eval_tramas.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _has_links() -> bool:
    doc = json.loads((ROOT / "data" / "world" / "fauna.json").read_text(encoding="utf-8"))
    return any(
        e.get("regiao") == "nova_arcadia" and e.get("tramas")
        for e in (doc.get("criaturas") or {}).values()
    )


SEM_LIGACAO = pytest.mark.xfail(
    not _has_links(), reason="sem ligação autorada (SPEC-372 Etapa 4)", strict=True
)


@pytest.fixture(scope="module")
def result():
    ev = _load_eval()
    return ev.run(20, 30, with_t7=False)


# --------------------------------------------------------------------------- avaliador


def test_limiares_congelados():
    ev = _load_eval()
    assert ev.T1_MAX_SHARE == 0.0
    assert ev.T1_MAX_PRESENCAS == 0
    assert ev.T1_MAX_TRACK == 0
    assert ev.T2_MIN_RATIO == 1.5
    assert ev.T3_MIN_LOCAIS == 1.0
    assert (ev.T4_MIN_DELTA, ev.T4_MAX_DELTA) == (-0.10, 0.05)
    assert ev.T5_MAX_VAZAMENTOS == 0
    assert ev.T8_MIN_CASES == 10
    assert (ev.DEFAULT_SEEDS, ev.DEFAULT_DAYS) == (20, 30)
    assert ev.STAGES == ("dormente", "tocada", "investigada", "revelada")
    assert ev.MODES == ("off", "dormente", "maximo")


def test_avaliador_estagio_maximo_literal():
    """O estado `maximo` tem estagio literal por trama de NA (sem `secret_ids` = investigada)."""
    ev = _load_eval()
    assert ev.max_stages() == {
        "tr_na_documento_da_legiao": "revelada",
        "tr_na_o_que_o_lorde_trocou": "revelada",
        "tr_na_corpos_marcados": "revelada",
        "tr_na_aco_que_lembra": "revelada",
        "tr_na_lista_de_fornalha": "investigada",
        "tr_na_a_colecao": "investigada",
        "tr_na_po_de_sonho": "revelada",
    }


def test_avaliador_normaliza_e_compara_estagio():
    ev = _load_eval()
    assert ev._norm_tramas(["tr_x", {"id": "tr_y", "desde": "revelada"}, {"desde": "tocada"}]) == [
        {"id": "tr_x", "desde": "tocada"},
        {"id": "tr_y", "desde": "revelada"},
    ]
    links = [{"id": "a", "desde": "investigada"}, {"id": "b", "desde": "tocada"}]
    assert ev._reached(links, {"a": "tocada", "b": "dormente"}) == []
    assert ev._reached(links, {"a": "revelada", "b": "tocada"}) == ["a", "b"]
    assert [ev._below(d) for d in ev.DESDE] == ["dormente", "tocada", "investigada"]


def test_avaliador_tokens_proibidos_vem_dos_dados():
    ev = _load_eval()
    forb = ev.forbidden_by_thread()
    assert {"valerius", "pacto", "imortalidade"} <= forb["tr_na_o_que_o_lorde_trocou"]
    assert {"silas", "vane", "corva"} <= forb["tr_na_corpos_marcados"]
    assert "grum" in forb["tr_na_documento_da_legiao"]


def test_avaliador_t8_tem_casos_suficientes():
    ev = _load_eval()
    names = [n for n, _s, _e in ev.stage_cases()]
    assert len(names) >= 10 and len(set(names)) == len(names)


def _table_stub(ev):
    table = {json.dumps(s, sort_keys=True, ensure_ascii=False): e for _n, s, e in ev.stage_cases()}

    def stage(state, tid):
        return table.get(json.dumps(state, sort_keys=True, ensure_ascii=False), {}).get(
            tid, "dormente"
        )

    return stage


def test_avaliador_t8_known_good(monkeypatch):
    ev = _load_eval()
    from services import plot_threads

    stub = _table_stub(ev)
    monkeypatch.setattr(plot_threads, "plot_stage", stub, raising=False)
    monkeypatch.setattr(
        plot_threads,
        "plot_stages",
        lambda st, region: {t: stub(st, t) for t in ev.region_threads()},
        raising=False,
    )
    out = ev.stage_metrics()
    assert out["wrong"] == [] and out["mutated"] == []


def test_avaliador_t8_known_bad(monkeypatch):
    ev = _load_eval()
    from services import plot_threads

    monkeypatch.setattr(plot_threads, "plot_stage", lambda st, tid: "dormente", raising=False)
    monkeypatch.setattr(
        plot_threads,
        "plot_stages",
        lambda st, region: {t: "dormente" for t in ev.region_threads()},
        raising=False,
    )
    wrong = {w["case"] for w in ev.stage_metrics()["wrong"]}
    assert {"tocada_npc_known_by_player", "investigada_quest_ativa", "maximo"} <= wrong
    assert "vazio" not in wrong


def test_avaliador_t8_detecta_mutacao(monkeypatch):
    ev = _load_eval()
    from services import plot_threads

    stub = _table_stub(ev)

    def mutating(state, tid):
        out = stub(state, tid)
        state.setdefault("_tocado", True)
        return out

    monkeypatch.setattr(plot_threads, "plot_stage", mutating, raising=False)
    monkeypatch.setattr(
        plot_threads,
        "plot_stages",
        lambda st, region: {t: stub(st, t) for t in ev.region_threads()},
        raising=False,
    )
    assert ev.stage_metrics()["mutated"]


# --------------------------------------------------------------------------- T1-T8


@SEM_LIGACAO
def test_t1_portao(result):
    m = result["metrics"]
    assert m["linked"] > 0, "sem ligação autorada"
    assert m["T1_max_share"] == 0.0, result["dist"]["t1"]
    assert m["T1_presencas"] == 0, m
    assert m["T1_track"] == 0 and m["T1_picks"] == 0, result["sim"]["dormente"]["linked_picks"]


@SEM_LIGACAO
def test_t2_puxao(result):
    m = result["metrics"]
    assert m["linked"] > 0, "sem ligação autorada"
    assert m["T2_unreachable"] == 0, result["dist"]["unreachable"]
    assert m["T2_min_ratio"] is not None and m["T2_min_ratio"] >= 1.5, result["dist"]["t2"]


@SEM_LIGACAO
def test_t3_locais_da_trama(result):
    m = result["metrics"]
    assert m["linked"] > 0, "sem ligação autorada"
    assert m["T3_n"] > 0, "nenhuma presença de criatura ligada e atingida nasceu"
    assert m["T3_locais"] == 1.0, result["t3_bad"]
    assert m["T3_off_trama_id"] == 0


def test_t4_quantidade(result):
    m = result["metrics"]
    assert result["sim"]["off"]["fauna_combats"] > 0
    assert len(set(m["T4_triggers"].values())) == 1, m["T4_triggers"]  # so QUEM, nunca QUANTOS
    assert -0.10 <= m["T4_delta_dormente"] <= 0.05, result["rates"]
    assert -0.10 <= m["T4_delta_maximo"] <= 0.05, result["rates"]


def test_t5_vazamento(result):
    assert result["metrics"]["T5_vazamentos"] == 0, result["leak_samples"]
    assert result["sim"]["dormente"]["texts"] + result["sim"]["maximo"]["texts"] > 0


def test_t6_determinismo():
    ev = _load_eval()
    a = ev.render(ev.run(3, 10, with_t7=False))
    b = ev.render(ev.run(3, 10, with_t7=False))
    assert a == b


def test_t7_flag_off_relatorio_360_identico():
    t7 = _load_eval().baseline_360_identical()
    assert t7["identical"], t7


def test_t8_estagio_literal():
    st = _load_eval().stage_metrics()
    assert len(st["cases"]) >= 10
    assert st["wrong"] == [], st["wrong"]
    assert st["mutated"] == [], st["mutated"]
