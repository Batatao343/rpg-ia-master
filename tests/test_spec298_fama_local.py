"""SPEC-298 Etapa 4 — fama por local e reação a notícias (R14-R16)."""

import copy

import pytest

from services import npc_knowledge
from services import reputation as rep
from services.event_processor import process_pending_events

LEGIAO = "legiao_ferro"
THRACE = {
    "id": "npc_comandante_thrace",
    "name": "Thrace",
    "in_scene": True,
    "relationship": 5,
    "known_by_player": True,
}
KILL = {
    "type": "npc_killed",
    "actor_id": "player",
    "target_id": "npc_korvus",
    "payload": {},
    "source": "engine",
}


def _state(npcs=None, **extra):
    st = {
        "game_id": "g298",
        "player": {"name": "T", "race": "Humano"},
        "world": {
            "turn_count": 5,
            "current_location_id": "nova_arcadia",
            "world_clock": {"day": 2, "period": "manha"},
        },
        "factions": [
            {"id": LEGIAO, "name": "Legião de Ferro", "reputation": 0, "disposition": "neutro"}
        ],
        "faction_intel": {LEGIAO: {"known": True}},
        "npcs": npcs if npcs is not None else {},
        "event_log": [],
        "world_projection": {},
        "quests": [],
        "pending_world_events": [copy.deepcopy(KILL)],
    }
    st.update(extra)
    return st


def _witness():
    # presença de uma testemunha qualquer (sem fação) na cena
    return {"Mira": {"id": "npc_mira", "name": "Mira", "in_scene": True, "relationship": 5}}


