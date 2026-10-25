"""SPEC-313: correcoes da revisao independente (P1/P2)."""

from __future__ import annotations

import pytest

import gamedata
from playtest import invariants
from services import lore_quests as lq
from services import npc_world, quest_log
from services import world_quests as wq
from tests.spec313_helpers import NPC_KEY, NPC_REF, npc_state, setup_env


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    setup_env(monkeypatch)


def test_hunt_completes_through_combat_node_with_instantiated_enemy(monkeypatch):
    """P1-1: o inimigo em runtime so tem `id = {bestiary_id}_{N}` (sem `bestiary_id`)."""
    from agents import combat as cbt
    from services import conflict_orchestrator as orch
    from tests.test_bug_contabilidade_recompensas import _combat_state

    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "Fim.")

    def fake_run_round(scene, actors_by_id, sides, *a, **k):
        actors_by_id["enemy_rato_peste_anel_lama_1"].update(
            {"hp": 0, "vitalidade": 0, "dead": True, "status": "morto"}
        )
        return {
            "logs": ["Voce acerta o rato."],
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
            "ended": True,
            "player_dead": False,
        }

    monkeypatch.setattr(orch, "run_round", fake_run_round)
    state = _combat_state()
    victim = {**state["enemies"][1], "id": "enemy_rato_peste_anel_lama_1"}
    assert "bestiary_id" not in victim
    state["enemies"] = [victim]
    state["turn_baseline"] = {"gold": 0, "xp": 0, "level": 1}
    loc = gamedata.get_location("nova_arcadia")
    state["world"] = {
        "turn_count": 20,
        "current_location_id": "nova_arcadia",
        "current_location": loc["name"],
        "world_clock": {"day": 17, "period": "Manhã"},
    }
    state["quests"] = [
        {
            "id": "h1",
            "status": "active",
            "world_kind": "cacar_criatura",
            "created_turn": 5,
            "progress_log": [],
            "lore_anchor": {
                "type": "enemy",
                "id": "enemy_rato_peste_anel_lama",
                "region_id": "nova_arcadia",
            },
        }
    ]
    out = cbt.combat_node(state)
    kinds = [r["kind"] for r in out["quests"][0]["progress_log"]]
    assert "hunt_kill" in kinds


def test_presence_does_not_show_escorted_npc_at_detour_before_sync():
    """P2-1: desvio no mesmo turno => o escoltado fica onde estava, nao no local novo."""
    from tests.test_spec313_delivery_escort import _escort, _hops, _move

    st, _q, dest = _escort()
    _closer, worse = _hops("nova_arcadia", dest)
    _move(st, worse)  # ainda sem escort_sync
    assert npc_world.presence(st, NPC_KEY)[0] == "nova_arcadia"


def test_world_unheard_npc_prefix_requires_known_origin():
    """P2-2: `npc:<ref>:<turno>` so vale se o NPC existe e e a origem da quest."""
    st = npc_state()
    q = {"origin_name": "Rolf"}
    assert invariants._npc_offer_known(q, "npc:npc_rolf:17", st)
    assert not invariants._npc_offer_known(q, "npc:fantasma:17", st)
    assert not invariants._npc_offer_known({"origin_name": "Outro"}, "npc:npc_rolf:17", st)
    assert not invariants._npc_offer_known(q, "npc:npc_rolf", st)


def test_hunt_menu_respects_danger_tier():
    """P2-4: perigo <= 2 so oferece Minion; perigo >= 4 so Elite."""
    low = {"type": "Minion"}
    elite = {"type": "Elite"}
    assert lq._rollable(low, 2) and not lq._rollable(elite, 2)
    assert lq._rollable(low, 3) and lq._rollable(elite, 3)
    assert not lq._rollable(low, 4) and lq._rollable(elite, 4)
    st = npc_state()
    danger = int(gamedata.get_location("skallgard").get("danger", 1) or 1)
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    for item in menu:
        if item["kind"] == "cacar_criatura":
            assert lq._rollable(gamedata.BESTIARY[item["anchor_id"]], danger)


def test_lore_offer_does_not_consume_a_305_slot(monkeypatch):
    """P2-5: criar quest de lore na rodada nao ocupa vaga do teto de 3 da 305."""
    from tests.spec313_helpers import add_rumor

    st = npc_state(loc="nova_arcadia")
    st["npcs"] = {}
    add_rumor(st)
    st["quests"] = [
        {"id": "a", "status": "active", "world_kind": "romper_cerco"},
        {"id": "b", "status": "active", "world_kind": "conter_praga"},
    ]
    quests, created = wq.offer_from_heard(st, 17)
    assert [q["world_kind"] for q in created] == ["investigar_rumor"]
    assert wq._active_world(quests) == 2


def test_escorted_npc_dead_releases_escort_and_expires_quest():
    """P2-6: morte por outra via => escolta solta e quest encerrada sem esperar o prazo."""
    from tests.test_spec313_delivery_escort import _escort

    st, q, _dest = _escort()
    st["npc_sim"]["npcs"][NPC_REF]["dead"] = True
    st["world_sim"]["last_ticked_day"] = 18
    quests, events = wq.sync_deadlines(st, 18)
    assert quests[0]["status"] == "expired" and events == []
    st["quests"] = quests
    st.update(npc_world.escort_sync(st))
    assert "escort" not in st["npc_sim"]["npcs"][NPC_REF]


def test_mortos_templates_do_not_name_unknown_faction():
    """P2-7."""
    desc = wq.kind_cfg("recolher_mortos")["description"]
    assert not [t for t in desc.values() if "Guilda dos Corvos" in t]


def test_rumor_and_mortos_completion_requires_two_evidences():
    """P2-10: location_reached + uma evidencia qualquer nao basta; precisa de completion_ready."""
    for kind in ("investigar_rumor", "recolher_mortos"):
        quest = {
            "id": "q",
            "status": "active",
            "world_kind": kind,
            "location_id": "brekmar",
            "created_turn": 1,
            "progress_log": [
                {"kind": "location_reached", "turn": 2},
                {"kind": "npc_interaction", "turn": 3},
            ],
        }
        state = {"world": {"turn_count": 5}}
        assert quest_log.has_completion_proof(quest, state)[0] is False
        quest["progress_log"].append({"kind": "completion_ready", "turn": 4})
        assert quest_log.has_completion_proof(quest, state)[0] is True
