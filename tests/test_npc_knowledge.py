"""SPEC-215 — conhecimento por NPC e propagação limitada (§4 passos 3–6, 8b, 9, 10).

100% offline e determinístico. O mapa real é usado para distâncias:
brekmar -3-> ophidia; nova_arcadia -2-> brekmar.
"""

from __future__ import annotations

import copy
import json

import pytest
from langchain_core.messages import AIMessage

from services import npc_knowledge as nk

KILL = {
    "event_id": "ev_kill_1",
    "turn": 7,
    "type": "npc_killed",
    "actor_id": "player",
    "target_id": "npc_valerius",
    "payload": {},
    "source": "combat",
}


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")


@pytest.fixture()
def always(monkeypatch):
    """Probabilidade 1.0 em todos os tipos (o sorteio seeded vira determinístico)."""
    params = {k: (1.0, radius, hops) for k, (_p, radius, hops) in nk.SUBJECT_PARAMS.items()}
    monkeypatch.setattr(nk, "SUBJECT_PARAMS", params)
    return params


def _state(**over) -> dict:
    base = {
        "game_id": "spec215-unit",
        "world": {
            "turn_count": 7,
            "current_location": "Brekmar",
            "current_location_id": "brekmar",
            "world_clock": {"day": 2, "period": "Tarde"},
        },  # clock 12
        "event_log": [],
        "world_projection": {},
        "memory_facts": [],
        "chronicle": [],
        "npcs": {
            "Lyra": {
                "name": "Lyra",
                "id": "npc_lyra",
                "home_location_id": "brekmar",
                "in_scene": True,
                "relationship": 5,
            },
            "Osric": {
                "name": "Osric",
                "id": "npc_osric",
                "home_location_id": "ophidia",
                "in_scene": False,
                "relationship": 5,
            },
        },
        "party": [],
        "knowledge_links": [],
        "knowledge_queue": [],
        "location_heard": {},
    }
    base.update(over)
    return base


def _merge(state: dict, upd: dict) -> dict:
    return {**state, **upd}


def _relations(links, holder):
    return {(lk["subject_id"], lk["relation"]) for lk in links if lk["holder_id"] == holder}


LYRA, OSRIC = "npc:npc_lyra", "npc:npc_osric"


# ------------------------------------------------------------------ testemunha (R2)
def test_witness_knows_death():
    links = nk.record_witnesses(_state(), KILL, "brekmar", 12)
    rel = _relations(links, LYRA)
    assert ("ev_kill_1", "observed_by") in rel and ("ev_kill_1", "believed_by") in rel
    assert all(lk["channel"] == "witness" and lk["hops"] == 0 for lk in links)


def test_distant_npc_unknown():
    st = _state()
    st["knowledge_links"] = nk.record_witnesses(st, KILL, "brekmar", 12)
    known = nk.known_subject_ids(st, "npc_osric")
    assert not any(known.values())


def test_party_present_witness():
    st = _state(party=[{"name": "Bram", "active": True, "status": "ativo"}])
    links = nk.record_witnesses(st, KILL, "brekmar", 12)
    assert ("ev_kill_1", "observed_by") in _relations(links, nk.holder_id(st, "Bram"))


def test_waiting_party_member_not_witness():
    st = _state(
        party=[{"name": "Bram", "active": False, "status": "ativo", "waiting_at": "Ophidia"}]
    )
    links = nk.record_witnesses(st, KILL, "brekmar", 12)
    assert not _relations(links, nk.holder_id(st, "Bram"))


def test_witness_only_at_event_location():
    assert nk.record_witnesses(_state(), KILL, "ophidia", 12) == []


# ------------------------------------------------------------------ propagação (R3/R4)
def _after_kill_turn(st=None):
    st = st or _state(event_log=[dict(KILL)])
    return _merge(st, nk.turn_updates(st))


def _delivery_to(state, to_id):
    return next(d for d in state["knowledge_queue"] if d["to_location_id"] == to_id)


def test_messenger_delivers_after_distance(always):
    st = _after_kill_turn()
    d = _delivery_to(st, "ophidia")
    assert d["due_clock"] >= 12 + 3 + 1  # distância + atraso mínimo de mensageiro
    early = _merge(st, nk.deliver_due(st, d["due_clock"] - 1))
    assert not any(nk.known_subject_ids(early, "npc_osric").values())
    on_time = _merge(st, nk.deliver_due(st, d["due_clock"]))
    rel = _relations(on_time["knowledge_links"], OSRIC)
    assert ("ev_kill_1", "told_to") in rel and ("ev_kill_1", "believed_by") in rel
    link = next(lk for lk in on_time["knowledge_links"] if lk["holder_id"] == OSRIC)
    assert link["channel"] == "messenger" and link["hops"] == 1
    assert "ev_kill_1" in on_time["location_heard"]["ophidia"]


