"""SPEC-203 Etapa 4 — state machine do encontro, desfecho e retorno à exploração,
com save/reload em cada fase (R5/R6/R10/R11). Offline e determinístico: a
resolução da rodada é roteirizada (run_round stub) para isolar o ciclo de vida."""
from __future__ import annotations

import json
import random

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.combat as combat
import api
import persistence
from agents.router import RouterDecision, RouteType, dm_router_node
from agents.turn_finalizer import turn_finalizer_node
from services import conflict_orchestrator as orch
from services import encounter_manifest as em
from tests.test_encounter_identity_repro import _BANDIT, _install_llm, _start_state


def _reload(state):
    raw = json.loads(json.dumps(persistence._state_to_save_data(state, state["game_id"]),
                                default=str))
    return {**state, **persistence._raw_to_state(raw)}


def _merge(state, out, msg="Continuo lutando."):
    merged = {**state, **{k: v for k, v in out.items() if k != "messages"}}
    merged["messages"] = [*state["messages"], *(out.get("messages") or []),
                          HumanMessage(content=msg)]
    return merged


def _scripted(plan):
    """run_round roteirizado: plan[i] decide o efeito da rodada i."""
    calls = {"n": 0}

    def fake_run_round(scene, actors_by_id, sides, *a, **k):
        step = plan[min(calls["n"], len(plan) - 1)]
        calls["n"] += 1
        player = actors_by_id["player"]
        enemy = actors_by_id[sides["enemy"][0]] if sides["enemy"] else None
        out = {"logs": ["O aço cruza o ar."], "deaths": [], "terminal": [], "abyss": [],
               "attacks": [], "reactions": [{"actor_id": "player", "card_id": "aparar"}],
               "last_stands": [], "stabilizations": [], "scars_pending": [],
               "resolved_turns": ["player"], "cards_used": [], "recidiva_event": None,
               "reason": "", "ended": False, "player_dead": False,
               "initiative": ["heroes", "enemy"]}
        player["vitalidade"] = max(1, int(player.get("vitalidade", 10)) - 2)
        if step == "kill" and enemy:
            enemy.update({"vitalidade": 0, "hp": 0, "dead": True, "status": "morto"})
            out["ended"] = True
        elif step == "surrender" and enemy:
            enemy.update({"status": "rendido", "surrendered": True})
            out["ended"] = True
        elif step == "die":
            player.update({"vitalidade": 0, "dead": True})
            out.update(ended=True, player_dead=True)
        return out

    return fake_run_round


def _decl(state):
    state["combat_declaration"] = {"actor_id": "player", "acao": {"kind": "pass"}}
    return state


def _start(monkeypatch, plan):
    random.seed(9)
    _install_llm(monkeypatch)
    monkeypatch.setattr(orch, "run_round", _scripted(plan))
    return _decl(_start_state(combat_encounter_hint={
        "enemy_id": _BANDIT, "reason": "random", "hint": "Bandido"},
        world={**_start_state()["world"], "danger_level": 1},
        continuity={"session_action_count": 4, "timeline_epoch": 0}))


def _play(monkeypatch, plan):
    """ameaça → entering → rodadas → terminal, com reload a cada passo."""
    state = _start(monkeypatch, plan)
    phases, manifests = [], []
    for _ in range(len(plan)):
        out = combat.combat_node(state)
        state = _reload(_merge(state, out))
        # R11: reload preserva manifesto, fase e próximo passo.
        assert state["combat"]["phase"] == out["combat"]["phase"]
        assert state["combat"].get("encounter") == out["combat"].get("encounter")
        assert em.next_step(state["combat"]) == em.next_step(out["combat"])
        phases.append(state["combat"]["phase"])
        manifests.append(state["combat"]["encounter"])
        if state["combat"]["phase"] == "ended":
            break
        _decl(state)
    for m in manifests[1:]:
        em.assert_immutable(manifests[0], m)
    return state, phases, out


def _finalize(state):
    fin = turn_finalizer_node(state)
    return {**state, **fin}


@pytest.mark.parametrize("plan,outcome", [
    (["hit", "kill"], "victory"),
    (["hit", "surrender"], "surrendered_enemy"),
])
def test_fluxo_completo_ate_exploracao(monkeypatch, plan, outcome):
    state, phases, out = _play(monkeypatch, plan)
    assert phases == ["active", "ended"]
    assert state["combat"]["outcome"] == outcome and state["combat"]["active"] is False
    events = {ev["kind"] for ev in state["combat"]["encounter"]["events"]}
    assert ("dead" if outcome == "victory" else "surrendered") in events
    state = _reload(_finalize(state))
    resp = api.format_response(state)
    assert resp.combat_result["outcome"] == outcome
    assert resp.combat_result["xp_event_ref"] == resp.turn_outcome["receipt_id"]
    if outcome == "victory":
        assert resp.combat_result["loot_ref"]
    # R8: nenhum XP narrado no chat.
    for m in state["messages"]:
        assert "XP" not in str(m.content)
    # R6: próximo turno → exploração sem mensagem extra (mesmo se o LLM diria COMBAT).

    class _CombatLLM:
        def with_structured_output(self, _schema):
            return self

        def invoke(self, _msgs):
            return RouterDecision(route=RouteType.COMBAT, target="Bandido",
                                  reasoning="x", confidence=0.9, loot_context=None)

    import agents.router as router
    monkeypatch.setattr(router, "get_llm", lambda **_k: _CombatLLM())
    nxt = {**state, "messages": [*state["messages"], HumanMessage(content="Sigo pela trilha.")]}
    routed = dm_router_node(nxt)
    assert routed["next"] == "storyteller"
    assert routed["combat"]["explore_resumed"] is True
    # Turno seguinte: o painel não reaparece (novo recibo).
    after = {**nxt, **routed, "messages": [*nxt["messages"], AIMessage(content="A trilha segue.")],
             "world": {**state["world"], "turn_count": 6}}
    after = _finalize(after)
    assert api.format_response(after).combat_result == {}


