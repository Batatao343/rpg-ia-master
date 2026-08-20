from __future__ import annotations

from langchain_core.messages import AIMessage

import llm_setup
from agents import combat
from playtest import invariants
from playtest.provider_profiles import (
    ProviderPacer, ProviderPreflightError, get_routes_profile,
    preflight_real_routes,
)
from playtest.runner import CampaignResult, terminal_llm_invocation_count
from playtest.report import RunReport, render_markdown
from services import conflict_orchestrator as orchestrator
from services import conflict_scene


def test_inimigo_escondido_nao_repete_carta_de_esconder():
    actor = {
        "id": "cervo", "cartas": ["bst_mimetismo_morto", "bst_toque_gelido"],
        "entropy": 4, "enemy_card_usage": {},
    }
    scene = conflict_scene.new_scene()
    conflict_scene.place(scene, "cervo")
    conflict_scene.hide(scene, "cervo", source="Mimetismo Morto")

    chosen = orchestrator._enemy_offensive_card(actor, scene=scene, actor_id="cervo")

    assert chosen != "bst_mimetismo_morto"


def test_inimigo_visivel_pode_usar_carta_de_esconder():
    actor = {
        "id": "cervo", "cartas": ["bst_mimetismo_morto"],
        "entropy": 4, "enemy_card_usage": {},
    }
    scene = conflict_scene.new_scene()
    conflict_scene.place(scene, "cervo")
    assert orchestrator._enemy_offensive_card(
        actor, scene=scene, actor_id="cervo",
    ) == "bst_mimetismo_morto"


def test_vitalidade_zero_bloqueia_tentativa_de_fuga():
    assert combat._can_attempt_flee({"vitalidade": 0, "conscious": True}) is False
    assert combat._can_attempt_flee({"vitalidade": 1, "conscious": True}) is True
    assert combat._can_attempt_flee({"vitalidade": 8, "conscious": False}) is False


def test_invariante_acusa_zero_fora_de_combate_sem_fluxo_terminal():
    state = {
        "player": {"vitalidade": 0, "max_vitalidade": 12},
        "combat": {"active": False}, "death_pending": False, "game_over": False,
    }
    got = invariants.check_zero_vitality_outside_terminal(state, None, 7)
    assert got and got[0].check_id == "player.zero_vitality_outside_terminal"
    assert got[0].severity == "error"


def test_zero_em_combate_ou_fluxo_terminal_e_valido():
    base = {"player": {"vitalidade": 0, "max_vitalidade": 12}}
    assert invariants.check_zero_vitality_outside_terminal(
        {**base, "combat": {"active": True}}, None, 1,
    ) == []
    assert invariants.check_zero_vitality_outside_terminal(
        {**base, "combat": {"active": False}, "death_pending": True}, None, 1,
    ) == []


def test_warning_npc_exige_uso_mecanico_atual():
    remote = {
        "Pérola": {"created_turn": 2, "home_location_id": "brekmar", "in_scene": True}
    }
    memory_only = {
        "world": {"current_location_id": "nova_arcadia"}, "npcs": remote,
        "party": [], "messages": [AIMessage(content="Você lembra o que Pérola disse.")],
    }
    assert invariants.check_recycled_npc(memory_only, None, 20) == []

    active = {**memory_only, "active_npc_name": "Pérola"}
    got = invariants.check_recycled_npc(active, None, 21)
    assert got and got[0].check_id == "narrative.recycled_npc"


def test_relatorio_lista_todas_as_mortes_da_campanha():
    deaths = [
        {"turn": 6, "location": "Pântano", "cause": "Viúva"},
        {"turn": 26, "location": "Saídas Baixas", "cause": "Observador"},
        {"turn": 38, "location": "O Trono", "cause": "Arpoador"},
    ]
    report = RunReport(
        run_id="matrix-a", campaigns=[{
            "profile": "explorador", "seed": 6201, "deaths": 3,
            "deaths_log": deaths, "latency_ms": {},
        }], top_violations=[], top_errors=[], deltas=None, mock_any=False,
    )
    markdown = render_markdown(report)
    deaths_section = markdown.split("## Mortes", 1)[1].split("## Violações", 1)[0]
    assert deaths_section.count("| explorador | 6201 |") == 3
    assert "Saídas Baixas" in markdown and "Arpoador" in markdown


def test_preset_groq_free_nao_tem_outro_provider():
    routes = get_routes_profile("groq-free")
    assert set(routes) == {"classify", "fast", "smart"}
    assert {
        provider for candidates in routes.values() for provider, _model in candidates
    } == {"groq"}
    assert routes["classify"] == [["groq", "openai/gpt-oss-20b"]]
    assert routes["fast"][-1] == ["groq", "openai/gpt-oss-20b"]
    assert routes["smart"][-1] == ["groq", "openai/gpt-oss-20b"]


