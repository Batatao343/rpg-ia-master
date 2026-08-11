"""Regressões do hardening de observabilidade do playtest."""
from __future__ import annotations

import json
from dataclasses import dataclass

from playtest import invariants, report, telemetry
from playtest.runner import CampaignResult, TurnRecord, _run_turn


def _result(**overrides) -> CampaignResult:
    data = {
        "profile": "explorador",
        "seed": 1,
        "turns_completed": 1,
        "errors": [],
        "history": [],
        "final_state": {"player": {}, "world": {}, "event_log": []},
        "save_path": "",
        "turns_requested": 1,
    }
    data.update(overrides)
    return CampaignResult(**data)


def _persist_formal_campaign(
    tmp_path,
    monkeypatch,
    *,
    run_id="run-formal",
    real=False,
    invariants_enabled=True,
    startup_llm_events=None,
):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path / "runs"))
    save = tmp_path / "save.json"
    save.write_text(
        json.dumps({"game_id": "game-formal", "player": {"name": "Playtest-explorador"}}),
        encoding="utf-8",
    )
    telemetry.begin_run(
        run_id,
        profiles=["explorador"],
        turns=1,
        seed=1,
        real=real,
        invariants_enabled=invariants_enabled,
    )
    rec = TurnRecord(
        turn=1,
        action="Observo.",
        route="storyteller",
        latency_ms=2,
        nodes_executed=["storyteller", "archivist"],
        decision={"text": "Observo.", "mode": "free_text", "kind": "free_text"},
    )
    result = _result(
        history=[rec],
        final_state={
            "game_id": "game-formal",
            "player": {},
            "world": {},
            "event_log": [],
        },
        save_path=str(save),
        mock=not real,
        startup_llm_events=list(startup_llm_events or []),
        invariants_enabled=invariants_enabled,
    )
    telemetry.persist_campaign(run_id, result)
    return tmp_path / "runs" / run_id, save


def test_run_turn_registra_todos_os_nos_inclusive_combate_aninhado():
    class Graph:
        def stream(self, state, stream_mode=None):
            yield "updates", {"campaign_manager": {}}
            yield "updates", {"dm_router": {"next": "storyteller"}}
            yield "updates", {"storyteller": {"next": "combat_agent"}}
            yield "updates", {"combat_agent": {
                "combat": {
                    "active": True,
                    "last_reactions": [{"actor_id": "e1", "card_id": "aparar"}],
                },
                "tactics": [{
                    "actor_id": "e1",
                    "action": "attack",
                    "target_id": "player",
                }],
                "enemies": [],
                "conflict_summary": {
                    "ferimentos": {
                        "Inimigo": [{
                            "categoria": "critico",
                            "regiao": "torso",
                        }],
                    },
                },
            }}
            yield "updates", {"archivist": {}}
            yield "values", {**state, "combat": {"active": True, "round": 1}}

    nodes: list[str] = []
    observations: dict = {}
    _state, route = _run_turn(
        Graph(),
        {"combat": {"active": False}},
        nodes_executed=nodes,
        node_observations=observations,
    )
    assert route == "storyteller"
    assert nodes == [
        "campaign_manager", "dm_router", "storyteller", "combat_agent", "archivist",
    ]
    assert observations["combat_agent"]["conflict_summary"]["ferimentos"][
        "Inimigo"
    ][0]["regiao"] == "torso"
    assert observations["combat_agent"]["tactics"][0]["actor_id"] == "e1"


