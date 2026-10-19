"""SPEC-226 - contabilidade de recompensas idempotente (XP/ouro/itens/rep)."""

from __future__ import annotations

import random
from copy import deepcopy
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

from agents import storyteller
from tests.test_audit_reward_contracts import _state as _story_state


# ---------------------------------------------------------------- R1
def _combat_state():
    from tests.test_fase43 import make_player

    p = make_player(hp=10, inventory=[])
    p.update(
        {
            "virtudes": {"forca": 2, "agilidade": 2, "corpo": 3, "mente": 1, "carisma": 1},
            "vitalidade": 30,
            "max_vitalidade": 30,
            "ferimento_espacos": {"leve": 3, "grave": 2, "critico": 1},
            "ferimentos": {"leve": [], "grave": [], "critico": []},
        }
    )
    live = {
        "id": "e2",
        "name": "Goblin B",
        "type": "Minion",
        "hp": 500,
        "max_hp": 500,
        "defense": 30,
        "status": "ativo",
        "attributes": {"dex": 1},
        "active_conditions": [],
        "attacks": [{"name": "M", "bonus": -20, "damage": "1d1"}],
        "stamina": 0,
        "mana": 0,
        "attack_mod": 0,
        "abilities": [],
    }
    corpse = {**live, "id": "e1", "name": "Goblin A", "hp": 0, "status": "morto", "dead": True}
    return {
        "messages": [HumanMessage(content="ataco o goblin")],
        "player": p,
        "enemies": [corpse, live],
        "combat": {"round": 2, "active": True},
        "combat_target": "Goblin B",
        "world": {"turn_count": 3},
        "bestiary_knowledge": {},
        "pending_world_events": [],
        "combat_declaration": {"actor_id": "player", "acao": {"kind": "attack", "target_id": "e2"}},
    }


def test_kill_xp_once_across_rounds(monkeypatch):
    from agents import combat as cbt

    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "Fim.")
    state = _combat_state()
    kills = []
    for _ in range(3):  # cadaver antigo nao rende XP/kill/evento em NENHUMA rodada
        out = cbt.combat_node(state)
        kills += [e for e in out.get("pending_world_events", []) if e.get("type") == "npc_killed"]
        # so o Goblin B (lacaio, 50 XP) pode render, e uma unica vez.
        assert out["player"]["xp"] in (0, 50)
        if not out["combat"]["active"]:
            break
        state = {**state, **out}
        state["messages"] = [HumanMessage(content="ataco o goblin")]
        state["combat_declaration"] = {
            "actor_id": "player",
            "acao": {"kind": "attack", "target_id": "e2"},
        }
    assert len(kills) <= 1


def test_kill_marks_xp_awarded_and_pays_once():
    import progression as pg

    assert pg.xp_for_kills([{"categoria": "lacaio"}]) == 50
    from agents import combat as cbt

    src = open(cbt.__file__, encoding="utf-8").read()
    assert 'e["xp_awarded"] = True' in src


# ---------------------------------------------------------------- R2
def test_quest_completed_twice_in_batch_pays_once():
    from services.event_processor import process_pending_events

    ev = {
        "type": "quest_completed",
        "actor_id": "player",
        "target_id": "q1",
        "payload": {"quest_id": "q1"},
        "source": "storyteller",
    }
    state = {
        "player": {"xp": 0, "gold": 0, "level": 1, "name": "A"},
        "world": {"turn_count": 5},
        "event_log": [],
        "world_projection": {},
        # SPEC-223 R1: quest com prova determinística (chegou + investigou).
        "quests": [
            {
                "id": "q1",
                "title": "T",
                "status": "active",
                "created_turn": 1,
                "location_id": "nova_arcadia",
                "progress_log": [
                    {"kind": "location_reached", "turn": 1},
                    {"kind": "investigation", "turn": 2},
                ],
            }
        ],
        "pending_world_events": [dict(ev), {**ev, "target_id": "q1_bis"}],
    }
    out = process_pending_events(state)
    assert out["player"]["xp"] == 200
    assert out["player"]["gold"] == 20
    assert len([e for e in out["event_log"] if e["type"] == "quest_completed"]) == 1


