"""SPEC-312 Etapa 7: interface da 313, invariantes, relatorio e cenario `mundo`."""

from __future__ import annotations

import pytest

from playtest import invariants, report
from services import rumors
from tests.spec312_helpers import base_state, make_rumor


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_RUMORS", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")


def _with(sim, **extra):
    return base_state(6, "na_anel_dourado", world_sim=sim, **extra)


def test_investigable_hides_truth_and_filters():
    sim: dict = {}
    seen_true = make_rumor(sim, "rumor_a", day=5, perceived=5, truth=True)
    seen_false = make_rumor(sim, "rumor_b", day=5, perceived=5, truth=False)  # falso tambem entra
    make_rumor(sim, "rumor_c", day=5, perceived=0)  # nao percebido: fora
    make_rumor(sim, "rumor_d", day=5, perceived=5, quest_eligible=False)
    make_rumor(sim, "rumor_e", day=-9, perceived=3)  # expirado
    st = _with(sim)
    got = rumors.investigable(st, 6)
    ids = {g["rumor_id"] for g in got}
    assert ids == {seen_true["subject_id"], seen_false["subject_id"]}
    for g in got:
        assert "truth" not in g
        assert set(g) == {
            "rumor_id",
            "family",
            "region_id",
            "location_id",
            "born_day",
            "expires_day",
            "subject",
            "entities",
        }
    assert rumors.truth_of(st, seen_true["subject_id"]) is True
    assert rumors.truth_of(st, seen_false["subject_id"]) is False
    assert rumors.truth_of(st, "inexistente") is None


def test_investigable_excludes_secret_signature(monkeypatch):
    import services.memory_provenance as mp

    sim: dict = {}
    make_rumor(sim, "rumor_valerius_nao_come_nem_dorme", day=5, perceived=5)
    monkeypatch.setattr(mp, "find_strict_unrevealed", lambda text, state: "segredo")
    assert rumors.investigable(_with(sim), 6) == []


def test_mark_resolved_single_writer():
    sim: dict = {}
    r = make_rumor(sim, "rumor_a", day=5, perceived=5)
    rid = r["subject_id"]
    out = rumors.mark_resolved(sim, rid, "desmentido", 7)
    inst = rumors.instance({"world_sim": out}, rid)
    assert inst["resolution"] == "desmentido" and inst["resolved_day"] == 7
    assert rumors.investigable(_with(out), 7) == []  # resolvido sai de investigable
    assert out["rumor_seed_last_born"]["rumor_a"] == rumors.NEVER_AGAIN
    # segundo desfecho nao reescreve; desfecho invalido nao muda nada
    again = rumors.mark_resolved(out, rid, "confirmado", 8)
    assert rumors.instance({"world_sim": again}, rid)["resolution"] == "desmentido"
    assert rumors.mark_resolved(sim, rid, "qualquer", 8) is sim
    # nao gravou fato: so o proprio world_sim mudou
    assert "event_log" not in out and "world_projection" not in out


def _ids(state):
    return {v.check_id for v in invariants.check_rumors(state, None, 1)}


def test_invariants_detect_fact_leak_cap_expired_truth():
    sim: dict = {}
    a = make_rumor(sim, "rumor_valerius_nao_come_nem_dorme", day=5, perceived=5)
    st = _with(sim)
    assert _ids(st) == set()
    gist = rumors.seed_of({"seed_id": "rumor_valerius_nao_come_nem_dorme"})["gist"]
    leaked = {**st, "memory_facts": [{"text": gist}]}
    assert "rumor.became_fact" in _ids(leaked)
    assert "rumor.became_fact" in _ids({**st, "event_log": [{"detail": a["subject_id"]}]})
    # quest da 313 e a unica ponte legitima
    ok_quest = {**st, "quests": [{"world_kind": "investigar_rumor", "title": gist}]}
    assert "rumor.became_fact" not in _ids(ok_quest)
    bad_quest = {**st, "quests": [{"world_kind": "outra", "title": gist}]}
    assert "rumor.became_fact" in _ids(bad_quest)
    # 2 percebidos no mesmo dia
    make_rumor(sim, "rumor_b", day=5, perceived=5)
    assert "rumor.over_daily_cap" in _ids(_with(sim))
    # news expirada
    st2 = _with({"rumors": [dict(sim["rumors"][0])]})
    st2["world"]["news"] = [{"kind": "rumor", "expires_day": 2, "text": "x"}]
    assert "rumor.expired_in_news" in _ids(st2)


def test_report_rumor_lines():
    summaries = [
        {
            "profile": "explorador",
            "world": {
                "enabled": True,
                "days_elapsed": 7,
                "rumors": {"born": 5, "perceived": 3, "false_pct": 33.3, "proposed_accepted": 1},
            },
        }
    ]
    rep = report.RunReport(
        run_id="r", campaigns=summaries, top_violations=[], top_errors=[], deltas=None
    )
    md = report.render_markdown(rep)
    assert "### Rumores" in md and "| explorador | 5 | 3 | 33.3 | 1 |" in md


def test_telemetry_rumor_summary_never_has_gist():
    from playtest.telemetry import _rumor_summary

    sim: dict = {}
    make_rumor(sim, "rumor_valerius_nao_come_nem_dorme", perceived=5, truth=False)
    make_rumor(sim, "rumor_b", day=6, perceived=0)
    out = _rumor_summary(sim)
    assert out == {"born": 2, "perceived": 1, "false_pct": 100.0, "proposed_accepted": 0}


def test_scenario_mundo_perceives_rumor_mock():
    from playtest.runner import run_campaign

    result = run_campaign("explorador", turns=14, seed=21, scenario="mundo")
    errors = [v for v in result.violations if v.get("severity") == "error"]
    assert not [v for v in errors if str(v.get("check_id", "")).startswith("rumor.")], errors
    sim = result.final_state["world_sim"]
    from playtest.telemetry import _rumor_summary

    assert _rumor_summary(sim)["perceived"] >= 1  # >= 1 rumor percebido no cenario