def test_runner_conta_rejeicao_nova_com_buffer_100_para_100(
    tmp_path,
    monkeypatch,
):
    import main
    from playtest import runner

    previous = [
        {
            "turn": index,
            "type": "evento_inventado",
            "target_id": f"alvo_{index}",
            "reason": f"motivo {index}",
        }
        for index in range(100)
    ]
    appended = {
        "turn": 101,
        "type": "evento_inventado",
        "target_id": "alvo_novo",
        "reason": "tipo não permitido",
    }

    class CappedRejectionGraph:
        def invoke(self, state, *_args, **_kwargs):
            return {**state, "event_rejections": list(previous)}

        def stream(self, state, stream_mode=None):
            yield "updates", {"campaign_manager": {}}
            yield "updates", {"dm_router": {"next": "storyteller"}}
            yield "updates", {"storyteller": {}}
            yield "updates", {"archivist": {}}
            yield "values", {
                **state,
                "event_rejections": [*previous[1:], appended],
            }

    monkeypatch.setattr(main, "app", CappedRejectionGraph())
    monkeypatch.setattr(
        runner,
        "PLAYTEST_SAVES_DIR",
        str(tmp_path / "saves-playtest"),
    )

    result = runner.run_campaign(
        "explorador",
        turns=1,
        seed=1,
        invariants=False,
    )

    assert result.errors == []
    assert result.history[0].events_rejected == 1


def test_excecao_de_check_vira_invariant_crash(monkeypatch):
    def broken(_state, _prev, _turn):
        raise RuntimeError("falha plantada")

    monkeypatch.setattr(invariants, "CHECKS", [broken])
    violations = invariants.check_all({}, turn=4)
    assert len(violations) == 1
    assert violations[0].check_id == "invariant.crash"
    assert violations[0].severity == "error"
    assert violations[0].details["check"] == "broken"
    assert "RuntimeError" in violations[0].message


def test_no_progress_so_falha_no_limiar_e_reseta_com_progresso():
    assert invariants.check_combat_no_progress(
        {"combat_no_progress_streak": invariants.COMBAT_NO_PROGRESS_LIMIT - 1},
        turn=7,
    ) == []
    violation = invariants.check_combat_no_progress(
        {"combat_no_progress_streak": invariants.COMBAT_NO_PROGRESS_LIMIT},
        turn=8,
    )
    assert violation[0].check_id == "combat.no_progress"

    base = {
        "player": {"vitalidade": 4, "ferimentos": {}},
        "enemies": [{"id": "e1", "status": "ativo", "vitalidade": 4, "ferimentos": {}}],
        "combat": {"active": True, "scene": {"positions": {}}},
    }
    changed = {
        **base,
        "enemies": [{"id": "e1", "status": "ativo", "vitalidade": 3, "ferimentos": {}}],
    }
    assert invariants.combat_progress_fingerprint(base) != \
        invariants.combat_progress_fingerprint(changed)


def test_invariante_detecta_summary_com_conflict_id_ja_consumido():
    state = {
        "conflict_summary": {"conflict_id": "conflict-duplicado"},
        "consumed_conflict_ids": ["conflict-duplicado"],
    }
    violations = invariants.check_all(state, turn=12)
    duplicate = [
        violation for violation in violations
        if violation.check_id == "summary.duplicate_consumption"
    ]
    assert len(duplicate) == 1
    assert duplicate[0].severity == "error"
    assert duplicate[0].details["conflict_id"] == "conflict-duplicado"


def test_combate_encerrado_nao_pode_deixar_summary_pendente_no_mesmo_invoke():
    state = {
        "combat": {"active": False},
        "conflict_summary": {"conflict_id": "conflict-pendente"},
        "chronicle": [],
        "world": {"turn_count": 12},
        "rag_persistence_error": None,
    }

    violations = invariants.check_all(
        state,
        turn=12,
        context={"combat_ended": True},
    )

    lifecycle = [
        violation for violation in violations
        if violation.check_id == "summary.lifecycle"
    ]
    assert len(lifecycle) == 1
    assert lifecycle[0].details["conflict_id"] == "conflict-pendente"


