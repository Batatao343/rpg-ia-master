"""SPEC-355 R1: o buff defensivo que o reagente poe EM SI numa Reacao vale ate o proximo ataque."""

from __future__ import annotations

import random

import pytest

import combat_mechanics as cm
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct

SIDES = {"hero": ["player"], "ally": [], "enemy": ["e"]}


def _mk(actor_id: str, **kw) -> dict:
    base = {
        "id": actor_id,
        "name": actor_id,
        "virtudes": {"forca": 2, "agilidade": 2, "corpo": 3, "mente": 1, "carisma": 1},
    }
    base.update(kw)
    return orch.ensure_combat_sheet(base, is_player=(actor_id == "player"))


def _scene() -> dict:
    scene = cs.new_scene()
    for i in ("player", "e"):
        cs.place(scene, i)
    cs.freeze(scene)
    return scene


def _protection(actor: dict) -> int:
    return int(cm.combat_modifiers(actor).get("protection", 0) or 0)


def _attack_decl() -> ct.TurnDeclaration:
    return ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="attack", target_id="e"))


@pytest.mark.parametrize(
    ("ordem", "initiator", "check_after_round"),
    [("hero_first", "heroes", 1), ("enemy_first", "enemy", 2)],
)
def test_reaction_self_protection_d1_lasts_until_next_enemy_attack(
    ordem, initiator, check_after_round
):
    """A Protecao d=1 que 'e' poe em si ao reagir sobrevive ao fim do PROPRIO turno seguinte."""
    player, enemy = _mk("player"), _mk("e", cartas=["bst_defesa_instintiva"])
    actors = {"player": player, "e": enemy}
    scene = _scene()
    seen = []
    for rnd in (1, 2):
        decl = _attack_decl() if rnd == 1 else ct.TurnDeclaration(actor_id="player")
        orch.run_round(
            scene,
            actors,
            SIDES,
            {"player": player},
            declarations={"player": decl},
            initiator=initiator,
            rng=random.Random(rnd),
        )
        seen.append(_protection(enemy))
    assert seen[check_after_round - 1] >= 1, (ordem, seen)


def test_tag_is_outside_resolve_reaction_effect():
    """Chamar `_resolve_reaction_effect` direto nao grava `source_actor_id` (golden intocado)."""
    from services import cards

    enemy = _mk("e", cartas=["bst_defesa_instintiva"])
    player = _mk("player")
    out = {"logs": [], "deaths": [], "terminal": []}
    orch._resolve_reaction_effect(
        _scene(),
        enemy,
        "e",
        cards.get_card("bst_defesa_instintiva"),
        "player",
        {"player": player, "e": enemy},
        out,
        rng=random.Random(1),
    )
    conds = enemy["active_conditions"]
    assert conds and not any("source_actor_id" in c for c in conds)


def test_window_tags_self_buff_with_reactor_as_source():
    player, enemy = _mk("player"), _mk("e", cartas=["bst_defesa_instintiva"])
    out = {"logs": [], "deaths": [], "terminal": []}
    orch._open_reaction_window(
        _scene(),
        "player",
        "e",
        {"player": player, "e": enemy},
        SIDES,
        out,
        rng=random.Random(1),
    )
    tagged = [c for c in enemy["active_conditions"] if c.get("source_actor_id")]
    assert tagged and all(c["source_actor_id"] == "e" for c in tagged)


def test_enemy_reaction_buff_also_marked():
    """Simetria: o marcador `_pula_tick` entra na condicao do reagente (inimigo)."""
    player, enemy = _mk("player"), _mk("e", cartas=["bst_defesa_instintiva"])
    actors = {"player": player, "e": enemy}
    before = orch._snapshot_conditions(actors)
    out = {"logs": [], "deaths": [], "terminal": []}
    orch._open_reaction_window(_scene(), "player", "e", actors, SIDES, out, rng=random.Random(1))
    marked = orch._mark_fresh_conditions(before, actors, "player", SIDES)
    assert marked >= 1
    assert any(c.get(orch._SKIP_KEY) for c in enemy["active_conditions"])
    # fim do turno do proprio reagente: a condicao marcada sobrevive uma vez
    present = list(enemy["active_conditions"])
    orch._expire_stat_conditions(enemy, present, {"logs": []})
    assert _protection(enemy) >= 1
    orch._expire_stat_conditions(enemy, list(enemy["active_conditions"]), {"logs": []})
    assert _protection(enemy) == 0
