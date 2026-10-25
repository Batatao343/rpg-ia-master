"""SPEC-315 Etapa 2: verdade deterministica, vies so do mundo e orcamento."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services import rumor_adoption as ra
from tests.spec315_helpers import (
    CREATURE,
    FAR,
    accept,
    adopted_row,
    claim,
    proposal,
    set_flags,
    state,
    with_rows,
)


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    set_flags(monkeypatch)


def test_truth_deterministic_and_never_resampled():
    st = state()
    c = claim()
    a = [ra._truth_roll(st, f"id{i}", 5, c) for i in range(40)]
    assert a == [ra._truth_roll(st, f"id{i}", 5, c) for i in range(40)]
    assert 0 < sum(a) < 40
    # gravada na instancia: o mesmo boato adotado duas vezes nao muda de verdade
    inst = {"rumor_id": "abc", "expires_day": 15}
    first, _ = ra.adopt(st, dict(inst), c, 5)
    assert first["truth"] is a_truth(st, "abc", c)
    # o ledger nunca re-sorteia: `adopted` + `truth` ficam na linha
    assert first["adopted"] is True


def a_truth(st, rid, c):
    return ra._truth_roll(st, rid, 5, c)


@pytest.mark.parametrize(
    "c,p",
    [
        (claim("esconderijo", FAR), 0.35),
        (claim("item_perdido", "pradaria_ruinas"), 0.30),
        (claim("perigo_na_estrada", "montanhas_afiadas"), 0.40),
        (claim("criatura_avistada", "nova_arcadia", CREATURE), 0.50),
    ],
)
def test_truth_rate_per_kind(c, p):
    st = state()
    assert ra.truth_p(st, c, 5) == pytest.approx(p)
    hits = sum(ra._truth_roll(st, f"r{i}", 5, c) for i in range(5000))
    assert abs(hits / 5000 - p) < 0.03


def test_truth_rate_npc(monkeypatch):
    monkeypatch.setattr(ra, "_npc_arrives_in_ttl", lambda *_a: True)
    c = claim("npc_em_local", FAR, "npc_x")
    assert ra.truth_p(state(), c, 5) == pytest.approx(0.40)
    monkeypatch.setattr(ra, "_npc_arrives_in_ttl", lambda *_a: False)
    assert ra.truth_p(state(), c, 5) == 0.0  # nao chega no TTL


def test_road_bias_guerra_and_route():
    c = claim("perigo_na_estrada", "montanhas_afiadas")
    base = ra.truth_p(state(), c, 5)
    war = state(world_sim={"bands": {"montanhas_afiadas": {"guerra": "crise"}}})
    sinal = state(world_sim={"bands": {"montanhas_afiadas": {"guerra": "sinal"}}})
    other = state(world_sim={"bands": {"nova_arcadia": {"guerra": "crise"}}})
    blocked = state(
        world_projection={"blocked_routes": [{"a": "ma_boca", "b": "montanhas_afiadas"}]}
    )
    assert ra.truth_p(war, c, 5) == pytest.approx(base + 0.25)
    assert ra.truth_p(sinal, c, 5) == pytest.approx(base + 0.25)
    assert ra.truth_p(blocked, c, 5) == pytest.approx(base + 0.25)
    assert ra.truth_p(other, c, 5) == pytest.approx(base)
    assert ra.truth_p(war, c, 5) <= 0.85


def test_creature_outside_region_always_false(monkeypatch):
    # rato do anel de lama vive em nova_arcadia; avistar em outra regiao nunca e verdade
    out = claim("criatura_avistada", "skallgard", CREATURE)
    assert ra.truth_p(state(), out, 5) == 0.0
    assert not any(ra._truth_roll(state(), f"r{i}", 5, out) for i in range(300))
    # criatura rareada na regiao tambem
    from services import ecology

    monkeypatch.setattr(ecology, "suppressed_creatures", lambda *_a: [CREATURE])
    assert ra.truth_p(state(), claim("criatura_avistada", "nova_arcadia", CREATURE), 5) == 0.0


def test_independent_of_player_stats():
    c = claim("perigo_na_estrada", "montanhas_afiadas")
    poor = state()
    rich = state()
    poor["player"] = {"name": "A", "level": 1, "gold": 0}
    rich["player"] = {"name": "A", "level": 20, "gold": 5000}
    assert ra.truth_p(poor, c, 5) == ra.truth_p(rich, c, 5)
    assert [ra._truth_roll(poor, f"r{i}", 5, c) for i in range(60)] == [
        ra._truth_roll(rich, f"r{i}", 5, c) for i in range(60)
    ]


def test_shares_312_gap():
    st = state(world_sim={"rumor_last_perceived_day": 4})
    assert ra.validate_claim(st, claim(), 5) == "gap"  # 1 dia < RUMOR_MIN_GAP_DAYS (2)
    assert ra.validate_claim(st, claim(), 6) == ""
    sim, _w, _why, extra = accept(
        state(world_sim={"rumor_last_perceived_day": 4}), [proposal(claim=claim())]
    )
    assert "adopted" not in sim["rumors"][-1] and not extra  # boato segue pela 312


def test_window_active_and_loot_caps_before_roll():
    # 2 adocoes nos ultimos 10 dias
    st = state(world_sim={"adopt_log": [1, 3]})
    assert ra.validate_claim(st, claim("perigo_na_estrada", "montanhas_afiadas"), 5) == "budget"
    st = state(world_sim={"adopt_log": [1]})
    assert ra.validate_claim(st, claim("perigo_na_estrada", "montanhas_afiadas"), 5) == ""
    # 2 adotadas ativas sem desfecho
    st = with_rows(
        state(),
        adopted_row("aaaaaaaaaaaa", "perigo_na_estrada", "skallgard", truth=False),
        adopted_row("bbbbbbbbbbbb", "perigo_na_estrada", "pradaria_ruinas", truth=False),
    )
    assert ra.validate_claim(st, claim("esconderijo", FAR), 5) == "budget"
    # achado verdadeiro nos ultimos 20 dias: so achados sao barrados, ANTES do sorteio
    st = with_rows(
        state(),
        adopted_row(
            "cccccccccccc", "item_perdido", "pradaria_ruinas", truth=True, born=-10, expires=3
        ),
    )
    assert ra.validate_claim(st, claim("esconderijo", FAR), 5) == "budget"
    assert ra.validate_claim(st, claim("perigo_na_estrada", "montanhas_afiadas"), 5) == ""
    old = with_rows(
        state(day=40),
        adopted_row(
            "dddddddddddd", "item_perdido", "pradaria_ruinas", truth=True, born=5, expires=15
        ),
    )
    assert ra.validate_claim(old, claim("esconderijo", FAR), 40) == ""  # janela de 20 dias passou


def test_no_global_random():
    tree = ast.parse(Path(ra.__file__).read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert "random" not in names and "random" not in imports


def test_forced_adopt_overrides_truth():
    st = state(
        world_sim={"forced_adopt": [{"kind": "esconderijo", "location_id": FAR, "truth": True}]}
    )
    assert all(ra._truth_roll(st, f"r{i}", 5, claim()) for i in range(20))


def test_shadow_does_not_adopt(monkeypatch):
    set_flags(monkeypatch, "shadow")
    sim, _w, _why, extra = accept(state(), [proposal(claim=claim())])
    inst = sim["rumors"][-1]
    assert inst["truth"] is False and inst["quest_eligible"] is False
    assert "adopted" not in inst and "claim" not in inst and not extra
    assert "adopt_log" not in sim