def test_invariante_detecta_ultimo_critico_sem_fluxo_terminal():
    state = {
        "player": {
            "is_player": True,
            "ferimento_espacos": {"leve": 1, "grave": 1, "critico": 1},
            "ferimentos": {
                "leve": [], "grave": [], "critico": [{"regiao": "torso"}],
            },
        },
        "world": {"turn_count": 2},
    }
    violations = invariants.check_all(state, turn=2)
    assert "wound.capacity" in {item.check_id for item in violations}


def test_summary_pendente_apos_combate_aceita_erro_rag_explicito():
    state = {
        "combat": {"active": False},
        "conflict_summary": {"conflict_id": "conflict-retry"},
        "chronicle": [],
        "world": {"turn_count": 12},
        "rag_persistence_error": "Falha ao persistir memória de sessão.",
    }

    violations = invariants.check_all(
        state,
        turn=12,
        context={"combat_ended": True},
    )

    assert not any(
        violation.check_id == "summary.lifecycle"
        for violation in violations
    )


def test_hp_zero_vivo_nao_cria_primeira_morte():
    result = _result(
        history=[
            TurnRecord(
                turn=1,
                action="Continuo.",
                route="storyteller",
                latency_ms=1,
                player_hp=0,
                player_max_hp=12,
            )
        ],
    )
    rows = [telemetry.turn_to_record(result.history[0])]
    summary = telemetry.build_summary(result, rows)
    assert summary["deaths"] == 0
    assert summary["first_death_turn"] is None


def test_deaths_log_define_primeira_e_ultima_morte():
    deaths = [
        {"turn": 3, "location": "Nova Arcádia", "cause": "Lobo"},
        {"turn": 9, "location": "Skallgard", "cause": "Afogado"},
    ]
    summary = telemetry.build_summary(
        _result(deaths_log=deaths),
        [],
    )
    assert summary["deaths"] == 2
    assert summary["first_death_turn"] == 3
    assert summary["death_location"] == "Nova Arcádia"
    assert summary["death_cause"] == "Lobo"
    assert summary["last_death_turn"] == 9
    assert summary["last_death_location"] == "Skallgard"
    assert summary["deaths_log"] == deaths


