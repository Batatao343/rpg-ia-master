"""SPEC-389 R8-R10: entrega de missão pela rota NPC fecha a quest quando há prova; a seed `14 entrega` é coerente."""

from __future__ import annotations

import pytest

from agents import campaign_manager
from services import quest_log
from tests.fixtures import spec368_seed as sd

ENTREGA = "Entrego a prova da caça ao contratante"


def _quest(**over):
    base = {
        "id": "q1",
        "title": "Caça",
        "status": "active",
        "created_turn": 1,
        "origin_name": "Contratante",
        "origin_entity_id": "contratante",
        "progress_log": [],
    }
    return {**base, **over}


def _state(turn=4, **over):
    return {"world": {"turn_count": turn}, "npcs": {}, **over}


def test_delivery_to_origin_completes():
    quests, patch = quest_log.sync_npc_delivery(
        [_quest()], "Contratante", ENTREGA, _state(), turn=4
    )
    (event,) = patch["pending_world_events"]
    assert event["type"] == "quest_completed" and event["source"] == "system"
    assert event["payload"] == {"quest_id": "q1"}
    assert any(r["kind"] == "npc_interaction" for r in quests[0]["progress_log"])


def test_delivery_appends_to_pending_events():
    prior = {"type": "x"}
    _, patch = quest_log.sync_npc_delivery(
        [_quest()], "Contratante", ENTREGA, _state(pending_world_events=[prior]), turn=4
    )
    assert patch["pending_world_events"][0] == prior and len(patch["pending_world_events"]) == 2


def test_delivery_other_npc_no():
    _, patch = quest_log.sync_npc_delivery([_quest()], "Osshari", ENTREGA, _state(), turn=4)
    assert patch == {}


@pytest.mark.parametrize(
    "text", ["Não entrego nada", "Nunca devolvo isso", "Converso com o contratante"]
)
def test_delivery_negated_or_absent_no(text):
    _, patch = quest_log.sync_npc_delivery([_quest()], "Contratante", text, _state(), turn=4)
    assert patch == {}


@pytest.mark.parametrize(
    "over",
    [{"world_kind": "cacar_criatura"}, {"personal_of": "player"}, {"status": "completed"}],
)
def test_delivery_mechanical_personal_or_closed_no(over):
    _, patch = quest_log.sync_npc_delivery(
        [_quest(**over)], "Contratante", ENTREGA, _state(), turn=4
    )
    assert patch == {}


def test_delivery_same_turn_creation_no():
    _, patch = quest_log.sync_npc_delivery(
        [_quest(created_turn=4)], "Contratante", ENTREGA, _state(turn=4), turn=4
    )
    assert patch == {}  # sem prova: a quest nasceu neste turno


@pytest.mark.parametrize("past_turn", [4, 2])
def test_delivery_cooldown_respected(past_turn):
    """Conclusão no mesmo turno ou dentro do cooldown de 3 turnos: sem evento (a fonte `system`
    pula o gate do validador, então o limite mora em `delivery_ready`)."""
    state = _state(event_log=[{"type": "quest_completed", "turn": past_turn}])
    _, patch = quest_log.sync_npc_delivery([_quest()], "Contratante", ENTREGA, state, turn=4)
    assert patch == {}
    old = _state(event_log=[{"type": "quest_completed", "turn": 1}])
    _, patch = quest_log.sync_npc_delivery([_quest()], "Contratante", ENTREGA, old, turn=4)
    assert len(patch["pending_world_events"]) == 1


def test_delivery_only_one_per_turn():
    quests = [_quest(id="a"), _quest(id="b")]
    _, patch = quest_log.sync_npc_delivery(quests, "Contratante", ENTREGA, _state(), turn=4)
    assert len(patch["pending_world_events"]) == 1


def test_delivery_event_processed_grants_completion():
    from services.event_processor import process_pending_events

    quests, patch = quest_log.sync_npc_delivery(
        [_quest()], "Contratante", ENTREGA, _state(), turn=4
    )
    state = {
        "world": {"turn_count": 4},
        "quests": quests,
        "player": {"gold": 0, "level": 1},
        "pending_world_events": patch["pending_world_events"],
    }
    out = process_pending_events(state)
    assert next(q for q in out["quests"] if q["id"] == "q1")["status"] == "completed"


@pytest.fixture(scope="module")
def entrega(tmp_path_factory):
    saves = str(tmp_path_factory.mktemp("spec389_entrega"))
    gid = sd.seed_save(14, variant="entrega", saves_dir=saves)
    return saves, gid


def test_seed_entrega_no_region_replan(entrega):
    import persistence

    saves, gid = entrega
    with sd._legacy(saves):
        st = persistence.load_game_state(persistence.save_path(gid))
    assert campaign_manager._replan_reason(st) != "region_change"
    in_scene = [n for n, v in st["npcs"].items() if v.get("in_scene")]
    assert in_scene == ["Contratante"]


def test_seed_entrega_has_proof_after_origin_talk(entrega):
    import persistence

    saves, gid = entrega
    with sd._legacy(saves):
        st = persistence.load_game_state(persistence.save_path(gid))
    turn = int(st["world"]["turn_count"])
    quests = quest_log.sync_npc_interaction(st["quests"], "Contratante", turn=turn)
    quest = next(q for q in quests if q["id"] == "q368")
    assert quest_log.has_completion_proof(quest, st)[0] is True
    assert quest_log.delivery_ready(quests, "Contratante", ENTREGA, st) == ["q368"]


def test_real_region_change_still_replans():
    state = {
        "campaign_plan": {"location": "Nova Arcádia", "beats": [], "last_planned_turn": 0},
        "world": {"current_location": "Brekmar", "turn_count": 1},
    }
    assert campaign_manager._replan_reason(state) == "region_change"


def test_npc_node_enqueues_delivery(entrega):
    """O nó `npc_actor` (MockLLM) com a seed `14 entrega` enfileira o `quest_completed` do sistema."""
    from langchain_core.messages import HumanMessage

    import persistence
    from agents.npc import npc_actor_node

    saves, gid = entrega
    with sd._legacy(saves):
        st = persistence.load_game_state(persistence.save_path(gid))
        st["messages"] = [*st.get("messages", []), HumanMessage(content=ENTREGA)]
        st["active_npc_name"] = "Contratante"
        out = npc_actor_node(st)
    events = out.get("pending_world_events") or []
    assert [e["payload"]["quest_id"] for e in events if e["type"] == "quest_completed"] == ["q368"]
