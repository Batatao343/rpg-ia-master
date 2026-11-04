"""SPEC-382 Etapa 3 (Sol P2-1): casos diretos de `run_round` para o golden de nos.

Cada caso monta cena/atores/lados com os construtores que os testes da 329/330/339/355/373 ja
usam, roda 1-3 rodadas com `rng` fixo e grava (via `Recorder(strict=True)`) o `out` de cada
rodada, o estado final, a sequencia de fases (`spec382_phase_spy`) e a ordem das chaves.
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable

from tests.spec382_node_golden import Recorder


def _orch():
    from services import conflict_orchestrator as orch

    return orch


def _rounds(rec: Recorder, world: tuple, plan: list, *, seed0: int = 20) -> None:
    """Roda `run_round` uma vez por item de `plan` (kwargs ou `fn(bundle) -> kwargs`)."""
    scene, actors, sides, state = world
    bundle = {"scene": scene, "actors": actors, "sides": sides, "state": state}
    orch = _orch()
    for i, item in enumerate(plan):
        kw = dict(item(bundle) if callable(item) else item)
        kw.setdefault("rng", random.Random(seed0 + i))

        def go(b, kw=kw):
            return orch.run_round(b["scene"], b["actors"], b["sides"], b["state"], **kw)

        rec.call(go, bundle, seed=seed0 + i)


def _intent_world(enemies: dict, *, ally_ids=()) -> tuple:
    from tests.test_enemy_intent import _world

    scene, actors, sides = _world(enemies, ally_ids=ally_ids)
    return scene, actors, sides, {"player": actors["player"]}


def _decl(kind: str = "pass", **step) -> dict:
    return {"actor_id": "player", "acao": {"kind": kind, **step}}


# --------------------------------------------------------------------------- casos
def r_off_kill(rec):
    """`off`: dois inimigos + aliada, o fraco cai; terminal, Entropia por morte, fim de rodada."""
    from tests.test_enemy_intent import _enemy

    world = _intent_world({"a": _enemy("a"), "b": _enemy("b")}, ally_ids=("cao",))
    world[1]["b"]["vitalidade"] = 1
    hit = {"declarations": {"player": _decl("attack", target_id="b")}}
    _rounds(rec, world, [hit, hit], seed0=28)  # seed 28: b cai na 1a, a na 2a (fim do conflito)


def r_item_refused(rec):
    """R8 da 227: item recusado (Vitalidade cheia) devolve cedo; nada na cena e tocado."""
    import inventory as inv
    from tests.test_enemy_intent import _enemy

    world = _intent_world({"gob_1": _enemy("gob_1")})
    world[1]["player"]["inventory"] = inv.add_item([], "pocao_cura", 1)
    item = {"declarations": {"player": _decl("item", item_id="pocao_cura")}}
    _rounds(rec, world, [item, {"declarations": {"player": _decl()}}])


def r_intent_on(rec):
    """Presságio `on`: congelado cumprido, atordoado frustrado, 2ª rodada calcula no inicio."""
    from services import enemy_intent as ei
    from tests.test_enemy_intent import _enemy

    rec.mp.setenv("RPG_ENEMY_INTENT", "on")
    world = _intent_world({"lobo": _enemy("lobo"), "urso": _enemy("urso")})
    scene, actors, sides, _st = world
    frozen = ei.forecast_round(scene, actors, sides, random.Random(2))
    actors["urso"]["active_conditions"] = [{"name": "Atordoado", "control": "stun", "duration": 1}]
    first = {"declarations": {"player": _decl("attack", target_id="lobo")}, "pressagios": frozen}
    _rounds(rec, world, [first, {"declarations": {"player": _decl()}}])


def r_intent_shadow(rec):
    """Presságio `shadow`: mede a troca tardia sem mudar o desfecho."""
    from tests.test_enemy_intent import _enemy

    rec.mp.setenv("RPG_ENEMY_INTENT", "shadow")
    world = _intent_world({"lobo": _enemy("lobo"), "urso": _enemy("urso")})
    step = {"declarations": {"player": _decl("attack", target_id="urso")}}
    _rounds(rec, world, [step, step])


def r_taunt_same_round(rec):
    """SPEC-355 R2: Provocação aplicada nesta rodada desvia o presságio congelado e gasta 1."""
    from services import enemy_intent as ei
    from tests.test_spec339_duracao_condicoes import _cena_devoto, _Rng0, _voto

    rec.mp.setenv("RPG_ENEMY_INTENT", "on")
    rec.mp.setattr(ei, "_fork_rng", lambda rng: _Rng0(0))
    actors, scene, sides = _cena_devoto()
    world = (scene, actors, sides, {"player": actors["player"]})

    def first(b):
        frozen = ei.forecast_round(b["scene"], b["actors"], b["sides"], _Rng0(1))
        return {
            "declarations": {"player": _voto()},
            "initiator": "heroes",
            "rng": _Rng0(1),
            "pressagios": frozen,
        }

    def second(b):
        frozen = ei.forecast_round(b["scene"], b["actors"], b["sides"], _Rng0(2))
        return {"declarations": {"player": _decl()}, "rng": _Rng0(2), "pressagios": frozen}

    _rounds(rec, world, [first, second])


def r_taunt_after_acted(rec):
    """SPEC-339 × 329: Provocação posta em quem JÁ agiu (inimigo primeiro, presságio `on`) não
    ganha marcador de pular tick (`taunt_frozen_acted` = `acted` da rodada)."""
    from services import enemy_intent as ei
    from tests.test_spec339_duracao_condicoes import _cena_devoto, _Rng0, _voto

    rec.mp.setenv("RPG_ENEMY_INTENT", "on")
    rec.mp.setattr(ei, "_fork_rng", lambda rng: _Rng0(0))
    actors, scene, sides = _cena_devoto()
    world = (scene, actors, sides, {"player": actors["player"]})

    def rnd(b, n=1, decl=None):
        frozen = ei.forecast_round(b["scene"], b["actors"], b["sides"], _Rng0(n))
        return {
            "declarations": {"player": decl or _voto()},
            "initiator": "enemy",
            "rng": _Rng0(n),
            "pressagios": frozen,
        }

    _rounds(rec, world, [rnd, lambda b: rnd(b, 2, _pass_decl())])


def _pass_decl():
    from services import conflict_turn as ct

    return ct.TurnDeclaration(actor_id="player")


def _boss_world():
    from agents.bestiary import load_bestiary
    from services import conflict_scene as cs
    from tests.test_spec373_acao_extra import BOSS, _player

    orch = _orch()
    entry = json.loads(json.dumps(load_bestiary()[BOSS]))
    boss = orch.ensure_combat_sheet({**entry, "id": f"{BOSS}_1"})
    scene = cs.new_scene()
    for i in ("player", boss["id"]):
        cs.place(scene, i)
    cs.freeze(scene)
    actors = {"player": _player(), boss["id"]: boss}
    sides = {"hero": ["player"], "ally": [], "enemy": [boss["id"]]}
    return scene, actors, sides, {"player": actors["player"]}


def r_boss_extra_decks(rec):
    """SPEC-295/332/355/373: chefe com ação extra, fases, promessas e prenúncio (decks `on`)."""
    from services import enemy_decks as edk

    rec.mp.setenv("RPG_ENEMY_DECKS", "on")
    edk.reload()
    try:
        _rounds(rec, _boss_world(), [{}, {}, {}], seed0=2)
    finally:
        rec.mp.delenv("RPG_ENEMY_DECKS")
        edk.reload()


def r_boss_extra_intent(rec):
    """Presságio `on` com chefe de 2 ações: um presságio por ação, extra no fim da rodada."""
    from services import enemy_intent as ei
    from tests.test_enemy_intent import _enemy

    rec.mp.setenv("RPG_ENEMY_INTENT", "on")
    world = _intent_world({"chefe": _enemy("chefe", acoes_por_rodada=2)})
    frozen = ei.forecast_round(world[0], world[1], world[2], random.Random(4))
    _rounds(rec, world, [{"declarations": {"player": _decl()}, "pressagios": frozen}], seed0=4)


def _interromper(rec, card: dict, initiator: str, *, boss_kw=None, hp=None) -> None:
    from tests import test_card_effects_review_spec330 as rv

    rec.mp.setenv("RPG_ENEMY_INTENT", "on")
    rv._card(rec.mp, card["id"], **{k: v for k, v in card.items() if k != "id"})
    player, e = rv._hero([card["id"]]), rv._boss(**(boss_kw or {}))
    if hp is not None:
        player["vitalidade"] = player["max_vitalidade"] = 200
        e["vitalidade"] = hp
    scene = rv._scene("player", "e")
    scene["gatilhos_armados"] = [rv._armed("player", "ao_pressagio_frustrado")]
    world = (scene, {"player": player, "e": e}, {"hero": ["player"], "enemy": ["e"]})
    kw = {
        "declarations": {"player": rv._play_decl(card["id"])},
        "pressagios": {"e": [rv._intent(0), rv._intent(1)]},
        "initiator": initiator,
        "rng": random.Random(4),
    }
    _rounds(rec, (*world, {"player": player}), [kw])


def r_interromper_stun(rec):
    """SPEC-330 Interromper: atordoar antes da 1ª ação frustra uma vez (`interrompido_por`)."""
    stun = {
        "id": "rv_stun",
        "efeitos": [{"kind": "aplicar_condicao", "condicao": "atordoado", "duracao": 1}],
        "palavras_chave": {"interromper": True},
    }
    _interromper(rec, stun, "heroes")


def r_interromper_queda(rec):
    """SPEC-330: queda real depois da 1ª ação do chefe frustra a ação extra (`incapaz`)."""
    golpe = {
        "id": "rv_golpe",
        "efeitos": [{"kind": "dano", "dano_base": 60, "categoria_arma": "pesada"}],
        "palavras_chave": {"interromper": True},
    }
    wounds = {"ferimento_espacos": {"leve": 1, "grave": 1, "critico": 1}}
    _interromper(rec, golpe, "enemy", boss_kw=wounds, hp=0)


def r_deck_on(rec):
    """Baralho `on`: várias jogadas da mão, Fôlego, pilhas, `end_round` (Guardar/Vazão)."""
    from services import conflict_turn as ct
    from tests.test_round_multi_play import _card, _plays, _setup

    rec.mp.setenv("RPG_CARD_DECK", "on")
    world = _setup()
    two = _plays(_card("bas_san_golpe"), _card("bas_san_guarda", "player"))
    out_of_hand = _plays(_card("san_corte_troca"))
    plan = [
        {"declarations": {"player": two}},
        {"declarations": {"player": out_of_hand}},
        {"declarations": {"player": ct.TurnDeclaration(actor_id="player")}},
    ]
    _rounds(rec, world, plan, seed0=5)


def r_scene_cards(rec):
    """SPEC-331: Cartas de Cena (início/fim de rodada) e Relógio do Abismo, 3 rodadas."""
    from tests.test_scene_cards import _actor, _scene

    rec.mp.setenv("RPG_SCENE_CARDS", "on")
    player, e = _actor("player"), _actor("e")
    scene = _scene(cartas=["nevoa_cinza_do_ermo", "sinos_de_nova_arcadia", "telhado_que_cede"])
    world = (scene, {"player": player, "e": e}, {"hero": ["player"], "enemy": ["e"]}, {})
    world[3]["player"] = player
    step = {"declarations": {"player": {"actor_id": "player"}}}
    _rounds(rec, world, [step, step, step], seed0=2)


def c_status_cards(rec):
    """Nó de combate com Baralho `on` e Cartas de status (SPEC-333): Sussurro na abertura e
    Ferimento novo no fim da rodada deixam `status_logs` não vazio (Sol P2-1: ordem de
    `_combat_close_round_meta` × `_combat_close_round_log`)."""
    from tests.spec325_helpers import lacaio
    from tests.spec382_node_cases import _cstate, _seq

    rec.mp.setenv("RPG_CARD_REWARDS", "on")
    brute = lacaio(
        "e1",
        "Ogro",
        hp=60,
        max_hp=60,
        vitalidade=60,
        max_vitalidade=60,
        attacks=[{"name": "Clava", "bonus": 30, "damage": "3d6"}],
        attack_mod=30,
        virtudes={"forca": 6, "agilidade": 2, "corpo": 6, "mente": 0, "carisma": 0},
    )
    st = _cstate([brute], player_over={"vitalidade": 8, "abyss_charge": 5})
    st["combat"] = {}
    st["combat_declaration"] = None
    sussurro = {"actor_id": "player", "jogadas": [_play("sus_sussurro_abismo", "e1")]}
    steps = [
        ("COMBAT START. Um ogro!", None),  # abre o tabuleiro: nenhuma rodada ainda
        ("jogo o sussurro", sussurro),
        ("ataco", {"actor_id": "player", "acao": {"kind": "attack", "target_id": "e1"}}),
        *[("passo", {"actor_id": "player", "acao": {"kind": "pass"}})] * 3,
    ]
    _seq(rec, st, steps, deck="on", seed0=3)


def _play(card_id: str, target: str) -> dict:
    return {"kind": "card", "card_id": card_id, "target_id": target}


ROUND_CASES: dict[str, Callable] = {
    "combat_status_cards_on": c_status_cards,
    "round_off_kill": r_off_kill,
    "round_item_refused": r_item_refused,
    "round_intent_on": r_intent_on,
    "round_intent_shadow": r_intent_shadow,
    "round_taunt_same_round": r_taunt_same_round,
    "round_taunt_after_acted": r_taunt_after_acted,
    "round_boss_extra_decks": r_boss_extra_decks,
    "round_boss_extra_intent": r_boss_extra_intent,
    "round_interromper_stun": r_interromper_stun,
    "round_interromper_queda": r_interromper_queda,
    "round_deck_on": r_deck_on,
    "round_scene_cards": r_scene_cards,
}
