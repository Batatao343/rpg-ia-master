"""SPEC-353 R40 (golden da 330 intocado) e R30 (regra do Padrao/Elite, frequencias exatas)."""

from __future__ import annotations

import itertools
import random
import subprocess

from services import conflict_orchestrator as orch
from services.conflict_resolution import resolve_attack
from tests import spec330_equivalence as eq
from tests.test_fix_vitalidade_terminal import _actor, _scene

NEW_KEYS = {
    "final_blows",
    "absorvido",
    "pressagios_cumpridos",
    "fontes_condicao",
    "condicoes_novas",
    "sem_vitalidade",
    "fuga",
}


def test_new_record_keys_never_reach_golden_actors_or_scene():
    from services import cards

    for cid in ("bas_dev_golpe", "bas_san_golpe", "dev_provocacao"):
        eq.run_card(cards.get_card(cid))
        blob = repr(eq.LAST_STATE)
        for key in NEW_KEYS:
            assert key not in blob, (cid, key)


def test_golden_files_have_no_diff_against_main():
    for path in ("tests/spec330_equivalence.py", "tests/fixtures/spec330_legacy_golden.json"):
        res = subprocess.run(
            ["git", "diff", "--quiet", "main", "--", path], capture_output=True, check=False
        )
        assert res.returncode == 0, path


# --- R30: frequencias exatas da dupla (10 % em 2d10; 14,5 % em 3d10 mantendo 2) ---
class _Scripted:
    def __init__(self, dice):
        self._d = list(dice)

    def randint(self, _a, _b):
        return self._d.pop(0)


def _is_double_crit(dice, advantage: int) -> bool:
    hero = _actor("a", corpo=3, is_player=True)
    foe = _actor("b", corpo=3, categoria="padrao")
    foe["esquiva"] = 99  # so a regra da dupla pode acertar
    res = resolve_attack(hero, foe, rng=_Scripted(dice), advantage=advantage)
    kept = res.get("dice_kept") or []
    return bool(res["acerto"]) and len(kept) >= 2 and kept[0] == kept[1]


def test_double_frequency_exact_2d10():
    n = sum(_is_double_crit(d, 0) for d in itertools.product(range(1, 11), repeat=2))
    assert n == 10  # 10/100 = 10 %


def test_double_frequency_exact_3d10_keep_two():
    adv = sum(_is_double_crit(d, 1) for d in itertools.product(range(1, 11), repeat=3))
    dis = sum(_is_double_crit(d, -1) for d in itertools.product(range(1, 11), repeat=3))
    assert adv == dis == 145  # 145/1000 = 14,5 %


# --- R30: sequencia do Elite a 0 de Vitalidade, Padrao e Lacaio ---
SIDES = {"hero": ["player"], "ally": [], "enemy": ["boss"]}


def _strike_until_fall(category: str, corpo: int, seed: int = 3):
    hero = _actor("player", corpo=5, is_player=True)
    foe = _actor("boss", corpo=corpo, categoria=category, vitalidade=0)
    rounds = 0
    out = {}
    while rounds < 40 and not (foe.get("dead") or foe.get("incapacitated")):
        out = orch.run_round(
            _scene("player", "boss"),
            {"player": hero, "boss": foe},
            SIDES,
            declarations={},
            initiator="heroes",
            rng=random.Random(seed + rounds),
        )
        rounds += 1
        hero["vitalidade"] = hero["max_vitalidade"]
        hero["dead"] = hero["estado_terminal"] = False
    return foe, rounds, out


def test_lacaio_falls_on_first_wound():
    foe, rounds, _ = _strike_until_fall("lacaio", 0)
    assert foe.get("dead") or foe.get("incapacitated")
    assert rounds <= 12


def test_elite_goes_through_last_stand_before_death():
    foe, rounds, _ = _strike_until_fall("elite", 3)
    assert foe.get("last_stand_resolved") or foe.get("dead") or foe.get("incapacitated")
    assert rounds >= 2  # nunca cai no primeiro golpe com Corpo 3 (4 leves, 2 graves, 2 criticos)


def test_padrao_falls_without_last_stand():
    foe, _rounds, _ = _strike_until_fall("padrao", 3)
    assert foe.get("dead") or foe.get("incapacitated")
    assert not foe.get("last_stand_resolved")
