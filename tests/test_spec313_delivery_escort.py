"""SPEC-313 Etapa 6: entrega (consome o material) e escolta (NPC viaja com o jogador)."""

from __future__ import annotations

import copy

import pytest
from langchain_core.messages import HumanMessage

import gamedata
import world_utils
from services import event_processor as ep
from services import lore_quests as lq
from services import npc_world
from services import world_distance as wd
from services import world_quests as wq
from tests.spec304_helpers import hook
from tests.spec313_helpers import NPC_KEY, NPC_REF, first_anchor, npc_state, proposal, setup_env


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    setup_env(monkeypatch)


# --- entrega -------------------------------------------------------------------------


def _delivery(inventory=None, text="Entrego o musgo ao boticário."):
    st = npc_state(loc="pantano_melancolia", role="druida herbalista")
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    aid = first_anchor(menu, "entregar_material")
    assert aid == "cha_druidas_anel_lama"
    _q, created, reason = wq.offer_from_proposal(
        st, proposal("entregar_material", aid), NPC_KEY, menu, 17
    )
    assert reason == ""
    st["quests"] = [created]
    inv = [{"id": "musgo_cinzento", "qty": 2}] if inventory is None else inventory
    st["player"] = {"name": "H", "level": 1, "xp": 0, "gold": 10, "inventory": inv}
    st["world"] = {
        **st["world"],
        "current_location_id": "na_anel_lama",
        "turn_count": 21,
        "world_clock": {"day": 19, "period": "Manhã"},
    }
    st["messages"] = [HumanMessage(content=text)]
    return st, created


def test_delivery_completes_at_destination_with_item_and_vocab():
    st, q = _delivery()
    events = wq.engine_completions(st)
    assert [e["type"] for e in events] == ["quest_completed"]
    # sem o verbo de entrega, ou fora do destino, nada acontece
    assert wq.engine_completions({**st, "messages": [HumanMessage(content="Olho ao redor.")]}) == []
    away = {**st, "world": {**st["world"], "current_location_id": "pantano_melancolia"}}
    assert wq.engine_completions(away) == []
    assert q["location_id"] == "na_anel_lama" and q["lore_anchor"]["qty"] == 2


def test_delivery_removes_item_once_in_same_apply_as_gold():
    st, q = _delivery(inventory=[{"id": "musgo_cinzento", "qty": 3}])
    out = ep.process_pending_events({**st, "pending_world_events": wq.engine_completions(st)})
    assert out["quests"][0]["status"] == "completed"
    assert out["player"]["gold"] == 10 + 15
    assert out["player"]["inventory"] == [{"id": "musgo_cinzento", "qty": 1}]
    again = ep.process_pending_events(
        {**st, **out, "pending_world_events": wq.engine_completions({**st, **out})}
    )
    assert again.get("player", out["player"])["inventory"] == [{"id": "musgo_cinzento", "qty": 1}]


def test_delivery_rejected_if_item_gone_before_apply():
    st, q = _delivery()
    events = wq.engine_completions(st)
    st["player"]["inventory"] = []  # vendeu entre a proposta e o apply
    out = ep.process_pending_events({**st, "pending_world_events": events})
    assert "quests" not in out or out["quests"][0]["status"] == "active"
    assert out.get("player", st["player"])["gold"] == 10


def test_delivery_requires_distance_destination_not_origin(monkeypatch):
    st = npc_state(loc="pantano_melancolia", role="druida herbalista")
    cfg = copy.deepcopy(lq.cfg())
    cfg["delivery_routes"][0]["to"] = "pantano_melancolia"
    monkeypatch.setattr(lq, "cfg", lambda: cfg)
    assert not [i for i in lq.anchor_menu(st, NPC_KEY)[1] if i["kind"] == "entregar_material"] or (
        lq.validate_anchor(
            st,
            "entregar_material",
            "cha_druidas_anel_lama",
            NPC_KEY,
            [{"kind": "entregar_material", "anchor_id": "cha_druidas_anel_lama"}],
        )[0]
        is False
    )