# ---------------------------------------------------------------- R3
@pytest.fixture
def story(monkeypatch):
    monkeypatch.setattr(
        storyteller,
        "build_context_pack",
        lambda *a, **k: SimpleNamespace(lore_block="", memory_block="", world_state_block=""),
    )
    monkeypatch.setattr(storyteller, "simulate_world", lambda s, w, *a: (w, ""))
    monkeypatch.setattr(storyteller, "check_encounter", lambda *a, **k: None)

    def run(state, **fields):
        update = storyteller.StoryUpdate(narrative="A cena permanece tranquila.", **fields)
        llm = SimpleNamespace(
            with_structured_output=lambda _: SimpleNamespace(invoke=lambda _: update)
        )
        monkeypatch.setattr(storyteller, "get_llm", lambda **k: llm)
        return storyteller.storyteller_node(state)

    return run


def _travel_state():
    s = _story_state()
    s["messages"] = [HumanMessage(content="Vou para Profundezas do Pantano")]
    s["world"].update(
        {
            "current_location_id": "pantano_melancolia",
            "current_location": "Pantano da Melancolia",
            "visited": ["pantano_melancolia"],
            "turn_count": 4,
        }
    )
    s["campaign_plan"] = {
        "beats": [{"description": "Investigar", "status": "pending"}],
        "current_step": 0,
    }
    return s


def test_beat_xp_keeps_discovery_loot(story):
    out = story(_travel_state(), beat_completed=True)
    p = out["player"]
    assert p["xp"] == 150
    assert p["gold"] == 40
    ids = {i["id"] for i in p["inventory"]}
    assert {"espada_curta", "pocao_cura_maior"} <= ids
    assert "pm_profundezas" in out["world"]["looted_locations"]


# ---------------------------------------------------------------- R4
def test_planner_failure_keeps_plan(monkeypatch):
    from langchain_core.messages import AIMessage

    from agents import campaign_manager as cm

    plan = {
        "location": "X",
        "beats": [{"description": "a", "status": "pending"}],
        "climax": "c",
        "current_step": 0,
        "last_planned_turn": 0,
        "arc_title": "T",
    }
    llm = SimpleNamespace(
        with_structured_output=lambda _: SimpleNamespace(invoke=lambda _: AIMessage(content="erro"))
    )
    monkeypatch.setattr(cm, "get_llm", lambda **k: llm)
    state = {
        "messages": [HumanMessage(content="x")],
        "player": {"name": "A"},
        "world": {
            "turn_count": 30,
            "current_location": "Nova Arcadia",
            "current_location_id": "nova_arcadia",
        },
        "campaign_plan": plan,
        "needs_replan": True,
    }
    assert cm._build_plan(state) is None
    state["campaign_plan"] = {}
    assert cm._build_plan(state)["beats"]  # sem plano: template generico


# ---------------------------------------------------------------- R5
def test_revisit_looted_treasure_no_discovery():
    from services import exploration as ex

    loc = {
        "id": "pm_profundezas",
        "name": "P",
        "danger": 4,
        "region_id": "pantano_melancolia",
        "treasure": {"gold": 40, "items": []},
    }
    for seed in range(200):
        player = {"inventory": [], "gold": 0}
        world = {
            "current_location_id": "pm_profundezas",
            "danger_level": 4,
            "visited": ["pm_profundezas"],
            "looted_locations": ["pm_profundezas"],
            "turn_count": 5,
        }
        note, _ = ex.discover_on_arrival(
            player, world, loc, 1, random.Random(seed), first_visit=False
        )
        assert note == "" and player["gold"] == 0 and not player["inventory"]


# ---------------------------------------------------------------- R6
def test_quest_fingerprint_punctuation():
    from services.quest_log import _is_distinct, normalize_fingerprint

    a = normalize_fingerprint("Investigo a pista")
    assert a == normalize_fingerprint("Investigo a pista.")
    assert not _is_distinct(a, [" ".join(sorted(a))])
    b = normalize_fingerprint("Pergunto ao guarda sobre o sumico")
    assert _is_distinct(b, [" ".join(sorted(a))])


# ---------------------------------------------------------------- R7
@pytest.mark.parametrize(
    "sheet,xp,cost",
    [
        ({"categoria": "lacaio"}, 50, 2),
        ({"categoria": "padrao"}, 100, 3),
        ({"categoria": "elite"}, 200, 5),
        ({"categoria": "chefe"}, 1000, 12),
        ({"categoria": "nomeado"}, 1000, 12),
        ({"type": "Standard"}, 100, 3),
        ({"type": "Minion"}, 50, 2),
        ({"type": "Elite"}, 200, 5),
        ({"type": "BOSS"}, 1000, 12),
    ],
)
def test_xp_tier_by_categoria(sheet, xp, cost):
    import encounter_budget as eb
    import progression as pg

    assert pg.xp_for_kills([sheet]) == xp
    assert eb.tier_cost(sheet) == cost


