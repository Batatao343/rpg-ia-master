"""SPEC-299 etapa 4 — testemunhas, furtividade, relato com atraso e eventos."""

from __future__ import annotations

import pytest

from services import law, law_codes, npc_knowledge, world_distance
from services.world_validators import validate_proposal
from tests.spec299_helpers import base_state, clock_where, commit, with_clock


@pytest.fixture(autouse=True)
def _law_on(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "on")
    monkeypatch.delenv("RPG_NPC_KNOWLEDGE", raising=False)


@pytest.fixture
def no_patrol(monkeypatch):
    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: False)


def _civil_reports(monkeypatch):
    """Todo civil relata (seed forçada) para isolar o atraso."""
    monkeypatch.setattr(law, "_unit", lambda *a: 0.0)


def test_party_is_not_a_reporting_witness(no_patrol):
    state = base_state()
    state["npcs"] = {
        "Lia": {
            "name": "Lia",
            "id": "npc_lia",
            "in_scene": True,
            "home_location_id": "nova_arcadia",
        }
    }
    state["party"] = [{"name": "Lia", "id": "npc_lia", "active": True, "status": "ativo"}]
    _st, rec, _why = commit(state, "furto")
    assert rec["witnesses"] == [] and rec["status"] == "unwitnessed"


def test_no_witness_no_report(no_patrol):
    state = base_state()
    state["npcs"] = {}
    st, rec, why = commit(state, "furto")
    assert why == "unwitnessed" and rec["status"] == "unwitnessed"
    assert st["law_state"]["reports"] == []
    out = law.turn_updates(st)
    assert not out.get("law_state", {}).get("wanted")
    assert "pending_world_events" not in out


def test_patrol_only_if_shown_in_scene():
    state = base_state()
    state["npcs"] = {}
    seen = clock_where(state, "nova_arcadia", patrol=True)
    unseen = clock_where(state, "nova_arcadia", patrol=False)
    # cena com patrulha: fato de cena aparece E a patrulha testemunha
    on = with_clock(state, seen)
    text, _ = law.scene_block(on)
    assert "patrulham" in text
    _st, rec, _ = commit(on, "furto")
    assert rec["witnesses"] == ["patrol:nova_arcadia"]
    # cena sem patrulha: nada no prompt e nenhuma testemunha
    off = with_clock(state, unseen)
    assert law.scene_block(off) == ("", {})
    _st, rec, _ = commit(off, "furto")
    assert rec["witnesses"] == [] and rec["status"] == "unwitnessed"


def test_covert_check_deterministic(no_patrol):
    state = base_state()
    results = {commit(state, "furto", covert=True)[1]["status"] for _ in range(3)}
    assert len(results) == 1  # mesma seed, mesmo resultado
    # DC alta + agilidade zero: um observador comum não percebe sempre; seeds diferentes variam
    outcomes = set()
    for gid in range(40):
        s = base_state(game_id=f"cov{gid}")
        outcomes.add(commit(s, "furto", covert=True)[1]["status"])
    assert "unwitnessed" in outcomes and len(outcomes) >= 2


def test_colmeia_ignores_covert(no_patrol):
    state = base_state("sx_cidades_hospedeiros")
    state["npcs"]["Mercador"]["home_location_id"] = "sx_cidades_hospedeiros"
    for gid in range(15):
        s = {**state, "game_id": f"col{gid}"}
        _st, rec, _ = commit(s, "furto", covert=True)
        assert rec["covert"] is False and rec["witnesses"] == ["npc:npc_mercador"]
        assert _st["law_state"]["reports"][0]["due_clock"] == rec["clock"]  # imediato


def test_civil_report_delay(no_patrol, monkeypatch):
    _civil_reports(monkeypatch)
    state = base_state()
    st, rec, _ = commit(state, "furto")
    rep = st["law_state"]["reports"][0]
    assert rep["due_clock"] == rec["clock"] + 1  # report_delay_periods
    assert (
        "wanted" not in (law.turn_updates(st).get("law_state") or {})
        or not law.turn_updates(st)["law_state"]["wanted"]
    )
    later = with_clock(st, rec["clock"] + 1)
    out = law.turn_updates(later)
    assert out["law_state"]["wanted"]["codigo_de_ferro"]["heat"] == 15
    assert out["law_state"]["crimes"][0]["status"] == "reported"


