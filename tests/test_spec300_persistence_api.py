"""SPEC-300 Etapa 2/9 — estado, persistência, writer único, flag e API sem números."""

import json
import re

from spec300_helpers import BRUNNA_ID, comp, make_state, npc

import persistence
from agents import turn_finalizer
from services import companion_soul as cs


def _old_state():
    return {
        "game_id": "55555555-5555-4555-8555-555555555555",
        "player": {"name": "T"},
        "world": {"current_location_id": "montanhas_afiadas"},
        "npcs": {},
        "messages": [],
    }


def test_save_antigo_sem_companion_souls_carrega():
    state = persistence._raw_to_state(_old_state())
    assert state["companion_souls"] == {}
    assert persistence.SCHEMA_VERSION == 8  # sem bump


def test_save_load_round_trip_alma():
    st = persistence._raw_to_state(_old_state())
    st["companion_souls"] = {
        BRUNNA_ID: cs.ensure_soul(
            {"npcs": {"B": npc()}, "world": {"world_clock": {"day": 2}}}, comp()
        )
    }
    assert persistence.save_game_state(st)
    back = persistence.load_game_state(persistence.save_path(st["game_id"]))
    assert back["companion_souls"] == st["companion_souls"]


def test_companion_souls_no_typeddict():
    from state import GameState

    hints = GameState.__annotations__
    assert {"companion_souls", "companion_voice_ack", "companion_feedback"} <= set(hints)


def test_companheiro_legado_ganha_alma_no_primeiro_turno():
    state = make_state(souls={})
    out = cs.apply_turn(state)
    soul = out["companion_souls"][BRUNNA_ID]
    assert soul["origin"] == "legacy" and soul["approval"] == 50
    assert out["companion_voice_ack"] is None


def test_recrutado_neste_turno_tem_origem_recruit():
    state = make_state(souls={})
    state["last_interaction_outcome"] = {"kind": "recruit", "progressed": True}
    assert cs.apply_turn(state)["companion_souls"][BRUNNA_ID]["origin"] == "recruit"


def test_flag_off_nao_escreve_nada(monkeypatch):
    monkeypatch.setenv("RPG_COMPANION_SOUL", "off")
    assert cs.apply_turn(make_state(souls={})) == {}


def test_sem_party_e_sem_almas_nao_escreve():
    assert cs.apply_turn(make_state(party=False)) == {}


def test_shadow_calcula_mas_nao_mostra(monkeypatch):
    monkeypatch.setenv("RPG_COMPANION_SOUL", "shadow")
    state = make_state(souls={})
    out = cs.apply_turn(state)
    assert BRUNNA_ID in out["companion_souls"] and out["companion_feedback"] == []
    import api

    assert api._companion_labels({**state, **out}, state["party"][0]) == {}


def test_finalizer_falha_na_alma_nao_derruba_turno(monkeypatch):
    def boom(_state):
        raise RuntimeError("boom")

    monkeypatch.setattr(cs, "apply_turn", boom)
    state = make_state()
    state["turn_baseline"] = {**state["turn_baseline"], "xp": 0, "level": 1}
    state["player"].update(xp=0, level=1)
    out = turn_finalizer.turn_finalizer_node(state)
    assert "last_turn_outcome" in out and "companion_souls" not in out


def test_finalizer_chama_o_writer_unico():
    state = make_state(souls={})
    state["player"].update(xp=0, level=1)
    state["turn_baseline"] = {**state["turn_baseline"], "xp": 0, "level": 1}
    out = turn_finalizer.turn_finalizer_node(state)
    assert BRUNNA_ID in out["companion_souls"]
    assert out["companion_voice_ack"] is None


def test_api_party_tem_rotulo_sem_numero():
    import api

    state = make_state(approval=62)
    labels = api._companion_labels(state, state["party"][0])
    assert labels == {"approval_label": "amistoso"}
    blob = json.dumps(labels, ensure_ascii=False)
    assert "62" not in blob and 'approval"' not in blob and "values" not in blob
    state["companion_souls"][BRUNNA_ID]["romance"] = "vinculo"
    assert api._companion_labels(state, state["party"][0])["bond_label"] == "vínculo"
    state["companion_souls"][BRUNNA_ID]["romance"] = "interesse"
    assert "bond_label" not in api._companion_labels(state, state["party"][0])


def test_companion_feedback_frases_sem_numero():
    state = make_state(
        traits=["honesto_demais", "generoso_escondido"],
        events=[{"event_id": "k", "type": "quest_failed", "target_id": "x", "payload": {}}],
        approval=60,
    )
    out = cs.apply_turn(state)
    assert out["companion_feedback"] == ["Brunna Ponte-Alta não gostou disso."]
    import api

    assert api._companion_feedback({**state, **out}) == out["companion_feedback"]
    assert not re.search(r"\d", " ".join(out["companion_feedback"]))
