"""SPEC-285: knobs de letalidade pós-232/275/283."""

from __future__ import annotations

import random

from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct

MURALHA_JOGADOR = "dev_muralha_viva"  # protecao 3, cena (Devoto nível 1)


def _player(**kw):
    p = {
        "id": "player",
        "name": "Herói",
        "is_player": True,
        "class_name": "Devoto do Abismo",
        "virtudes": {"forca": 4, "agilidade": 5, "corpo": 3, "mente": 1, "carisma": 1},
        "entropy": 10,
        "max_entropy": 10,
        "abyss_charge": 0,
        "prepared_cards": [MURALHA_JOGADOR],
        "known_cards": [MURALHA_JOGADOR],
    }
    p.update(kw)
    return orch.ensure_combat_sheet(p, is_player=True)


def _ally():
    return orch.ensure_combat_sheet(
        {
            "id": "npc",
            "name": "Aliada",
            "hp": 10,
            "max_hp": 10,
            "transient": True,
            "virtudes": {"forca": 1, "agilidade": 0, "corpo": 2, "mente": 1, "carisma": 1},
        },
        is_ally=True,
    )


def _enemy(eid="wolf"):
    return orch.ensure_combat_sheet(
        {
            "id": eid,
            "name": "Lobo",
            "type": "Minion",
            "hp": 12,
            "max_hp": 12,
            "virtudes": {"forca": 2, "agilidade": 0, "corpo": 2, "mente": 0, "carisma": 0},
        }
    )


def _world():
    player, ally, wolf = _player(), _ally(), _enemy()
    scene = cs.new_scene()
    for aid in ("player", "npc", "wolf"):
        cs.place(scene, aid)
    cs.freeze(scene)
    actors = {"player": player, "npc": ally, "wolf": wolf}
    sides = {"hero": ["player"], "ally": ["npc"], "enemy": ["wolf"]}
    return scene, actors, sides


def _pass(aid):
    return ct.TurnDeclaration(actor_id=aid, acao=ct.TurnStep(kind="pass"))


def _muralha(target):
    return ct.TurnDeclaration(
        actor_id="player",
        acao=ct.TurnStep(kind="card", card_id=MURALHA_JOGADOR, target_id=target),
    )


def _protection_on(actor):
    return [c for c in actor.get("active_conditions") or [] if c.get("source") == MURALHA_JOGADOR]


def test_player_protection_on_ally_survives_ally_turn_this_round():
    """R3 (pendente da SPEC-283): proteção que o JOGADOR põe num aliado que ainda
    vai agir na rodada ganha +1 turno, como a do inimigo — senão expira no fim
    do turno do aliado, antes de qualquer ataque inimigo da rodada seguinte."""
    scene, actors, sides = _world()
    out = orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={
            "player": _muralha("npc"),
            "npc": _pass("npc"),
            "wolf": _pass("wolf"),
        },
        initiator="heroes",
        rng=random.Random(3),
    )
    assert out["resolved_turns"].index("player") < out["resolved_turns"].index("npc")
    conds = _protection_on(actors["npc"])
    assert conds and conds[0]["stat"] == "protection"


def test_player_protection_on_self_unchanged():
    scene, actors, sides = _world()
    orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={
            "player": _muralha("player"),
            "npc": _pass("npc"),
            "wolf": _pass("wolf"),
        },
        initiator="heroes",
        rng=random.Random(3),
    )
    conds = _protection_on(actors["player"])
    # duração da Carta (1) sem o bônus de aliado: expira no fim do turno do portador
    assert not conds or conds[0]["duration"] <= 1


# --- R4: Controle tático nega exatamente UM turno do alvo ---------------------


def _mystic():
    from agents import bestiary

    actor = bestiary.materialize_enemy_concept(
        {
            "id": "mystic",
            "name": "Místico",
            "description": "teste",
            "categoria": "padrao",
            "arquetipo": "mistico",
        }
    )
    actor["id"] = "mystic"
    actor["virtudes"] = {**actor["virtudes"], "agilidade": 0}
    return orch.ensure_combat_sheet(actor)


def _lost_turns(out):
    return sum(1 for line in out["logs"] if "Herói está atordoado e perde o turno" in line)


def test_tactical_control_denies_exactly_one_target_turn():
    player = _player()
    mystic = _mystic()
    scene = cs.new_scene()
    for aid in ("player", "mystic"):
        cs.place(scene, aid)
    cs.freeze(scene)
    actors = {"player": player, "mystic": mystic}
    sides = {"hero": ["player"], "ally": [], "enemy": ["mystic"]}
    rounds = []
    for seed in range(4):
        rounds.append(
            orch.run_round(
                scene,
                actors,
                sides,
                {"player": player},
                declarations={"player": _pass("player")},
                initiator="heroes",
                rng=random.Random(seed),
            )
        )
    controls = [
        t
        for out in rounds
        for t in out.get("tactics", [])
        if t["action_key"] == "control" and t["ok"]
    ]
    lost = sum(_lost_turns(out) for out in rounds[1:])
    assert controls, "o Místico precisa controlar ao menos uma vez"
    # Cada controle bem-sucedido nega um turno do alvo — não dois.
    controls_before_last = [
        t for out in rounds[:-1] for t in out.get("tactics", []) if t["action_key"] == "control" and t["ok"]
    ]
    assert lost == len(controls_before_last)


# --- R5: nenhuma Carta de inimigo mata sozinha um herói padrão cheio ----------

HEROI_PADRAO_VITALIDADE = 18  # Corpo 3 × 6 (conflito-01): 3 das 5 classes no nível 1


def _card_total_damage(card: dict) -> int:
    """Acerto (`dano_base`) + DoT completo (`dano_base` × `duracao`): é o que
    `_apply_attack_card_effect` aplica numa única Carta que acerta."""
    efeito = card.get("efeito") or {}
    base = int(efeito.get("dano_base") or 0)
    if efeito.get("kind") == "dot":
        return base + base * max(1, int(efeito.get("duracao") or 1))
    return base


def test_no_enemy_card_kills_standard_hero_alone():
    from services import cards

    over = {
        cid: _card_total_damage(card)
        for cid, card in cards.all_cards().items()
        if cid.startswith("bst_") and _card_total_damage(card) >= HEROI_PADRAO_VITALIDADE
    }
    assert over == {}


def test_toque_gelido_rebalanced_from_generator():
    from services import cards

    efeito = cards.get_card("bst_toque_gelido")["efeito"]
    assert efeito == {"kind": "dot", "dano_base": 3, "duracao": 3}