def test_no_delivery_before_due_after_save_load(always):
    import persistence

    st = _after_kill_turn()
    d = _delivery_to(st, "ophidia")
    raw = json.loads(json.dumps(persistence._state_to_save_data(st, "spec215-unit")))
    loaded = persistence._raw_to_state(raw)
    assert loaded["knowledge_queue"] == st["knowledge_queue"]
    # recarregar não antecipa: antes do due nada chega a Osric.
    out = _merge(loaded, nk.deliver_due(loaded, d["due_clock"] - 1))
    assert not any(nk.known_subject_ids(out, "npc_osric").values())
    # repetir o turno de origem também não reagenda nem entrega antes.
    again = _merge(out, nk.turn_updates(out))
    assert not any(nk.known_subject_ids(again, "npc_osric").values())


def test_seeded_replay_identical():
    a = nk.turn_updates(_state(event_log=[dict(KILL)]))
    b = nk.turn_updates(copy.deepcopy(_state(event_log=[dict(KILL)])))
    assert a == b
    other = nk.turn_updates(_state(event_log=[dict(KILL)], game_id="outro-jogo"))
    assert isinstance(other.get("knowledge_queue"), list)


def test_probability_zero_never_delivers(monkeypatch):
    params = {k: (0.0, radius, hops) for k, (_p, radius, hops) in nk.SUBJECT_PARAMS.items()}
    monkeypatch.setattr(nk, "SUBJECT_PARAMS", params)
    st = _after_kill_turn()
    assert st["knowledge_queue"] == []


def test_max_hops_two(always):
    st = _after_kill_turn()
    for clock in range(12, 80):
        st = _merge(st, nk.deliver_due(st, clock))
    assert st["knowledge_links"]
    assert max(lk["hops"] for lk in st["knowledge_links"]) <= nk.MAX_HOPS
    assert any(lk["hops"] == 2 for lk in st["knowledge_links"]) or any(
        "ev_kill_1" in subs for subs in st["location_heard"].values()
    )
    assert not st["knowledge_queue"]  # hop 2 não agenda hop 3
    # raio respeitado: nenhum local fora do raio do tipo ouviu.
    from services.world_distance import travel_periods

    radius = nk.SUBJECT_PARAMS["npc_killed"][1]
    for loc, subs in st["location_heard"].items():
        if "ev_kill_1" in subs:
            assert travel_periods("brekmar", loc) <= radius


def test_queue_and_link_caps():
    links = [
        {
            "link_id": f"l{i}",
            "holder_id": f"npc:n{i}",
            "subject_kind": "event",
            "subject_id": f"e{i}",
            "relation": "told_to",
            "source": "world",
            "channel": "messenger",
            "hops": 1,
            "acquired_clock": i,
            "acquired_turn": i,
        }
        for i in range(nk.MAX_KNOWLEDGE_LINKS + 50)
    ]
    links.append(
        {
            "link_id": "obs",
            "holder_id": "npc:old",
            "subject_kind": "event",
            "subject_id": "e_old",
            "relation": "observed_by",
            "source": "world",
            "channel": "witness",
            "hops": 0,
            "acquired_clock": -5,
            "acquired_turn": 0,
        }
    )
    queue = [
        {
            "delivery_id": f"d{i}",
            "subject_kind": "event",
            "subject_id": "e",
            "from_location_id": "brekmar",
            "to_location_id": "ophidia",
            "hop": 1,
            "due_clock": 1000 - i,
            "created_turn": 1,
        }
        for i in range(nk.MAX_QUEUE + 30)
    ]
    heard = {"ophidia": [f"s{i}" for i in range(nk.MAX_HEARD_PER_LOCATION + 10)]}
    out = nk.normalize_knowledge(
        {"knowledge_links": links, "knowledge_queue": queue, "location_heard": heard}
    )
    assert len(out["knowledge_links"]) == nk.MAX_KNOWLEDGE_LINKS
    assert any(lk["link_id"] == "obs" for lk in out["knowledge_links"])  # observed preservado
    assert len(out["knowledge_queue"]) == nk.MAX_QUEUE
    dues = [d["due_clock"] for d in out["knowledge_queue"]]
    assert dues == sorted(dues) and dues[0] == 1000 - (nk.MAX_QUEUE + 29)
    assert len(out["location_heard"]["ophidia"]) == nk.MAX_HEARD_PER_LOCATION


