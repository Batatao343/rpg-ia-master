"""SPEC-298 Etapa 3 — fação por eventos validados (R10-R13)."""

from pathlib import Path

import pytest

from agents.storyteller import StoryUpdate, _coerce_faction_impacts
from services import reputation as rep
from services.event_processor import process_pending_events
from services.world_validators import validate_proposal

LEGIAO = "legiao_ferro"
THRACE = {
    "Thrace": {
        "id": "npc_comandante_thrace",
        "name": "Thrace",
        "in_scene": True,
        "relationship": 5,
    }
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
        "pending_world_events": [],
    }
    st.update(extra)
    return st


def _deed(direction="ajudou", magnitude="menor", fid=LEGIAO):
    return {
        "type": "faction_deed",
        "actor_id": "player",
        "target_id": fid,
        "payload": {"direction": direction, "magnitude": magnitude},
        "source": "storyteller",
    }


def _faction(out, state, fid=LEGIAO):
    return next(f for f in out.get("factions", state["factions"]) if f["id"] == fid)


def test_direction_livre_descartada():
    for bad in ("+", "atacou", "contra", "AJUDOU", ""):
        assert _coerce_faction_impacts([{"faction_id": LEGIAO, "direction": bad}]) == []
        upd = StoryUpdate(narrative="x", faction_impacts=[{"faction_id": LEGIAO, "direction": bad}])
        assert upd.faction_impacts == []
    ok = StoryUpdate(
        narrative="x",
        faction_impacts=[{"faction_id": LEGIAO, "direction": "ajudou", "magnitude": "enorme"}],
    )
    assert ok.faction_impacts[0].magnitude == "menor"


