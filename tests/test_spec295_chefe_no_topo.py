"""SPEC-295 — Chefe no topo: ações extras (K2) e Proteção por Nível do Encontro."""

from __future__ import annotations

import importlib.util
import random
from pathlib import Path

import pytest

import combat_mechanics as cm
from agents import bestiary
from combat_mechanics import normalize_categoria
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct

ROOT = Path(__file__).resolve().parents[1]


def _generator():
    spec = importlib.util.spec_from_file_location(
        "migrate_bestiary_v4", ROOT / "scripts" / "migrate_bestiary_v4.py"
    )
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return gen


def _split():
    db = bestiary.load_bestiary()
    bosses = sorted(b for b, e in db.items() if normalize_categoria(e) in ("chefe", "nomeado"))
    others = sorted(b for b, e in db.items() if normalize_categoria(e) not in ("chefe", "nomeado"))
    return db, bosses, others


def _mk(actor_id, **kw):
    base = {
        "id": actor_id,
        "name": actor_id,
        "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1},
    }
    base.update(kw)
    return orch.ensure_combat_sheet(base, is_player=(actor_id == "player"))


def _round(enemy: dict, *, seed: int = 3, ally: dict | None = None):
    player = _mk("player", max_vitalidade=999, vitalidade=999)
    actors = {"player": player, enemy["id"]: enemy}
    sides = {"hero": ["player"], "ally": [], "enemy": [enemy["id"]]}
    if ally is not None:
        actors[ally["id"]] = ally
        sides["ally"] = [ally["id"]]
    scene = cs.new_scene()
    for aid in actors:
        cs.place(scene, aid)
    cs.freeze(scene)
    # Inimigo resistente: o ataque do herói não encerra a luta antes das ações extras.
    enemy["max_vitalidade"] = enemy["vitalidade"] = 99
    decl = {
        "player": ct.TurnDeclaration(
            actor_id="player", acao=ct.TurnStep(kind="attack", target_id=enemy["id"])
        )
    }
    out = orch.run_round(
        scene, actors, sides, {"player": player}, declarations=decl, rng=random.Random(seed)
    )
    return out, player


# --- R6: dados só pelo gerador ------------------------------------------------
def test_generator_sets_boss_fields_only_on_chefe():
    gen = _generator()
    db, bosses, others = _split()
    assert bosses
    for bid in bosses:
        cat = db[bid]["categoria"]
        assert db[bid].get("acoes_por_rodada") == gen.ACOES_POR_RODADA[cat], bid
    for bid in others:
        assert "acoes_por_rodada" not in db[bid], bid


def test_generator_is_idempotent_for_boss_fields():
    gen = _generator()
    db, bosses, others = _split()
    for bid in (bosses[0], others[0]):
        once = gen.migrate_creature(dict(db[bid]))
        twice = gen.migrate_creature(dict(once))
        assert once.get("acoes_por_rodada") == twice.get("acoes_por_rodada")


def test_runtime_default_matches_generator():
    assert bestiary.DEFAULT_ACTIONS_PER_ROUND == _generator().ACOES_POR_RODADA


def test_materialized_llm_boss_gets_actions():
    out = bestiary.materialize_enemy_concept({"name": "X", "categoria": "chefe"})
    assert out["acoes_por_rodada"] == 2
    out = bestiary.materialize_enemy_concept({"name": "Y", "categoria": "elite"})
    assert "acoes_por_rodada" not in out


# --- Proteção do Chefe pelo Nível do Encontro (R5) ------------------------------
@pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 10])
def test_boss_protection_depends_only_on_encounter_level(level):
    _db, bosses, others = _split()
    expected = bestiary.CHEFE_PROTECAO_POR_NIVEL_ENCONTRO.get(level, 0)
    for bid in bosses:
        tpl = bestiary.template_by_id(bid, encounter_level=level)
        assert int(tpl.get("protecao_natural") or 0) == expected, (bid, level)
    for bid in others:
        tpl = bestiary.template_by_id(bid, encounter_level=level)
        assert "protecao_natural" not in tpl, (bid, level)


def test_boss_template_keeps_spec287_vitality():
    """A Proteção não mexe na Vitalidade (testes da SPEC-287/290 seguem valendo)."""
    db, bosses, _ = _split()
    bid = bosses[0]
    assert bestiary.template_by_id(bid, encounter_level=1)["max_vitalidade"] == int(
        db[bid]["max_vitalidade"]
    )


