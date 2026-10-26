"""SPEC-325 Fase A / R8 - resistencia revelada pelo `combat_node` real."""

from __future__ import annotations

import random

import pytest

from agents import combat as cbt
from services import bestiary_knowledge as bk
from services import conflict_damage as cd
from tests.spec325_helpers import lacaio, make_state, run_node


def _tough(**over):
    base = {
        "vitalidade": 60,
        "max_vitalidade": 60,
        "hp": 60,
        "max_hp": 60,
        "ferimento_espacos": {"leve": 9, "grave": 9, "critico": 9},
    }
    base.update(over)
    return lacaio(**base)


# --- dano devolve qual defesa agiu -------------------------------------------
def _target(**over):
    t = {
        "vitalidade": 30,
        "max_vitalidade": 30,
        "ferimento_espacos": {"leve": 9, "grave": 9, "critico": 9},
    }
    t.update(over)
    return t


def test_damage_returns_resistance_hit_imune():
    res = cd.resolve_damage_and_wounds(
        _target(immunities=["igneo"]), damage_base=5, damage_type="igneo", rng=random.Random(1)
    )
    assert res["resistance_hit"] == {"type": "igneo", "effect": "imune"}


def test_damage_returns_resistance_hit_resiste():
    res = cd.resolve_damage_and_wounds(
        _target(resistances={"cortante": "resistencia"}),
        damage_base=5,
        damage_type="cortante",
        rng=random.Random(1),
    )
    assert res["resistance_hit"] == {"type": "cortante", "effect": "resiste"}


def test_damage_returns_resistance_hit_vulneravel():
    res = cd.resolve_damage_and_wounds(
        _target(resistances={"cortante": "vulnerabilidade"}),
        damage_base=5,
        damage_type="cortante",
        rng=random.Random(1),
    )
    assert res["resistance_hit"] == {"type": "cortante", "effect": "vulneravel"}


def test_damage_returns_resistance_hit_none():
    res = cd.resolve_damage_and_wounds(
        _target(), damage_base=5, damage_type="cortante", rng=random.Random(1)
    )
    assert res["resistance_hit"] is None


# --- via combat_node -----------------------------------------------------------
@pytest.fixture
def spy(monkeypatch):
    seen = {}
    real = cbt._finish_encounter

    def wrapped(meta, enemies, outcome, *, loot):
        seen["enemies"] = enemies
        return real(meta, enemies, outcome, loot=loot)

    monkeypatch.setattr(cbt, "_finish_encounter", wrapped)
    return seen


def _hit(monkeypatch, enemy, mode="on"):
    monkeypatch.setenv("RPG_COMBAT_REVEAL_RESIST", mode)
    return run_node(make_state([enemy], "ataco o goblin"), monkeypatch)


def test_node_reveals_on_hero_hit(monkeypatch):
    out = _hit(monkeypatch, _tough(immunities=["cortante"]))
    enemy = out["enemies"][0]
    assert enemy["revealed_resistances"] == ["cortante:imune"]
    # a UI recebe o rotulo pt-BR
    import api

    view = api._combat_block({**make_state([enemy]), **out})["enemies"][0]
    assert view["revealed_resistances"] == ["Cortante (imune)"]


@pytest.mark.parametrize(
    "archetype,sheet,expected",
    [
        ("lobo", {"resistances": {"cortante": "resistencia"}}, "cortante:resiste"),
        ("urso", {"resistances": {"cortante": "vulnerabilidade"}}, "cortante:vulneravel"),
    ],
)
def test_node_reveals_resiste_and_vulneravel(monkeypatch, archetype, sheet, expected):
    out = _hit(monkeypatch, _tough(id=f"{archetype}_1", **sheet))
    assert out["enemies"][0]["revealed_resistances"] == [expected]


def test_enemy_hit_on_player_reveals_nothing():
    enemy = _tough()
    attacks = [
        {
            "actor_id": "e1",
            "target_id": "player",
            "resistance_hit": {"type": "cortante", "effect": "imune"},
        }
    ]
    player = {"id": "player"}
    cbt._reveal_resistances(
        attacks, [enemy, player], {"hero": ["player"], "ally": [], "enemy": ["e1"]}
    )
    assert not enemy.get("revealed_resistances") and not player.get("revealed_resistances")


