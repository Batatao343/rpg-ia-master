"""SPEC-290 — sobrevivência de Chefe/Nomeado para Chefe do LLM e laboratório."""

from __future__ import annotations

import pytest

from agents import bestiary


def _chefe_id() -> str:
    from combat_mechanics import normalize_categoria

    db = bestiary.load_bestiary()
    return next(b for b, e in db.items() if normalize_categoria(e) == "chefe")


def _lacaio_id() -> str:
    from combat_mechanics import normalize_categoria

    db = bestiary.load_bestiary()
    return next(b for b, e in db.items() if normalize_categoria(e) == "lacaio")


def test_default_matches_generator_constant():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "migrate_bestiary_v4",
        Path(__file__).resolve().parents[1] / "scripts" / "migrate_bestiary_v4.py",
    )
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    assert bestiary.DEFAULT_SURVIVAL_PER_LEVEL == gen.SOBREVIVENCIA_POR_NIVEL_ENCONTRO


@pytest.mark.parametrize("cat", ["chefe", "nomeado"])
def test_missing_field_gets_canonical_default(cat):
    data = {"categoria": cat, "max_vitalidade": 30}
    bestiary.apply_encounter_survival(data, 4)
    assert data["max_vitalidade"] == 30 + 2 * 12


def test_present_field_beats_default():
    data = {"categoria": "chefe", "max_vitalidade": 30, "vitalidade_por_nivel_encontro": 5}
    bestiary.apply_encounter_survival(data, 3)
    assert data["max_vitalidade"] == 35


def test_other_categories_get_no_bonus():
    for cat in ("lacaio", "padrao", "elite"):
        data = {"categoria": cat, "max_vitalidade": 20}
        bestiary.apply_encounter_survival(data, 10)
        assert data["max_vitalidade"] == 20


def test_below_level_3_no_bonus():
    data = {"categoria": "chefe", "max_vitalidade": 30}
    bestiary.apply_encounter_survival(data, 2)
    assert data["max_vitalidade"] == 30


def test_materialized_chefe_carries_field():
    out = bestiary.materialize_enemy_concept({"name": "X", "categoria": "chefe"})
    assert out["vitalidade_por_nivel_encontro"] == 12
    out = bestiary.materialize_enemy_concept({"name": "Y", "categoria": "elite"})
    assert "vitalidade_por_nivel_encontro" not in out


def _fake_llm(monkeypatch, categoria: str):
    class _Designer:
        def invoke(self, _msgs):
            return bestiary.EnemySchema(name="Colosso Teste", description="d", categoria=categoria)

    class _LLM:
        def with_structured_output(self, _schema):
            return _Designer()

    monkeypatch.setattr(bestiary, "get_llm", lambda **k: _LLM())
    monkeypatch.setattr(bestiary, "find_existing_entity", lambda *a, **k: None)
    monkeypatch.setattr(bestiary, "query_rag", lambda *a, **k: "")
    saved = {}
    monkeypatch.setattr(bestiary, "save_enemy", lambda d: saved.update(copy=dict(d)))
    return saved


def test_llm_generated_chefe_scales_but_saved_overlay_is_base(monkeypatch):
    saved = _fake_llm(monkeypatch, "chefe")
    base = bestiary.generate_new_enemy("Colosso Teste", encounter_level=1)
    scaled = bestiary.generate_new_enemy("Colosso Teste", encounter_level=4)
    assert scaled["max_vitalidade"] == base["max_vitalidade"] + 24
    assert scaled["vitalidade"] == scaled["hp"] == scaled["max_hp"] == scaled["max_vitalidade"]
    assert saved["copy"]["max_vitalidade"] == base["max_vitalidade"]  # sem bônus no cache


def test_llm_generated_lacaio_not_scaled(monkeypatch):
    _fake_llm(monkeypatch, "lacaio")
    a = bestiary.generate_new_enemy("Colosso Teste", encounter_level=1)
    b = bestiary.generate_new_enemy("Colosso Teste", encounter_level=4)
    assert a["max_vitalidade"] == b["max_vitalidade"]


def test_fallback_path_chefe_not_applicable_lacaio(monkeypatch):
    class _Boom:
        def with_structured_output(self, _s):
            raise RuntimeError("x")

    monkeypatch.setattr(bestiary, "get_llm", lambda **k: _Boom())
    monkeypatch.setattr(bestiary, "find_existing_entity", lambda *a, **k: None)
    monkeypatch.setattr(bestiary, "query_rag", lambda *a, **k: "")
    out = bestiary.generate_new_enemy("Qualquer", encounter_level=5)
    assert out["categoria"] == "lacaio"


