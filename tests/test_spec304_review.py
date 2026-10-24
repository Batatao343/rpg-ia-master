"""SPEC-304 correções da revisão Sol (P1-1, P1-2, P2-3, P2-4, P2-6, P2-7)."""

from __future__ import annotations

import copy

import pytest

from services import companion_soul as cs
from services import event_processor as ep
from services import npc_perils, npc_world
from services.world_validators import validate_proposal
from tests.spec304_helpers import BRUNNA_ID, hook, setup_env, waiting_state

FATES = ("morto", "ferido", "capturado", "escapou")


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    setup_env(monkeypatch, "on")


def _cfg(monkeypatch, p, fate):
    cfg = copy.deepcopy(npc_perils.cfg())
    cfg["BASE_HAZARD"] = {"3": p, "4": p}
    cfg["HOME_MULT"] = 1.0
    cfg["constants"]["P_FLEE"] = 0.0
    for kind in cfg["fate_weights"]:
        cfg["fate_weights"][kind] = {f: (1 if f == fate else 0) for f in FATES}
    monkeypatch.setattr(npc_perils, "cfg", lambda: cfg)


def _resolved_companion(monkeypatch, fate: str) -> tuple[dict, dict]:
    """Brunna espera num local de perigo; destino aplicado, jogador NAO percebeu o destino."""
    _cfg(monkeypatch, 1.0, fate)
    monkeypatch.setattr(npc_world, "_candidates", lambda state, sim: [BRUNNA_ID])
    st = waiting_state()
    hook(st, 2)
    st["world_sim"]["calm_until_day"] = 0
    st["quests"] = [cs.build_personal_quest(st, st["party"][0], turn=1)]
    hook(st, 3)
    before = {
        "party": copy.deepcopy(npc_world.public_party(st)),
        "quests": copy.deepcopy(npc_world.public_quests(st)),
    }
    _cfg(monkeypatch, 0.0, fate)
    d = 3
    while not any(p["resolution"] for p in st["npc_sim"]["perils"]) and d < 20:
        d += 1
        st["world_sim"].setdefault("perceived_ids", []).append(
            st["npc_sim"]["perils"][0]["warning_event_id"]
        )
        hook(st, d)
    assert st["npc_sim"]["perils"][0]["resolution"] == fate
    return st, before


@pytest.mark.parametrize("fate", ["ferido", "capturado", "morto"])
def test_party_and_quests_show_last_seen_until_perceived(monkeypatch, fate):
    st, before = _resolved_companion(monkeypatch, fate)
    pub_party = npc_world.public_party(st)
    pub_quests = npc_world.public_quests(st)
    assert pub_party == before["party"]  # sem status literal, vitalidade real nem sumico
    assert [q["status"] for q in pub_quests] == ["active"]
    assert not any(c["status"] in ("capturado", "morto") for c in pub_party)
    # a verdade mudou (controle): o motor aplicou o destino
    assert st["party"] != before["party"] or fate == "escapou"
    # contexto/dossie: a missao pessoal `failed` do motor fica oculta
    failed = [e for e in st["event_log"] if e["type"] == "quest_failed"]
    assert all(npc_world.event_hidden_from_player(st, e) for e in failed)
    chron = " ".join(
        c.get("text", "") for ch in st.get("chronicle", []) for c in ch.get("entries", [])
    )
    assert "morreu" not in chron and "capturado" not in chron
    # depois de PERCEBER, vale a verdade
    fid = st["npc_sim"]["npcs"][BRUNNA_ID]["fate_event_id"]
    st["npc_beliefs"] = {BRUNNA_ID: {"status_known": fate, "source_event_id": fid}}
    assert npc_world.public_party(st) == [c for c in st["party"] if isinstance(c, dict)]
    assert [q["status"] for q in npc_world.public_quests(st)] == [q["status"] for q in st["quests"]]


def test_api_response_uses_public_party(monkeypatch):
    import api

    st, before = _resolved_companion(monkeypatch, "capturado")
    st["world"] = {**st["world"], "current_location": "Nova Arcádia", "visited": ["nova_arcadia"]}
    st.setdefault("player", {"name": "T", "class_name": "Devoto do Abismo", "race": "Humano"})
    st["messages"] = []
    resp = api.format_response(st)
    assert [c["status"] for c in resp.party] == [c["status"] for c in before["party"]]
    assert [c["vitalidade"] for c in resp.party] == [c["vitalidade"] for c in before["party"]]


def test_orphan_quest_deferred_until_fate_learned():
    ref = "npc_mv_skek_eco_curto"
    st = waiting_state()
    st["quests"] = [{"id": "q1", "title": "Ajudar", "status": "active", "origin_entity_id": ref}]
    kill = {
        "type": "npc_killed",
        "actor_id": "world",
        "target_id": ref,
        "source": "engine",
        "event_id": "k1",
        "payload": {"offscreen": True, "location_id": "montanhas_afiadas", "fate": "morto"},
    }
    st["pending_world_events"] = [kill]
    out = ep.process_pending_events(st)
    assert not out.get("quests") or out["quests"][0]["status"] == "active"
    assert not [e for e in out["event_log"] if e["type"] == "quest_failed"]
    # a MESMA morte, mas on-screen (sem offscreen), falha na hora (comportamento antigo)
    st2 = waiting_state()
    st2["quests"] = copy.deepcopy(st["quests"])
    st2["pending_world_events"] = [{**kill, "source": "combat", "payload": {}}]
    out2 = ep.process_pending_events(st2)
    assert out2["quests"][0]["status"] == "failed"


