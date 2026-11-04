"""SPEC-391: reforço de combate no tabuleiro de cartas ("Chamado do Bando" do líder de matilha).

Etapa 1 (avaliador do gate, congelado): oráculo de equivalência da arena
``docs/spec391/arena_reforco_cartas.py`` contra ``scripts/cards/sim.py::_fight`` com a flag do
reforço ``off``, e o formato da saída por célula.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARENA_PATH = os.path.join(ROOT, "docs", "spec391", "arena_reforco_cartas.py")
LEADERS = ("enemy_soldado_legiao_ferro", "mon_auroque_ruinas")
SEEDS = (0, 1)
LEVEL = 3


@pytest.fixture(scope="module")
def arena():
    name = "arena_reforco_cartas_391"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ARENA_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def deck_flags_off(monkeypatch):
    """As duas pontas com baralho de cartas e baralhos/intenção de inimigo `on`; reforço `off`."""
    monkeypatch.setenv("RPG_FORCE_MOCK", "1")
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    monkeypatch.setenv("RPG_COMBAT_REINFORCEMENTS", "off")


def test_arena_reforco_off_equivale_sim_fight(arena, deck_flags_off):
    """R14/Etapa 1: com a flag `off`, a arena nova devolve o mesmo `(desfecho, rodadas)` de
    `sim._fight` em 20 lutas fixas (5 Posturas × 2 líderes × 2 sementes, L3)."""
    assert set(LEADERS) <= set(arena.A.leader_pool())
    assert len(arena.CLASSES) == 5
    pairs = []
    for cls in arena.CLASSES:
        deck = arena.sim.full_deck(cls, LEVEL)
        for bid in LEADERS:
            for seed in SEEDS:
                counters: dict = {}
                got = arena.fight(bid, 1, cls, LEVEL, seed, deck, "391", counters)
                ref = arena.sim._fight(bid, 1, cls, LEVEL, seed, deck, "391")
                pairs.append((cls, bid, seed, got, ref))
                assert counters == dict.fromkeys(arena.FLOW_COUNTERS, 0)
    assert len(pairs) == 20
    diverge = [p for p in pairs if p[3] != p[4]]
    assert not diverge, diverge
    assert all(p[3][0] in ("win", "death", "timeout") for p in pairs)


def test_arena_reforco_saida_tem_campos(arena, deck_flags_off):
    """Etapa 1: cada célula tem `death/win/timeout/fights/avg_rounds/per_class` e os contadores
    do fluxo `telegraphed/called/fired/cancelled` (também no total)."""
    classes = list(arena.CLASSES[:2])
    res = arena.run(range(1), [LEVEL], classes)
    pool = arena.A.leader_pool()
    assert res["pool"] == pool and res["mode"] == "off"
    assert isinstance(res["card_flow"], bool)
    cell = res["cells"][f"L{LEVEL}|lider_matilha"]
    for block in (cell, res["total"]):
        for key in ("death", "win", "timeout", "fights", "avg_rounds", "per_class"):
            assert key in block, key
        for key in ("telegraphed", "called", "fired", "cancelled"):
            assert isinstance(block[key], int) and block[key] == 0, key
        assert block["fights"] == len(pool) * len(classes)
        assert block["death"] + block["win"] + block["timeout"] == block["fights"]
        assert set(block["per_class"]) == set(classes)
        for pc in block["per_class"].values():
            assert pc["fights"] == len(pool)
            assert {"death", "win", "timeout", "death_rate", "win_rate"} <= set(pc)
