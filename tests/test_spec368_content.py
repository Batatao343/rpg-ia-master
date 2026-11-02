"""SPEC-368 R4-R5 - toda familia e toda faccao de combate tem baralho e >= 1 Carta exclusiva."""

from __future__ import annotations

from services import card_lint, cards, enemy_decks as edk
from services import card_effects as fx

NEW_FACTIONS = (
    "tribos_devoradores_sol",
    "bandos_nomades",
    "colmeia_hospedeiros",
    "mercadores_escravos_pradaria",
)


def test_every_family_and_faction_has_exclusive_card():
    pools = edk._pools()
    assert len(pools["familias"]) == 11 and set(pools["familias"]) == set(edk.FAMILIAS)
    assert len(pools["faccoes"]) == 14
    groups = [("familia", k, v) for k, v in pools["familias"].items()] + [
        ("faccao", k, v) for k, v in pools["faccoes"].items()
    ]
    for kind, key, ids in groups:
        others = {c for k2, k, v2 in groups if k != key for c in v2}
        assert set(ids) - others, f"{kind} {key} sem carta exclusiva"
        assert len(ids) == len(set(ids))


def test_new_faction_decks_lint_and_budget():
    pools = edk._pools()["faccoes"]
    for fac in NEW_FACTIONS:
        ids = pools[fac]
        assert 6 <= len(ids) <= 8, fac
        for cid in ids:
            raw = cards.get_card(cid)
            assert raw and raw["classe"] == "Inimigo" and raw["subclasse"] == fac
            card = fx.materialize(raw)
            assert fx.budget_error(card) is None, (cid, fx.budget_error(card))
            issues = card_lint.errors(
                card_lint.check_vocabulary(card)
                + card_lint.check_budget(card)
                + card_lint.check_voice(card)
            )
            assert not issues, (cid, [str(i) for i in issues])


def test_every_bestiary_faction_deck_is_reachable():
    # as facções do R4 só valem se alguma criatura do bestiário as referencia
    from agents.bestiary import load_bestiary

    used = {edk._fold(c.get("faction")) for c in load_bestiary().values()}
    assert set(NEW_FACTIONS) <= used
