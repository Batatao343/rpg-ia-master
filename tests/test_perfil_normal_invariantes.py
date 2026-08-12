import random

from langchain_core.messages import AIMessage

import progression
from playtest import invariants
from playtest.profiles import PROFILES
from playtest.runner import CampaignResult, TurnRecord, _resolve_profile_progression
from playtest.telemetry import build_summary, turn_to_record


def _base_state(**over):
    state = {
        "player": {
            "name": "Valen", "class_name": "Devoto do Abismo",
            "vitalidade": 20, "max_vitalidade": 20,
            "hp": 20, "max_hp": 20, "inventory": [],
        },
        "world": {
            "current_location_id": "nova_arcadia",
            "current_location": "Nova Arcádia",
            "danger_level": 1, "visited": ["nova_arcadia"],
        },
        "combat": {"active": False}, "enemies": [], "npcs": {},
        "messages": [], "quests": [], "campaign_plan": {"beats": []},
    }
    state.update(over)
    return state


def test_perfil_normal_existe_e_varia_intencoes():
    profile = PROFILES["normal"]
    profile.reset()
    state = _base_state()
    actions = [profile.decide(state, random.Random(4)).text for _ in range(8)]
    corpus = " ".join(actions).lower()
    assert "viajo" in corpus or "entro" in corpus
    assert "vasculho" in corpus
    assert "objetivo" in corpus
    assert "descanso" in corpus


def test_perfil_normal_conversa_com_npc_ainda_nao_ouvido():
    profile = PROFILES["normal"]
    profile.reset()
    state = _base_state(npcs={"Mara": {"name": "Mara", "in_scene": True}})
    assert "Mara" in profile.decide(state, random.Random(1)).text


def test_perfil_normal_foge_quando_risco_extremo_sem_cura():
    profile = PROFILES["normal"]
    profile.reset()
    state = _base_state(
        player={
            "name": "Valen", "vitalidade": 3, "max_vitalidade": 20,
            "hp": 3, "max_hp": 20, "inventory": [],
        },
        combat={"active": True, "round": 4},
        enemies=[{"id": "lobo", "name": "Lobo", "status": "ativo"}],
    )
    assert profile.decide(state, random.Random(2)).mode == "flee"


def test_runner_resolve_escolhas_do_perfil_normal():
    player = {
        "class_name": "Devoto do Abismo", "known_cards": ["dev_provocacao"],
        "pending_choices": [{"id": "lvl2-virtude", "kind": "virtude", "level": 2}],
        "virtudes": {"mente": 1, "agilidade": 1, "forca": 1,
                     "carisma": 1, "corpo": 2},
        "vitalidade": 10, "max_vitalidade": 10,
    }
    state = {"player": player}
    choices = _resolve_profile_progression(state, PROFILES["normal"])
    assert choices and choices[0]["kind"] == "virtude"
    assert state["player"]["pending_choices"] == []


def test_invariantes_novas_detectam_resumo_grounding_recompensa_fuga_e_slo():
    state = _base_state(
        narrative_summary="x" * 1201,
        campaign_plan={"location": "Nova Arcádia", "beats": []},
        world={
            "current_location_id": "brekmar", "current_location": "Brekmar",
            "visited": ["brekmar"], "turn_count": 3,
        },
        messages=[AIMessage(content="Você percebe que nada novo foi obtido.")],
        combat={"active": True, "chase": {"trilha": "afastado"}},
    )
    prev = _base_state()
    prev["world"] = dict(state["world"])
    prev["player"]["gold"] = 0
    state["player"]["gold"] = 15
    violations = invariants.check_all(state, prev, 3, context={
        "decision": {"mode": "flee", "kind": "flee"},
        "resolved_action": {"kind": "flee", "result": "flee_failed"},
        "combat_executed": True,
        "latency_ms": 95_000,
        "real_llm": True,
    })
    ids = {v.check_id for v in violations}
    assert {"memory.summary_bounds", "campaign.region_grounding",
            "narrative.reward_contradiction", "combat.flee_progress_mislabeled",
            "performance.turn_latency"} <= ids
    assert next(v for v in violations if v.check_id == "performance.turn_latency").severity == "error"


def test_summary_agrega_diversidade_slo_e_escolhas():
    rec = TurnRecord(turn=1, action="Viajo", route="storyteller", latency_ms=50_000)
    rec.decision = {"kind": "free_text"}
    rec.progression_choices = [{"kind": "virtude", "choice_id": "x"}]
    result = CampaignResult(
        profile="normal", seed=1, turns_completed=1, errors=[], history=[rec],
        final_state=_base_state(), save_path="save.json",
    )
    summary = build_summary(result, [turn_to_record(rec)])
    assert summary["latency_slo"]["over_warning_45s"] == 1
    assert summary["diversity"]["unique_routes"] == 1
    assert summary["progression_choices"] == 1
