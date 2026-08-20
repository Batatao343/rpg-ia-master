"""Regressões das decisões atômicas do harness de playtest."""
from __future__ import annotations

import random

import pytest

from playtest import invariants
from playtest import runner
from playtest.profiles import PROFILES, ProfileDecision


def _combat_state(*, vitality: int = 12, inventory=None) -> dict:
    return {
        "player": {
            "name": "Kael",
            "class_name": "Devoto do Abismo",
            "vitalidade": vitality,
            "max_vitalidade": 12,
            "hp": vitality,
            "max_hp": 12,
            "entropy": 8,
            "max_entropy": 8,
            "prepared_cards": ["dev_golpe_convite", "dev_muralha_viva"],
            "inventory": inventory or [],
        },
        "enemies": [
            {
                "id": "lobo_1",
                "name": "Lobo Cinzento",
                "status": "ativo",
                "vitalidade": 8,
                "max_vitalidade": 8,
            }
        ],
        "combat": {"active": True, "round": 2},
        "world": {
            "current_location_id": "nova_arcadia",
            "danger_level": 2,
        },
        "messages": [],
        "npcs": {},
    }


def test_profile_decision_rejeita_combinacoes_ambiguas():
    with pytest.raises(ValueError):
        ProfileDecision(text="Ataco.", mode="declaration")
    with pytest.raises(ValueError):
        ProfileDecision(
            text="Fujo.",
            mode="flee",
            declaration={"actor_id": "player", "acao": {"kind": "attack"}},
        )
    with pytest.raises(ValueError):
        ProfileDecision(
            text="Converso.",
            mode="free_text",
            flee_destination_id="nova_arcadia",
        )


def test_carta_texto_e_declaracao_nascem_do_mesmo_id():
    state = _combat_state()
    decisions = [PROFILES["agressivo"].decide(state, random.Random(seed))
                 for seed in range(30)]
    chosen = next(
        d for d in decisions
        if d.mode == "declaration"
        and (d.declaration or {}).get("acao", {}).get("kind") == "card"
    )
    step = chosen.declaration["acao"]
    assert step["card_id"] == "dev_golpe_convite"
    assert "Golpe do Convite" in chosen.text
    assert "Lobo Cinzento" in chosen.text
    assert step["target_id"] == "lobo_1"


def test_cura_baixa_vitalidade_declara_o_item_real():
    state = _combat_state(
        vitality=2,
        inventory=[{"id": "pocao_cura", "qty": 1}],
    )
    decision = PROFILES["combate"].decide(state, random.Random(4))
    assert decision.mode == "declaration"
    assert decision.declaration["acao"] == {
        "kind": "item",
        "item_id": "pocao_cura",
        "target_id": "player",
    }
    assert "Poção de Cura Menor" in decision.text


def test_fujao_e_explorador_em_combate_emitem_fuga_sem_declaracao():
    state = _combat_state()
    for profile in ("fujao", "explorador"):
        decision = PROFILES[profile].decide(state, random.Random(7))
        assert decision.mode == "flee"
        assert decision.declaration is None
        assert decision.mechanical_kind == "flee"

    assert PROFILES["explorador"].decide(
        state, random.Random(7)
    ).flee_destination_id in {
        conn["id"]
        for conn in __import__("gamedata").get_connections("nova_arcadia")
    }


def test_decisao_atomica_e_deterministica_para_todos_os_perfis():
    state = _combat_state()
    for profile in PROFILES.values():
        a = profile.decide(state, random.Random(19))
        b = profile.decide(state, random.Random(19))
        assert a.to_record() == b.to_record(), profile.name
        assert a.text
        assert a.mechanical_kind in {
            "attack", "card", "item", "maneuver", "move", "pass", "flee",
        }


def test_invariante_action_declaration_matches_preserva_detalhes():
    decision = ProfileDecision(
        text="Uso Golpe do Convite em Lobo Cinzento.",
        mode="declaration",
        declaration={
            "actor_id": "player",
            "acao": {
                "kind": "card",
                "card_id": "dev_golpe_convite",
                "target_id": "lobo_1",
            },
        },
    )
    violations = invariants.check_action_declaration(
        decision.to_record(),
        {
            "kind": "attack",
            "card_id": None,
            "target_id": "lobo_1",
            "result": "hit",
        },
        turn=8,
        combat_executed=True,
    )
    assert len(violations) == 1
    violation = violations[0]
    assert violation.check_id == "action.declaration_matches"
    assert violation.severity == "error"
    assert violation.details["expected_kind"] == "card"
    assert violation.details["resolved_kind"] == "attack"


