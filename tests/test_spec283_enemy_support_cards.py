"""SPEC-283: IA inimiga usa Cartas de suporte do bestiário no próprio lado."""

from __future__ import annotations

import copy
import itertools
import random

from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct

MURALHA = "bst_postura_muralha"  # protecao 6, cena, custo 0
NOITE = "bst_noite_skallgard"  # buff_dano 5, cena, custo 2
CORO = "bst_coro_colmeia"  # buff_acerto 4, cena, custo 2
RUINA = "bst_carregar_ruina"  # reposicionar, cena, custo 1
POEIRA = "bst_poeira_pradaria"  # reposicionar, turno, custo 0
ROUBAR = "bst_roubar_calor"  # buff_defesa, cena, custo 1
SUPPORT_CARDS = (MURALHA, NOITE, CORO, RUINA, POEIRA, ROUBAR)


def _player(**kw):
    p = {
        "id": "player",
        "name": "Herói",
        "is_player": True,
        "class_name": "Devoto do Abismo",
        "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
        "entropy": 10,
        "max_entropy": 10,
        "abyss_charge": 0,
    }
    p.update(kw)
    return orch.ensure_combat_sheet(p, is_player=True)


def _enemy(eid, cards=(), name=None, **kw):
    e = {
        "id": eid,
        "name": name or eid.capitalize(),
        "type": "Minion",
        "hp": 12,
        "max_hp": 12,
        "ac": 11,
        "entropy": 10,
        "cartas": list(cards),
        "attributes": {"str": 10, "dex": 12, "con": 10, "int": 8, "wis": 8, "cha": 6},
    }
    e.update(kw)
    return orch.ensure_combat_sheet(e)


def _world(enemies: dict[str, dict], *, ally_ids=()):
    player = _player()
    scene = cs.new_scene()
    ids = ["player", *ally_ids, *enemies]
    for i in ids:
        cs.place(scene, i)
    cs.freeze(scene)
    actors = {"player": player, **enemies}
    for aid in ally_ids:
        actors[aid] = orch.ensure_combat_sheet(
            {"id": aid, "name": "Aliada", "hp": 10, "max_hp": 10, "transient": True},
            is_ally=True,
        )
    sides = {"hero": ["player"], "ally": list(ally_ids), "enemy": list(enemies)}
    return scene, actors, sides


# Perfil curado do bestiário: prioridades sem ``action_key`` — o arquétipo
# materializa a ação (``normalize_runtime_profile``).
CURATED = {"priorities": [{"trigger": "sempre", "tipo": "obrigatorio", "action_hint": "Age."}]}


def _wound(actor, ratio=0.4):
    actor["vitalidade"] = max(1, int(actor["max_vitalidade"] * ratio))


def _decl(scene, eid, actors, sides):
    return orch.enemy_declaration(scene, eid, actors, sides, rng=random.Random(1))


def _pass():
    return ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass"))


# --- R2.1 defensiva -----------------------------------------------------------


def test_defensive_card_protects_ally_in_danger():
    scene, actors, sides = _world({"guard": _enemy("guard", (MURALHA,)), "hurt": _enemy("hurt")})
    _wound(actors["hurt"])
    decl = _decl(scene, "guard", actors, sides)
    assert decl.acao.kind == "card" and decl.acao.card_id == MURALHA
    assert decl.acao.target_id == "hurt"
    out = orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": _pass(), "guard": decl},
        rng=random.Random(2),
    )
    # A proteção sobrevive ao turno do próprio aliado nesta rodada e cobre os
    # ataques do lado oposto na rodada seguinte.
    conds = [c for c in actors["hurt"]["active_conditions"] if c.get("source") == MURALHA]
    assert conds and conds[0]["stat"] == "protection" and conds[0]["delta"] == 6
    assert out["enemy_support_cards"][0]["target_id"] == "hurt"
    assert "hurt" in out["resolved_turns"]


def test_defensive_card_on_self_when_badly_wounded():
    scene, actors, sides = _world({"guard": _enemy("guard", (MURALHA,))})
    _wound(actors["guard"], 0.3)
    decl = _decl(scene, "guard", actors, sides)
    assert (decl.acao.card_id, decl.acao.target_id) == (MURALHA, "guard")


def test_defensive_card_not_used_when_healthy():
    scene, actors, sides = _world({"guard": _enemy("guard", (MURALHA,))})
    decl = _decl(scene, "guard", actors, sides)
    assert decl.acao.card_id is None
    assert decl.acao.target_id == "player"


# --- R2.2 ofensiva -------------------------------------------------------------


