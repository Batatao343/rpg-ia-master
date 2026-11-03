"""SPEC-368 R4-R5 - toda familia e toda faccao do bestiario tem baralho e >= 1 Carta exclusiva."""

from __future__ import annotations

from agents.bestiary import load_bestiary
from services import card_effects as fx
from services import card_lint, cards
from services import enemy_decks as edk


def _bestiary_factions() -> set[str]:
    return {edk._fold(c.get("faction")) for c in load_bestiary().values() if c.get("faction")}


def test_every_family_and_faction_has_exclusive_card():
    pools = edk._pools()
    assert set(pools["familias"]) == set(edk.FAMILIAS)
    # derivado do bestiario: facção nova com criatura e sem baralho reprova aqui (sem lista fixa)
    missing = _bestiary_factions() - set(pools["faccoes"])
    assert not missing, f"facções do bestiário sem baralho: {sorted(missing)}"
    groups = [("familia", k, v) for k, v in pools["familias"].items()] + [
        ("faccao", k, v) for k, v in pools["faccoes"].items()
    ]
    for kind, key, ids in groups:
        others = {c for k2, k, v2 in groups if k != key for c in v2}
        assert set(ids) - others, f"{kind} {key} sem carta exclusiva"
        assert len(ids) == len(set(ids))


def test_spec368_faction_decks_lint_and_budget():
    pools = edk._pools()["faccoes"]
    authored = {
        fac
        for fac, ids in pools.items()
        if any((cards.get_card(i) or {}).get("origem") == "cartas-368" for i in ids)
    }
    assert len(authored) == 14
    for fac in sorted(authored):
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