def test_npc_created_later_inherits_only_delivered(always):
    st = _after_kill_turn()
    d = _delivery_to(st, "ophidia")
    pending = {
        **d,
        "delivery_id": "pend",
        "subject_id": "ev_pendente",
        "due_clock": d["due_clock"] + 50,
    }
    st["knowledge_queue"] = [*st["knowledge_queue"], pending]
    st = _merge(st, nk.deliver_due(st, d["due_clock"]))
    st["npcs"] = {
        **st["npcs"],
        "Nova": {"name": "Nova", "id": "npc_nova", "home_location_id": "ophidia"},
    }
    links = nk.inherit_local(st, "npc_nova", "ophidia", d["due_clock"] + 1)
    subjects = {lk["subject_id"] for lk in links}
    assert subjects == {"ev_kill_1"}
    assert all(lk["channel"] == "local_rumor" and lk["relation"] == "told_to" for lk in links)


# ------------------------------------------------------------------ rumor/mentira (R5)
def _claim(text="O ferreiro envenenou o poço.", mid="mem_claim_1", **over):
    row = {
        "memory_id": mid,
        "text": text,
        "provenance": "npc_claim",
        "confidence": "reported",
        "source_id": "npc:npc_lyra",
        "source_turn": 7,
        "canonical_entity_ids": ["npc_lyra"],
    }
    row.update(over)
    return row


def test_npc_claim_never_promoted(always):
    st = _state(
        memory_facts=[_claim()],
        npcs={
            **_state()["npcs"],
            "Tom": {
                "name": "Tom",
                "id": "npc_tom",
                "home_location_id": "brekmar",
                "in_scene": True,
            },
        },
    )
    before = copy.deepcopy(st)
    out = _merge(st, nk.turn_updates(st))
    for _clock in range(12, 40):
        out = _merge(out, nk.deliver_due(out, _clock))
    assert out["memory_facts"] == before["memory_facts"]
    assert out["event_log"] == before["event_log"]
    assert out["world_projection"] == before["world_projection"]
    assert any(lk["subject_id"] == "mem_claim_1" for lk in out["knowledge_links"])
    lines = [line for _sid, line in nk.knowledge_lines(out, "npc_tom")]
    assert lines and all(line.startswith("[BOATO") for line in lines)
    assert not any(
        lk["holder_id"] == LYRA
        for lk in out["knowledge_links"]
        if lk["subject_id"] == "mem_claim_1"
    )  # quem disse não "aprende"


def test_lie_believed_stays_in_relation():
    st = _state(
        memory_facts=[_claim()],
        npcs={
            **_state()["npcs"],
            "Tom": {
                "name": "Tom",
                "id": "npc_tom",
                "home_location_id": "brekmar",
                "in_scene": True,
            },
        },
    )
    out = _merge(st, nk.turn_updates(st))
    rel = _relations(out["knowledge_links"], "npc:npc_tom")
    assert ("mem_claim_1", "believed_by") in rel
    assert out["memory_facts"][0]["confidence"] == "reported"
    assert "revealed_facts" not in (out.get("world_projection") or {})


def _player_knows_kill(**over):
    chronicle = [
        {
            "chapter_id": "c1",
            "entries": [
                {"text": "Valerius caiu.", "turn": 6, "kind": "milestone", "event_id": "ev_kill_1"}
            ],
        }
    ]
    return _state(event_log=[{**KILL, "turn": 6}], chronicle=chronicle, **over)


def test_player_told_belief_threshold():
    st = _player_knows_kill()
    low = nk.record_player_told(st, "npc_lyra", "Sabia que Valerius morreu?", 12)
    assert _relations(low, LYRA) == {("ev_kill_1", "told_to")}
    assert low[0]["source"] == "player" and low[0]["channel"] == "player"
    st["npcs"]["Lyra"]["relationship"] = nk.BELIEF_MIN_RELATIONSHIP
    high = nk.record_player_told(st, "npc_lyra", "Sabia que Valerius morreu?", 12)
    assert _relations(high, LYRA) == {("ev_kill_1", "told_to"), ("ev_kill_1", "believed_by")}


def test_player_text_not_fact():
    st = _state()  # jogador não conhece nenhum evento
    before = copy.deepcopy(st)
    links = nk.record_player_told(st, "npc_lyra", "Valerius morreu e o rei também!", 12)
    assert links == []
    assert st == before
    told = nk.record_player_told(_player_knows_kill(), "npc_lyra", "falo do tempo", 12)
    assert told == []  # não mencionou a entidade