def test_cached_overlay_chefe_without_field_scales(monkeypatch):
    base = bestiary.materialize_enemy_concept(
        {"name": "Velho", "id": "velho", "categoria": "chefe"}
    )
    base.pop("vitalidade_por_nivel_encontro")
    monkeypatch.setattr(bestiary, "load_bestiary", lambda: {"velho": base})
    monkeypatch.setattr(bestiary, "find_existing_entity", lambda *a, **k: "velho")
    out = bestiary.generate_new_enemy("Velho", encounter_level=3)
    assert out["max_vitalidade"] == base["max_vitalidade"] + 12


def _lab(enemy_id: str, quantity: int = 1) -> list[dict]:
    import api

    req = api.CombatSimulatorRequest(
        class_name=next(iter(__import__("gamedata").CLASSES)),
        level=5,
        enemy_id=enemy_id,
        quantity=quantity,
    )
    return api._build_combat_simulator_state(req)["enemies"]


def test_lab_chefe_gets_survival_bonus():
    import gamedata

    bid = _chefe_id()
    tpl = gamedata.BESTIARY[bid]
    per = int(tpl.get("vitalidade_por_nivel_encontro") or 12)
    for enemy in _lab(bid, 2):
        assert enemy["max_vitalidade"] == int(tpl["max_vitalidade"]) + 2 * per
        assert enemy["vitalidade"] == enemy["max_vitalidade"]
    assert int(gamedata.BESTIARY[bid]["max_vitalidade"]) == int(tpl["max_vitalidade"])


def test_lab_lacaio_unchanged():
    import gamedata

    bid = _lacaio_id()
    for enemy in _lab(bid):
        assert enemy["max_vitalidade"] == int(gamedata.BESTIARY[bid]["max_vitalidade"])


# --- Revisão: round-trip real do overlay e do save (não acumula) -------------


def test_real_overlay_round_trip_does_not_accumulate(monkeypatch):
    """Overlay gravado de verdade (save_enemy real) volta na base; dois encontros
    de cache-hit no nível 4 dão o mesmo valor (base + 24), sem somar de novo."""

    class _Designer:
        def invoke(self, _msgs):
            return bestiary.EnemySchema(name="Titã Revisão", description="d", categoria="chefe")

    class _LLM:
        def with_structured_output(self, _schema):
            return _Designer()

    monkeypatch.setattr(bestiary, "get_llm", lambda **k: _LLM())
    monkeypatch.setattr(bestiary, "query_rag", lambda *a, **k: "")
    hits: list[str] = []
    monkeypatch.setattr(bestiary, "find_existing_entity", lambda *a, **k: hits[0] if hits else None)
    first = bestiary.generate_new_enemy("Titã Revisão", encounter_level=4)
    hits.append(first["id"])
    stored = bestiary.load_bestiary()[first["id"]]
    assert stored["vitalidade_por_nivel_encontro"] == 12
    base = int(stored["max_vitalidade"])
    assert first["max_vitalidade"] == base + 24
    again = bestiary.generate_new_enemy("Titã Revisão", encounter_level=4)
    third = bestiary.generate_new_enemy("Titã Revisão", encounter_level=4)
    assert again["max_vitalidade"] == third["max_vitalidade"] == base + 24
    assert int(bestiary.load_bestiary()[first["id"]]["max_vitalidade"]) == base


def test_lab_chefe_save_load_keeps_value(tmp_path, monkeypatch):
    """Reload do laboratório não reaplica o bônus; o laboratório não mexe no
    bestiário global (nada vaza para o jogo normal)."""
    import gamedata
    import persistence

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    bid = _chefe_id()
    before = dict(gamedata.BESTIARY[bid])
    import api

    req = api.CombatSimulatorRequest(
        class_name=next(iter(gamedata.CLASSES)), level=5, enemy_id=bid, quantity=1
    )
    state = api._build_combat_simulator_state(req)
    scaled = state["enemies"][0]["max_vitalidade"]
    assert persistence.save_game_state(state) is True
    loaded = persistence.load_game_state(persistence.save_path(state["game_id"]))
    assert loaded["enemies"][0]["max_vitalidade"] == scaled
    assert gamedata.BESTIARY[bid] == before
    assert bestiary.template_by_id(bid, encounter_level=1)["max_vitalidade"] == int(
        before["max_vitalidade"]
    )
