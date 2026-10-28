"""SPEC-347 R7: a Forja diz por que cada via está fechada, com o mesmo texto dos erros das ações."""

from __future__ import annotations

import pytest

from services import card_rewards as cr
from services import cards
from tests.test_forge import ESTRADA, TEMPLO, _extra_card, _state


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


def _view(st):
    return cr.public_forge(st)


def test_off_temple_has_reason_and_matches_forget_error():
    st = _state(ESTRADA)
    mot = _view(st)["esquecer"]["motivos"]
    assert mot["templo"] == cr.MSG_FORGET_NOT_TEMPLE
    assert cr.forget(st, _extra_card(st), "templo")["error"] == mot["templo"]


def test_temple_without_gold_reports_gold_msg():
    st = _state(TEMPLO)
    st["player"]["gold"] = 3
    mot = _view(st)["esquecer"]["motivos"]
    assert mot["templo"] == cr.msg_forget_gold(cr.FORGET_GOLD)
    assert cr.forget(st, _extra_card(st), "templo")["error"] == mot["templo"]


def test_temple_with_gold_is_open():
    st = _state(TEMPLO)
    assert _view(st)["esquecer"]["motivos"]["templo"] is None


def test_rest_reason_and_open_after_long_rest():
    st = _state(ESTRADA)
    mot = _view(st)["esquecer"]["motivos"]
    assert mot["descanso"] == cr.MSG_FORGET_NO_REST
    assert cr.forget(st, _extra_card(st), "descanso")["error"] == mot["descanso"]
    cr.on_long_rest(st["player"])
    assert _view(st)["esquecer"]["motivos"]["descanso"] is None


def test_purge_reasons():
    st = _state(ESTRADA)
    mot = _view(st)["purgar"]["motivos"]
    assert mot["templo"] == cr.MSG_PURGE_NOT_TEMPLE
    assert mot["medico"] == cr.MSG_PURGE_NO_MEDIC
    st = _state(TEMPLO)
    st["player"]["gold"] = 1
    assert _view(st)["purgar"]["motivos"]["templo"] == cr.msg_purge_gold(cr.PURGE_GOLD)


def test_basic_at_deck_minimum_has_bloqueio():
    st = _state(TEMPLO)
    basics = {c for ids in cards.basicas_for_class("Sangromante").values() for c in ids}
    st["player"]["deck"] = [c for c in st["player"]["deck"] if c in basics][: cards.DECK_MIN]
    st["player"]["deck"] += [next(iter(basics))] * max(
        0, cards.DECK_MIN - len(st["player"]["deck"])
    )
    rows = _view(st)["baralho"]
    assert any(r["bloqueio"] == cr.MSG_DECK_MIN for r in rows if r["id"] in basics)
    assert all("bloqueio" in r for r in rows)


def test_not_allowed_closes_every_route_with_the_same_reason(monkeypatch):
    st = _state(TEMPLO)
    monkeypatch.setattr(cards, "reorganize_status", lambda s: (False, "Em combate."))
    view = _view(st)
    assert view["permitido"] is False
    for mot in (view["esquecer"]["motivos"], view["purgar"]["motivos"]):
        assert set(mot.values()) == {"Em combate."}
