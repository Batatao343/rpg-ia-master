"""SPEC-417 R12: propriedades da mecânica numérica (dados, dano, descanso, troca, preço).

Toda aleatoriedade do produto vem de um `random.Random(seed)` com `seed` sorteado pelo
Hypothesis. Dados do catálogo vêm dos dicionários reais (`ARTIFACTS_DB`, `MERCHANTS`).
Limites registrados no exemplo: o estado de keeper/patente de P5 não é montado (a fábrica
não o cobre em <= 30 linhas); P5 varre item x mercador x tipo de preço no estado base.
"""

from __future__ import annotations

import copy
import random
from unittest.mock import patch

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

import combat_mechanics
import gamedata
import world_utils
from gamedata import ARTIFACTS_DB
from services import conflict_damage, economy
from tests.factories import make_player, make_state, make_world
from tests.fakes.property_settings import deterministic_settings

SEEDS = st.integers(min_value=0, max_value=2**32 - 1)
ITEM_IDS = sorted(ARTIFACTS_DB)
MERCHANT_LOCATIONS = sorted({m["location_id"] for m in economy.MERCHANTS.values()})


@deterministic_settings(max_examples=100)
@given(
    count=st.integers(1, 6),
    sides=st.sampled_from([2, 4, 6, 8, 10, 12, 20]),
    sign=st.sampled_from(["", "+", "-"]),
    bonus=st.integers(0, 20),
    seed=SEEDS,
)
def test_p1_dice_stay_in_range(count: int, sides: int, sign: str, bonus: int, seed: int) -> None:
    """P1: `NdM(+/-K)` fica entre o mínimo e o máximo teóricos, e nunca abaixo de 0."""
    formula = f"{count}d{sides}{sign}{bonus if sign else ''}"
    delta = {"": 0, "+": bonus, "-": -bonus}[sign]
    with patch.object(combat_mechanics, "random", random.Random(seed)):
        total, _ = combat_mechanics.roll_dice_numeric(formula)
    assert total >= 0
    assert max(0, count + delta) <= total <= max(0, count * sides + delta), formula


def _armor(prot: int, integ_max: int, integ: int, reducoes: int) -> dict:
    return {
        "protecao": prot,
        "integridade_max": integ_max,
        "integridade_atual": min(integ, integ_max),
        "reducoes_max": reducoes,
        "comprometida": False,
    }


@st.composite
def damage_cases(draw: st.DrawFn) -> dict:
    integ_max = draw(st.integers(0, 10))
    armor = draw(
        st.none()
        | st.builds(
            _armor,
            st.integers(0, 6),
            st.just(integ_max),
            st.integers(0, 10),
            st.integers(0, 3),
        )
    )
    return {
        "vit": draw(st.integers(0, 30)),
        "armor": armor,
        "damage_base": draw(st.integers(0, 60)),
        "crit_mult": draw(st.sampled_from([1, 2])),
        "damage_type": draw(st.sampled_from(gamedata.DANO_FISICO + gamedata.DANO_SOBRENATURAL)),
        "bypass_armor": draw(st.booleans()),
        "seed": draw(SEEDS),
    }


@deterministic_settings(max_examples=100)
@given(case=damage_cases())
def test_p2_damage_within_bounds(case: dict) -> None:
    """P2: dano nunca negativo, Vitalidade em [0, antes], Integridade em [0, max]."""
    target = make_player()
    target["max_vitalidade"] = max(target["max_vitalidade"], case["vit"])
    target["vitalidade"] = case["vit"]
    armor = copy.deepcopy(case["armor"])
    target["armor"] = armor
    target["shield"] = None
    before_integrity = armor["integridade_atual"] if armor else None
    result = conflict_damage.resolve_damage_and_wounds(
        target,
        damage_base=case["damage_base"],
        crit_mult=case["crit_mult"],
        damage_type=case["damage_type"],
        bypass_armor=case["bypass_armor"],
        rng=random.Random(case["seed"]),
    )
    assert result["dano_final"] >= 0
    assert 0 <= target["vitalidade"] <= case["vit"]
    if not result["imune"]:
        assert target["vitalidade"] == max(0, case["vit"] - result["dano_final"])
    if armor:
        assert 0 <= armor["integridade_atual"] <= armor["integridade_max"]
        if case["bypass_armor"]:
            assert armor["integridade_atual"] == before_integrity