def test_natural_protection_counts_as_protection_modifier():
    boss = _mk("boss", categoria="chefe", protecao_natural=2)
    assert cm.combat_modifiers(boss)["protection"] == 2
    assert cm.combat_modifiers(_mk("e"))["protection"] == 0


def test_natural_protection_absorbs_hit_but_not_dot():
    from services.conflict_damage import _resolve_damage_and_wounds

    boss = _mk("boss", categoria="chefe", protecao_natural=2, max_vitalidade=30, vitalidade=30)
    hit = _resolve_damage_and_wounds(boss, damage_base=5, rng=random.Random(1))
    assert hit["vitalidade"] == 30 - 3
    dot = _resolve_damage_and_wounds(boss, damage_base=2, bypass_armor=True, rng=random.Random(1))
    assert dot["vitalidade"] == 27 - 2


def test_player_ignores_natural_protection_field():
    player = _mk("player", protecao_natural=5)
    assert cm.combat_modifiers(player)["protection"] == 0


# --- K2: ações extras ----------------------------------------------------------
def test_extra_actions_defaults_and_bad_values():
    assert orch.extra_actions({}) == 0
    assert orch.extra_actions({"acoes_por_rodada": 1}) == 0
    assert orch.extra_actions({"acoes_por_rodada": 2}) == 1
    assert orch.extra_actions({"acoes_por_rodada": "x"}) == 0
    assert orch.extra_actions({"acoes_por_rodada": None}) == 0


def test_boss_extra_action_acts_twice_and_logs():
    boss = _mk("boss", categoria="chefe", acoes_por_rodada=2)
    out, _ = _round(boss)
    assert out["resolved_turns"].count("boss") == 2
    assert any("age de novo" in line for line in out["logs"])


def test_extra_action_comes_after_everyone():
    boss = _mk("boss", categoria="chefe", acoes_por_rodada=2)
    out, _ = _round(boss)
    turns = out["resolved_turns"]
    assert turns[-1] == "boss"
    assert turns.index("player") < len(turns) - 1


def test_non_boss_acts_once():
    out, _ = _round(_mk("e", categoria="elite"))
    assert out["resolved_turns"].count("e") == 1
    assert not any("age de novo" in line for line in out["logs"])


def test_extra_actions_only_for_enemy_side():
    ally = _mk("ally", is_ally=True, acoes_por_rodada=3)
    ally = orch.ensure_combat_sheet(ally, is_ally=True)
    out, _ = _round(_mk("e", categoria="padrao"), ally=ally)
    assert out["resolved_turns"].count("ally") <= 1


def test_stun_denies_all_boss_actions():
    boss = _mk("boss", categoria="chefe", acoes_por_rodada=2)
    cm.apply_condition(boss, {"name": "Atordoado", "dot": 0, "duration": 1, "control": "stun"})
    out, _ = _round(boss)
    assert out["resolved_turns"].count("boss") == 0


def test_condition_ticks_once_per_round():
    boss = _mk("boss", categoria="chefe", acoes_por_rodada=3, max_vitalidade=50, vitalidade=50)
    cm.apply_condition(boss, {"name": "Sangrando", "dot": 1, "duration": 5})
    before_dur = boss["active_conditions"][0]["duration"]
    out, _ = _round(boss)
    assert out["resolved_turns"].count("boss") == 3
    dots = [line for line in out["logs"] if "Sangrando" in line and "sofre" in line]
    assert len(dots) == 1
    assert boss["active_conditions"][0]["duration"] == before_dur - 1


def test_old_save_enemy_without_new_fields_acts_once():
    """R9: ficha de inimigo salva antes desta spec (sem `acoes_por_rodada`)."""
    old = _mk("boss", categoria="chefe")
    assert "acoes_por_rodada" not in old and "protecao_natural" not in old
    out, _ = _round(old)
    assert out["resolved_turns"].count("boss") == 1
    assert cm.combat_modifiers(old)["protection"] == 0


def test_same_seed_same_outcome():
    def run():
        _db, bosses, _ = _split()
        tpl = bestiary.template_by_id(bosses[0], encounter_level=1)
        boss = orch.ensure_combat_sheet({**tpl, "id": "boss"})
        out, player = _round(boss, seed=11)
        return out["logs"], player["vitalidade"], boss["vitalidade"]

    assert run() == run()
