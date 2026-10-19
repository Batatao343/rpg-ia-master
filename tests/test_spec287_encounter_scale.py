"""SPEC-287 — escala do encontro no nível 5+: economia de ações no piso."""

from __future__ import annotations

from pathlib import Path

import pytest

import encounter_budget as eb


def _body(cat: str, i: int = 1) -> dict:
    return {"id": f"{cat}_{i}", "categoria": cat}


def _fill(category: str, start: list[dict], budget: int, monkeypatch) -> list[dict]:
    import world_utils as wu

    monkeypatch.setattr(
        wu, "pick_encounter_enemy", lambda loc, danger, turn=0: {"categoria": category}
    )
    kept, _ = eb.fill_encounter(
        start,
        budget,
        {"region_id": "x"},
        1,
        make_instance=lambda entry, i: {**entry, "id": f"{category}_{i}"},
    )
    return kept


def _legacy_fill_count(category: str, start: int, budget: int) -> int:
    """Regra anterior (custo linear) — referência para os níveis 1–4."""
    floor = max(eb.TIER_COST["minion"], budget // 2)
    cost = eb.CATEGORIA_COST[category]
    n, spent, i = start, start * cost, 0
    while spent < floor and i < 4:
        i += 1
        n += 1
        spent += cost
    return n


def test_floor_cost_single_body_is_linear():
    for cat in ("lacaio", "padrao", "elite", "chefe", "nomeado"):
        assert eb.floor_cost([_body(cat)]) == eb.CATEGORIA_COST[cat]


def test_floor_cost_superlinear_in_bodies():
    two = eb.floor_cost([_body("lacaio", 1), _body("lacaio", 2)])
    three = eb.floor_cost([_body("lacaio", i) for i in (1, 2, 3)])
    assert two > 2 * eb.floor_cost([_body("lacaio")])
    assert three - two > two - eb.floor_cost([_body("lacaio")])


def test_floor_cost_boss_is_linear_and_not_counted_as_body():
    assert eb.floor_cost([_body("chefe"), _body("lacaio")]) == 12 + 2
    assert eb.floor_cost(
        [_body("chefe"), _body("lacaio", 1), _body("lacaio", 2)]
    ) == 12 + eb.floor_cost([_body("lacaio", 1), _body("lacaio", 2)])


@pytest.mark.parametrize("level", [1, 2, 3, 4])
@pytest.mark.parametrize("danger", [1, 2, 3, 4])
@pytest.mark.parametrize("allies", [0, 1])
@pytest.mark.parametrize("category", ["lacaio", "padrao", "elite"])
def test_levels_1_to_4_floor_unchanged(level, danger, allies, category, monkeypatch):
    """R2: em pisos ≤ 4 (todo nível 1–4 em perigo 1–2, o recorte da arena) o
    número de corpos é exatamente o da regra linear. Acima disso (nível 2–4 em
    perigo 3–4) o piso nunca ganha corpos: só pode ficar menor."""
    budget = eb.encounter_budget(level, danger, allies)
    floor = max(eb.TIER_COST["minion"], budget // 2)
    kept = _fill(category, [_body(category)], budget, monkeypatch)
    if floor <= 4:
        assert len(kept) == _legacy_fill_count(category, 1, budget)
    else:
        assert len(kept) <= _legacy_fill_count(category, 1, budget)


@pytest.mark.parametrize("level,danger", [(5, 3), (6, 3), (7, 4), (8, 4)])
@pytest.mark.parametrize("category", ["lacaio", "padrao", "elite"])
def test_levels_5_to_8_floor_at_most_two_bodies(level, danger, category, monkeypatch):
    """R1: no nível 5–8 no perigo da arena, o piso fecha com até 2 corpos."""
    budget = eb.encounter_budget(level, danger, 0)
    kept = _fill(category, [_body(category)], budget, monkeypatch)
    assert len(kept) <= 2
    assert eb.floor_cost(kept) >= max(eb.TIER_COST["minion"], budget // 2)


def test_lacaio_horde_floor_shrinks_at_level_8(monkeypatch):
    budget = eb.encounter_budget(8, 4, 0)
    assert _legacy_fill_count("lacaio", 1, budget) == 5
    assert len(_fill("lacaio", [_body("lacaio")], budget, monkeypatch)) == 2


def test_clamp_stays_linear():
    """R3: o teto (`clamp_encounter`) não muda — só o piso usa economia de ações."""
    horde = [_body("lacaio", i) for i in range(1, 6)]
    kept, logs = eb.clamp_encounter(horde, 10, player_level=5)
    assert len(kept) == 5 and logs == []


# --- R4: sobrevivência específica do Chefe/Nomeado por Nível do Encontro -----
def _chefes_and_others():
    from agents.bestiary import load_bestiary
    from combat_mechanics import normalize_categoria

    db = load_bestiary()
    chefes = [b for b, e in db.items() if normalize_categoria(e) in ("chefe", "nomeado")]
    others = [b for b, e in db.items() if normalize_categoria(e) not in ("chefe", "nomeado")]
    return db, chefes, others


def test_generator_sets_survival_only_on_chefe_and_nomeado():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migrate_bestiary_v4",
        Path(__file__).resolve().parents[1] / "scripts" / "migrate_bestiary_v4.py",
    )
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    db, chefes, others = _chefes_and_others()
    assert chefes, "bestiário sem Chefe"
    for bid in chefes:
        cat = db[bid].get("categoria")
        assert (
            db[bid].get("vitalidade_por_nivel_encontro")
            == (gen.SOBREVIVENCIA_POR_NIVEL_ENCONTRO[cat])
        ), bid
    for bid in others:
        assert "vitalidade_por_nivel_encontro" not in db[bid], bid


def test_template_by_id_survival_scales_from_encounter_level_3():
    from agents.bestiary import template_by_id

    db, chefes, others = _chefes_and_others()
    bid = chefes[0]
    base = int(db[bid]["max_vitalidade"])
    per = int(db[bid]["vitalidade_por_nivel_encontro"])
    assert template_by_id(bid, encounter_level=1)["max_vitalidade"] == base
    assert template_by_id(bid, encounter_level=2)["max_vitalidade"] == base
    lvl3 = template_by_id(bid, encounter_level=3)
    assert lvl3["max_vitalidade"] == lvl3["vitalidade"] == lvl3["hp"] == base + per
    assert template_by_id(bid, encounter_level=4)["max_vitalidade"] == base + 2 * per
    assert int(db[bid]["max_vitalidade"]) == base  # bestiário em memória intacto
    other = others[0]
    assert template_by_id(other, encounter_level=4)["max_vitalidade"] == int(
        db[other]["max_vitalidade"]
    )


def test_generate_new_enemy_cache_hit_applies_survival(monkeypatch):
    from agents import bestiary

    db, chefes, _ = _chefes_and_others()
    bid = chefes[0]
    monkeypatch.setattr(bestiary, "find_existing_entity", lambda *a, **k: bid)
    out = bestiary.generate_new_enemy(db[bid]["name"], encounter_level=3)
    assert out["max_vitalidade"] == int(db[bid]["max_vitalidade"]) + int(
        db[bid]["vitalidade_por_nivel_encontro"]
    )
