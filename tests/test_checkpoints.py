"""Suíte da spec checkpoints-morte — fundação (serviço + persistência).

Offline/determinístico. Cobre a cadência (D1), o slot único (D5), o round-trip
em disco e a resolução da tela de morte (D2/D7). O flip do fluxo em combat.py +
endpoint API + tela são o vertical seguinte.
"""
import uuid

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import persistence
from services import checkpoints as cp


@pytest.fixture()
def saves_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    return tmp_path


def _state(game_id, turn=5, danger=2, loc="pantano", gold=50):
    return {
        "game_id": game_id,
        "player": {"name": "Herói", "class_name": "Sangromante", "level": 2,
                   "hp": 20, "max_hp": 30, "gold": gold, "inventory": [],
                   "known_abilities": ["ataque_basico"]},
        "world": {"current_location_id": loc, "current_location": loc,
                  "turn_count": turn, "danger_level": danger, "visited": [loc]},
        "messages": [HumanMessage(content="ação"), AIMessage(content="narração")],
        "campaign_plan": {"beats": []},
    }


# --- D5/round-trip: slot único em disco --------------------------------------

def test_save_load_checkpoint_roundtrip(saves_dir):
    gid = str(uuid.uuid4())
    st = _state(gid, gold=77)
    assert persistence.save_checkpoint(st) is True
    assert persistence.has_checkpoint(gid) is True
    got = persistence.load_checkpoint(gid)
    assert got is not None
    assert got["player"]["gold"] == 77
    assert got["world"]["turn_count"] == 5
    assert [m.content for m in got["messages"]] == ["ação", "narração"]


def test_checkpoint_slot_unico_sobrescreve(saves_dir):
    gid = str(uuid.uuid4())
    persistence.save_checkpoint(_state(gid, gold=10))
    persistence.save_checkpoint(_state(gid, gold=99))  # sobrescreve (D5)
    assert persistence.load_checkpoint(gid)["player"]["gold"] == 99


def test_checkpoint_ausente(saves_dir):
    assert persistence.has_checkpoint(str(uuid.uuid4())) is False
    assert persistence.load_checkpoint(str(uuid.uuid4())) is None


def test_checkpoint_nao_colide_com_save_vivo(saves_dir):
    gid = str(uuid.uuid4())
    persistence.save_game_state(_state(gid, gold=1))
    persistence.save_checkpoint(_state(gid, gold=2))
    # save vivo e checkpoint são arquivos distintos
    assert persistence.load_game_state(persistence.save_path(gid))["player"]["gold"] == 1
    assert persistence.load_checkpoint(gid)["player"]["gold"] == 2


# --- D1: cadência ------------------------------------------------------------

def test_should_checkpoint_a_cada_10_turnos():
    assert cp.should_checkpoint(_state("g", turn=10)) is True
    assert cp.should_checkpoint(_state("g", turn=20)) is True
    assert cp.should_checkpoint(_state("g", turn=7)) is False
    assert cp.should_checkpoint(_state("g", turn=0)) is False


def test_should_checkpoint_ao_entrar_zona_segura():
    prev = _state("g", turn=7, danger=4, loc="pantano")
    cur = _state("g", turn=8, danger=1, loc="nova_arcadia")  # chegou em cidade segura
    assert cp.should_checkpoint(cur, prev) is True


def test_zona_segura_exige_mudanca_de_local():
    prev = _state("g", turn=7, danger=1, loc="cidade")
    cur = _state("g", turn=8, danger=1, loc="cidade")  # mesmo local, sem re-checkpoint
    assert cp.entered_safe_zone(cur, prev) is False


def test_should_checkpoint_nao_grava_em_morte():
    st = _state("g", turn=10)
    st["game_over"] = True
    assert cp.should_checkpoint(st) is False
    st2 = _state("g", turn=10)
    st2["death_pending"] = True
    assert cp.should_checkpoint(st2) is False


# --- D2/D7: resolução da tela de morte ---------------------------------------

def test_resolve_accept_vira_memorial():
    st = _state("g")
    st["death_pending"] = True
    out = cp.resolve_death_choice(st, "accept")
    assert out["game_over"] is True and out["death_pending"] is False


def test_resolve_continue_restaura_checkpoint_em_memoria():
    snap = _state("g", turn=10, gold=200)
    st = _state("g", turn=15, gold=0)  # morreu depois, com menos ouro
    st["death_pending"] = True
    out = cp.resolve_death_choice(st, "continue", checkpoint=snap)
    assert out["player"]["gold"] == 200          # voltou ao checkpoint
    assert out["world"]["turn_count"] == 10       # progresso desde ali perdido (D3)
    assert out["death_pending"] is False and out["game_over"] is False


def test_resolve_continue_restaura_do_disco(saves_dir):
    gid = str(uuid.uuid4())
    persistence.save_checkpoint(_state(gid, turn=10, gold=150))
    dead = _state(gid, turn=18, gold=0)
    dead["death_pending"] = True
    out = cp.resolve_death_choice(dead, "continue")  # sem arg -> disco
    assert out["player"]["gold"] == 150
    assert out["game_over"] is False


def test_resolve_continue_sem_checkpoint_usa_inicial(saves_dir):
    gid = str(uuid.uuid4())
    inicial = _state(gid, turn=1, gold=50)
    dead = _state(gid, turn=6, gold=0)
    dead["death_pending"] = True
    out = cp.resolve_death_choice(dead, "continue", initial_state=inicial)  # D7
    assert out["player"]["gold"] == 50 and out["world"]["turn_count"] == 1
    assert out["game_over"] is False
