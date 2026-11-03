"""SPEC-387 R17-R18: Carta fora do baralho é recusada antes de gastar, com linha legível."""

from __future__ import annotations

import copy
import re

from services import card_piles as cp
from services import cards, round_log
from tests.test_card_piles import _player, _Step

ID_RE = re.compile(r"\b[a-z]{2,4}_[a-z0-9_]+\b")


def _known_only():
    p = _player()
    extra = next(
        c["id"]
        for c in cards.cards_for_class(p["class_name"])
        if c["id"] not in p["deck"] and c["id"] not in p["prepared_cards"] and c.get("tipo") == "ativa"
    )
    p["known_cards"] = [*p["known_cards"], extra]
    piles = cp.start_piles(p, 1)
    piles["mao"] = [extra]
    return p, piles, extra


def test_plan_plays_refuses_known_only_card():
    p, piles, extra = _known_only()
    snap = (copy.deepcopy(piles), copy.deepcopy(p))
    plan = cp.plan_plays(piles, p, [_Step("card", extra)])
    assert not plan["ok"]
    name = cards.get_card(extra)["name"]
    assert plan["motivo"] == f"{name} não está no seu baralho."
    assert (piles, p) == snap  # nada gasto


def test_playable_ids_same_rule_as_use_card():
    p, piles, extra = _known_only()
    state = {"player": p, "combat": {"pilhas": piles}}
    assert extra not in cards.playable_ids(state)
    assert not cards.use_card(state, extra)["ok"]
    for cid in list(p["deck"])[:3]:
        assert cid in cards.playable_ids(state)
        assert cards.use_card({**state, "player": copy.deepcopy(p)}, cid)["ok"]


def test_refusal_line_visible_no_cost():
    p, piles, extra = _known_only()
    entropy = p["entropy"]
    res = cards.use_card({"player": p, "combat": {"pilhas": piles}}, extra)
    assert not res["ok"] and p["entropy"] == entropy
    assert round_log._is_human_line(res["error"])
    assert not ID_RE.search(res["error"])


def test_engine_refusal_catalog_is_human():
    lines = [
        "Golpe Rachado não pôde ser jogada.",
        "Golpe Rachado não está no seu baralho.",
        "Essa Carta não existe mais.",
        "Golpe Rachado já foi usada (1×cena).",
        "Entropia insuficiente (1/3).",
        "Fôlego insuficiente (0/1).",
        "Fôlego insuficiente: estas jogadas custam 5, você tem 2 e o Pacto do Abismo empresta no máximo 2 por rodada.",
        "Fardo é um Fardo e não pode ser jogada.".replace("Fardo é um", "O Caco é um"),
        "Golpe Rachado não está na sua mão.",
        "'Golpe' só pode ser jogada 1× por rodada.",
        "Falta Fôlego para descartar Caco (1).",
        "Caco não pode ser descartada.",
        "Golpe Rachado não é uma Carta ativa.",
        "Hero está silenciado — sem Cartas.",
    ]
    for line in lines:
        assert round_log._is_human_line(line), line
        assert not ID_RE.search(line), line