def test_forged_offscreen_flag_from_llm_is_ignored():
    forged = {"type": "npc_killed", "source": "storyteller", "payload": {"offscreen": True}}
    assert not ep.is_offscreen_event(forged)
    ev = {**forged, "event_id": "f1", "target_id": "x"}
    assert npc_world.event_hidden_from_player({}, ev) is False
    real = {**forged, "source": "engine"}
    assert ep.is_offscreen_event(real)


def test_leader_cascade_inherits_secret():
    st = waiting_state()
    peril = {"peril_id": "p", "npc_id": "npc_kahen", "kind": "emboscada", "location_id": "brekmar"}
    st["pending_world_events"] = npc_perils.fate_events(st, peril, "morto", 5, graph_npc=True)
    out = ep.process_pending_events(st)
    derived = [e for e in out["event_log"] if e.get("source") == "rule_engine"]
    ctrl = [e for e in derived if e["type"] == "location_control_changed"]
    assert ctrl and all(e["payload"]["offscreen"] and e["payload"]["cause_event_id"] for e in ctrl)
    assert all(npc_world.event_hidden_from_player({**st, **out}, e) for e in ctrl)
    chron = " ".join(c["text"] for ch in out.get("chronicle", []) for c in ch["entries"])
    assert "tomou o controle" not in chron
    kill_id = out["event_log"][0]["event_id"]
    known = {**st, **out, "npc_beliefs": {"npc_kahen": {"source_event_id": kill_id}}}
    assert not npc_world.event_hidden_from_player(known, ctrl[0])  # percebida a causa, aparece


def test_belief_keeps_earlier_perceived_events():
    st = waiting_state()
    st["npc_sim"] = {"version": 1, "perils": [], "npcs": {}}
    warn = {
        "kind": "npc_perigo",
        "template_id": "npc_perigo.rumor",
        "params": {"npc_id": "npc_zed"},
        "location_id": "ma_saidas_baixas",
        "subject_id": "w1",
    }
    b1, _ = npc_world.on_perceived(st, [warn])
    b2, _ = npc_world.on_perceived(
        {**st, "npc_beliefs": b1},
        [
            {
                **warn,
                "kind": "npc_ausente",
                "template_id": "npc_ausente.ignorado",
                "subject_id": "a1",
            }
        ],
    )
    assert b2["npc_zed"]["source_event_id"] == "a1"
    assert {"w1", "a1"} <= npc_world._known_sources({"npc_beliefs": b2})
    hidden = {"event_id": "w1", "type": "npc_peril_warning", "payload": {}}
    assert not npc_world.event_hidden_from_player({"npc_beliefs": b2}, hidden)


@pytest.mark.parametrize(
    "etype,payload",
    [
        ("npc_peril_warning", {"peril_id": "p", "location_id": "ma_saidas_baixas"}),
        ("npc_offscreen_fate", {"fate": "ferido"}),
        ("npc_fate_learned", {"source_event_id": "x"}),
        ("npc_defected", {"from_faction_id": "legiao_ferro", "to_faction_id": "poder_kahen"}),
    ],
)
def test_all_four_types_engine_only(etype, payload):
    state = {"npcs": {}, "world": {}, "event_log": []}
    base = {
        "type": etype,
        "actor_id": "world",
        "target_id": "npc_mv_jax_corda_seca",
        "payload": payload,
    }
    for src in ("storyteller", "combat", None):
        prop = base if src is None else {**base, "source": src}
        res = validate_proposal(prop, state)
        assert not res.ok and "motor" in res.reason, (etype, src)
    assert validate_proposal({**base, "source": "engine"}, state).ok


def test_save_without_keys_when_off(tmp_path, monkeypatch):
    import persistence

    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = "11111111-2222-4333-8444-555555555999"
    state = {"game_id": gid, "messages": [], "player": {}, "world": {}}
    assert persistence.save_game_state(state)
    import json
    import pathlib

    raw = json.loads(pathlib.Path(persistence.save_path(gid)).read_text(encoding="utf-8"))
    assert "npc_sim" not in raw and "npc_beliefs" not in raw and "npc_sim_shadow" not in raw
    assert persistence.load_game_state(persistence.save_path(gid))["npc_sim"] == {}


def test_encounter_path_does_not_overwrite_scene_npcs_with_patch():
    """P2-1: no caminho de encontro o `npcs` do state_patch ja esta em `scene_npcs` (com o
    reset_scene da viagem); `updates.update(sim_updates)` nao pode sobrescrevê-lo."""
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[1].joinpath("agents", "storyteller.py")
    text = src.read_text(encoding="utf-8")
    assert "updates.update(sim_updates)\n" not in text
    assert 'if k != "npcs"' in text
