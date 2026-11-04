"""SPEC-373 R2/R9/R10: família como tempero para criatura autoral; população da 332 e `off` intactos."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agents.bestiary import load_bestiary
from services import conflict_orchestrator as orch
from services import enemy_decks as edk

BASE = Path(__file__).resolve().parents[1] / "docs" / "spec373" / "base"


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.delenv("RPG_ENEMY_DECKS", raising=False)
    edk.reload()
    yield
    edk.reload()


def _autorais() -> dict[str, dict]:
    return {k: v for k, v in load_bestiary().items() if edk._autoral({**v, "id": k})}


def _sig_ids(entry: dict) -> set[str]:
    return {str(s["carta"]) for s in edk._signature_configs(entry)}


def test_snapshot_off_existe_e_bate(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "off")
    snap = json.loads((BASE / "snapshot-off.json").read_text("utf-8"))
    bestiary = load_bestiary()
    assert set(snap) == set(bestiary)
    recal = set(json.loads((BASE.parent / "recalibradas.json").read_text("utf-8")))  # R8
    for bid, entry in bestiary.items():
        if bid in recal:
            continue
        sheet = orch.ensure_combat_sheet({**json.loads(json.dumps(entry)), "id": bid})
        blob = json.dumps(sheet, sort_keys=True, ensure_ascii=False, default=str)
        assert hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16] == snap[bid], bid


def test_autoral_sem_assinatura_da_familia(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    pop = _autorais()
    assert len(pop) >= 200
    for bid, entry in pop.items():
        for seed in range(4):
            deck = edk.build_enemy_deck({**entry, "id": bid}, seed)
            assert not (set(deck) & _sig_ids(entry)), (bid, seed)


def test_autoral_familia_1_ou_2(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    pools = edk._pools()
    for bid, entry in _autorais().items():
        fam = edk.family_key(entry)
        if not fam:
            continue
        for seed in range(6):
            creature = {**entry, "id": bid}
            deck = edk.build_enemy_deck(creature, seed)
            n = len(set(deck) & set(pools["familias"].get(fam, [])))
            assert 0 <= n <= 2, (bid, seed, n)
            assert deck == edk.build_enemy_deck(creature, seed)
    assert any(
        len(
            set(edk.build_enemy_deck({**e, "id": b}, 0))
            & set(pools["familias"].get(edk.family_key(e), []))
        )
        >= 1
        for b, e in _autorais().items()
    )


def test_populacao_332_identica(monkeypatch):
    """R9: a regra de montagem não muda a população da 332. As Cartas novas da R14
    (`origem: cartas-373`) mudam os pools de propósito, então a identidade vale com os
    pools da `main` (sem elas)."""
    from services import cards

    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    pools = edk._pools()
    novas = {
        c
        for ids in pools["familias"].values()
        for c in ids
        if (cards.get_card(c) or {}).get("origem") == "cartas-373"
    }
    main_fams = {f: [c for c in ids if c not in novas] for f, ids in pools["familias"].items()}
    monkeypatch.setattr(edk, "_pools_cache", {"familias": main_fams, "faccoes": pools["faccoes"]})
    fixture = json.loads((BASE / "deck-332-main.json").read_text("utf-8"))
    bestiary = load_bestiary()
    assert fixture
    for bid, decks in fixture.items():
        entry = {**bestiary[bid], "id": bid}
        assert [edk.build_enemy_deck(entry, s) for s in range(12)] == decks, bid


def test_save_antigo_nao_remonta(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    bid, entry = next(iter(_autorais().items()))
    fam = edk.family_key(entry)
    pool = [c for c in edk._pools()["familias"][fam] if c not in _sig_ids(entry)]
    # baralho antigo (3-5 da família) sem marcador: não remonta
    old = {
        **json.loads(json.dumps(entry)),
        "id": bid + "_1",
        "cartas": [*edk._own_ids(entry), *pool[:4]],
    }
    got = [c for c in orch.ensure_combat_sheet(old)["cartas"] if c.startswith("inf_")]
    assert got == pool[:4]
    # montado pelo R9 (1 carta de pool), sem marcador: também não remonta
    one = {
        **json.loads(json.dumps(entry)),
        "id": bid + "_1",
        "cartas": [*edk._own_ids(entry), pool[0]],
    }
    got = [c for c in orch.ensure_combat_sheet(one)["cartas"] if c.startswith("inf_")]
    assert got == [pool[0]]


def test_round_trip_save_load_on(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    bid = "mon_borda_que_anda"
    e = orch.ensure_combat_sheet({**json.loads(json.dumps(load_bestiary()[bid])), "id": bid + "_1"})
    e["fase_idx"] = 1
    before = list(e["cartas"])
    assert e.get("_deck332")
    again = orch.ensure_combat_sheet(json.loads(json.dumps(e)))
    assert again["cartas"] == before and again["fase_idx"] == 1
    stripped = json.loads(json.dumps(e))
    stripped.pop("_deck332")
    assert orch.ensure_combat_sheet(stripped)["cartas"] == before
