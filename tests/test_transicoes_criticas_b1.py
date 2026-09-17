from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from agents.action_guard import action_guard_node
from agents import combat
from agents.turn_finalizer import turn_finalizer_node
from services import checkpoints
from services import conflict_summary
from services.actor_lifecycle import (
    transition_readiness,
)


def _player(**updates):
    player = {
        "id": "player",
        "name": "Playtest-normal",
        "is_player": True,
        "vitalidade": 0,
        "max_vitalidade": 18,
        "conscious": False,
        "dead": False,
        "estado_terminal": False,
        "last_stand_pending": False,
        "ferimentos": {"leve": [], "grave": [], "critico": []},
    }
    player.update(updates)
    return player


def _state(player=None, **updates):
    state = {
        "game_id": "b1-regression",
        "player": player or _player(conscious=True, vitalidade=10),
        "world": {
            "turn_count": 174,
            "current_location_id": "pradaria_ruinas",
            "current_location": "Pradaria das Ruínas",
            "danger_level": 2,
        },
        "combat": {"active": False, "round": 9, "scene": None},
        "death_pending": False,
        "game_over": False,
    }
    state.update(updates)
    return state


def test_b1_ultima_acao_pendente_nao_e_elegivel_para_fuga_forcada():
    player = _player(last_stand_pending=True, conscious=False)

    assert combat._can_attempt_flee(player) is False
    escaped, chase = combat._enforce_flee_attempt_limit(
        {"eligible": False, "blocked_reason": "last_stand_pending"},
        attempts=combat.MAX_CONSECUTIVE_FLEE_ATTEMPTS,
    )

    assert escaped is False
    assert chase["blocked_reason"] == "last_stand_pending"


def test_decisao_fuga_bloqueada_nao_e_progresso():
    import random

    decision = combat._attempt_flee({}, _player(last_stand_pending=True), [], {}, random.Random(1))
    assert isinstance(decision, combat.FleeDecision)
    assert not decision.eligible and not decision.escaped
    outcome = combat._canonical_player_action(
        None, {}, flee_requested=True, chase_state=decision.chase,
    )
    assert outcome["result"] == "flee_blocked"


def test_boundary_e_checkpoint_recusam_toda_transicao_critica():
    cases = [
        _state(combat={"active": True}),
        _state(death_pending=True),
        _state(player=_player(last_stand_pending=True)),
        _state(player=_player(estado_terminal=True)),
        _state(player=_player(dead=True)),
    ]

    for state in cases:
        assert transition_readiness(state)["ready"] is False
        assert checkpoints.should_checkpoint(state) is False
        assert checkpoints.snapshot(state) is None


def test_restore_sanitiza_checkpoint_legado_envenenado_da_b1():
    poisoned = _state(player=_player(
        dead=False,
        conscious=False,
        last_stand_pending=True,
        ferimentos={
            "leve": [],
            "grave": [],
            "critico": [{"regiao": "torso", "tipo": "perfurante"}],
        },
    ))
    dead = _state(player=_player(dead=True), death_pending=True)

    restored = checkpoints.resolve_death_choice(
        dead,
        "continue",
        checkpoint=poisoned,
    )

    assert restored["player"]["last_stand_pending"] is False
    assert restored["player"]["estado_terminal"] is False
    assert restored["player"]["dead"] is False
    assert restored["player"]["conscious"] is False
    assert transition_readiness(restored)["ready"] is True


def test_load_sanitiza_save_legado_orfao_da_b1():
    from persistence import _raw_to_state, _state_to_save_data

    poisoned = _state(player=_player(
        conscious=False,
        last_stand_pending=True,
        ferimentos={"leve": [], "grave": [], "critico": [{"regiao": "torso"}]},
    ))
    raw = _state_to_save_data(poisoned, poisoned["game_id"])

    loaded = _raw_to_state(raw)

    assert loaded["player"]["last_stand_pending"] is False
    assert loaded["player"]["conscious"] is False
    assert loaded["needs_replan"] is True
    assert transition_readiness(loaded)["ready"] is True


def test_guard_repara_transicao_orfa_uma_vez_sem_consumir_turno():
    state = _state(player=_player(
        conscious=False,
        last_stand_pending=True,
        ferimentos={"leve": [], "grave": [], "critico": [{"regiao": "torso"}]},
    ))
    state["messages"] = [HumanMessage(content="Descanso e aguardo socorro.")]

    first = action_guard_node(state)

    assert first["action_guard_blocked"] is True
    assert first["last_action_outcome"]["code"] == "transition_repair_required"
    assert first["player"]["last_stand_pending"] is False
    assert "world" not in first

    repaired = {**state, **first}
    repaired["messages"] = [*state["messages"], *first["messages"],
                            HumanMessage(content="Descanso e aguardo socorro.")]
    second = action_guard_node(repaired)
    assert second["action_guard_blocked"] is False
    assert second["last_action_outcome"]["code"] == "recovery_requested"


def test_finalizer_usa_readiness_e_recusa_boundary_orfao():
    stable = _state()
    stable["messages"] = []
    stable_out = turn_finalizer_node(stable)["last_turn_outcome"]
    assert stable_out["transition_readiness"] == {
        "ready": True, "code": "ready", "phase": "active",
    }

    combat_state = _state(combat={"active": True})
    combat_state["messages"] = []
    assert (
        turn_finalizer_node(combat_state)["last_turn_outcome"]
        ["transition_readiness"]["code"]
        == "combat_active"
    )

    death_choice = _state(death_pending=True)
    death_choice["messages"] = []
    assert (
        turn_finalizer_node(death_choice)["last_turn_outcome"]
        ["transition_readiness"]["code"]
        == "transition_death_pending"
    )

    orphan = _state(player=_player(last_stand_pending=True))
    orphan["messages"] = []
    with pytest.raises(RuntimeError, match="turn_boundary_not_ready:transition_last_stand"):
        turn_finalizer_node(orphan)