def test_delivery_fail_keeps_item():
    st, q = _delivery()
    st["world"]["world_clock"]["day"] = q["deadline_day"]
    st["world_sim"]["last_ticked_day"] = q["deadline_day"]
    quests, events = wq.sync_deadlines(st, q["deadline_day"])
    assert [e["type"] for e in events] == ["quest_failed"]
    st["quests"] = quests
    out = ep.process_pending_events({**st, "pending_world_events": events})
    assert out["quests"][0]["status"] == "failed"
    assert st["player"]["inventory"] == [{"id": "musgo_cinzento", "qty": 2}]
    assert "player" not in out or out["player"]["gold"] == 10


# --- escolta -------------------------------------------------------------------------


def _escort(dest_index=0):
    st = npc_state(loc="nova_arcadia", role="mercador", archetype="mercador_itinerante")
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    items = [i for i in menu if i["kind"] == "escoltar"]
    item = items[dest_index]
    _q, created, reason = wq.offer_from_proposal(
        st, proposal("escoltar", item["anchor_id"]), NPC_KEY, menu, 17
    )
    assert reason == ""
    st["quests"] = [created]
    dest = created["lore_anchor"]["to"]
    st["npc_sim"] = npc_world.escort_start(st, NPC_REF, created["id"], dest, 17)
    return st, created, dest


def _move(st, loc):
    st["world"] = {**st["world"], "current_location_id": loc}
    return st


def _hops(cur, dest):
    """Vizinhos de `cur`: (o que mais aproxima de `dest`, um que NAO aproxima)."""
    d0 = wd.travel_periods(cur, dest)
    nbrs = [n["id"] for n in gamedata.get_connections(cur) if n.get("id")]
    scored = sorted(
        (wd.travel_periods(n, dest), n) for n in nbrs if wd.travel_periods(n, dest) is not None
    )
    closer = next(n for d, n in scored if d < d0)
    worse = next(n for d, n in reversed(scored) if d >= d0)
    return closer, worse


def test_escort_start_marks_npc_and_presence_follows_player():
    st, q, dest = _escort()
    assert st["npc_sim"]["npcs"][NPC_REF]["escort"]["to"] == dest
    assert npc_world.presence(st, NPC_KEY) == ("nova_arcadia", False)
    closer, _worse = _hops("nova_arcadia", dest)
    _move(st, closer)
    assert npc_world.presence(st, NPC_KEY)[0] == closer


def test_escort_npc_follows_player_and_skips_daily_step():
    from tests.spec300_helpers import make_state

    st = make_state(party=False, location="nova_arcadia", day=3)
    st["npcs"] = {
        NPC_KEY: {
            "id": NPC_REF,
            "name": "Rolf",
            "role": "mercador de caravana",
            "in_scene": False,
            "known_by_player": True,
            "home_location_id": "nova_arcadia",
            "relationship": 5,
            "hidden_traits": [],
            "revealed_traits": [],
        }
    }
    st["quests"] = [{"id": "qe", "status": "active", "world_kind": "escoltar"}]
    hook(st, 3)
    st["npc_sim"] = npc_world.escort_start(st, NPC_REF, "qe", "pantano_melancolia", 3)
    assert st["npc_sim"]["npcs"][NPC_REF]["escort"]
    _move(st, "brekmar")  # jogador longe: a agenda da 304 so anda com o NPC fora da cena
    for day in range(4, 24):
        hook(st, day)
        entry = st["npc_sim"]["npcs"][NPC_REF]
        assert entry["pos"]["location_id"] == "nova_arcadia" and entry["escort"]
        assert not [p for p in st["npc_sim"]["perils"] if p["npc_id"] == NPC_REF]
    control = make_state(party=False, location="nova_arcadia", day=3)
    control["npcs"], control["quests"] = copy.deepcopy(st["npcs"]), []
    hook(control, 3)
    _move(control, "brekmar")
    moved = set()
    for day in range(4, 24):
        hook(control, day)
        moved.add(control["npc_sim"]["npcs"][NPC_REF]["pos"]["location_id"])
    assert moved != {"nova_arcadia"}  # sem escolta, a agenda da 304 anda