# ------------------------------------------------------------------ segredo (R7)
SECRET_TXT = "Dizem que a rede carmesim pode despertar em breve."


def test_secret_not_propagated(always):
    st = _state(
        memory_facts=[_claim(text=SECRET_TXT, mid="mem_secret")],
        event_log=[
            {
                "event_id": "ev_sec",
                "turn": 7,
                "type": "secret_revealed",
                "target_id": "npc_valerius",
                "payload": {},
                "source": "storyteller",
            }
        ],
    )
    out = _merge(st, nk.turn_updates(st))
    assert not any(d["subject_id"] in {"mem_secret", "ev_sec"} for d in out["knowledge_queue"])
    assert not any(lk["subject_id"] == "mem_secret" for lk in out["knowledge_links"])


def test_secret_absent_from_other_npc_context():
    st = _state(memory_facts=[_claim(text=SECRET_TXT, mid="mem_secret")])
    st["knowledge_links"] = [
        {
            "link_id": "x",
            "holder_id": OSRIC,
            "subject_kind": "memory_fact",
            "subject_id": "mem_secret",
            "relation": "told_to",
            "source": "loc:brekmar",
            "channel": "messenger",
            "hops": 1,
            "acquired_clock": 5,
            "acquired_turn": 3,
        }
    ]
    assert nk.knowledge_lines(st, "npc_osric") == []
    assert "carmesim" not in nk.npc_knowledge_block(st, "npc_osric")


# ------------------------------------------------------------------ cronologia/identidade (R12)
def test_links_ordered_by_clock():
    rows = [
        {
            "link_id": n,
            "holder_id": LYRA,
            "subject_kind": "event",
            "subject_id": "ev_kill_1",
            "relation": "told_to",
            "source": "world",
            "channel": "messenger",
            "hops": 1,
            "acquired_clock": c,
            "acquired_turn": 1,
        }
        for n, c in (("b", 9), ("a", 3), ("c", 30))
    ]
    out = nk.normalize_knowledge({"knowledge_links": rows})["knowledge_links"]
    assert [lk["acquired_clock"] for lk in out] == [3, 9, 30]
    # nunca "sabe antes": link com clock futuro não entra no contexto.
    st = _state(event_log=[dict(KILL)], knowledge_links=[out[2]])
    assert nk.knowledge_lines(st, "npc_lyra") == []


def test_identity_alias_holder_merge():
    st = _state(
        npcs={
            "Brunna Ponte-Alta": {
                "name": "Brunna Ponte-Alta",
                "id": "npc_brunna",
                "aliases": ["a barqueira"],
                "home_location_id": "brekmar",
                "in_scene": True,
            }
        }
    )
    assert (
        nk.holder_id(st, "a barqueira")
        == nk.holder_id(st, "Brunna Ponte-Alta")
        == nk.holder_id(st, "npc_brunna")
        == "npc:npc_brunna"
    )
    st["knowledge_links"] = nk.record_witnesses(st, KILL, "brekmar", 12)
    assert nk.known_subject_ids(st, "a barqueira")["observed"] == {"ev_kill_1"}


# ------------------------------------------------------------------ entrega no finalizer (8b)
def _finalizer_state(**over):
    st = _state(
        messages=[AIMessage(content="Você foge pela estrada.")],
        player={"xp": 0},
        enemies=[],
        **over,
    )
    return st


def test_flee_travel_triggers_delivery(always):
    from agents.turn_finalizer import turn_finalizer_node

    base = _after_kill_turn()
    d = _delivery_to(base, "ophidia")
    day, idx = divmod(d["due_clock"], 5)
    import world_utils

    # fuga de combate avançou o relógio até o due (sem storyteller no turno).
    st = _finalizer_state(
        knowledge_queue=base["knowledge_queue"],
        knowledge_links=base["knowledge_links"],
        location_heard=base["location_heard"],
        event_log=base["event_log"],
        world={
            **base["world"],
            "turn_count": 8,
            "current_location_id": "nova_arcadia",
            "world_clock": {"day": day, "period": world_utils.PERIODS[idx]},
        },
    )
    out = turn_finalizer_node(st)
    assert ("ev_kill_1", "told_to") in _relations(out["knowledge_links"], OSRIC)


def test_deliver_due_idempotent_twice_same_turn(always):
    st = _after_kill_turn()
    d = _delivery_to(st, "ophidia")
    once = _merge(st, nk.deliver_due(st, d["due_clock"]))
    twice = _merge(once, nk.deliver_due(once, d["due_clock"]))
    assert once["knowledge_links"] == twice["knowledge_links"]
    again = _merge(once, nk.turn_updates(once))
    assert len(again["knowledge_links"]) == len(once["knowledge_links"])