def test_offensive_buff_on_self_before_attack():
    scene, actors, sides = _world({"wolf": _enemy("wolf", (NOITE,))})
    decl = _decl(scene, "wolf", actors, sides)
    assert (decl.acao.kind, decl.acao.card_id, decl.acao.target_id) == ("card", NOITE, "wolf")
    orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": _pass(), "wolf": decl},
        rng=random.Random(2),
    )
    assert actors["wolf"]["entropy"] == 8  # custo 2 cobrado
    conds = [c for c in actors["wolf"]["active_conditions"] if c.get("source") == NOITE]
    assert conds and conds[0]["stat"] == "damage" and conds[0]["delta"] == 5
    # Na rodada seguinte o reforço já está ativo: ataca (sem repetir a Carta).
    nxt = _decl(scene, "wolf", actors, sides)
    assert nxt.acao.card_id is None and nxt.acao.target_id == "player"


def test_offensive_buff_on_available_ally_for_support_action():
    leader = _enemy(
        "leader", (CORO,), arquetipo="lider_matilha", tactical_profile=copy.deepcopy(CURATED)
    )
    scene, actors, sides = _world({"leader": leader, "pup": _enemy("pup")})
    decl = _decl(scene, "leader", actors, sides)
    assert (decl.acao.card_id, decl.acao.target_id) == (CORO, "pup")


# --- R2.3 movimento ------------------------------------------------------------


def test_reposition_closes_distance_only_when_far():
    scene, actors, sides = _world({"rider": _enemy("rider", (RUINA,))})
    assert _decl(scene, "rider", actors, sides).acao.card_id is None  # proximo
    scene["positions"]["rider"]["distance_state"] = "distante"
    decl = _decl(scene, "rider", actors, sides)
    assert (decl.acao.card_id, decl.acao.target_id, decl.acao.direction) == (
        RUINA,
        "rider",
        "aproximar",
    )
    orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": _pass(), "rider": decl},
        rng=random.Random(2),
    )
    assert scene["positions"]["rider"]["distance_state"] == "proximo"


# --- R4 lado / R5 economia / R2.4 sem repetição --------------------------------


def test_support_card_never_targets_player_side():
    for card, wounded_self, wounded_peer, far, archetype in itertools.product(
        SUPPORT_CARDS, (False, True), (False, True), (False, True), (None, "lider_matilha")
    ):
        kw = (
            {"arquetipo": archetype, "tactical_profile": copy.deepcopy(CURATED)}
            if archetype
            else {}
        )
        scene, actors, sides = _world(
            {"e1": _enemy("e1", (card,), **kw), "e2": _enemy("e2")}, ally_ids=("npc",)
        )
        _wound(actors["player"], 0.3)
        _wound(actors["npc"], 0.3)
        if wounded_self:
            _wound(actors["e1"], 0.3)
        if wounded_peer:
            _wound(actors["e2"], 0.3)
        if far:
            scene["positions"]["e1"]["distance_state"] = "distante"
        decl = _decl(scene, "e1", actors, sides)
        if decl.acao.kind == "card":
            assert decl.acao.target_id in {"e1", "e2"}, (card, decl)


def test_support_card_respects_frequency_and_entropy():
    scene, actors, sides = _world({"wolf": _enemy("wolf", (NOITE,))})
    actors["wolf"]["entropy"] = 1  # custo 2
    assert _decl(scene, "wolf", actors, sides).acao.card_id is None
    actors["wolf"]["entropy"] = 10
    actors["wolf"]["enemy_card_usage"] = {NOITE: {"used_this_scene": 1, "used_this_turn": 1}}
    decl = _decl(scene, "wolf", actors, sides)
    assert decl.acao.card_id is None and decl.acao.kind == "attack"


def test_no_repeat_while_condition_active():
    scene, actors, sides = _world({"bug": _enemy("bug", (POEIRA, NOITE))})
    actors["bug"]["active_conditions"].append(
        {
            "name": "Noite no Sangue",
            "dot": 0,
            "duration": 1,
            "source": NOITE,
            "stat": "damage",
            "delta": 5,
        }
    )
    assert _decl(scene, "bug", actors, sides).acao.card_id is None


def test_forced_attack_skips_support_cards():
    scene, actors, sides = _world({"wolf": _enemy("wolf", (NOITE,))})
    actors["wolf"]["_forced_attack"] = True
    decl = _decl(scene, "wolf", actors, sides)
    assert decl.acao.kind == "attack" and decl.acao.card_id is None


def test_stabilize_precedes_support_card():
    medic = _enemy("medic", (MURALHA,))
    medic["tactical_profile"] = {
        "priorities": [
            {"trigger": "aliado_terminal", "action_key": "stabilize"},
            {"trigger": "sempre", "action_key": "attack"},
        ]
    }
    scene, actors, sides = _world({"medic": medic, "down": _enemy("down")})
    actors["down"]["estado_terminal"] = True
    actors["down"]["vitalidade"] = 0
    decl = _decl(scene, "medic", actors, sides)
    assert decl.acao.kind == "tactic" and decl.acao.maneuver == "stabilize"