def test_escort_no_offscreen_peril_while_escorted():
    st, _q, _dest = _escort()
    entry = st["npc_sim"]["npcs"][NPC_REF]
    assert entry["escort"] and entry.get("status") == ""


def test_escort_pauses_when_player_detours_and_resumes_on_return():
    st, q, dest = _escort()
    closer, worse = _hops("nova_arcadia", dest)
    _move(st, worse)
    patch = npc_world.escort_sync(st)
    st.update(patch)
    esc = st["npc_sim"]["npcs"][NPC_REF]["escort"]
    assert esc["paused_at"] == "nova_arcadia"
    assert npc_world.presence(st, NPC_KEY)[0] == "nova_arcadia"  # fica onde o jogador saiu
    assert wq._source_state(st, q) == "active"  # nao falha por isso
    _move(st, "nova_arcadia")
    st.update(npc_world.escort_sync(st))
    assert st["npc_sim"]["npcs"][NPC_REF]["escort"]["paused_at"] == ""
    _move(st, closer)
    st.update(npc_world.escort_sync(st))
    assert st["npc_sim"]["npcs"][NPC_REF]["pos"]["location_id"] == closer


def test_escort_completes_on_arrival_and_npc_stays_at_destination():
    st, q, dest = _escort()
    cur = "nova_arcadia"
    for _ in range(12):
        if cur == dest:
            break
        cur, _w = _hops(cur, dest)
        _move(st, cur)
        st.update(npc_world.escort_sync(st))
    assert cur == dest
    events = wq.engine_completions({**st, "world": {**st["world"], "turn_count": 30}})
    assert [e["type"] for e in events] == ["quest_completed"]
    out = ep.process_pending_events(
        {
            **st,
            "pending_world_events": events,
            "player": {"name": "H", "level": 1, "xp": 0, "gold": 0, "inventory": []},
        }
    )
    assert out["quests"][0]["status"] == "completed"
    st.update(out)
    st.update(npc_world.escort_sync(st))
    entry = st["npc_sim"]["npcs"][NPC_REF]
    assert "escort" not in entry and entry["pos"]["location_id"] == dest


def test_escort_fail_on_deadline_clears_escort_resumes_simulation():
    st, q, dest = _escort()
    st["world"]["world_clock"]["day"] = q["deadline_day"]
    quests, events = wq.sync_deadlines(st, q["deadline_day"])
    assert [e["type"] for e in events] == ["quest_failed"]
    out = ep.process_pending_events({**st, "quests": quests, "pending_world_events": events})
    st.update(out)
    st.update(npc_world.escort_sync(st))
    entry = st["npc_sim"]["npcs"][NPC_REF]
    assert "escort" not in entry and entry["pos"]["location_id"] == "nova_arcadia"


def test_escorted_npc_never_in_party_nor_combat():
    st, _q, _dest = _escort()
    assert not st.get("party")
    assert st["npc_sim"]["npcs"][NPC_REF]["escort"]
    assert not any(c.get("name") == "Rolf" for c in st.get("party") or [])


def test_escort_and_delivery_do_not_change_encounters():
    """R27: check_encounter nao le quests de escolta/entrega."""
    loc = next(
        loc_row["id"]
        for loc_row in gamedata.WORLD_MAP["locations"]
        if int(loc_row.get("danger", 1) or 1) >= 4
    )
    seq = []
    for hunt in ("", ""):
        row = []
        for turn in range(0, 60, 2):
            world = {"current_location_id": loc, "last_encounter_turn": -99}
            enc = world_utils.check_encounter(world, [], {}, turn, player_level=5, hunt_anchor=hunt)
            row.append(bool(enc))
        seq.append(row)
    assert seq[0] == seq[1]
