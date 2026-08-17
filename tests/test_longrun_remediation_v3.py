import json

from services import checkpoints, combat_origin, quest_log


def _state(turn=10, *, active=False):
    return {
        "game_id": "test", "world": {"turn_count": turn, "danger_level": 1,
        "current_location_id": "brekmar", "current_location": "Brekmar"},
        "combat": {"active": active, "round": 3, "origin": "player_provoked"},
        "enemies": [{"id": "e", "name": "Esqueleto"}] if active else [],
        "player": {"vitalidade": 0 if active else 10, "max_vitalidade": 18,
                   "dead": active, "conscious": not active},
        "continuity": {"session_action_count": turn, "timeline_epoch": 0,
                       "last_checkpoint_turn": turn, "death_history": []},
        "death_pending": active, "game_over": False,
    }


def test_checkpoint_nunca_e_gravado_durante_combate():
    assert checkpoints.should_checkpoint(_state(active=True)) is False
    assert checkpoints.snapshot(_state(active=True)) is None
    assert checkpoints.persistence.save_checkpoint(_state(active=True)) is False


def test_checkpoint_legado_ativo_e_saneado_no_restore():
    dead = _state(14, active=True)
    legacy = _state(10, active=True)
    restored = checkpoints.resolve_death_choice(dead, "continue", checkpoint=legacy)
    assert restored["combat"]["active"] is False
    assert restored["enemies"] == []
    assert restored["player"]["vitalidade"] >= 1
    assert restored["player"]["dead"] is False
    assert restored["player"]["conscious"] is True


def test_hint_novo_de_origem_vence_cena_anterior():
    assert combat_origin.materialize(
        {"origin": "player_provoked"}, "travel_encounter"
    ) == "travel_encounter"


def test_origem_de_encontro_distingue_descanso_e_viagem():
    assert combat_origin.from_encounter({}, {}, trigger="rest") == "regional_danger"
    assert combat_origin.from_encounter({}, {}, trigger="travel") == "travel_encounter"


def test_quest_fecha_apos_local_e_duas_acoes_verificaveis():
    quest = {"id": "q", "title": "Varo", "description": "Ache Varo",
             "status": "active", "location_id": "brekmar",
             "progress_log": [{"kind": "created", "turn": 1, "detail": ""}]}
    quests = quest_log.sync_location_progress([quest], "brekmar", turn=2)
    quests, ready = quest_log.sync_action_progress(
        quests, "brekmar", "Investigo pistas de Varo", turn=3,
    )
    assert ready == []
    quests, ready = quest_log.sync_action_progress(
        quests, "brekmar", "Procuro o próximo passo da missão Varo", turn=4,
    )
    assert ready == ["q"]
    assert quests[0]["completion_ready"] is True


def test_acao_generica_nao_avanca_quest():
    quest = {"id": "q", "title": "Varo", "status": "active",
             "location_id": "brekmar", "progress_log": []}
    quests, ready = quest_log.sync_action_progress(
        [quest], "brekmar", "Olho o céu", turn=2,
    )
    assert ready == []
    assert quests[0].get("progress_log") == []


def test_especulacao_antiga_e_omitida_do_contexto():
    from services.context_builder import active_memory_facts
    rows = [
        {"text": "talvez", "provenance": "inference", "confidence": "speculative",
         "source_turn": 1},
        {"text": "relato", "provenance": "npc_claim", "confidence": "reported",
         "source_turn": 1, "source_id": "npc:x"},
    ]
    active = active_memory_facts(rows, current_turn=25)
    assert [row["text"] for row in active] == ["relato"]


def test_preparacao_de_cena_nao_invoca_llm(monkeypatch):
    import agents.combat as combat
    monkeypatch.setattr(combat, "get_llm", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("não deve chamar LLM para geometria")))
    monkeypatch.setattr(combat, "build_context_pack", lambda *a, **k: type(
        "Pack", (), {"world_state_block": ""})())
    player = {"id": "player", "name": "Heroi"}
    enemy = {"id": "e", "name": "Esqueleto"}
    scene = combat._prepare_scene(_state(active=False), [enemy], player, [])
    assert scene["frozen"] is True
    assert scene["zones"]
    assert scene["positions"]["player"]


def test_summary_usa_historico_de_morte_que_nao_retrocede():
    from playtest import telemetry
    from playtest.runner import CampaignResult
    final = {
        "player": {}, "world": {}, "event_log": [],
        "continuity": {"death_history": [{
            "epoch": 2, "session_action": 31, "death_turn": 18,
            "location": "Brekmar", "cause": "Lobo",
        }]},
    }
    result = CampaignResult(
        profile="explorador", seed=1, turns_completed=0, errors=[], history=[],
        final_state=final, save_path="", turns_requested=0,
    )
    summary = telemetry.build_summary(result, [])
    assert summary["downed_count"] == 1
    assert summary["deaths_log"][0] == {
        "turn": 31, "session_action": 31, "canonical_turn": 18,
        "timeline_epoch": 2, "location": "Brekmar", "cause": "Lobo",
    }


def test_coverage_deduplica_mesmo_conflito_no_mesmo_epoch():
    from playtest import telemetry
    from playtest.runner import CampaignResult
    rows = [{
        "turn": turn, "combat_started": True,
        "conflict_instance_id": "g:0:3", "timeline_epoch": 0,
    } for turn in (3, 4)]
    result = CampaignResult(
        profile="explorador", seed=1, turns_completed=2, errors=[], history=[],
        final_state={"player": {}, "world": {}, "event_log": []},
        save_path="", turns_requested=2,
    )
    coverage = telemetry.build_summary(result, rows)["combat_coverage"]
    assert coverage["started"] == 1
    assert coverage["replayed_starts"] == 1


def test_manifesto_abortado_aceita_prefixo_timeout_valido(tmp_path, monkeypatch):
    from playtest import telemetry
    from playtest.runner import CampaignResult, TurnRecord
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    save = tmp_path / "save.json"
    save.write_text(json.dumps({"game_id": "game-timeout"}), encoding="utf-8")
    telemetry.begin_run(
        "abort-prefix", profiles=["explorador"], turns=3, seed=1, real=False,
    )
    rec = TurnRecord(
        turn=1, action="Ajo.", route="timeout", latency_ms=120_000,
        nodes_executed=["campaign_manager", "dm_router"],
        node_latency_ms={"campaign_manager": 10},
        decision={"text": "Ajo.", "mode": "free_text", "kind": "free_text"},
        error="PlaytestTimeoutError()",
    )
    result = CampaignResult(
        profile="explorador", seed=1, turns_completed=1,
        errors=[{"turn": 1, "exc": rec.error}], history=[rec],
        final_state={
            "game_id": "game-timeout", "player": {}, "world": {},
            "event_log": [],
        },
        save_path=str(save), turns_requested=3,
        aborted_reason="timeout: turno 1 excedeu 120s",
    )
    telemetry.persist_campaign("abort-prefix", result)
    inspected = telemetry.finish_run(
        "abort-prefix", status="aborted", reason=result.aborted_reason,
    )
    assert inspected["complete"] is False
    assert inspected["invalid_jsonls"] == []