def test_feito_sem_testemunha_nao_gera_fama(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    out = process_pending_events(_state({}))
    assert not out["location_fame"]


def test_feito_testemunhado_gera_fama_no_local(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")
    out = process_pending_events(_state(_witness()))
    fame = rep.fame_at({"location_fame": out["location_fame"]}, "nova_arcadia")
    assert fame["infamy"] == 15 and fame["infamy_label"] == "malvisto"
    assert any(n["kind"] == "fame" for n in out["reputation_notices"])


def _after_kill(monkeypatch, mode="on", with_witness=False):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", mode)
    st = _state(_witness() if with_witness else {})
    out = process_pending_events(st)
    return {**st, **out, "pending_world_events": []}


def test_entrega_spec215_gera_fama_no_destino(monkeypatch):
    st = _after_kill(monkeypatch, with_witness=True)
    kill = next(e for e in st["event_log"] if e["type"] == "npc_killed")
    st["location_heard"] = {
        "nova_arcadia": [kill["event_id"]],
        "skallgard": [kill["event_id"]],
    }
    st["world"] = {**st["world"], "current_location_id": "skallgard"}
    out = rep.turn_updates(st)
    assert out["location_fame"]["skallgard"]["infamy"] == 15
    # origem não é recontada pela entrega (só a testemunha vale lá)
    assert out["location_fame"]["nova_arcadia"]["infamy"] == 15
    assert any(n["kind"] == "fame" for n in out["reputation_notices"])


def test_origem_sem_testemunha_nao_ganha_fama_por_heard(monkeypatch):
    st = _after_kill(monkeypatch, with_witness=False)
    kill = next(e for e in st["event_log"] if e["type"] == "npc_killed")
    st["location_heard"] = {"nova_arcadia": [kill["event_id"]]}
    out = rep.turn_updates(st)
    assert "location_fame" not in out or not out["location_fame"].get("nova_arcadia")


def test_fama_idempotente_por_assunto(monkeypatch):
    st = _after_kill(monkeypatch, with_witness=True)
    kill = next(e for e in st["event_log"] if e["type"] == "npc_killed")
    st["location_heard"] = {"skallgard": [kill["event_id"]]}
    first = rep.turn_updates(st)
    st2 = {**st, **first}
    second = rep.turn_updates(st2)
    assert "location_fame" not in second
    assert rep.fame_at(st2, "skallgard")["infamy"] == 15
    assert rep.deed_known_at(st2, kill["event_id"], "skallgard")


def test_off_so_testemunha(monkeypatch):
    st = _after_kill(monkeypatch, mode="off", with_witness=True)
    kill = next(e for e in st["event_log"] if e["type"] == "npc_killed")
    st["location_heard"] = {"skallgard": [kill["event_id"]]}
    out = rep.turn_updates(st)
    assert "location_fame" not in out


def test_npc_reage_uma_vez_por_assunto(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    st = _state({"Thrace": dict(THRACE)}, pending_world_events=[])
    st["event_log"] = [
        {
            "event_id": "d1",
            "turn": 5,
            "type": "faction_deed",
            "actor_id": "player",
            "target_id": LEGIAO,
            "payload": {
                "deed": {
                    "faction_id": LEGIAO,
                    "npc_delta": -1,
                    "renown": 0,
                    "infamy": 0,
                    "direction": "prejudicou",
                },
                "location_id": "nova_arcadia",
            },
        }
    ]
    st["knowledge_links"] = [
        {
            "link_id": "l1",
            "holder_id": "npc:npc_comandante_thrace",
            "subject_kind": "event",
            "subject_id": "d1",
            "relation": "observed_by",
            "source": "world",
            "channel": "witness",
            "hops": 0,
            "acquired_clock": 0,
            "acquired_turn": 5,
        }
    ]
    out = rep.turn_updates(st)
    assert out["npcs"]["Thrace"]["relationship"] == 4
    assert out["npcs"]["Thrace"]["heard_deeds"] == ["d1"]
    assert any(n["text"] == "Thrace não gostou disso." for n in out["reputation_notices"])
    st2 = {**st, **out}
    st2["world"] = {**st2["world"], "turn_count": 6}
    again = rep.turn_updates(st2)
    assert "npcs" not in again


def test_pendencia_aplicada_quando_noticia_chega_a_local_da_faccao(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    st = _state({}, pending_world_events=[])
    st["event_log"] = [
        {
            "event_id": "d2",
            "turn": 4,
            "type": "npc_killed",
            "actor_id": "player",
            "target_id": "npc_korvus",
            "payload": {
                "location_id": "nova_arcadia",
                "deed": {"faction_id": LEGIAO, "npc_delta": -1, "renown": 0, "infamy": 15},
            },
        }
    ]
    st["reputation_pending"] = [
        {"subject_id": "d2", "faction_id": LEGIAO, "delta": -12, "created_day": 2}
    ]
    st["world_projection"] = {
        "dynamic_edges": [
            {"id": "dyn_y", "source": LEGIAO, "type": "controls", "target": "skallgard"}
        ]
    }
    st["location_heard"] = {"skallgard": ["d2"]}
    out = rep.turn_updates(st)
    legiao = next(f for f in out["factions"] if f["id"] == LEGIAO)
    assert legiao["reputation"] == -12 and out["reputation_pending"] == []
    assert out["event_log"][-1]["type"] == "reputation_changed"
    # entregue longe do jogador: sem aviso de fação
    assert not any(n["kind"] == "faction" for n in out.get("reputation_notices", []))


def test_aviso_de_faccao_nao_emitido_quando_longe(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    st = _state({}, pending_world_events=[])
    st["reputation_notices"] = [{"kind": "fame", "subject_id": "x", "text": "velho", "turn": 1}]
    out = rep.turn_updates(st)
    assert out["reputation_notices"] == []  # avisos de turnos antigos são descartados


def test_aviso_de_faccao_so_se_conhecida():
    npcs = {"Thrace": dict(THRACE)}
    deed = {
        "type": "faction_deed",
        "actor_id": "player",
        "target_id": LEGIAO,
        "payload": {"direction": "ajudou", "magnitude": "menor"},
        "source": "storyteller",
    }
    known = process_pending_events(_state(npcs, pending_world_events=[deed]))
    assert any(n["kind"] == "faction" for n in known["reputation_notices"])
    unknown = process_pending_events(
        _state(npcs, faction_intel={}, pending_world_events=[copy.deepcopy(deed)])
    )
    assert not any(n["kind"] == "faction" for n in unknown["reputation_notices"])


def test_register_deed_kind_extensivel(monkeypatch):
    monkeypatch.setattr(rep, "_EXTRA_DEED_KINDS", dict(rep._EXTRA_DEED_KINDS))
    monkeypatch.setattr(npc_knowledge, "PLAYER_DEED_TYPES", set(npc_knowledge.PLAYER_DEED_TYPES))
    rep.register_deed_kind("crime_teste", {"infamy": 20})
    assert "crime_teste" in npc_knowledge.PLAYER_DEED_TYPES
    info = rep.deed_info(_state(), {"type": "crime_teste", "target_id": "x", "payload": {}})
    assert info and info["infamy"] == 20 and info["faction_delta"] == 0
    assert npc_knowledge._witnessable({"type": "crime_teste"})
    assert npc_knowledge.SUBJECT_PARAMS["player_deed"]


@pytest.mark.parametrize("mode", ["on", "off"])
def test_turn_updates_replay_identico(monkeypatch, mode):
    st = _after_kill(monkeypatch, mode=mode, with_witness=True)
    kill = next(e for e in st["event_log"] if e["type"] == "npc_killed")
    st["location_heard"] = {"skallgard": [kill["event_id"]]}
    assert rep.turn_updates(copy.deepcopy(st)) == rep.turn_updates(copy.deepcopy(st))