def test_invariante_action_declaration_matches_falha_sem_resultado_canonico():
    decision = ProfileDecision(
        text="Ataco Lobo Cinzento.",
        mode="declaration",
        declaration={
            "actor_id": "player",
            "acao": {"kind": "attack", "target_id": "lobo_1"},
        },
    )
    violations = invariants.check_action_declaration(
        decision.to_record(),
        {},
        turn=9,
        combat_executed=True,
    )
    assert [violation.check_id for violation in violations] == [
        "action.declaration_matches",
    ]
    assert violations[0].details["mismatches"]["resolved_action"] == [
        "present", "missing",
    ]


def test_declaracao_interrompida_por_queda_antes_da_iniciativa_nao_e_mismatch():
    decision = ProfileDecision(
        text="Uso uma poção.",
        mode="declaration",
        declaration={
            "actor_id": "player",
            "acao": {"kind": "item", "item_id": "pocao_cura_maior",
                     "target_id": "player"},
        },
    ).to_record()
    resolved = {
        "kind": "item", "item_id": "pocao_cura_maior",
        "target_id": "player", "result": "interrupted", "attempted": False,
    }

    assert invariants.check_action_declaration(
        decision, resolved, turn=3, combat_executed=True,
    ) == []


def test_perfil_descansa_antes_de_abrir_novo_combate_se_inconsciente():
    state = _combat_state()
    state["combat"] = {"active": False}
    state["enemies"] = []
    state["player"]["conscious"] = False
    state["player"]["post_combat_state"] = "inconsciente"

    decision = PROFILES["agressivo"].decide(state, random.Random(1))

    assert decision.mode == "free_text"
    assert "descanso" in decision.text.casefold()


def test_resolved_action_so_existe_quando_observada_no_turno_atual():
    previous_state = {
        "combat": {
            "last_player_action": {
                "kind": "flee", "result": "fled", "attempted": True,
            },
        },
    }

    assert runner._observed_resolved_action({}) == {}
    assert runner._observed_resolved_action({
        "storyteller": previous_state,
    }) == {}
    assert runner._observed_resolved_action({
        "combat_agent": previous_state,
    }) == previous_state["combat"]["last_player_action"]


def test_runner_chama_decide_uma_vez_e_injeta_o_mesmo_payload(monkeypatch):
    import llm_setup
    import main
    import persistence
    from langchain_core.messages import HumanMessage
    from playtest import profiles, runner

    class AtomicProfile:
        name = "explorador"

        def __init__(self):
            self.calls = 0

        def reset(self):
            pass

        def decide(self, state, rng):
            self.calls += 1
            return ProfileDecision(
                text="Ataco Lobo Cinzento.",
                mode="declaration",
                declaration={
                    "actor_id": "player",
                    "acao": {"kind": "attack", "target_id": "lobo_1"},
                },
            )

        def next_action(self, state, rng):  # pragma: no cover - deve explodir se usado
            raise AssertionError("runner não pode chamar next_action")

    atomic = AtomicProfile()
    monkeypatch.setitem(profiles.PROFILES, "explorador", atomic)
    state = _combat_state()
    state.update({"game_id": "00000000-0000-0000-0000-000000000111",
                  "messages": [], "event_log": [], "campaign_plan": {}})
    monkeypatch.setattr(runner, "_build_initial_state", lambda *a, **k: state)
    monkeypatch.setattr(persistence, "save_game_state", lambda _state: True)
    monkeypatch.setattr(persistence, "save_path", lambda _gid: "fake-save.json")

    class Graph:
        captured = None

        def invoke(self, initial):
            return initial

        def stream(self, current, stream_mode=None):
            self.captured = current
            out = dict(current)
            out["combat"] = {
                **current["combat"],
                "last_player_action": {
                    "kind": "attack", "target_id": "lobo_1", "result": "hit",
                },
            }
            yield "updates", {"dm_router": {"next": "combat_agent"}}
            yield "updates", {"combat_agent": {"combat": out["combat"]}}
            yield "values", out

    graph = Graph()
    monkeypatch.setattr(main, "app", graph)
    monkeypatch.setattr(llm_setup, "set_llm_attempt_telemetry_hook",
                        lambda _fn: None, raising=False)

    result = runner.run_campaign(
        "explorador", turns=1, seed=3, invariants=True,
    )

    assert atomic.calls == 1
    assert graph.captured["combat_declaration"]["acao"]["target_id"] == "lobo_1"
    human = next(m for m in reversed(graph.captured["messages"])
                 if isinstance(m, HumanMessage))
    assert human.content == "Ataco Lobo Cinzento."
    assert result.history[0].decision["kind"] == "attack"
    assert result.history[0].resolved_action["kind"] == "attack"
