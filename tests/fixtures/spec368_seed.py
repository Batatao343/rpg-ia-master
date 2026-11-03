"""SPEC-368 R13 (P1-1) - `seed_save(item, ...)`: grava um save `legacy` REAL pronto para cada cena do §6.

O jogo e criado e o conflito aberto pelo caminho real da API (MockLLM, sem rede, cartas `on`); depois a
receita do item troca inimigos/mao/Folego/espolio no estado salvo e regrava com `persistence.save_game_state`.
O coordenador sobe a API `legacy` apontando para a mesma pasta de saves e abre `/game/state?game_id=...`:
a cena ja esta la (round 0, mao distribuida), sem depender de sorte de LLM.

    from tests.fixtures.spec368_seed import seed_save
    gid = seed_save(3, variant="rachadura")            # grava em ./saves (padrao)
    gid = seed_save(6, variant="espolio", saves_dir="saves")

Itens 8-11 (draft.py, modo `off`, router esgotado, retrato/concorrencia) NAO tem save: o roteiro executavel
esta no §9 da SPEC-368.
"""

from __future__ import annotations

import contextlib
import copy
from typing import Any

from tests.fixtures.spec368_scenarios import CARDS_ON, env

# item -> variantes aceitas ("" = padrao)
ITEMS: dict[int, tuple[str, ...]] = {
    1: ("", "rollback"),
    2: ("",),
    3: ("", "rachadura"),
    4: ("",),
    5: ("", "chefe", "nova"),
    6: ("", "espolio"),
    7: ("", "medico"),
    12: ("",),
    13: ("", "leitura", "armadura", "renegado", "reacao"),
    14: ("",),
}
_CLASS = {
    (3, "rachadura"): "Corruptor",
    (7, ""): "Corruptor",
    (7, "medico"): "Médico de Campo",
    (13, ""): "Devoto do Abismo",
    (13, "reacao"): "Devoto do Abismo",
    (13, "leitura"): "Arcanista Cinzento",
    (13, "armadura"): "Corruptor",
    (5, ""): "Devoto do Abismo",
    (5, "chefe"): "Devoto do Abismo",
}


@contextlib.contextmanager
def _legacy(saves_dir: str | None):
    import persistence

    patch = {
        "RPG_RUNTIME_PROFILE": "legacy",
        "RPG_FORCE_MOCK": "1",
        "RPG_RATE_LIMIT": "0",
        **CARDS_ON,
    }
    with env(patch):
        old = persistence.SAVES_DIR
        if saves_dir:
            persistence.SAVES_DIR = saves_dir
        try:
            yield
        finally:
            persistence.SAVES_DIR = old