def test_pacer_espaca_apenas_sucesso_groq_120b():
    now = [100.0]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    pacer = ProviderPacer(
        min_interval_seconds=12, clock=lambda: now[0], sleeper=sleep,
    )
    pacer.observe({
        "provider": "groq", "model": "openai/gpt-oss-120b", "status": "success",
    })
    pacer.observe({
        "provider": "groq", "model": "openai/gpt-oss-120b", "status": "success",
    })
    pacer.observe({
        "provider": "groq", "model": "openai/gpt-oss-20b", "status": "success",
    })
    pacer.observe({
        "provider": "deepseek", "model": "openai/gpt-oss-120b", "status": "success",
    })
    assert sleeps == [12.0, 12.0]


def test_pacer_desligado_nao_dorme():
    pacer = ProviderPacer(min_interval_seconds=0, sleeper=lambda _seconds: 1 / 0)
    pacer.observe({
        "provider": "groq", "model": "openai/gpt-oss-120b", "status": "success",
    })


def test_preflight_prova_os_tres_tiers(monkeypatch):
    seen = []

    class Fake:
        def __init__(self, tier):
            self.tier = tier
            self.schema = None

        def with_structured_output(self, schema):
            self.schema = schema
            return self

        def invoke(self, _messages):
            seen.append(self.tier.value)
            return self.schema(status="READY")

    monkeypatch.setattr(llm_setup, "get_llm", lambda **kwargs: Fake(kwargs["tier"]))
    monkeypatch.setattr(llm_setup, "reset_llm_circuit_breakers", lambda: None)
    monkeypatch.setattr(llm_setup, "set_llm_attempt_telemetry_hook", lambda _hook: None)

    proof = preflight_real_routes()

    assert proof["tiers"] == ["classify", "fast", "smart"]
    assert seen == proof["tiers"]


def test_preflight_falha_sem_structured_output_real(monkeypatch):
    class Fake:
        def with_structured_output(self, _schema):
            return self

        def invoke(self, _messages):
            return AIMessage(content="")

    monkeypatch.setattr(llm_setup, "get_llm", lambda **_kwargs: Fake())
    monkeypatch.setattr(llm_setup, "reset_llm_circuit_breakers", lambda: None)
    monkeypatch.setattr(llm_setup, "set_llm_attempt_telemetry_hook", lambda _hook: None)
    try:
        preflight_real_routes()
    except ProviderPreflightError as exc:
        assert "classify" in str(exc)
    else:
        raise AssertionError("preflight deveria falhar")


def test_fallback_com_sucesso_nao_e_invocacao_terminal():
    events = [
        {"attempt_index": 0, "status": "invoke_error"},
        {"attempt_index": 1, "status": "success"},
        {"attempt_index": 0, "status": "success"},
    ]

    assert terminal_llm_invocation_count(events) == 0


def test_grupo_sem_sucesso_e_invocacao_terminal():
    events = [
        {"attempt_index": 0, "status": "circuit_open"},
        {"attempt_index": 1, "status": "build_error"},
        {"attempt_index": 0, "status": "invoke_error"},
        {"attempt_index": 1, "status": "invalid_structured"},
    ]

    assert terminal_llm_invocation_count(events) == 2


def test_matrix_real_para_apos_primeira_falha_llm_terminal(monkeypatch):
    import importlib
    from types import SimpleNamespace

    cli = importlib.import_module("playtest.__main__")
    from playtest import telemetry

    calls = []
    begin = {}
    monkeypatch.setattr(telemetry, "new_run_id", lambda: "run-strict")
    monkeypatch.setattr(
        telemetry, "begin_run", lambda *args, **kwargs: begin.update(kwargs),
    )
    monkeypatch.setattr(telemetry, "touch_run", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(telemetry, "run_dir", lambda run_id: run_id)
    monkeypatch.setattr(telemetry, "finish_run", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        telemetry,
        "persist_campaign",
        lambda *_args, **_kwargs: {
            "error_violations": 0,
            "observability_errors": 0,
        },
    )

    def fake_run(profile, **kwargs):
        calls.append((profile, kwargs))
        return CampaignResult(
            profile=profile,
            seed=kwargs["seed"],
            turns_completed=1,
            errors=[{"turn": 1, "exc": "llm_terminal_failure"}],
            history=[],
            final_state={},
            save_path="",
            mock=False,
            aborted_reason="llm_terminal_failure (turno 1)",
            turns_requested=kwargs["turns"],
        )

    monkeypatch.setattr(cli, "run_campaign", fake_run)
    args = SimpleNamespace(
        label="A", turns=200, real=True, max_cost=0.25,
        max_requests=800, routes_profile="groq-free",
        groq_min_interval=12.0, turn_timeout=120.0,
    )

    assert cli._run_matrix_suite(args) == 1
    assert len(calls) == 1
    assert calls[0][1]["require_all_llm_invocations_successful"] is True
    assert begin["require_all_llm_invocations_successful"] is True