def test_shadow_no_state_change(monkeypatch):
    imune = _tough(immunities=["cortante"])
    off = _hit(monkeypatch, dict(imune), mode="off")
    shadow = _hit(monkeypatch, dict(imune), mode="shadow")
    assert not off["enemies"][0].get("revealed_resistances")
    assert not shadow["enemies"][0].get("revealed_resistances")
    assert shadow["combat"] == off["combat"] and shadow["player"] == off["player"]


def test_off_has_no_resistance_hit_key_in_attacks(monkeypatch):
    seen = []
    real = cbt.orch.run_round

    def spy_round(*a, **k):
        res = real(*a, **k)
        seen.extend(res.get("attacks") or [])
        return res

    monkeypatch.setattr(cbt.orch, "run_round", spy_round)
    _hit(monkeypatch, _tough(immunities=["cortante"]), mode="off")
    assert seen and all("resistance_hit" not in a for a in seen)


def test_hosted_profile_does_not_persist_overlay(monkeypatch):
    persisted = []
    monkeypatch.setattr(bk, "reveal_resistance", lambda *a, **k: persisted.append(a))
    monkeypatch.setenv("RPG_COMBAT_REVEAL_RESIST", "on")
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")
    enemy = _tough()
    attacks = [
        {
            "actor_id": "player",
            "target_id": "e1",
            "resistance_hit": {"type": "cortante", "effect": "imune"},
        }
    ]
    cbt._reveal_resistances(attacks, [enemy], {"hero": ["player"], "ally": [], "enemy": ["e1"]})
    assert enemy["revealed_resistances"] == ["cortante:imune"]
    assert persisted == []


def test_legacy_profile_persists_overlay(monkeypatch):
    monkeypatch.setenv("RPG_COMBAT_REVEAL_RESIST", "on")
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    out = run_node(
        make_state([_tough(immunities=["cortante"], id="goblin_1")], "ataco"), monkeypatch
    )
    assert "cortante:imune" in bk._load_all()["goblin"]["revealed_resistances"]
    assert out["enemies"][0]["revealed_resistances"] == ["cortante:imune"]


def test_unrevealed_not_in_api_nor_narration(monkeypatch):
    """Regra de ouro: imunidade a `igneo` nunca agiu (golpe cortante) -> some da API e da prosa."""
    sent = []

    def narrate(*a, **k):
        sent.append(repr(a[2]))  # logs que o narrador recebe (3o argumento)
        return "Fim."

    enemy = _tough(immunities=["igneo"], resistances={"gelido": "vulnerabilidade"})
    monkeypatch.setenv("RPG_COMBAT_REVEAL_RESIST", "on")
    out = run_node(make_state([enemy], "ataco o goblin"), monkeypatch, narrate=narrate)
    import api

    view = api._combat_block({**make_state([enemy]), **out})
    blob = repr(view) + "".join(sent)
    assert not out["enemies"][0].get("revealed_resistances")
    assert "igneo" not in blob.lower() and "gelido" not in blob.lower()
    assert "Ígneo" not in blob


def test_playtest_invariant_flags_bad_format_and_incapacitated_dead():
    from playtest.invariants import check_conflict_capabilities

    ok = {
        "enemies": [
            {
                "name": "A",
                "status": "incapacitado",
                "revealed_resistances": ["igneo:imune", "legado"],
            }
        ]
    }
    assert check_conflict_capabilities(ok, None, 1) == []
    bad = {
        "enemies": [
            {"name": "B", "status": "incapacitado", "dead": True},
            {"name": "C", "revealed_resistances": ["igneo:talvez"]},
        ]
    }
    ids = {v.check_id for v in check_conflict_capabilities(bad, None, 1)}
    assert ids == {"conflict.incapacitated_dead", "conflict.resistance_format"}