def test_finalizer_off_is_noop(monkeypatch, always):
    from agents.turn_finalizer import turn_finalizer_node

    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")
    out = turn_finalizer_node(_finalizer_state(event_log=[dict(KILL)]))
    assert not any(k.startswith("knowledge_") or k == "location_heard" for k in out)


def test_finalizer_survives_internal_error(monkeypatch):
    from agents.turn_finalizer import turn_finalizer_node

    def boom(_state):
        raise RuntimeError("ledger quebrado")

    monkeypatch.setattr(nk, "turn_updates", boom)
    out = turn_finalizer_node(_finalizer_state(event_log=[dict(KILL)]))
    assert "last_turn_outcome" in out


def test_legacy_events_never_distributed(always):
    old = {**KILL, "turn": 2}
    st = _state(event_log=[old], legacy_knowledge=True)
    out = _merge(st, nk.turn_updates(st))
    assert out["knowledge_links"] == [] and out["knowledge_queue"] == []


# ------------------------------------------------------------------ invariantes (passo 10)
def test_invariant_teleport_and_rumor_promoted():
    from playtest import invariants as inv

    bad_link = {
        "link_id": "t",
        "holder_id": OSRIC,
        "subject_kind": "event",
        "subject_id": "ev_kill_1",
        "relation": "told_to",
        "source": "loc:brekmar",
        "channel": "messenger",
        "hops": 1,
        "acquired_clock": 13,
        "acquired_turn": 7,
        "origin_location_id": "brekmar",
        "origin_clock": 12,
        "location_id": "ophidia",
    }
    st = _state(knowledge_links=[bad_link])
    ids = {v.check_id for v in inv.check_all(st)}
    assert "knowledge.teleport" in ids
    ok = {**bad_link, "acquired_clock": 16}
    assert "knowledge.teleport" not in {
        v.check_id for v in inv.check_all(_state(knowledge_links=[ok]))
    }
    promoted = _claim(confidence="confirmed")
    st2 = _state(
        memory_facts=[promoted],
        knowledge_links=[{**ok, "subject_kind": "memory_fact", "subject_id": "mem_claim_1"}],
    )
    assert "knowledge.rumor_promoted" in {v.check_id for v in inv.check_all(st2)}
    clean = _state(
        memory_facts=[_claim()],
        knowledge_links=[{**ok, "subject_kind": "memory_fact", "subject_id": "mem_claim_1"}],
    )
    assert "knowledge.rumor_promoted" not in {v.check_id for v in inv.check_all(clean)}


def test_mode_parsing(monkeypatch):
    for raw, want in (
        ("on", "on"),
        ("SHADOW", "shadow"),
        ("off", "off"),
        ("", "off"),
        ("lixo", "off"),
    ):
        monkeypatch.setenv("RPG_NPC_KNOWLEDGE", raw)
        assert nk.mode() == want
    monkeypatch.delenv("RPG_NPC_KNOWLEDGE")
    assert nk.mode() == "off"


# ------------------------------------------------------------------ revisão Astra
def test_witness_only_secret_never_heard_nor_inherited(always):
    """R7: `secret_revealed` é só testemunhável — não entra em `location_heard`
    nem é herdado como rumor local por NPC criado depois no mesmo local."""
    ev = {
        "event_id": "ev_secret_1",
        "turn": 7,
        "type": "secret_revealed",
        "actor_id": "player",
        "target_id": "brekmar",
        "payload": {"location_id": "brekmar", "detail": "fato revelado"},
    }
    st = _state(
        event_log=[ev],
        world_projection={
            "revealed_facts": {
                "ev_secret_1": {
                    "entity_id": "brekmar",
                    "fact": "fato revelado",
                    "revealed_at_turn": 7,
                }
            }
        },
    )
    st = _merge(st, nk.turn_updates(st))
    assert "ev_secret_1" not in (st.get("location_heard") or {}).get("brekmar", [])
    assert not [d for d in st.get("knowledge_queue") or [] if d["subject_id"] == "ev_secret_1"]
    st["location_heard"] = {"brekmar": ["ev_secret_1"]}  # save adulterado/antigo
    st["npcs"] = {
        **st["npcs"],
        "Nova": {"name": "Nova", "id": "npc_nova", "home_location_id": "brekmar"},
    }
    assert nk.inherit_local(st, "npc_nova", "brekmar", 13) == []
