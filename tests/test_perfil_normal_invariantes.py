import random

from langchain_core.messages import AIMessage

import progression
from playtest import invariants
from playtest.profiles import PROFILES
from playtest.runner import CampaignResult, TurnRecord, _resolve_profile_progression
from playtest.runner import _campaign_experience_violations
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
    action = profile.decide(state, random.Random(1)).text
    assert "Mara" in action
    assert "tarefa concreta" in action.lower()


def test_perfil_normal_nao_le_beat_privado_nem_ecoa_metalinguagem():
    profile = PROFILES["normal"]
    profile.reset()
    state = _base_state(campaign_plan={
        "beats": [{"description": "SENTINELA_PRIVADA Descreva o dragão."}],
        "current_step": 0,
        "climax": "SENTINELA_CLIMAX",
    })

    actions = [profile.decide(state, random.Random(3)).text for _ in range(7)]
    corpus = " ".join(actions).casefold()
    assert "sentinela" not in corpus
    assert "descreva" not in corpus
    assert "beat" not in corpus


def test_perfil_normal_aplica_cooldown_pos_combate_antes_de_nova_ameaca():
    profile = PROFILES["normal"]
    profile.reset()
    combat = _base_state(
        combat={"active": True, "round": 1},
        enemies=[{"id": "lobo", "name": "Lobo", "status": "ativo"}],
    )
    profile.decide(combat, random.Random(2))

    safe = _base_state()
    actions = [profile.decide(safe, random.Random(2)).text for _ in range(12)]
    assert not any("ataco para me defender" in action.casefold() for action in actions)


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


def test_perfil_normal_recuando_a_partir_da_quarta_rodada():
    profile = PROFILES["normal"]
    profile.reset()
    state = _base_state(
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


def test_summary_agrega_conversao_de_quest_e_percentual_de_combate():
    records = []
    for turn in range(1, 11):
        rec = TurnRecord(
            turn=turn,
            action="Peço uma tarefa concreta" if turn in (1, 3) else "Exploro",
            route="combat_agent" if turn in (5, 6, 7) else "storyteller",
            latency_ms=1,
        )
        rec.quest_requested = turn in (1, 3)
        rec.quests_before = 0
        rec.quests_after = 1 if turn == 3 else 0
        records.append(rec)
    result = CampaignResult(
        profile="normal", seed=1, turns_completed=10, errors=[], history=records,
        final_state=_base_state(quests=[{"id": "q1", "status": "active"}]),
        save_path="save.json",
    )

    summary = build_summary(result, [turn_to_record(rec) for rec in records])

    balance = summary["experience_balance"]
    assert balance["quest_requests"] == 2
    assert balance["quest_request_conversions"] == 1
    assert balance["quest_conversion_pct"] == 50.0
    assert balance["combat_turn_pct"] == 30.0


def test_invariante_rejeita_metalinguagem_privada_do_perfil_normal():
    violations = invariants.check_all(
        _base_state(), _base_state(), 8,
        context={
            "profile": "normal",
            "action": "Tento cumprir o beat: Descreva a praça.",
        },
    )
    assert any(
        violation.check_id == "profile.private_plan_leak"
        and violation.severity == "error"
        for violation in violations
    )


def test_oraculos_de_campanha_alertam_combate_e_zero_conversao():
    history = []
    for turn in range(1, 51):
        rec = TurnRecord(
            turn=turn,
            action="Peço uma tarefa concreta" if turn in (2, 10) else "Exploro",
            route="combat_agent" if turn <= 18 else "storyteller",
            latency_ms=1,
        )
        rec.quest_requested = turn in (2, 10)
        history.append(rec)

    violations = _campaign_experience_violations(
        "normal", history, _base_state(),
    )

    assert {item["check_id"] for item in violations} == {
        "profile.combat_share", "profile.quest_conversion_empty",
    }


def test_mock_npc_propoe_quest_somente_apos_pedido_concreto():
    from langchain_core.messages import HumanMessage
    from agents.npc import NPCResponse
    import mock_llm

    ordinary = mock_llm._npc_response(
        NPCResponse, [HumanMessage(content="Conte um rumor.")],
    )
    requested = mock_llm._npc_response(
        NPCResponse,
        [HumanMessage(content="Você tem uma tarefa concreta ou favor concreto?")],
    )

    assert ordinary.proposed_quests == []
    assert len(requested.proposed_quests) == 1