def test_violation_details_sobrevivem_jsonl_summary_e_report(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    detail = {
        "check_id": "invariant.crash",
        "severity": "error",
        "turn": 1,
        "message": "broken levantou RuntimeError",
        "details": {"check": "broken"},
    }
    rec = TurnRecord(
        turn=1,
        action="Ajo.",
        route="storyteller",
        latency_ms=2,
        violations=["invariant.crash"],
        violation_details=[detail],
    )
    result = _result(history=[rec], violations=[detail])
    summary = telemetry.persist_campaign("run-detail", result)

    with open(tmp_path / "run-detail" / "explorador_1.jsonl", encoding="utf-8") as fp:
        row = json.loads(fp.readline())
    assert row["violation_details"] == [detail]
    assert summary["violation_samples"]["invariant.crash"]["message"] == \
        "broken levantou RuntimeError"

    markdown = report.render_markdown(report.aggregate(str(tmp_path / "run-detail")))
    assert "invariant.crash" in markdown
    assert "broken levantou RuntimeError" in markdown
    assert "error" in markdown


@dataclass(frozen=True)
class _Attempt:
    provider: str = "deepseek"
    model: str = "deepseek-v4-flash"
    tier: str = "fast"
    latency_ms: int = 17
    fell_back: bool = False
    outcome: str = "invoke_error"
    error: str = "HTTP 500"
    structured: bool = True


def test_evento_de_tentativa_e_normalizado_sem_vazar_payload():
    from playtest.runner import _normalize_llm_event

    event = _normalize_llm_event(_Attempt())
    assert event["status"] == "invoke_error"
    assert event["network_attempted"] is True
    assert event["provider"] == "deepseek"
    assert "prompt" not in event
    assert event["error"] == "HTTP 500"

    build = _normalize_llm_event(
        {
            "provider": "anthropic",
            "model": "claude",
            "tier": "smart",
            "outcome": "build_error",
            "error": "missing dep",
        }
    )
    assert build["network_attempted"] is False

    circuit = _normalize_llm_event({
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "tier": "fast",
        "outcome": "circuit_open",
        "error": "402 Payment Required",
    })
    assert circuit["network_attempted"] is False


def test_circuit_open_e_skip_auditavel_sem_request_custo_ou_falha():
    from playtest.runner import _normalize_llm_event

    circuit = _normalize_llm_event({
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "tier": "fast",
        "outcome": "circuit_open",
        "error": "402 Payment Required",
    })
    rec = TurnRecord(
        turn=1,
        action="Observo.",
        route="storyteller",
        latency_ms=1,
        llm_events=[circuit],
    )
    result = _result(history=[rec], startup_llm_events=[dict(circuit)])

    summary = telemetry.build_summary(
        result, [telemetry.turn_to_record(rec)],
    )

    assert summary["llm_attempts"] == 2
    assert summary["llm_skipped"] == 2
    assert summary["llm_failures"] == 0
    assert summary["llm_network_requests"] == 0
    assert summary["llm_requests_by_provider"] == {}
    assert summary["cost_usd_total"] == 0
    assert summary["startup_llm_network_successes"] == 0


def test_startup_entra_no_total_de_tentativas_e_custo():
    startup = [{
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "tier": "smart",
        "status": "success",
        "network_attempted": True,
        "latency_ms": 10,
        "fell_back": False,
    }]
    turn_event = {
        **startup[0],
        "tier": "fast",
        "status": "invoke_error",
    }
    rec = TurnRecord(
        turn=1,
        action="Ajo.",
        route="storyteller",
        latency_ms=1,
        llm_events=[turn_event],
    )
    result = _result(history=[rec], startup_llm_events=startup)
    summary = telemetry.build_summary(result, [telemetry.turn_to_record(rec)])
    assert summary["llm_attempts"] == 2
    assert summary["llm_successes"] == 1
    assert summary["llm_failures"] == 1
    assert summary["startup_llm_attempts"] == 1
    assert summary["cost_usd_total"] > 0


def test_manifest_detecta_campanha_ou_turnos_ausentes(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    telemetry.begin_run(
        "run-incomplete",
        profiles=["explorador", "fujao"],
        turns=3,
        seed=1,
        real=False,
    )
    telemetry.persist_campaign(
        "run-incomplete",
        _result(profile="explorador", turns_requested=3, turns_completed=2),
    )
    telemetry.finish_run("run-incomplete", status="failed")

    aggregated = report.aggregate(str(tmp_path / "run-incomplete"))
    assert aggregated.complete is False
    assert aggregated.status == "failed"
    markdown = report.render_markdown(aggregated)
    assert "INCOMPLETA" in markdown
    assert "fujao" in markdown


def test_manifest_valida_parse_e_presenca_de_summary_e_jsonl(tmp_path, monkeypatch):
    run_dir, _save = _persist_formal_campaign(tmp_path, monkeypatch)
    (run_dir / "explorador_1.summary.json").write_text("{quebrado", encoding="utf-8")
    (run_dir / "explorador_1.jsonl").unlink()

    inspected = telemetry.finish_run("run-formal", status="complete")

    assert inspected["complete"] is False
    assert inspected["invalid_summaries"]
    assert inspected["missing_jsonls"] == ["explorador_1.jsonl"]


def test_manifest_rejeita_jsonl_corrompido_ou_com_turnos_incoerentes(
    tmp_path,
    monkeypatch,
):
    run_dir, _save = _persist_formal_campaign(tmp_path, monkeypatch)
    jsonl = run_dir / "explorador_1.jsonl"
    jsonl.write_text(
        json.dumps({"turn": 2, "route": "storyteller"}) + "\n{quebrado\n",
        encoding="utf-8",
    )

    inspected = telemetry.finish_run("run-formal", status="complete")

    assert inspected["complete"] is False
    assert inspected["invalid_jsonls"]


def test_run_legado_sem_manifesto_nao_e_aceite_formal(tmp_path):
    run_dir = tmp_path / "legacy"
    run_dir.mkdir()
    (run_dir / "explorador_1.summary.json").write_text("{}", encoding="utf-8")

    inspected = telemetry.inspect_run(str(run_dir))

    assert inspected["manifest"] is False
    assert inspected["status"] == "legacy"
    assert inspected["complete"] is False
    assert inspected["data_complete"] is False


def test_run_real_exige_sucesso_de_rede_e_nao_apenas_intencao(
    tmp_path,
    monkeypatch,
):
    build_skip = {
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "tier": "smart",
        "status": "build_error",
        "network_attempted": False,
        "latency_ms": 1,
        "fell_back": False,
    }
    _run_dir, _save = _persist_formal_campaign(
        tmp_path,
        monkeypatch,
        real=True,
        startup_llm_events=[build_skip],
    )

    inspected = telemetry.finish_run("run-formal", status="complete")

    assert inspected["complete"] is False
    assert any(
        "sucesso de rede" in error
        for error in inspected["configuration_errors"]
    )


def test_run_real_com_sucesso_de_rede_pode_fechar_verde(
    tmp_path,
    monkeypatch,
):
    success = {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "tier": "smart",
        "status": "success",
        "network_attempted": True,
        "latency_ms": 12,
        "fell_back": False,
    }
    _run_dir, _save = _persist_formal_campaign(
        tmp_path,
        monkeypatch,
        real=True,
        startup_llm_events=[success],
    )

    inspected = telemetry.finish_run("run-formal", status="complete")

    assert inspected["complete"] is True
    assert inspected["configuration_errors"] == []


def test_manifest_rejeita_summary_parseavel_com_campos_incoerentes(
    tmp_path,
    monkeypatch,
):
    run_dir, _save = _persist_formal_campaign(tmp_path, monkeypatch)
    summary_path = run_dir / "explorador_1.summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["turns_completed"] = 99
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    inspected = telemetry.finish_run("run-formal", status="complete")

    assert inspected["complete"] is False
    assert any(
        item["field"] == "summary.turns_completed"
        for item in inspected["artifact_mismatches"]
    )


def test_no_invariants_nunca_fecha_run_formal_verde(tmp_path, monkeypatch):
    _run_dir, _save = _persist_formal_campaign(
        tmp_path,
        monkeypatch,
        invariants_enabled=False,
    )

    inspected = telemetry.finish_run("run-formal", status="complete")

    assert inspected["complete"] is False
    assert any(
        "invariantes" in error.casefold()
        for error in inspected["configuration_errors"]
    )


def test_manifest_e_summary_vinculam_save_e_game_id(tmp_path, monkeypatch):
    run_dir, save = _persist_formal_campaign(tmp_path, monkeypatch)

    inspected = telemetry.finish_run("run-formal", status="complete")
    summary = json.loads(
        (run_dir / "explorador_1.summary.json").read_text(encoding="utf-8")
    )
    meta = json.loads((run_dir / "run.meta.json").read_text(encoding="utf-8"))
    campaign = meta["campaigns"]["explorador_1"]
    row = json.loads(
        (run_dir / "explorador_1.jsonl").read_text(encoding="utf-8")
    )

    assert inspected["complete"] is True
    assert summary["game_id"] == "game-formal"
    assert summary["save_path"] == str(save.resolve())
    assert campaign["game_id"] == "game-formal"
    assert campaign["save_path"] == str(save.resolve())
    assert row["game_id"] == "game-formal"
    assert row["save_path"] == str(save.resolve())


def test_jsonl_expoe_reacoes_e_ferimentos_mecanicos():
    from playtest.runner import _fill_state_metrics

    rec = TurnRecord(
        turn=3,
        action="Ataco.",
        route="combat_agent",
        latency_ms=1,
        combat_executed=True,
    )
    state = {
        "player": {
            "name": "Herói",
            "vitalidade": 5,
            "max_vitalidade": 10,
            "ferimentos": {
                "leve": [],
                "grave": [{"regiao": "braco"}],
                "critico": [],
            },
        },
        # No turno terminal o combat_node já devolve enemies=[]; a telemetria
        # precisa recuperar os Ferimentos finais do ConflictSummary.
        "enemies": [],
        "conflict_summary": {
            "ferimentos": {
                "Lobo": [{
                    "categoria": "critico",
                    "regiao": "torso",
                }],
            },
        },
        "combat": {
            "active": True,
            "last_reactions": [{"actor_id": "lobo", "card_id": "aparar"}],
            "last_tactics": [{
                "actor_id": "lobo",
                "action": "attack",
                "target_id": "player",
            }],
        },
        "world": {},
    }

    _fill_state_metrics(rec, state)
    row = telemetry.turn_to_record(rec)

    assert row["reactions"] == [{"actor_id": "lobo", "card_id": "aparar"}]
    assert row["last_tactics"] == [{
        "actor_id": "lobo",
        "action": "attack",
        "target_id": "player",
    }]
    assert row["player_wounds"]["grave"][0]["regiao"] == "braco"
    assert row["enemy_wounds"]["Lobo"]["critico"][0]["regiao"] == "torso"
    assert row["conflict_wounds"]["Lobo"][0]["regiao"] == "torso"

    summary = telemetry.build_summary(
        _result(history=[rec]),
        [row],
    )
    assert summary["combat_coverage"]["tactics"] == 1
    markdown = report.render_markdown(report.RunReport(
        run_id="tactics",
        campaigns=[summary],
        top_violations=[],
        top_errors=[],
        deltas=None,
    ))
    assert "| perfil | turnos combat | conflitos iniciados | encerrados | reações | táticas |" \
        in markdown


def test_backend_rag_offline_simula_writes_com_eventos_sem_faiss(monkeypatch):
    import rag
    from agents import archivist as archivist_module
    from agents import npc as npc_module
    from agents import world_simulator as world_module
    from playtest.runner import _offline_embeddings

    events = []
    rag.set_rag_operation_hook(events.append)
    monkeypatch.setattr(
        rag,
        "_save_index",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("offline não pode tocar FAISS")
        ),
    )
    try:
        with _offline_embeddings(True):
            assert rag.add_memory_to_session("game-1", ["fato"]) is True
            assert rag.add_npc_memory("game-1", "Ária", ["lembrança"]) is True
            # Aliases importados antes do context manager também precisam apontar
            # para o backend efêmero.
            assert archivist_module.add_memory_to_session(
                "game-1", ["arquivo"],
            ) is True
            assert archivist_module.add_npc_memory(
                "game-1", "Ária", ["arquivo NPC"],
            ) is True
            assert npc_module.add_npc_memory(
                "game-1", "Ária", ["ator NPC"],
            ) is True
            assert world_module.add_memory_to_session(
                "game-1", ["pulso do mundo"],
            ) is True
    finally:
        rag.set_rag_operation_hook(None)

    assert len(events) == 6
    assert {event.operation for event in events} == {
        "add_session_memory", "add_npc_memory",
    }
    assert all(event.success for event in events)
    assert all(event.provider == "offline-simulated" for event in events)
    assert all(str(event.path).startswith("memory://playtest/") for event in events)


def test_backend_rag_offline_restaura_aliases_entre_multiplas_campanhas():
    import rag
    from agents import archivist as archivist_module
    from agents import npc as npc_module
    from playtest.runner import _offline_embeddings

    originals = {
        "rag_session": rag.add_memory_to_session,
        "rag_npc": rag.add_npc_memory,
        "archivist_session": archivist_module.add_memory_to_session,
        "archivist_npc": archivist_module.add_npc_memory,
        "npc_npc": npc_module.add_npc_memory,
    }
    stubs = []

    for campaign in ("one", "two"):
        with _offline_embeddings(True):
            stubs.append(rag.add_memory_to_session)
            assert rag.add_memory_to_session(campaign, ["fato"]) is True
            assert archivist_module.add_memory_to_session is \
                rag.add_memory_to_session
            assert archivist_module.add_npc_memory is rag.add_npc_memory
            assert npc_module.add_npc_memory is rag.add_npc_memory
        assert rag.add_memory_to_session is originals["rag_session"]
        assert rag.add_npc_memory is originals["rag_npc"]
        assert archivist_module.add_memory_to_session is \
            originals["archivist_session"]
        assert archivist_module.add_npc_memory is originals["archivist_npc"]
        assert npc_module.add_npc_memory is originals["npc_npc"]

    assert stubs[0] is not stubs[1]


def test_backend_rag_offline_nao_altera_modo_real():
    import rag
    from agents import archivist as archivist_module
    from playtest.runner import _offline_embeddings

    originals = (
        rag.get_embeddings,
        rag.add_memory_to_session,
        rag.add_npc_memory,
        archivist_module.add_memory_to_session,
        archivist_module.add_npc_memory,
    )
    with _offline_embeddings(False):
        assert (
            rag.get_embeddings,
            rag.add_memory_to_session,
            rag.add_npc_memory,
            archivist_module.add_memory_to_session,
            archivist_module.add_npc_memory,
        ) == originals


def test_campanhas_offline_confirmam_rag_e_consumo_do_resumo(
    tmp_path,
    monkeypatch,
):
    import rag
    from playtest import runner

    monkeypatch.setattr(
        runner,
        "PLAYTEST_SAVES_DIR",
        str(tmp_path / "saves-playtest"),
    )
    monkeypatch.setattr(
        rag,
        "_save_index",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("campanha offline não pode gravar FAISS")
        ),
    )

    # Exercita o alias de add_npc_memory importado por agents.npc e, em seguida,
    # abre outra campanha no mesmo processo (store efêmero novo).
    npc_result = runner.run_campaign("npc_only", turns=8, seed=0)
    fugitive_result = runner.run_campaign("fujao", turns=12, seed=0)

    npc_rag_events = [
        event
        for record in npc_result.history
        for event in record.rag_events
    ]
    assert npc_rag_events
    assert all(event["success"] for event in npc_rag_events)
    assert all(
        event["provider"] == "offline-simulated"
        for event in npc_rag_events
    )
    assert all(
        event["path"].startswith("memory://playtest/")
        for event in npc_rag_events
    )

    target_checks = {"rag.persistence_error", "summary.lifecycle"}
    for result in (npc_result, fugitive_result):
        assert result.errors == []
        assert not target_checks.intersection(
            violation["check_id"] for violation in result.violations
        )


def test_cli_retorna_um_para_error_ou_aborto(monkeypatch, tmp_path):
    from playtest import telemetry as telemetry_module
    from playtest import __main__ as cli

    monkeypatch.setattr(
        telemetry_module, "PLAYTEST_RUNS_DIR", str(tmp_path / "runs"),
    )

    monkeypatch.setattr(
        cli,
        "run_campaign",
        lambda *a, **k: _result(
            profile="explorador",
            errors=[{"turn": 1, "action": "x", "exc": "boom"}],
            turns_completed=1,
            turns_requested=1,
        ),
    )
    assert cli.main([
        "run", "--profile", "explorador", "--turns", "1", "--seed", "1",
    ]) == 1

    monkeypatch.setattr(
        cli,
        "run_campaign",
        lambda *a, **k: _result(
            profile="explorador",
            aborted_reason="max_requests atingido",
            turns_completed=0,
            turns_requested=1,
        ),
    )
    assert cli.main([
        "run", "--profile", "explorador", "--turns", "1", "--seed", "1",
    ]) == 1
