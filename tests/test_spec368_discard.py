"""SPEC-368 R6/R8a - descartar por Fôlego (Dor Surda) e escolha do descartar marcada na UI."""

from __future__ import annotations

import json

import pytest

from services import card_piles as cp
from services import conflict_turn as ct
from tests.test_card_effects_piles import (  # noqa: F401
    _enemy,
    _player,
    _run,
    _setup,
    _step,
    _synthetic,  # noqa: F401  (fixture autouse)
)

DOR = "sts_dor_surda"


def _discard(cid=DOR):
    return ct.TurnStep(kind="discard", card_id=cid)


def test_dor_surda_discard_costs_one_folego():
    s = _setup([DOR, "bas_san_golpe"])
    piles = s[3]["_piles"]
    before = piles["folego"]
    out = _run(s, _discard())
    assert piles["folego"] == before - 1
    assert DOR not in piles["mao"] and DOR in piles["exaurida"]
    assert any("descarta" in line for line in out["logs"])
    assert "player" in out.get("resolved_turns", [])  # o turno do jogador é registrado


def test_dor_surda_discard_refused_without_folego():
    s = _setup([DOR, "bas_san_golpe"])
    piles = s[3]["_piles"]
    piles["folego"] = 0
    plan = cp.plan_plays(piles, s[3]["player"], [_discard()])
    assert not plan["ok"] and "Fôlego" in plan["motivo"]
    out = _run(s, _discard())
    assert piles["folego"] == 0 and DOR in piles["mao"] and DOR not in piles["exaurida"]
    assert any("Falta Fôlego para descartar Dor Surda" in line for line in out["logs"])


def test_discard_only_for_discardable_cards_in_hand():
    s = _setup([DOR, "bas_san_golpe"])
    piles, player = s[3]["_piles"], s[3]["player"]
    assert not cp.plan_plays(piles, player, [_discard("bas_san_golpe")])["ok"]
    assert not cp.plan_plays(piles, player, [_discard("sts_membro_falho")])["ok"]  # fora da mão
    plan = cp.plan_plays(
        piles,
        player,
        [_discard(), ct.TurnStep(kind="card", card_id="bas_san_golpe", target_id="gob_1")],
    )
    assert plan["ok"] and plan["folego_total"] == 2


def test_discard_does_not_use_the_abyss_pact():
    s = _setup([DOR])
    piles = s[3]["_piles"]
    piles["folego"] = 0
    assert not cp.plan_plays(piles, s[3]["player"], [_discard()])["ok"]  # nada de Fôlego emprestado


def test_hand_view_exposes_discard_cost_additively():
    s = _setup([DOR, "bas_san_golpe"])
    rows = {r["id"]: r for r in cp.public_view(s[3]["_piles"], s[3]["player"])["mao"]}
    assert rows[DOR]["descartar_folego"] == 1 and "descartar_folego" not in rows["bas_san_golpe"]


def test_choice_discard_uses_ui_picks_then_policy():
    s = _setup(["t_descartar", "bas_san_golpe", "bas_san_guarda", cp.FARDO_ID])
    step = ct.TurnStep(
        kind="card",
        card_id="t_descartar",
        target_id="player",
        params={"descartar": ["bas_san_guarda"]},
    )
    _run(s, step)
    piles = s[3]["_piles"]
    assert "bas_san_guarda" not in piles["mao"] and cp.FARDO_ID in piles["mao"]
    assert "descartar_escolhidas" not in piles  # transitório: nunca persiste


def test_choice_discard_ignores_invalid_picks_and_falls_back():
    s = _setup(["t_descartar", "bas_san_golpe", cp.FARDO_ID])
    step = ct.TurnStep(
        kind="card", card_id="t_descartar", target_id="player", params={"descartar": ["nao_existe"]}
    )
    _run(s, step)
    assert s[3]["_piles"]["mao"] == ["bas_san_golpe"]  # política: Fardo primeiro


def test_hand_view_marks_choice_discards():
    s = _setup(["t_descartar", "bas_san_golpe"])
    rows = {r["id"]: r for r in cp.public_view(s[3]["_piles"], s[3]["player"])["mao"]}
    assert rows["t_descartar"]["descarta_escolha"] == 1
    json.dumps(rows)


def test_api_play_list_accepts_discard_and_picks(monkeypatch):
    import api

    monkeypatch.setenv("RPG_CARD_DECK", "on")
    state = {"combat": {"active": True, "pilhas": {"mao": [DOR, "t_descartar"]}}}
    req = api.ActionRequest(
        input_text="Encerro a rodada.",
        jogadas=[
            api.PlayStepRequest(card_id=DOR, action_kind="discard"),
            api.PlayStepRequest(
                card_id="t_descartar", target_id="player", descartar=["bas_san_golpe"]
            ),
        ],
    )
    api._apply_play_list(state, req, [{"id": "gob_1"}])
    steps = state["combat_declaration"]["jogadas"]
    assert steps[0] == {"kind": "discard", "card_id": DOR}
    assert steps[1]["params"]["descartar"] == ["bas_san_golpe"]
    with pytest.raises(ValueError):
        api.PlayStepRequest(card_id=DOR, descartar=["a"] * 5)


def test_essencia_de_cinza_obtainable():
    import random as _random

    from services import economy

    got = {
        economy.roll_loot("default", 4, _random.Random(seed), boost=True)["item_id"]
        for seed in range(400)
    }
    assert "essencia_de_cinza" in got
    from services import card_rewards

    assert (
        card_rewards.sharpen_material({"inventory": [{"id": "essencia_de_cinza", "qty": 1}]})
        == "essencia_de_cinza"
    )


def test_ressoar_needs_a_single_value_key_and_catalog_is_clean():
    from services import card_effects as fx
    from services import cards

    ambiguous = {
        "id": "x",
        "name": "X",
        "tipo": "ativa",
        "efeito": {"kind": "dano", "categoria_arma": "leve", "dano_base": 2, "valor": 3},
        "palavras_chave": {"ressoar": 1},
    }
    assert any("Ressoar" in e for e in fx.validate_card(fx.materialize(ambiguous)))
    for cid, card in cards._load_cards().items():
        assert not any("Ressoar" in e for e in fx.validate_card(card)), cid
