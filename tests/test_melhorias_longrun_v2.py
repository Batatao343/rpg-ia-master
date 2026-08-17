from copy import deepcopy

from services import checkpoints, combat_origin, continuity, objectives, quest_log, social_direction
from playtest.runner import TurnRecord
from playtest.telemetry import turn_to_record


def test_objetivo_publico_nao_expoe_beat_privado():
    plan = {
        "arc_title": "Cinzas no Caminho",
        "current_step": 0,
        "beats": [{"description": "Descreva o traidor escondido sob a ponte."}],
        "climax": "Revele que o regente é o traidor.",
    }
    view = objectives.public_objective(
        plan, [], {"current_location": "Nova Arcádia", "current_location_id": "nova_arcadia"}
    )
    assert "Descreva" not in view["objective"]
    assert "traidor" not in view["objective"].lower()
    assert "Nova Arcádia" in view["objective"]


def test_objetivo_publico_prioriza_side_quest_ativa():
    view = objectives.public_objective({}, [{
        "id": "q1", "title": "A Ponte Partida", "description": "Inspecione os pilares.",
        "status": "active", "location_id": "ponte",
    }], {"current_location": "Campo"})
    assert view["source"] == "side_quest"
    assert view["quest_id"] == "q1"
    assert view["objective"] == "Inspecione os pilares."


def test_quest_tem_progresso_e_recompensa_idempotentes(monkeypatch):
    monkeypatch.setattr(quest_log, "_valid_location_ids", lambda: {"ponte"})
    monkeypatch.setattr(quest_log, "_valid_entity_ids", lambda: set())
    quests, created = quest_log.register_proposed_quests([], [{
        "title": "A Ponte Partida", "description": "Inspecione os pilares.",
        "location_id": "ponte",
    }], turn=3)
    assert created[0]["progress_log"] == [{"kind": "created", "turn": 3, "detail": ""}]

    progressed = quest_log.sync_location_progress(quests, "ponte", turn=4)
    progressed_twice = quest_log.sync_location_progress(progressed, "ponte", turn=5)
    assert [r["kind"] for r in progressed_twice[0]["progress_log"]].count("location_reached") == 1

    completed, reward = quest_log.complete_quest_with_reward(progressed_twice, created[0]["id"], 6)
    completed2, reward2 = quest_log.complete_quest_with_reward(completed, created[0]["id"], 7)
    assert reward == quest_log.QUEST_REWARD_GOLD
    assert reward2 == 0
    assert completed2[0]["reward_delivered"] is True
    assert completed2[0]["reward_gold"] == quest_log.QUEST_REWARD_GOLD


def test_direcao_social_usa_destino_canonico(monkeypatch):
    monkeypatch.setattr("gamedata.get_connections", lambda _loc: [
        {"id": "mercado", "name": "Mercado Velho", "danger": 1},
    ])
    hint = social_direction.build_social_direction({
        "world": {"current_location_id": "ermo", "current_location": "Ermo"},
        "npcs": {}, "quests": [], "campaign_plan": {},
    })
    assert "Mercado Velho" in hint


def test_origem_de_combate_tem_vocabulario_fechado_e_prioriza_cena_nova():
    assert combat_origin.normalize("qualquer") == "unknown"
    assert combat_origin.from_encounter({"reason": "reinforcements"}, {}) == "regional_danger"
    assert combat_origin.from_encounter({}, {"chase": {"active": True}}) == "pursuit_recurrence"
    assert combat_origin.materialize(
        {"origin": "travel_encounter"}, "player_provoked"
    ) == "player_provoked"


def test_restore_preserva_metatempo_e_registra_consequencia():
    checkpoint = {
        "game_id": "g", "world": {"turn_count": 10, "current_location": "Ponte"},
        "continuity": {"session_action_count": 10, "timeline_epoch": 0,
                       "last_checkpoint_turn": 10, "death_history": []},
        "death_pending": False,
    }
    dead = deepcopy(checkpoint)
    dead["world"]["turn_count"] = 14
    dead["world"]["current_location"] = "Ruínas"
    dead["continuity"]["session_action_count"] = 14
    dead["death_pending"] = True
    dead["combat"] = {"death_context": {"killer": "Carniçal"}}

    restored = checkpoints.resolve_death_choice(dead, "continue", checkpoint=checkpoint)
    meta = restored["continuity"]
    assert restored["world"]["turn_count"] == 10
    assert meta["session_action_count"] == 14
    assert meta["timeline_epoch"] == 1
    assert meta["death_history"][-1]["lost_canonical_turns"] == 4
    assert meta["death_history"][-1]["cause"] == "Carniçal"


def test_continuidade_migrada_e_incrementada_sem_confundir_turno():
    normalized = continuity.normalize({}, canonical_turn=8)
    assert normalized["session_action_count"] == 8
    bumped = continuity.advance_action(normalized, canonical_turn=9)
    assert bumped["session_action_count"] == 9
    assert bumped["timeline_epoch"] == 0
    first_player_action = continuity.advance_action(
        {"session_action_count": 0, "timeline_epoch": 0,
         "last_checkpoint_turn": 1, "death_history": []}, canonical_turn=2,
    )
    assert first_player_action["session_action_count"] == 1


def test_turn_record_serializa_latencia_origem_e_tres_relogios():
    rec = TurnRecord(turn=1, action="olho ao redor", route="storyteller", latency_ms=30)
    rec.node_latency_ms = {"campaign_manager": 5, "storyteller": 20}
    rec.combat_origin = "travel_encounter"
    rec.session_action_count = 12
    rec.canonical_turn = 9
    rec.timeline_epoch = 1
    row = turn_to_record(rec)
    assert row["node_latency_ms"]["storyteller"] == 20
    assert row["combat_origin"] == "travel_encounter"
    assert (row["session_action_count"], row["canonical_turn"], row["timeline_epoch"]) == (12, 9, 1)


def test_inferencia_repetida_nao_se_promove_sozinha():
    from services.memory_provenance import commit_memory_facts
    fact = {"text": "Talvez a torre esteja vazia", "provenance": "inference",
            "confidence": "speculative", "source_turn": 1}
    ledger, promotions = commit_memory_facts([fact], [{**fact, "source_turn": 2}])
    assert ledger[0]["confidence"] == "speculative"
    assert promotions == 0