def test_dead_witness_report_dropped(no_patrol, monkeypatch):
    _civil_reports(monkeypatch)
    st, rec, _ = commit(base_state(), "furto")
    st["npcs"]["Mercador"]["status"] = "morto"
    later = with_clock(st, rec["clock"] + 1)
    out = law.turn_updates(later)
    assert out["law_state"]["reports"][0]["status"] == "dropped"
    assert not out["law_state"]["wanted"]
    assert "pending_world_events" not in out


def test_witness_who_joined_party_does_not_report(no_patrol, monkeypatch):
    _civil_reports(monkeypatch)
    st, rec, _ = commit(base_state(), "furto")
    st["party"] = [{"name": "Mercador", "id": "npc_mercador", "active": True, "status": "ativo"}]
    out = law.turn_updates(with_clock(st, rec["clock"] + 1))
    assert out["law_state"]["reports"][0]["status"] == "dropped"


def test_spread_delay_uses_world_distance():
    state = base_state()
    state["npcs"] = {}
    state = with_clock(state, clock_where(state, "nova_arcadia", patrol=True))
    st, rec, _ = commit(state, "furto")
    out = law.turn_updates(st)
    known = out["law_state"]["wanted"]["codigo_de_ferro"]["known_at"]
    code = law_codes.get_code("codigo_de_ferro")
    assert known["nova_arcadia"] == rec["clock"]
    for loc in ("na_anel_dourado", "na_anel_ferro"):
        dist = world_distance.travel_periods("nova_arcadia", loc)
        assert known[loc] == rec["clock"] + dist + code["courier_delay_periods"]
    assert "brekmar" not in known  # outra jurisdição / sem lei: a notícia não vai


def test_crime_witnessed_requires_source_law():
    state = base_state()
    state["npcs"] = {}
    state = with_clock(state, clock_where(state, "nova_arcadia", patrol=True))
    st, rec, _ = commit(state, "furto")
    out = law.turn_updates(st)
    event = out["pending_world_events"][0]
    assert event["type"] == "crime_witnessed" and event["source"] == "law"
    st = {**st, **out}
    assert validate_proposal(event, st).ok
    forged = {k: v for k, v in event.items() if k != "source"}
    assert not validate_proposal(forged, st).ok
    assert not validate_proposal({**event, "source": "storyteller"}, st).ok
    bad = {**event, "target_id": "crime_inexistente"}
    assert not validate_proposal(bad, st).ok


def test_law_resolved_validator_and_source():
    ev = {
        "type": "law_resolved",
        "actor_id": "player",
        "target_id": "codigo_de_ferro",
        "payload": {"mode": "fine"},
    }
    assert not validate_proposal(ev, base_state()).ok
    assert validate_proposal({**ev, "source": "law"}, base_state()).ok
    assert not validate_proposal({**ev, "source": "law", "payload": {"mode": "x"}}, base_state()).ok


def test_npc_knowledge_propagates_crime_when_on(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    state = base_state()
    state["event_log"] = [
        {
            "event_id": "ev_crime",
            "turn": 5,
            "type": "crime_witnessed",
            "actor_id": "player",
            "target_id": "c1",
            "payload": {"location_id": "nova_arcadia"},
            "source": "law",
        }
    ]
    out = npc_knowledge.turn_updates(state)
    assert any(d["subject_id"] == "ev_crime" for d in out["knowledge_queue"])
    assert "crime_witnessed" in npc_knowledge.SUBJECT_PARAMS


def test_law_independent_of_npc_knowledge_off():
    assert npc_knowledge.mode() == "off"
    state = base_state()
    state["npcs"] = {}
    state = with_clock(state, clock_where(state, "nova_arcadia", patrol=True))
    st, _rec, _ = commit(state, "furto")
    assert law.turn_updates(st)["law_state"]["wanted"]["codigo_de_ferro"]["heat"] > 0