@deterministic_settings(max_examples=30)
@given(
    level=st.integers(1, 5),
    frac=st.floats(0, 1),
    blocked=st.booleans(),
)
def test_p3_rest_never_exceeds_max_nor_hurts(level: int, frac: float, blocked: bool) -> None:
    """P3: descanso sobe a Vitalidade até o máximo; clima com `rest_block` não muda nada.

    O clima é controlado trocando `weather_effects`, o que cobre os dois ramos."""
    player = make_player(level=level)
    before = int(player["max_vitalidade"] * frac)
    player["vitalidade"] = before
    with patch.object(world_utils, "weather_effects", return_value={"rest_block": blocked}):
        after_player, _ = world_utils.apply_rest(player, make_world(level=level))
    after = after_player["vitalidade"]
    if blocked:
        assert after == before
    else:
        assert before <= after <= after_player["max_vitalidade"]


def _trade_state(location: str, gold: int) -> dict:
    state = copy.deepcopy(make_state(world={"current_location_id": location}))
    state["player"]["gold"] = gold
    return state


def _trade_input(location: str, gold: int, mode: str, pick: int) -> tuple[dict, str] | None:
    """Estado com a loja já visitada (estoque no mundo) e o item da troca; None = sem item."""
    state = _trade_state(location, gold)
    if mode == "buy":
        _, stock = economy.merchant_stock(state, location)  # semeia `merchant_stocks`
        if not stock:
            return None
        ids = sorted(stock)
        return state, ids[pick % len(ids)]
    item = ITEM_IDS[pick % len(ITEM_IDS)]
    state["player"]["inventory"] = economy.add_item(state["player"]["inventory"], item, 3)
    return state, item


TRADE_ARGS = {
    "location": st.sampled_from(MERCHANT_LOCATIONS),
    "gold": st.integers(0, 5000),
    "mode": st.sampled_from(["buy", "sell"]),
    "pick": st.integers(0, 10_000),
    "qty": st.integers(1, 3),
}


@deterministic_settings(max_examples=30)
@given(**TRADE_ARGS)
def test_p4_trade_conserves_gold_and_stock(
    location: str, gold: int, mode: str, pick: int, qty: int
) -> None:
    """P4 (a, b): ouro bate com `gold_delta` e o estoque devolvido nunca fica negativo."""
    prepared = _trade_input(location, gold, mode, pick)
    if prepared is None:
        return
    state, item = prepared
    qty_before_all = copy.deepcopy(state["player"]["inventory"])
    out = economy.execute_trade(state, mode, item, qty)
    if not out["ok"]:
        return
    player = out["player"]
    assert player["gold"] == gold + out["gold_delta"] >= 0
    qty_before = economy.get_qty(qty_before_all, out["item_id"])
    qty_after = economy.get_qty(player["inventory"], out["item_id"])
    assert qty_after == qty_before + (out["qty"] if mode == "buy" else -out["qty"])
    for stocks in out["world"].get("merchant_stocks", {}).values():
        assert all(v >= 0 for v in stocks.values())


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SPEC-417 achado 1: execute_trade muta o estado de entrada (world['merchant_stocks'] "
        "e compartilhado pela copia rasa em services/economy.py:812); exemplo minimo: "
        "location='brekmar', gold=5000, mode='buy', pick=0, qty=1 com a loja ja visitada"
    ),
)
@example(location="brekmar", gold=5000, mode="buy", pick=0, qty=1)
@deterministic_settings(max_examples=30)
@given(**TRADE_ARGS)
def test_p4_trade_does_not_mutate_input(
    location: str, gold: int, mode: str, pick: int, qty: int
) -> None:
    """P4 (c): `execute_trade` não muta o `state` de entrada (promessa de economy.py:571)."""
    prepared = _trade_input(location, gold, mode, pick)
    if prepared is None:
        return
    state, item = prepared
    snapshot = copy.deepcopy(state)
    economy.execute_trade(state, mode, item, qty)
    assert state == snapshot


@deterministic_settings(max_examples=30)
@given(
    item=st.sampled_from(ITEM_IDS),
    merchant_id=st.none() | st.sampled_from(sorted(economy.MERCHANTS)),
    location=st.sampled_from(MERCHANT_LOCATIONS),
)
def test_p5_no_arbitrage(item: str, merchant_id: str | None, location: str) -> None:
    """P5: revender na hora nunca dá lucro (`sell <= buy`)."""
    state = _trade_state(location, 100)
    merchant = economy.MERCHANTS[merchant_id] if merchant_id else None
    sell = economy.price(item, mode="sell", state=state, merchant=merchant)
    buy = economy.price(item, mode="buy", state=state, merchant=merchant)
    assert sell <= buy
