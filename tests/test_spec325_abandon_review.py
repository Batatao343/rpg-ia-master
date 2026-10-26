"""SPEC-325 Fase B, revisão Sol (B-P1-1, B-P2-1..5): fuga sem destino, alma off, save/load, perigo."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import HumanMessage

from agents.npc import npc_actor_node
from services import chase as chase_mod
from services import companion_soul as cs
from tests.spec325_chase_helpers import step
from tests.test_spec325_abandon import (
    LOC,
    PRESSIONADO,
    _brunna,
    _offer_state,
    _round1,
)

BRUNNA_ID = cs.comp_id({"origin_npc": "npc_mv_brunna_ponte_alta"})
BRUNNA = "Brunna Ponte-Alta"


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setenv("RPG_CHASE_ABANDON", "on")
    monkeypatch.setenv("RPG_CHASE_ATTACK", "on")


def _escape_now(monkeypatch):
    """A rodada de fuga termina em `escapou` (sem destino de viagem: o herói fica no local)."""

    def stub(chase, **kw):
        chase.update(trilha="escapou", escapou=True, alcancado=False)
        chase["_last"] = {"total": 99, "difficulty": 10, "sucesso": True, "advantage": 0}
        return chase

    monkeypatch.setattr(chase_mod, "resolve_chase_round", stub)


def _finished(monkeypatch, how):
    """combat_node real -> combate ENCERRADO com um selo; nenhum ajuste manual de local."""
    if how == "sacrifice":
        state, out = _offer_state(monkeypatch, approval=80, coragem=1)
        _m, out2 = step(state, out, monkeypatch, "Aceito o sacrifício.")
    else:
        state, out = _round1(monkeypatch)
        out["combat"]["chase"]["last_luck"] = {BRUNNA_ID: -1}
        _escape_now(monkeypatch)
        _m, out2 = step(state, out, monkeypatch, "Fujo e deixo a Brunna para trás.")
    final = {**state, **{k: v for k, v in out2.items() if k != "next"}}
    assert final["combat"]["phase"] == "ended"
    assert final["world"]["current_location_id"] == LOC  # fuga sem destino: o herói não saiu
    assert _brunna(final)["pending_fate"]
    return final


def _tick(state, *, day=None, location=None):
    world = dict(state["world"])
    if location:
        world["current_location_id"] = location
    if day:
        world["world_clock"] = {"day": day, "period": "manha"}
    state = {**state, "world": world}
    return {**state, **cs.apply_turn(state)}


def _force_fate(state, fate):
    party = [
        {**c, "pending_fate": {**c["pending_fate"], "fate": fate}} if c.get("pending_fate") else c
        for c in state["party"]
    ]
    return {**state, "party": party}


def _fates(state):
    return [e for e in state.get("event_log", []) if e["type"] == "companion_fate"]


@pytest.mark.parametrize("how", ["abandon", "sacrifice"])
def test_staying_in_place_never_rescues_nor_applies(monkeypatch, how):
    st = _force_fate(_finished(monkeypatch, how), "morto")
    st = _tick(st)  # mesmo turno, mesmo local
    assert _brunna(st)["pending_fate"] and _brunna(st)["active"] is False
    st = _tick(st, day=9)  # dias depois, ainda parado: o gate da 304 recusa (jogador no local)
    assert _brunna(st)["pending_fate"] and not _fates(st)


@pytest.mark.parametrize("how", ["abandon", "sacrifice"])
def test_leaving_then_one_day_applies_fate(monkeypatch, how):
    st = _force_fate(_finished(monkeypatch, how), "capturado")
    day0 = st["world"]["world_clock"]["day"]
    st = _tick(st, location="nova_arcadia")  # viajou: marca `left`, mesmo dia
    assert _brunna(st)["pending_fate"]["left"] is True and not _fates(st)
    st = _tick(st, day=day0 + 1)
    assert _fates(st)
    assert _brunna(st)["status"] == "capturado" and "pending_fate" not in _brunna(st)


@pytest.mark.parametrize("how", ["abandon", "sacrifice"])
def test_leave_and_return_rescues(monkeypatch, how):
    st = _force_fate(_finished(monkeypatch, how), "morto")
    st = _tick(st, location="nova_arcadia")
    st = _tick(st, location=LOC)  # voltou antes de 1 dia
    assert "pending_fate" not in _brunna(st) and _brunna(st)["status"] == "ativo"
    st = _tick(st, location="nova_arcadia", day=20)
    assert not _fates(st)


def test_sacrifice_emits_perceived_event_and_chronicle(monkeypatch):
    st = _finished(monkeypatch, "sacrifice")
    ev = [e for e in st["event_log"] if e["type"] == "companion_sacrificed"]
    assert len(ev) == 1
    blob = json.dumps(ev[0])
    pf = _brunna(st)["pending_fate"]
    assert "fate" not in blob and pf["resultado"] not in blob and pf["seed"] not in blob
    text = " ".join(str(c) for c in st["chronicle"])
    assert "ficou para trás para que o herói escapasse" in text
    assert pf["resultado"] not in text and "morto" not in text


def test_soul_off_refuses_abandon_and_unseals_recalled(monkeypatch):
    monkeypatch.setenv("RPG_COMPANION_SOUL", "off")
    state, out = _round1(monkeypatch)
    out["combat"]["chase"]["last_luck"] = {BRUNNA_ID: -1}
    _m, out2 = step(state, out, monkeypatch, "Fujo e deixo a Brunna para trás.")
    assert "pending_fate" not in _brunna(out2)  # ninguém consumiria o selo
    sealed = {
        **state,
        "party": [{**c, "pending_fate": {"fate": "morto", "day": 1}} for c in state["party"]],
    }
    freed = cs.apply_turn(sealed)  # active=True (rechamado): o selo não fica preso
    assert freed and "pending_fate" not in freed["party"][0]


def test_save_load_mid_seal_then_fate_applies(monkeypatch):
    import persistence

    st = _force_fate(_finished(monkeypatch, "abandon"), "morto")
    st = _tick(st, location="nova_arcadia")
    st["game_id"] = "0b6f1c2e-3d4a-4e5f-8a9b-325325325325"
    day0 = st["world"]["world_clock"]["day"]
    assert persistence.save_game_state(st)
    loaded = persistence.load_game_state(
        persistence.save_path("0b6f1c2e-3d4a-4e5f-8a9b-325325325325")
    )
    assert _brunna(loaded)["pending_fate"] == _brunna(st)["pending_fate"]
    assert loaded["combat"]["chase"].get("abandoned") == st["combat"]["chase"].get("abandoned")
    assert (
        loaded["companion_souls"][BRUNNA_ID]["telegraphs"]
        == (st["companion_souls"][BRUNNA_ID]["telegraphs"])
    )
    assert _fates(_tick(loaded, day=day0 + 1))


def test_offscreen_peril_skips_sealed_companion(monkeypatch):
    from tests.spec304_helpers import hook
    from tests.test_spec304_perils import _fresh, _hot

    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_WORLD", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")
    _hot(monkeypatch)
    free = _fresh(monkeypatch)
    assert any(e["type"] == "npc_peril_warning" for e in hook(free, 3).events)  # controle
    sealed = _fresh(monkeypatch)
    sealed["party"][0]["pending_fate"] = {"fate": "morto", "day": 2, "location_id": LOC}
    res = hook(sealed, 3)
    assert not any(e["type"] == "npc_peril_warning" for e in res.events)
    assert not sealed["npc_sim"]["perils"]


def test_refused_melee_keeps_flee_attempts(monkeypatch):
    state, out = _round1(monkeypatch)
    out["combat"] = {
        **out["combat"],
        "chase": {**PRESSIONADO, "trilha": "afastado"},
        "flee_attempts": 4,
    }
    decl = {"actor_id": "player", "acao": {"kind": "attack", "target_id": "e1"}}
    _m, out2 = step(state, out, monkeypatch, "ataco o inimigo", declaration=decl)
    assert out2["combat"]["last_player_action"]["attempted"] is False
    assert out2["combat"]["flee_attempts"] == 4


def test_waiting_message_shows_display_name():
    from gamedata import get_location

    name = get_location(LOC)["name"]
    st = {
        "messages": [HumanMessage(content="Oi Brunna")],
        "active_npc_name": BRUNNA,
        "game_id": "g",
        "npcs": {},
        "party": [{"name": BRUNNA, "active": False, "waiting_at": LOC}],
        "world": {"current_location": "Pântano", "current_location_id": "pantano"},
    }
    text = npc_actor_node(st)["messages"][0].content
    assert f"Está esperando em {name}" in text and LOC not in text