# --- R6 reação / R7 narração ---------------------------------------------------


def test_support_card_does_not_open_reaction_window(monkeypatch):
    scene, actors, sides = _world({"wolf": _enemy("wolf", (NOITE,))})
    opened = []
    monkeypatch.setattr(orch, "_open_reaction_window", lambda *a, **k: opened.append(a))
    decl = _decl(scene, "wolf", actors, sides)
    out = {"logs": [], "attacks": [], "cards_used": [], "deaths": [], "terminal": []}
    orch._resolve_actor_turn(
        scene, actors["wolf"], "wolf", actors, sides, decl, None, out, random.Random(1)
    )
    assert opened == []
    assert out["cards_used"] and out["cards_used"][0]["card_id"] == NOITE


def test_support_card_log_is_ptbr_without_ids():
    enemy = _enemy("mon_lobo_1", (RUINA,), name="Lobo da Aurora")
    scene, actors, sides = _world({"mon_lobo_1": enemy})
    scene["positions"]["mon_lobo_1"]["distance_state"] = "distante"
    out = orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": _pass()},
        rng=random.Random(4),
    )
    ev = out["enemy_support_cards"]
    assert ev == [
        {
            "event": "enemy_support_card",
            "actor_id": "mon_lobo_1",
            "card_id": RUINA,
            "target_id": "mon_lobo_1",
            "kind": "reposicionar",
        }
    ]
    prose = "\n".join(out["logs"])
    assert "Lobo da Aurora usa Carregar pela Ruína" in prose
    assert "mon_lobo_1" not in prose and "->" not in prose
    assert "enemy_support_card" not in prose


def test_choice_is_deterministic():
    leader = _enemy(
        "leader",
        (CORO, MURALHA, NOITE),
        arquetipo="lider_matilha",
        tactical_profile=copy.deepcopy(CURATED),
    )
    scene, actors, sides = _world({"leader": leader, "pup": _enemy("pup")})
    _wound(actors["pup"])
    snap = copy.deepcopy((scene, actors))
    a = _decl(scene, "leader", actors, sides)
    b = _decl(*copy.deepcopy(snap[:1]), "leader", copy.deepcopy(snap[1]), sides)
    assert a.model_dump() == b.model_dump()
    assert (a.acao.card_id, a.acao.target_id) == (MURALHA, "pup")


# --- revisão independente (2026-10-19) -----------------------------------------


def test_silenced_enemy_skips_support_and_attacks():
    scene, actors, sides = _world({"wolf": _enemy("wolf", (NOITE,))})
    actors["wolf"]["active_conditions"].append(
        {"name": "Silêncio", "dot": 0, "duration": 2, "control": "silence"}
    )
    decl = _decl(scene, "wolf", actors, sides)
    assert decl.acao.kind == "attack" and decl.acao.card_id is None
    assert decl.acao.target_id == "player"


class _AlwaysLow:
    def random(self):
        return 0.0


def test_taunted_enemy_attacks_taunt_source_instead_of_buffing():
    scene, actors, sides = _world({"wolf": _enemy("wolf", (NOITE,))})
    actors["wolf"]["active_conditions"].append(
        {
            "name": "Provocação",
            "dot": 0,
            "duration": 2,
            "control": "taunt",
            "source_actor_id": "player",
        }
    )
    decl = orch.enemy_declaration(scene, "wolf", actors, sides, rng=_AlwaysLow())
    assert decl.acao.kind == "attack" and decl.acao.card_id is None
    assert decl.acao.target_id == "player"


def test_player_side_actor_never_uses_bestiary_support_cards():
    scene, actors, sides = _world({"wolf": _enemy("wolf")}, ally_ids=("npc",))
    actors["npc"]["cartas"] = [NOITE]
    actors["npc"]["entropy"] = 10
    decl = _decl(scene, "npc", actors, sides)
    assert decl.acao.card_id is None


def test_player_own_side_support_card_is_not_a_declared_attack():
    _, _, sides = _world({"wolf": _enemy("wolf")}, ally_ids=("npc",))
    for target in ("player", "npc"):
        step = ct.TurnStep(kind="card", card_id=MURALHA, target_id=target)
        assert orch._own_side_support(step, "player", sides) is True
    hostile = ct.TurnStep(kind="card", card_id=MURALHA, target_id="wolf")
    assert orch._own_side_support(hostile, "player", sides) is False
    attack = ct.TurnStep(kind="card", card_id="bst_golpe_sombras", target_id="wolf")
    assert orch._own_side_support(attack, "player", sides) is False