# ---------------------------------------------------------------- R8
def test_faction_impact_dedupe(story):
    from agents.storyteller import FactionImpact
    from world_utils import REP_STEP

    s = _story_state()
    impacts = [
        FactionImpact(faction_id="legiao_ferro", direction="ajudou"),
        FactionImpact(faction_id="legiao_ferro", direction="ajudou"),
    ]
    out = story(s, faction_impacts=impacts)
    fac = next(f for f in out["factions"] if f["id"] == "legiao_ferro")
    assert fac["reputation"] == REP_STEP  # 1x, nao 2x
    revs = [e for e in out.get("pending_world_events", []) if e["type"] == "reputation_changed"]
    assert len(revs) == 1


# ---------------------------------------------------------------- R9
def test_rule_engine_derived_turn(monkeypatch):
    from services import rule_engine

    monkeypatch.setattr(
        rule_engine,
        "_rules_cache",
        [
            {
                "id": "rule_loop",
                "trigger": "npc_killed",
                "actions": [{"op": "emit_event", "type": "npc_killed", "targets": ["npc_grum"]}],
            }
        ],
    )
    state = {"world_projection": {}, "factions": []}
    ev = {
        "event_id": "x",
        "turn": 42,
        "type": "npc_killed",
        "actor_id": "player",
        "target_id": "npc_grum",
        "payload": {},
        "source": "storyteller",
    }
    derived = rule_engine.run_rules(ev, state, depth=0)
    assert derived and all(d["turn"] == 42 for d in derived)


# ---------------------------------------------------------------- R10
def test_reward_delta_gross():
    from services.narrative_evidence import build_evidence, validate_narrative

    state = deepcopy(_story_state())
    state["player"]["gold"] = 30  # baseline 10: ganhou 50, gastou 30 => liquido +20
    state["turn_baseline"] = {"gold": 10, "xp": 0, "gold_spent": 30}
    checked = validate_narrative(
        "Voce recebeu 50 ouro. O vento sopra.", build_evidence(state), channel="message"
    )
    assert not checked.rejections


def test_kill_transition_pays_once_across_save_reload(monkeypatch):
    """Revisao Sol (R1/D-A): inimigo que morre na rodada N paga 1x; rodada N+1
    apos round-trip JSON (save/reload no meio do combate) nao paga de novo."""
    import json

    from agents import combat as cbt
    from services import conflict_orchestrator as orch

    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "Fim.")

    def fake_run_round(scene, actors_by_id, sides, *a, **k):
        # rodada deterministica (sem dados): so a vitima declarada morre na 1a
        out = {
            "logs": [],
            "deaths": [],
            "terminal": [],
            "abyss": [],
            "attacks": [],
            "reactions": [],
            "last_stands": [],
            "stabilizations": [],
            "scars_pending": [],
            "resolved_turns": ["player"],
            "cards_used": [],
            "recidiva_event": None,
            "reason": None,
        }
        victim = actors_by_id.get("enemy_rato_peste_anel_lama_1")
        if victim is not None and calls["n"] == 0:
            victim.update({"hp": 0, "vitalidade": 0, "dead": True, "status": "morto"})
        calls["n"] += 1
        out["ended"] = False
        out["player_dead"] = False
        return out

    calls = {"n": 0}
    monkeypatch.setattr(orch, "run_round", fake_run_round)
    state = _combat_state()
    third = {**state["enemies"][1], "id": "e3", "name": "Goblin C"}
    # id de instancia de criatura real do bestiario (record_kills conta defeated)
    victim0 = {**state["enemies"][1], "id": "enemy_rato_peste_anel_lama_1"}
    state["enemies"] = [victim0, third]  # sem cadaver previo
    state["player"]["xp"] = 0
    state["turn_baseline"] = {"gold": 0, "xp": 0}

    out1 = cbt.combat_node(state)
    assert out1["turn_baseline"]["xp_gains"] == [50]  # R10: ganho do abate
    kills1 = [e for e in out1.get("pending_world_events", []) if e.get("type") == "npc_killed"]
    assert out1["player"]["xp"] == 50
    assert len(kills1) <= 1  # npc_killed so para entidade canonica do grafo
    defeated = sum(int(v.get("defeated", 0)) for v in out1["bestiary_knowledge"].values())
    assert defeated == 1

    # save/reload: o marcador sobrevive ao JSON
    reloaded = json.loads(
        json.dumps(
            {
                "enemies": out1["enemies"],
                "player": out1["player"],
                "bestiary_knowledge": out1["bestiary_knowledge"],
                "combat": out1["combat"],
            }
        )
    )
    state2 = {
        **state,
        **reloaded,
        "messages": [HumanMessage(content="ataco o goblin")],
        "combat_declaration": {"actor_id": "player", "acao": {"kind": "attack", "target_id": "e3"}},
    }
    out2 = cbt.combat_node(state2)
    kills2 = [e for e in out2.get("pending_world_events", []) if e.get("type") == "npc_killed"]
    assert out2["player"]["xp"] == 50
    assert kills2 == []
    defeated2 = sum(
        int(v.get("defeated", 0))
        for v in (out2.get("bestiary_knowledge") or reloaded["bestiary_knowledge"]).values()
    )
    assert defeated2 == 1