def _new_game(client, class_name: str, hero: str) -> str:
    r = client.post(
        "/game/new",
        json={
            "name": hero,
            "race": "Humano",
            "class_name": class_name,
            "region": "Nova Arcádia",
            "level": 1,
            "backstory": "",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["game_id"]


def _open_combat(client, gid: str) -> None:
    r = client.post("/game/action", json={"game_id": gid, "input_text": "Ataco o goblin"})
    assert r.status_code == 200, r.text


def _load(gid: str) -> dict:
    import persistence

    state = persistence.load_game_state(persistence.save_path(gid))
    assert state, f"save {gid} nao encontrado"
    return state


def _force_hand(piles: dict, hand: list[str]) -> None:
    """Mao forcada sem encolher o baralho: tira 1 copia por Carta de mao+compra e devolve o resto a compra."""
    pool = list(piles["mao"]) + list(piles["compra"])
    for cid in hand:
        if cid in pool:
            pool.remove(cid)
    piles["mao"] = list(hand)
    piles["compra"] = pool


def _reseed(state, creature_id, n=1, *, hand=None, folego=None, enemy_vitality=None, seed=7):
    """Troca o elenco do conflito ABERTO pelo caminho real: instancias do spawn, cena, manifesto, pilhas e Pressagio."""
    import random

    from agents.bestiary import template_by_id
    from agents.combat import _instances
    from services import card_piles, enemy_decks, enemy_intent
    from services import conflict_scene as cs
    from services import encounter_manifest as em

    meta = state["combat"]
    scene = meta["scene"]
    old_ids = [e["id"] for e in state["enemies"]]
    ref = copy.deepcopy((scene.get("positions") or {}).get(old_ids[0]) or {})
    zone = ref.get("zone_id") or "z0"
    template = template_by_id(creature_id, encounter_level=int(meta.get("encounter_level", 1) or 1))
    assert template, creature_id
    enemies = _instances(template, n, {}, seed)
    if enemy_decks.mode() != "off":
        for e in enemies:
            enemy_decks.apply_deck(e, seed)
    if enemy_vitality is not None:
        for e in enemies:
            e["vitalidade"] = enemy_vitality
    for oid in old_ids:
        (scene.get("positions") or {}).pop(oid, None)
    scene["enemies"] = [
        e for e in (scene.get("enemies") or []) if str(e.get("id", e)) not in old_ids
    ]
    for e in enemies:
        cs.place(scene, e["id"], zone_id=zone, distance_state=ref.get("distance_state", "proximo"))
    cs.freeze(scene)
    state["enemies"] = enemies
    state["combat_target"] = enemies[0].get("name", "Inimigo")
    meta["encounter"] = em.build_manifest(
        enemies,
        source="bestiary",
        origin="player_provoked",
        encounter_id=str(
            (meta.get("encounter") or {}).get("encounter_id") or f"{state['game_id']}:0:1"
        ),
        target_ref=enemies[0].get("name", ""),
        scene=scene,
    )
    player = state["player"]
    piles = card_piles.start_piles(player, seed)
    if hand is not None:
        _force_hand(piles, hand)
    if folego is not None:
        piles["folego"] = folego
    meta["pilhas"] = piles
    actors = {"player": player, **{e["id"]: e for e in enemies}}
    sides = {"hero": ["player"], "ally": [], "enemy": [e["id"] for e in enemies]}
    forecast = enemy_intent.forecast_round(scene, actors, sides, random.Random(seed))
    meta["pressagios"] = forecast
    meta["pressagios_publicos"] = enemy_intent.public_round(
        forecast, actors, cs.tactical_round(scene) + 1
    )


def _known(state: dict, *ids: str) -> None:
    p = state["player"]
    for cid in ids:
        if cid not in p.setdefault("known_cards", []):
            p["known_cards"].append(cid)


def _recipe(item: int, variant: str, state: dict) -> None:
    from services import card_piles, card_rewards
    from services import enemy_decks as edk

    g = "bas_san_golpe"
    if item == 1 and variant == "rollback":
        card_piles.activate_deck(state["player"])
        return
    if item == 1:
        _reseed(state, "enemy_goblin", 1, hand=[g, g, "bas_san_guarda"], folego=1)
    elif item == 2:
        _reseed(state, "enemy_goblin", 1)
        for e in state["enemies"]:
            e["revealed_cards"] = [
                c["id"] if isinstance(c, dict) else c for c in e.get("cartas") or []
            ]
    elif item == 3 and variant == "rachadura":
        _known(state, "cor1_ino_junta_emperrada")
        _reseed(state, "enemy_goblin", 1, hand=["cor1_ino_junta_emperrada", "bas_cor_golpe"])
    elif item == 3:
        _known(state, "san1_exp_segundo_ato")
        _reseed(state, "enemy_goblin", 1, hand=["san1_exp_segundo_ato", g])
    elif item == 4:
        _reseed(state, "enemy_goblin", 2)
        scene = state["combat"]["scene"]
        scene["npcs"] = [{"id": "escoltado", "name": "Escoltado"}]
        scene["objetivo"] = {"tipo": "proteger", "alvo": "escoltado"}
    elif item == 5:
        cid = {
            "": "enemy_soldado_legiao_ferro",
            "chefe": "enemy_boss_valerius",
            "nova": "mon_costurado_de_lentes",
        }[variant]
        _reseed(state, cid, 2 if variant == "" else 1)
    elif item == 6 and variant == "espolio":
        state["combat"] = {"active": False, "phase": "ended", "round": 0}
        _reseed_for_reward(state, edk)
        card_rewards.on_long_rest(state["player"])
    elif item == 6:
        _reseed(state, "enemy_degolador_mao_sombria", 2, hand=["sts_dor_surda", g])
    elif item == 7:
        _reseed(state, "enemy_goblin", 2)
    elif item == 12:
        _reseed(state, "enemy_goblin", 1, hand=[g, "bas_san_guarda"], enemy_vitality=1)
    elif item == 13:
        spec = {
            "": ("enemy_goblin", 2, ["bas_dev_voto", "bas_dev_golpe"], ()),
            "leitura": (
                "enemy_goblin",
                1,
                ["arc1_cal_leitura", "bas_arc_golpe"],
                ("arc1_cal_leitura",),
            ),
            "armadura": (
                "enemy_goblin",
                1,
                ["cor_ino_fadiga", "bas_cor_golpe"],
                ("cor_ino_fadiga",),
            ),
            "renegado": ("enemy_renegado_ermo", 1, None, ()),
            "reacao": ("enemy_goblin", 1, ["dev_encaixe", "bas_dev_golpe"], ()),
        }[variant]
        _known(state, *spec[3])
        _reseed(
            state, spec[0], spec[1], hand=spec[2], enemy_vitality=1 if variant == "reacao" else None
        )
    elif item == 14:
        state.setdefault("quests", []).append(
            {
                "id": "q368",
                "title": "Caça",
                "status": "active",
                "created_turn": 1,
                "location_id": "brekmar",
                "reward_gold_planned": 25,
                "reward_hint": "justa · uma técnica",
                "reward_card_planned": True,
                "reward_card_label": "justa",
                "progress_log": [
                    {"kind": "location_reached", "turn": 1},
                    {"kind": "investigation", "turn": 2},
                ],
            }
        )


def _reseed_for_reward(state: dict, edk) -> None:
    """Espolio deterministico: Mao Sombria derrotada, semente que oferece Carta da facção."""
    from agents.bestiary import template_by_id
    from agents.combat import _instances
    from services import card_rewards

    enemies = _instances(template_by_id("enemy_degolador_mao_sombria", encounter_level=1), 2, {}, 7)
    for e in enemies:
        edk.apply_deck(e, 7)
        e["dead"] = True
        e["status"] = "morto"
    state["enemies"] = enemies
    player = state["player"]
    for seed in range(400):
        offers = card_rewards.roll_rewards(state, None, seed, defeated=enemies)
        if any(c.startswith("inf_fac_mao_sombria") for c in offers):
            card_rewards.grant_after_conflict(
                state,
                player,
                conflict_id="spec368:espolio",
                seed=seed,
                defeated=enemies,
                objective_result=None,
                turn=int((state.get("world") or {}).get("turn_count", 0) or 0),
            )
            return
    raise AssertionError("nenhuma semente ofereceu Carta da facção Mão Sombria")


def seed_save(
    item: int, *, variant: str = "", saves_dir: str | None = None, hero: str = "Smoke368"
) -> str:
    """Cria o jogo, abre o conflito (se a cena e de combate), aplica a receita e regrava. Devolve o `game_id`."""
    from fastapi.testclient import TestClient

    import api
    import persistence

    if item not in ITEMS or variant not in ITEMS[item]:
        raise ValueError(f"item/variante sem seed: {item}/{variant!r} (validos: {ITEMS})")
    combat_scene = not (item == 14 or (item, variant) in {(1, "rollback"), (6, "espolio")})
    with _legacy(saves_dir):
        client = TestClient(api.app)
        gid = _new_game(client, _CLASS.get((item, variant), "Sangromante"), hero)
        if combat_scene:
            _open_combat(client, gid)
        state = _load(gid)
        _recipe(item, variant, state)
        assert persistence.save_game_state(state)
        return gid


def view(gid: str, saves_dir: str | None = None) -> dict[str, Any]:
    """O que a UI recebe em `/game/state` para este save (usado pelos testes e pelo smoke)."""
    from fastapi.testclient import TestClient

    import api

    with _legacy(saves_dir):
        r = TestClient(api.app).get("/game/state", params={"game_id": gid})
        assert r.status_code == 200, r.text
        return r.json()
