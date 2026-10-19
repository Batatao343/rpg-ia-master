"""SPEC-275: impasse eterno — inimigo oculto com Carta de suporte recusada."""
from __future__ import annotations

import copy
import random

from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct

SUPPORT_A = "bst_carregar_ruina"   # reposicionar (suporte)
SUPPORT_B = "bst_coro_colmeia"     # buff_acerto (suporte)


def _player(**kw):
    p = {"id": "player", "name": "Herói", "is_player": True, "class_name": "Devoto do Abismo",
         "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
         "entropy": 10, "max_entropy": 10, "abyss_charge": 0}
    p.update(kw)
    return orch.ensure_combat_sheet(p, is_player=True)


def _enemy(eid="viuva", cards=(SUPPORT_A,), **kw):
    e = {"id": eid, "name": eid, "type": "Minion", "hp": 12, "max_hp": 12, "ac": 11,
         "entropy": 10, "cartas": list(cards),
         "attributes": {"str": 10, "dex": 12, "con": 10, "int": 8, "wis": 8, "cha": 6}}
    e.update(kw)
    return orch.ensure_combat_sheet(e)


def _world(enemy_ids=("viuva",), hidden=True, **enemy_kw):
    player = _player()
    enemies = {i: _enemy(i, **enemy_kw) for i in enemy_ids}
    scene = cs.new_scene()
    for i in ("player", *enemy_ids):
        cs.place(scene, i)
    cs.freeze(scene)
    if hidden:
        for i in enemy_ids:
            cs.hide(scene, i, source="cobertura", observers=["player"], spend=False)
    actors = {"player": player, **enemies}
    sides = {"hero": ["player"], "enemy": list(enemy_ids)}
    return scene, actors, sides


def _pass_decl():
    return {"player": ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass"))}


def test_enemy_offensive_card_never_support():
    _, actors, _ = _world()
    enemy = actors["viuva"]
    enemy["cartas"] = [SUPPORT_A, SUPPORT_B]
    assert orch._enemy_offensive_card(enemy) is None


def test_enemy_declaration_falls_to_basic_attack_without_offensive_card():
    scene, actors, sides = _world()
    actors["viuva"]["cartas"] = [SUPPORT_A, SUPPORT_B]
    decl = orch.enemy_declaration(scene, "viuva", actors, sides, rng=random.Random(1))
    assert decl.acao.kind in ("attack", "tactic")
    assert decl.acao.card_id is None


def test_enemy_refused_declaration_falls_back_once():
    scene, actors, sides = _world(hidden=False)
    step = ct.TurnStep(kind="card", card_id=SUPPORT_A, target_id="player")
    decl = ct.TurnDeclaration(actor_id="viuva", acao=step)
    out = orch.run_round(scene, actors, sides, {"player": actors["player"]},
                         declarations={"player": _pass_decl()["player"], "viuva": decl},
                         rng=random.Random(3))
    assert any(a["actor_id"] == "viuva" for a in out["attacks"])
    assert any("enemy_declaration_fallback" in line or "fallback" in line.lower()
               for line in out["logs"])
    # Entropia/frequência da Carta recusada não foram cobradas
    assert actors["viuva"]["entropy"] == 10


def test_hidden_ambusher_attacks_visible_player():
    scene, actors, sides = _world(("viuva", "mosq"), cards=(SUPPORT_A, SUPPORT_B))
    rng = random.Random(5)
    attacks = []
    for _ in range(3):
        out = orch.run_round(scene, actors, sides, {"player": actors["player"]},
                             declarations=_pass_decl(), rng=rng)
        attacks += out["attacks"]
    assert any(a["target_id"] == "player" for a in attacks)


def test_stalemate_guard_breaks_after_k_rounds():
    scene, actors, sides = _world(("viuva",))
    actors["viuva"]["tactical_archetype"] = "covarde_oportunista"
    # nada muda mecanicamente: o guard é chamado direto, K rodadas idênticas
    for _ in range(orch.STALEMATE_ROUNDS):
        assert orch._stalemate_guard(scene, actors, sides) == []
    events = orch._stalemate_guard(scene, actors, sides)
    assert events and "conflict_stalemate_broken" in events[0]
    assert actors["viuva"].get("fled") is True


def test_stalemate_guard_reveals_non_cowards_and_forces_attack():
    scene, actors, sides = _world(("brute",))
    assert cs.is_hidden_from(scene, "brute", "player")
    for _ in range(orch.STALEMATE_ROUNDS + 1):
        orch._stalemate_guard(scene, actors, sides)
    assert not cs.is_hidden_from(scene, "brute", "player")
    assert actors["brute"].get("fled") is not True
    assert actors["brute"].get("_forced_attack") is True


def test_stalemate_counter_resets_on_damage():
    scene, actors, sides = _world(("brute",))
    for _ in range(orch.STALEMATE_ROUNDS - 1):
        orch._stalemate_guard(scene, actors, sides)
    actors["player"]["vitalidade"] -= 1
    assert orch._stalemate_guard(scene, actors, sides) == []
    assert scene["stalemate"]["rounds"] == 0


def test_player_refusal_still_free():
    scene, actors, sides = _world(("viuva",))
    before = actors["player"]["entropy"]
    out = {"logs": [], "attacks": [], "cards_used": []}
    step = ct.TurnStep(kind="attack", target_id="viuva")
    ct._resolve_attack_step(scene, actors["player"], "player", actors, step, out,
                            state={"player": actors["player"]}, rng=random.Random(2),
                            sides=sides)
    assert out["attacks"] == []
    assert any("sem posição conhecida" in line for line in out["logs"])
    assert actors["player"]["entropy"] == before


def test_old_scene_without_stalemate_key_loads():
    scene, actors, sides = _world(("brute",))
    scene.pop("stalemate", None)
    assert orch._stalemate_guard(scene, actors, sides) == []


def test_enemy_support_card_targets_own_side():
    scene, actors, sides = _world(hidden=False)
    actors["viuva"]["cartas"] = ["bst_mimetismo_morto"]
    decl = orch.enemy_declaration(scene, "viuva", actors, sides, rng=random.Random(1))
    if decl.acao.kind == "card":
        assert decl.acao.target_id == "viuva"