def test_planner_failure_other_region_uses_grounded_template(monkeypatch):
    """Revisao Sol (R4): plano antigo de OUTRA regiao nao sobrevive a falha do
    provider (transplante de ganchos); cai no template ancorado no local atual."""
    from langchain_core.messages import AIMessage

    from agents import campaign_manager as cm

    plan = {
        "location": "Nova Arcádia",
        "beats": [{"description": "a", "status": "pending"}],
        "climax": "c",
        "current_step": 0,
        "last_planned_turn": 0,
        "arc_title": "T",
    }
    llm = SimpleNamespace(
        with_structured_output=lambda _: SimpleNamespace(invoke=lambda _: AIMessage(content="erro"))
    )
    monkeypatch.setattr(cm, "get_llm", lambda **k: llm)
    state = {
        "messages": [HumanMessage(content="x")],
        "player": {"name": "A"},
        "world": {"turn_count": 30, "current_location": "Deserto de Zhur"},
        "campaign_plan": plan,
        "needs_replan": True,
    }
    new = cm._build_plan(state)
    assert new and new["location"] == "Deserto de Zhur"
    state["world"]["current_location"] = "Nova Arcádia"
    assert cm._build_plan(state) is None  # mesma regiao: mantem o plano


# ------------------------------------------- R10 integracao (ganhos por fonte)
def test_reward_guard_accepts_each_real_gain_beat_quest_discovery(story):
    """Turno real: viagem (baú +40 ouro) + beat (+150 XP) no storyteller, depois
    quest concluída (+200 XP, +20 ouro) no event_processor do arquivista. O guard
    aceita cada ganho individual e segue rejeitando ganho inventado."""
    from services.event_processor import process_pending_events
    from services.narrative_evidence import build_evidence, validate_narrative
    from services.turn_outcome import capture_baseline

    state = _travel_state()
    # SPEC-223 R1: quest com prova (chegou ao local + investigou em turno anterior).
    state["quests"] = [
        {
            "id": "q1",
            "title": "T",
            "status": "active",
            "created_turn": 1,
            "location_id": "pantano_melancolia",
            "progress_log": [
                {"kind": "location_reached", "turn": 2},
                {"kind": "investigation", "turn": 3},
            ],
        }
    ]
    state["pending_world_events"] = [
        {
            "type": "quest_completed",
            "actor_id": "player",
            "target_id": "q1",
            "payload": {"quest_id": "q1"},
            "source": "storyteller",
        }
    ]
    state["turn_baseline"] = capture_baseline(state)  # action_guard do grafo
    state = {**state, **story(state, beat_completed=True)}
    state = {**state, **process_pending_events(state)}  # mesmo passo do archivist
    assert state["player"]["xp"] == 350 and state["player"]["gold"] == 60
    assert sorted(state["turn_baseline"]["xp_gains"]) == [150, 200]
    assert sorted(state["turn_baseline"]["gold_gains"]) == [20, 40]
    ev = build_evidence(state)
    for ok in (
        "Voce recebeu 150 XP.",
        "Voce recebeu 200 XP.",
        "Voce recebeu 350 XP.",
        "Voce recebeu 40 ouro.",
        "Voce recebeu 20 ouro.",
    ):
        assert not validate_narrative(ok, ev, channel="message").rejections, ok
    for bad in ("Voce recebeu 999 XP.", "Voce recebeu 75 ouro."):
        assert validate_narrative(bad, ev, channel="message").rejections, bad