def test_player_downed_e_caido_nunca_morto_no_resumo_ou_fatos():
    player = _player(dead=True, conscious=True)
    summary = conflict_summary.build_summary(
        [player],
        extras={"turn": 134, "downed_ids": ["player"]},
    )

    assert summary["caidos"] == ["Playtest-normal"]
    assert summary["mortos"] == []
    assert summary["sobreviventes"] == ["Playtest-normal"]
    facts = conflict_summary.summary_facts(summary)
    assert facts == ["Playtest-normal caiu no conflito e aguarda recuperação."]
    assert "Caídos: Playtest-normal." in conflict_summary.canonical_summary_text(summary)


def test_player_real_sem_id_ainda_e_reconhecido_como_caido():
    player = _player(dead=True, conscious=False)
    player.pop("id")
    player.pop("is_player")

    summary = conflict_summary.build_summary(
        [player],
        extras={"turn": 199, "downed_ids": combat._downed_identity_tokens(player)},
    )

    assert summary["caidos"] == ["Playtest-normal"]
    assert summary["mortos"] == []
    assert conflict_summary.summary_facts(summary) == [
        "Playtest-normal caiu no conflito e aguarda recuperação."
    ]


def test_morte_confirmada_continua_canonica_e_separada():
    summary = conflict_summary.build_summary([_player(dead=True, conscious=False)])

    assert summary["caidos"] == []
    assert summary["mortos"] == ["Playtest-normal"]
    assert conflict_summary.summary_facts(summary) == [
        "Playtest-normal morreu no conflito."
    ]


def test_cronica_da_queda_nao_afirma_recuperacao_antes_da_escolha():
    from services.chronicle import render_milestone

    text = render_milestone({"type": "player_downed", "payload": {}}, {})
    assert "aguarda uma escolha" in text
    assert "levantou" not in text and "saqueado" not in text
    memorial = render_milestone({"type": "player_died", "payload": {}}, {})
    assert "Aqui termina a saga" in memorial


def test_invariante_curta_detecta_falso_fato_de_morte_na_queda():
    from playtest.invariants import check_false_player_death

    before = _state()
    before["event_log"] = []
    before["memory_facts"] = []
    after = _state(player=_player(name="Playtest-normal"), death_pending=True)
    after["event_log"] = [{
        "event_id": "down-1", "type": "player_downed", "turn": 199,
    }]
    after["memory_facts"] = [{
        "memory_id": "bad-1",
        "text": "Playtest-normal morreu no conflito.",
    }]

    violations = check_false_player_death(after, before, 199)

    assert [violation.check_id for violation in violations] == [
        "narrative.false_player_death"
    ]


def test_invariante_aceita_queda_e_morte_confirmada():
    from playtest.invariants import check_false_player_death

    before = {**_state(), "event_log": [], "memory_facts": []}
    downed = _state(player=_player(name="Playtest-normal"), death_pending=True)
    downed["event_log"] = [{"event_id": "down", "type": "player_downed"}]
    downed["memory_facts"] = [{
        "memory_id": "good", "text": "Playtest-normal caiu no conflito.",
    }]
    assert check_false_player_death(downed, before, 1) == []

    memorial = {**downed, "game_over": True}
    memorial["event_log"] = [
        *downed["event_log"], {"event_id": "died", "type": "player_died"},
    ]
    memorial["memory_facts"] = [{
        "memory_id": "death", "text": "Playtest-normal morreu no conflito.",
    }]
    assert check_false_player_death(memorial, before, 2) == []


def test_memoria_recusa_morte_do_player_sem_evento_terminal():
    from services.memory_provenance import make_memory_fact, validate_memory_fact

    state = _state(player=_player(name="Playtest-normal"), death_pending=True)
    state["event_log"] = [{
        "event_id": "down-1", "type": "player_downed", "target_id": "player",
    }]
    bad = make_memory_fact(
        "Playtest-normal morreu no conflito.",
        provenance="canonical_event", source_id="down-1", source_turn=199,
    )
    good = make_memory_fact(
        "Playtest-normal caiu no conflito e aguarda recuperação.",
        provenance="canonical_event", source_id="down-1", source_turn=199,
    )

    assert validate_memory_fact(bad, state)[1] == "player_downed_not_dead"
    assert validate_memory_fact(good, state)[0] is not None


def test_contexto_omite_fato_legado_falso_sem_apagar_o_ledger():
    from services.context_builder import active_memory_facts
    from services.memory_provenance import make_memory_fact

    state = _state(player=_player(name="Playtest-normal"), death_pending=True)
    state["event_log"] = [{"event_id": "down", "type": "player_downed"}]
    bad = make_memory_fact(
        "Playtest-normal morreu no conflito.",
        provenance="canonical_event", source_id="down", source_turn=10,
    )
    good = make_memory_fact(
        "Playtest-normal caiu no conflito.",
        provenance="canonical_event", source_id="down", source_turn=10,
    )
    ledger = [bad, good]

    active = active_memory_facts(ledger, current_turn=11, state=state)

    assert [row["text"] for row in active] == ["Playtest-normal caiu no conflito."]
    assert len(ledger) == 2