def test_sem_cues_no_world_utils():
    import world_utils

    for name in ("_POS_CUES", "_NEG_CUES", "_direction_sign", "REP_STEP"):
        assert not hasattr(world_utils, name)
    root = Path(__file__).resolve().parent.parent
    for rel in ("agents/storyteller.py", "services/event_processor.py", "world_utils.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "_POS_CUES" not in text and "_revert_reputation" not in text


def test_faction_deed_rejeitado_fora_de_cena():
    res = validate_proposal(_deed(), _state())
    assert not res.ok and "em cena" in res.reason


def test_faction_deed_aceito_membro_presente():
    assert validate_proposal(_deed(), _state(THRACE)).ok


def test_faction_deed_aceito_controlador_local():
    st = _state(world_projection={"dynamic_edges": [
        {"id": "dyn_x", "source": LEGIAO, "type": "controls", "target": "nova_arcadia"}
    ]})  # fmt: skip
    assert validate_proposal(_deed(), st).ok


def test_faction_deed_de_llm_sem_source_rejeitado():
    prop = _deed()
    prop.pop("source")
    res = validate_proposal(prop, _state(THRACE))
    assert not res.ok


def test_faction_deed_payload_invalido_rejeitado():
    assert not validate_proposal(_deed(direction="+"), _state(THRACE)).ok
    assert not validate_proposal(_deed(magnitude="gigante"), _state(THRACE)).ok


def test_estado_so_muda_apos_aceite():
    st = _state(THRACE, pending_world_events=[_deed("prejudicou", "maior")])
    out = process_pending_events(st)
    assert _faction(out, st)["reputation"] == -15
    rc = [e for e in out["event_log"] if e["type"] == "reputation_changed"]
    assert len(rc) == 1 and rc[0]["source"] == "reputation"
    assert rc[0]["payload"]["delta"] == -15 and rc[0]["payload"]["new_value"] == -15
    rejeitada = _state(pending_world_events=[_deed("prejudicou", "maior")])
    out2 = process_pending_events(rejeitada)
    assert "factions" not in out2
    assert not [e for e in out2["event_log"] if e["type"] == "reputation_changed"]


@pytest.mark.parametrize(
    ("direction", "magnitude", "expected"),
    [("ajudou", "menor", 4), ("ajudou", "maior", 10), ("prejudicou", "menor", -6)],
)
def test_tabela_faction_deed(direction, magnitude, expected):
    st = _state(THRACE, pending_world_events=[_deed(direction, magnitude)])
    assert _faction(process_pending_events(st), st)["reputation"] == expected
    assert rep.faction_deed_delta(direction, magnitude) == expected


def test_um_impacto_por_faccao_turno():
    st = _state(THRACE, pending_world_events=[_deed(), _deed()])
    out = process_pending_events(st)
    assert _faction(out, st)["reputation"] == 4  # a 2a é duplicata do turno
    assert len([e for e in out["event_log"] if e["type"] == "reputation_changed"]) == 1


def test_quest_completed_gera_delta_tabela():
    st = _state(
        THRACE,
        quests=[
            {
                "id": "q1",
                "title": "Q",
                "status": "active",
                "origin_entity_id": "npc_comandante_thrace",
            }
        ],
        pending_world_events=[
            {
                "type": "quest_completed",
                "actor_id": "player",
                "target_id": "q1",
                "payload": {"quest_id": "q1"},
                "source": "engine",
            }
        ],
    )
    out = process_pending_events(st)
    assert _faction(out, st)["reputation"] == 8


GUARDA = {
    "Guarda": {
        "id": "npc_guarda_legiao",
        "name": "Guarda",
        "in_scene": True,
        "relationship": 5,
        "faction_id": LEGIAO,
    }
}


def test_npc_killed_por_player_gera_delta():
    # testemunha real: um SEGUNDO membro presente (a vítima não conta)
    npcs = {**THRACE, **GUARDA}
    st = _state(
        npcs,
        pending_world_events=[
            {
                "type": "npc_killed",
                "actor_id": "player",
                "target_id": "npc_comandante_thrace",
                "payload": {},
                "source": "engine",
            }
        ],
    )
    out = process_pending_events(st)
    assert _faction(out, st)["reputation"] == -12
    deed = next(e for e in out["event_log"] if e["type"] == "npc_killed")["payload"]["deed"]
    assert deed["infamy"] == 15


def test_pendencia_sem_testemunha_em_modo_on(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    # npc_killed com vítima da Legião, mas nenhum membro presente e sem controle local
    st = _state(
        {},
        pending_world_events=[
            {
                "type": "npc_killed",
                "actor_id": "player",
                "target_id": "npc_comandante_thrace",
                "payload": {},
                "source": "engine",
            }
        ],
    )
    out = process_pending_events(st)
    assert _faction(out, st)["reputation"] == 0
    pend = out["reputation_pending"]
    assert len(pend) == 1 and pend[0]["faction_id"] == LEGIAO and pend[0]["delta"] == -12


def test_off_sem_pendencia(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")
    st = _state(
        {},
        pending_world_events=[
            {
                "type": "npc_killed",
                "actor_id": "player",
                "target_id": "npc_comandante_thrace",
                "payload": {},
                "source": "engine",
            }
        ],
    )
    out = process_pending_events(st)
    assert not out.get("reputation_pending")


def test_pendencia_expira_30_dias(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    st = _state(
        {},
        reputation_pending=[
            {"subject_id": "ev1", "faction_id": LEGIAO, "delta": -12, "created_day": 1}
        ],
    )
    st["world"]["world_clock"]["day"] = 40
    out = rep.turn_updates(st)
    assert out["reputation_pending"] == []
    assert "factions" not in out


def test_reputation_changed_source_reputation_alimenta_historico():
    from services import state_views as sv

    st = _state(THRACE, pending_world_events=[_deed()])
    out = process_pending_events(st)
    hist = sv.reputation_history(out["event_log"], LEGIAO)
    assert hist == [{"turn": 5, "delta": 4, "value": 4}]


def test_vitima_sozinha_nao_e_testemunha_da_faccao(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    st = _state(
        {**THRACE},
        pending_world_events=[
            {
                "type": "npc_killed",
                "actor_id": "player",
                "target_id": "npc_comandante_thrace",
                "payload": {},
                "source": "engine",
            }
        ],
    )
    out = process_pending_events(st)
    assert _faction(out, st)["reputation"] == 0
    assert len(out["reputation_pending"]) == 1


def test_quest_ativa_so_vale_para_aceite_nao_para_testemunho(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    quest = {
        "id": "q1",
        "title": "Q",
        "status": "active",
        "origin_entity_id": "npc_comandante_thrace",
    }
    st = _state({}, quests=[quest], pending_world_events=[_deed()])
    assert validate_proposal(_deed(), st).ok  # aceite R11 pela quest
    out = process_pending_events(st)
    assert _faction(out, st)["reputation"] == 0  # a Legião não viu
    assert len(out["reputation_pending"]) == 1
    assert not any(n["kind"] == "faction" for n in out["reputation_notices"])
    assert not _faction(out, st).get("recent_changes")


def test_npc_legado_sem_in_scene_nao_e_testemunha_universal():
    legado = {"Thrace": {"id": "npc_comandante_thrace", "name": "Thrace", "relationship": 5}}
    assert not rep.faction_witnessed(_state(legado), LEGIAO)
    assert rep.faction_witnessed(_state({**THRACE}), LEGIAO)