def test_reward_guard_sale_and_purchase_record_ledger():
    from services.turn_outcome import record_gain

    bl = {"gold": 10, "xp": 0}
    bl = record_gain(bl, "gold", 50)  # venda
    bl = record_gain(bl, "gold", -30)  # compra
    assert bl["gold_gains"] == [50] and bl["gold_spent"] == 30
    assert record_gain(None, "gold", 50) is None  # fora do grafo: nao inventa baseline


@pytest.mark.parametrize("mode,delta,gold_after", [("sell", 50, 60), ("buy", -30, 0)])
def test_loot_trade_records_ledger_and_guard(monkeypatch, mode, delta, gold_after):
    """loot_node real (SHOP): venda grava ganho bruto, compra grava gasto; o guard
    aceita a frase do ganho/rejeita valor inventado."""
    from agents import loot
    from services import economy
    from services.narrative_evidence import build_evidence, validate_narrative
    from services.turn_outcome import capture_baseline

    state = deepcopy(_story_state())
    state["player"].update({"gold": 10, "inventory": [{"id": "espada_curta", "qty": 1}]})
    state.update(
        {"loot_source": "SHOP", "messages": [HumanMessage(content=f"{mode} espada curta")]}
    )
    state["turn_baseline"] = capture_baseline(state)
    monkeypatch.setattr(
        loot,
        "_parse_trade_intent",
        lambda *a: loot.TradeIntent(mode=mode, item_ref="espada_curta", qty=1),
    )

    def fake_trade(work_state, m, item_ref, qty):
        return {
            "ok": True,
            "mode": m,
            "qty": 1,
            "item_id": "espada_curta",
            "item_name": "Espada Curta",
            "gold_delta": delta,
            "player": {**work_state["player"], "gold": gold_after},
        }

    monkeypatch.setattr(economy, "execute_trade", fake_trade)
    out = loot.loot_node(state)
    bl = out["turn_baseline"]
    if delta > 0:
        assert bl["gold_gains"] == [50]
        merged = {**state, **out}
        ev = build_evidence(merged)
        assert not validate_narrative("Voce recebeu 50 ouro.", ev, channel="message").rejections
        assert validate_narrative("Voce recebeu 80 ouro.", ev, channel="message").rejections
    else:
        assert bl["gold_spent"] == 30 and not bl.get("gold_gains")


# ------------------------------------------- R8 rejeicao por outro motivo
def test_rejected_reputation_is_reverted(story):
    """Facção derrotada: o validador rejeita o reputation_changed (não por
    duplicata) e a reputação aplicada pelo storyteller é desfeita."""
    from agents.storyteller import FactionImpact
    from services.event_processor import process_pending_events

    s = _story_state()
    s["world_projection"] = {"entities": {"legiao_ferro": {"alive": False}}}
    out = story(s, faction_impacts=[FactionImpact(faction_id="legiao_ferro", direction="ajudou")])
    moved = next(f for f in out["factions"] if f["id"] == "legiao_ferro")
    assert moved["reputation"] != 0
    merged = {**s, **out}
    done = process_pending_events(merged)
    fac = next(f for f in done["factions"] if f["id"] == "legiao_ferro")
    assert fac["reputation"] == 0
    assert not [e for e in done["event_log"] if e["type"] == "reputation_changed"]
    assert any(r["type"] == "reputation_changed" for r in done["event_rejections"])


def test_accepted_reputation_not_touched(story):
    from agents.storyteller import FactionImpact
    from services.event_processor import process_pending_events
    from world_utils import REP_STEP

    s = _story_state()
    out = story(s, faction_impacts=[FactionImpact(faction_id="legiao_ferro", direction="ajudou")])
    done = process_pending_events({**s, **out})
    assert "factions" not in done  # aceito: nada a desfazer, sem aplicar 2x
    assert next(f for f in out["factions"] if f["id"] == "legiao_ferro")["reputation"] == REP_STEP
