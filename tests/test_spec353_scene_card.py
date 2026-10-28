"""SPEC-353 etapa 1: Carta de objeto de cena jogavel e recusa sem id (R1-R3)."""

from __future__ import annotations

import re

import pytest

from services import card_piles, cards
from services import scene_cards as sc

ID_RE = re.compile(
    r"\b(cena|bas|dev|san|cor|arc|vig|bst|inf|mon|npc|enemy|fallback|sus)_[a-z0-9_]+\b"
)


def _obj_card() -> dict:
    obj = {"id": "sino_rachado", "name": "Sino Rachado"}
    it = {"label": "derrubar", "effect": {"kind": "damage", "params": {"amount": 4}}}
    card = sc._object_card(obj, it)
    assert card is not None
    cards.register_temp_card(card)
    return card


def _state(card_id: str | None, in_hand: bool) -> dict:
    mao = [card_id] if card_id and in_hand else []
    return {
        "player": {"prepared_cards": [], "card_usage": {}, "entropy": 5},
        "combat": {"pilhas": {"mao": mao, "compra": [], "descarte": [], "exaurida": []}},
    }


def test_object_card_in_hand_is_playable():
    card = _obj_card()
    st = _state(card["id"], True)
    res = cards.use_card(st, card["id"])
    assert res["ok"], res
    # frequencia de cena cobrada: segundo uso recusado
    again = cards.use_card(st, card["id"])
    assert not again["ok"]


def test_object_card_not_in_hand_refused_by_name():
    card = _obj_card()
    st = _state(card["id"], False)
    res = cards.use_card(st, card["id"])
    assert not res["ok"]
    assert "Derrubar (Sino Rachado)" in res["error"]
    assert not ID_RE.search(res["error"])


def test_unknown_card_error_has_no_id():
    res = cards.use_card(_state(None, False), "cena_fantasma_deadbeef")
    assert not res["ok"] and not ID_RE.search(res["error"])


@pytest.mark.parametrize("cid", ["muralha_viva", "golpe_devoto"])
def test_named_refusals_never_expose_id(cid):
    res = cards.use_card({"player": {"prepared_cards": []}}, cid)
    if not res["ok"]:
        assert not ID_RE.search(res["error"])


def _engine_state(player: dict, piles: dict) -> dict:
    """Formato que o agente passa ao motor (agents/combat.py: round_state)."""
    return {"player": player, "_piles": piles, "_deck_mode": "on"}


@pytest.mark.parametrize(
    "klass",
    ["Devoto do Abismo", "Sangromante", "Corruptor", "Arcanista Cinzento", "Médico de Campo"],
)
def test_hand_contract_playable_cards_accepted(monkeypatch, klass):
    """R2: toda Carta ativa da mao inicial (+ 1 objeto de cena) e aceita por use_card no
    formato de producao ({"player", "_piles"})."""
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    basics = cards.basicas_for_class(klass)
    deck = (basics["golpe"] * 5) + (basics["guarda"] * 4) + (basics["assinatura"] * 3)
    assert deck and all(cards.get_card(c) for c in deck)  # ids reais, nada pulado
    card = _obj_card()
    player = {
        "class_name": klass,
        "prepared_cards": [],
        "deck": deck,
        "card_usage": {},
        "entropy": 9,
        "level": 1,
    }
    piles = card_piles.start_piles(player, 11)
    piles["mao"].append(card["id"])
    checked = 0
    for cid in list(piles["mao"]):
        if (cards.get_card(cid) or {}).get("tipo") != "ativa":
            continue
        fresh = dict(player, card_usage={}, entropy=9)
        assert cards.use_card(_engine_state(fresh, piles), cid)["ok"], cid
        checked += 1
    assert checked >= 2


def test_object_card_end_to_end_via_run_round(monkeypatch):
    """P1-1: com pilhas reais e o objeto na mao, o motor resolve o ataque do heroi."""
    import random

    from services import conflict_orchestrator as orch
    from services import conflict_turn as ct
    from tests.test_fix_vitalidade_terminal import _actor, _scene

    monkeypatch.setenv("RPG_CARD_DECK", "on")
    card = _obj_card()
    hero = _actor("player", corpo=5, is_player=True)
    hero.update(class_name="Devoto do Abismo", prepared_cards=[], card_usage={}, entropy=9)
    basics = cards.basicas_for_class("Devoto do Abismo")
    hero["deck"] = (basics["golpe"] * 5) + (basics["guarda"] * 4) + (basics["assinatura"] * 3)
    piles = card_piles.start_piles(hero, 3)
    piles["mao"].append(card["id"])
    boss = _actor("boss", corpo=3, categoria="padrao")
    step = ct.TurnStep(kind="card", card_id=card["id"], target_id="boss")
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        {"hero": ["player"], "ally": [], "enemy": ["boss"]},
        declarations={"player": ct.TurnDeclaration(actor_id="player", acao=step, jogadas=[step])},
        initiator="heroes",
        state=_engine_state(hero, piles),
        rng=random.Random(4),
    )
    mine = [a for a in out["attacks"] if a["actor_id"] == "player"]
    assert mine and mine[0]["card_id"] == card["id"], out["logs"]
    assert not any("não pôde ser jogada" in str(log) for log in out["logs"])