def test_fluxo_derrota_morte_mantem_death_pending(monkeypatch):
    state, phases, out = _play(monkeypatch, ["hit", "die"])
    assert phases[-1] == "ended" and state["combat"]["outcome"] == "death"
    assert out["death_pending"] is True
    import agents.router as router  # noqa: F401
    # death não força exploração (fluxo SPEC-060 intacto)
    assert em.next_step(state["combat"]) == "explore"


def test_fluxo_fuga(monkeypatch):
    from tests.test_combat_lifecycle import _DEST_ID, _enemy, _player, _world
    random.seed(3)
    state = {"game_id": "flee", "messages": [HumanMessage(content="Viajo para longe")],
             "player": _player(), "enemies": [_enemy()], "combat": {"active": True},
             "world": _world(), "party": [],
             "combat_flee_attempt": True, "combat_flee_destination": _DEST_ID}
    out = combat.combat_node(state)
    assert out["combat"]["phase"] == "ended" and out["combat"]["outcome"] == "fled"
    assert out["combat"]["result"]["outcome"] == "fled"
    state = _reload(_merge(state, out))
    assert state["combat"]["result"] == out["combat"]["result"]


def test_fluxo_expiracao_router():
    combat_state = {"active": True, "phase": "active", "round": 2, "instance_id": "g:0:1",
                    "encounter": em.build_manifest(
                        [{"id": f"{_BANDIT}_1", "name": "Bandido", "status": "ativo"}],
                        source="systemic", origin="unknown", encounter_id="g:0:1")}
    out = None
    for _ in range(3):
        st = {"combat": combat_state, "world": {"current_location_id": "x"},
              "messages": [HumanMessage(content="fico parado observando")]}
        out = dm_router_node(st)
        combat_state = out.get("combat", combat_state)
    assert out["combat"]["phase"] == "ended" and out["combat"]["outcome"] == "expired"
    assert out["combat"]["result"]["outcome"] == "expired"


@pytest.mark.parametrize("phase", ["entering", "active", "resolving", "ended"])
def test_reload_em_cada_fase(phase):
    m = em.build_manifest([{"id": f"{_BANDIT}_1", "name": "Bandido", "status": "ativo"}],
                          source="systemic", origin="unknown", encounter_id="g:0:1")
    active = phase != "ended"
    combat_meta = {"active": active, "phase": phase,
                   "outcome": None if active else "victory", "encounter": m, "round": 1}
    state = {"game_id": "00000000-0000-4000-8000-000000000001", "player": {"name": "K"},
             "world": {}, "messages": [],
             "enemies": [{"id": f"{_BANDIT}_1", "name": "Bandido", "status": "ativo"}]
             if active else [], "combat": combat_meta}
    loaded = _reload(state)
    assert loaded["combat"]["phase"] == phase
    assert loaded["combat"]["encounter"] == m
    assert em.next_step(loaded["combat"]) == em.next_step(combat_meta)


def test_replay_action_id_nao_duplica_resultado(monkeypatch):
    """R10: reprocessar o mesmo turno de término não duplica evento de
    composição, result_event_id, XP nem kill."""
    state = _start(monkeypatch, ["kill"])
    state["player"]["xp"] = 0
    out1 = combat.combat_node(dict(state))
    monkeypatch.setattr(orch, "run_round", _scripted(["kill"]))
    out2 = combat.combat_node(dict(state))
    r1, r2 = out1["combat"]["result"], out2["combat"]["result"]
    assert r1["result_event_id"] == r2["result_event_id"]
    assert out1["combat"]["encounter"]["events"] == out2["combat"]["encounter"]["events"]
    assert out1["player"]["xp"] == out2["player"]["xp"]
    # Rodar de novo sobre o estado já encerrado não paga XP/kill de novo.
    merged = _decl(_merge(state, out1))
    merged["messages"] = [*merged["messages"]]
    xp_after = merged["player"]["xp"]
    fin = turn_finalizer_node(merged)
    fin2 = turn_finalizer_node({**merged, **fin})
    assert "combat" not in fin2
    assert merged["player"]["xp"] == xp_after
