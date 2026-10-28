"""SPEC-353 etapa 5: texto da Carta = previa = motor; custo; utilitaria; provocacao."""

from __future__ import annotations

import random

import pytest

from services import card_text, cards
from services import combat_preview as cpv
from services import conflict_orchestrator as orch
from services import conflict_turn as ct
from tests.test_combat_preview import _state
from tests.test_fix_vitalidade_terminal import _actor, _scene

STRIKES = ["bas_dev_golpe", "bas_san_golpe", "bas_cor_golpe", "bas_arc_golpe", "bas_med_golpe"]


@pytest.mark.parametrize("card_id", STRIKES)
def test_effective_damage_equals_preview_and_engine(card_id):
    hero = _actor("player", corpo=3, is_player=True)
    hero["level"] = 1
    boss = _actor("boss", corpo=5, categoria="padrao")
    boss["esquiva"] = 0
    card = cards.get_card(card_id)
    expected, _dtype, _partes = cpv.effective_damage_base(hero, card)
    hit = None
    for seed in range(60):
        h = {**hero, "prepared_cards": [card_id], "card_usage": {}}
        b = dict(boss, vitalidade=boss["max_vitalidade"], ferimentos={"leve": [], "grave": [], "critico": []})
        out = orch.run_round(
            _scene("player", "boss"),
            {"player": h, "boss": b},
            {"hero": ["player"], "ally": [], "enemy": ["boss"]},
            declarations={
                "player": ct.TurnDeclaration(
                    actor_id="player",
                    acao=ct.TurnStep(kind="card", card_id=card_id, target_id="boss"),
                )
            },
            initiator="heroes",
            state={"player": h},
            rng=random.Random(seed),
        )
        mine = [a for a in out["attacks"] if a["actor_id"] == "player"]
        if mine and mine[0].get("resultado") == "acerto":
            hit = mine[0]
            break
    assert hit is not None
    assert hit["dano_final"] == expected, (card_id, hit["dano_final"], expected)


def test_preview_equals_effective_base(monkeypatch):
    state = _state(monkeypatch)
    enemy = state["enemies"][0]
    enemy.pop("armor", None)
    card = cards.effective_card(state["player"], "bas_san_golpe")
    base, _t, _p = cpv.effective_damage_base(state["player"], card)
    out = cpv.preview(state, "bas_san_golpe", str(enemy["id"]))
    assert out["dano_min"] == base and out["dano_max"] == 2 * base


def test_hand_text_shows_effective_damage_with_parts():
    hero = _actor("player", corpo=3, is_player=True)
    hero["level"] = 1
    card = cards.get_card("bas_dev_golpe")
    text = card_text.effective_rule_text(hero, card, in_combat=True)
    base, _t, partes = cpv.effective_damage_base(hero, card)
    assert f"Causa {base} de dano" in text
    if len(partes) > 1:
        assert "da Carta" in text and "(" in text


def test_self_harm_cost_in_text():
    card = cards.get_card("san_corte_troca")
    assert "Custa 3 de Vitalidade." in card_text.effective_rule_text(None, card)


def test_utility_text_in_combat():
    util = next(c for c in cards.all_cards().values() if c.get("tipo") == "utilitaria")
    assert card_text.effective_rule_text(None, util, in_combat=True).startswith(
        "Sem efeito no conflito."
    )
    assert "Fora" in card_text.effective_rule_text(None, util)


def test_taunt_text_is_honest():
    taunt = next(
        c for c in cards.all_cards().values() if (c.get("efeito") or {}).get("kind") == "taunt"
    )
    assert "tende a atacar você" in card_text.effective_rule_text(None, taunt)


def test_preview_known_defense_only_public(monkeypatch):
    state = _state(monkeypatch)
    enemy = state["enemies"][0]
    enemy["armor"] = {"protecao": 2, "integridade_atual": 3}
    out = cpv.preview(state, "bas_san_golpe", str(enemy["id"]))
    assert out["defesa_conhecida"] == 2
    assert out["dano_min_apos_defesa"] == max(0, out["dano_min"] - 2)
    enemy.pop("armor")
    out2 = cpv.preview(state, "bas_san_golpe", str(enemy["id"]))
    assert out2["defesa_conhecida"] is None and "dano_min_apos_defesa" not in out2


def test_mech_log_shows_absorbed():
    atk = {
        "actor_id": "player",
        "target_id": "boss",
        "dice_rolled": [3, 4],
        "dice_kept": [3, 4],
        "virtude": 3,
        "modificador": 0,
        "total": 10,
        "esquiva_alvo": 8,
        "resultado": "acerto",
        "acerto": True,
        "dano_final": 5,
        "absorvido": 1,
    }
    assert "acerto · Proteção −1 · 5 dano" in cpv.mech_log([atk], [])[0]
