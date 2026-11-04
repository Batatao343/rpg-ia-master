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
    2: ("", "frustrar"),
    3: ("", "rachadura", "eco", "inelegivel"),
    4: ("",),
    5: ("", "chefe", "nova", "chefe_fase"),
    6: ("", "espolio"),
    7: ("", "medico"),
    12: ("",),
    13: ("", "leitura", "armadura", "renegado", "reacao", "voto", "condicao_carta"),
    14: ("", "entrega"),
    15: ("", "vg_ouro"),  # SPEC-387 R23: loja com saldo para o V-G do ouro
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
    (2, "frustrar"): "Arcanista Cinzento",
    (5, "chefe_fase"): "Devoto do Abismo",
    (13, "voto"): "Devoto do Abismo",
    (13, "condicao_carta"): "Devoto do Abismo",
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


def _reseed(
    state,
    creature_id,
    n=1,
    *,
    hand=None,
    folego=None,
    enemy_vitality=None,
    seed=7,
    allies=None,
    want_alvo=None,
    late_vitality=None,
):
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
    actors = {
        "player": player,
        **{e["id"]: e for e in enemies},
        **{a["id"]: a for a in allies or []},
    }
    sides = {
        "hero": ["player"],
        "ally": [a["id"] for a in allies or []],
        "enemy": [e["id"] for e in enemies],
    }
    forecast = enemy_intent.forecast_round(scene, actors, sides, random.Random(seed))
    for s_ in range(seed, seed + 400):  # SPEC-387 R22: busca a semente que mira o alvo pedido
        if want_alvo is None:
            break
        forecast = enemy_intent.forecast_round(scene, actors, sides, random.Random(s_))
        if any(
            i.get("tipo") == "ataque" and i.get("alvo_id") == want_alvo
            for v in forecast.values()
            for i in v
        ):
            break
    else:
        if want_alvo is not None:
            raise AssertionError(f"nenhuma semente mirou {want_alvo}")
    for e in enemies:
        if late_vitality is not None:
            e["vitalidade"] = late_vitality  # DEPOIS do presságio: o inimigo ferido ainda ataca
    meta["pressagios"] = forecast
    meta["pressagios_publicos"] = enemy_intent.public_round(
        forecast, actors, cs.tactical_round(scene) + 1
    )


def _known(state: dict, *ids: str) -> None:
    p = state["player"]
    for cid in ids:
        if cid not in p.setdefault("known_cards", []):
            p["known_cards"].append(cid)


def _learn(state: dict, *ids: str) -> None:
    """SPEC-387 R21: Carta CONHECIDA, Preparada e no baralho (jogável de verdade). `_known` sozinho
    deixa a Carta só no Acervo: a jogada seria recusada (variante de teste `3 inelegivel`)."""
    _known(state, *ids)
    p = state["player"]
    for key in ("prepared_cards", "deck"):
        for cid in ids:
            if cid not in p.setdefault(key, []):
                p[key].append(cid)


def _escort(state: dict) -> None:
    """SPEC-387 R19/R21: o protegido é um aliado ATOR do conflito (`party`), não só um NPC da cena."""
    import party as party_mod
    from services import conflict_scene as cs

    comp = party_mod.make_companion_from_npc({"id": "escoltado", "name": "Escoltado"}, "Escoltado")
    comp["active"] = True
    state["party"] = [comp]
    scene = state["combat"]["scene"]
    ref = next(iter((scene.get("positions") or {}).values()), {})
    cs.place(scene, comp["id"], zone_id=ref.get("zone_id") or "z0", distance_state="proximo")
    cs.freeze(scene)
    scene["allies"] = [comp["id"]]
    scene["objetivo"] = {"tipo": "proteger", "alvo": comp["id"]}


def _soft(state: dict, vitality: int | None = None) -> None:
    """SPEC-387 R22: Esquiva do inimigo negativa (acerto certo em 2d10, sem depender de sorte)."""
    for e in state["enemies"]:
        e["esquiva_penalidade"] = 30
        if vitality is not None:
            e["vitalidade"] = e["max_vitalidade"] = vitality


def _recipe(item: int, variant: str, state: dict) -> None:
    from services import card_piles, card_rewards
    from services import enemy_decks as edk

    g = "bas_san_golpe"
    if item == 1 and variant == "rollback":
        card_piles.activate_deck(state["player"])
        return
    if item == 1:
        _reseed(state, "enemy_goblin", 1, hand=[g, g, "bas_san_guarda"], folego=1)
    elif item == 2 and variant == "frustrar":
        _learn(state, "arc1_des_estouro_contido")
        _reseed(state, "enemy_goblin", 1, hand=["arc1_des_estouro_contido", "bas_arc_golpe"])
        _soft(state)
    elif item == 2:
        _reseed(state, "enemy_goblin", 1)
        for e in state["enemies"]:
            e["revealed_cards"] = [
                c["id"] if isinstance(c, dict) else c for c in e.get("cartas") or []
            ]
    elif item == 3 and variant == "rachadura":
        _learn(state, "cor1_ino_junta_emperrada")
        _reseed(state, "enemy_goblin", 1, hand=["cor1_ino_junta_emperrada", "bas_cor_golpe"])
        _soft(state, 60)
    elif item == 3 and variant == "eco":
        _learn(state, "san1_exp_segundo_ato")
        _reseed(state, "enemy_goblin", 1, hand=[g, "san1_exp_segundo_ato"])
        _soft(state, 60)
    elif item == 3 and variant == "inelegivel":  # a receita ANTIGA, de propósito (R17/R18)
        _known(state, "san1_exp_segundo_ato")
        _reseed(state, "enemy_goblin", 1, hand=["san1_exp_segundo_ato", g])
    elif item == 3:
        _learn(state, "san1_exp_segundo_ato")
        _reseed(state, "enemy_goblin", 1, hand=["san1_exp_segundo_ato", g])
    elif item == 4:
        _reseed(state, "enemy_goblin", 2)
        _escort(state)
    elif item == 5 and variant == "chefe_fase":
        _reseed(state, "enemy_boss_valerius", 1, hand=["bas_dev_golpe", "bas_dev_golpe"])
        _soft(state)
        boss = state["enemies"][0]
        first = edk._sorted_phases(boss)[0]["ate_vitalidade_pct"]  # 1 ponto acima do limiar
        boss["vitalidade"] = int(int(boss["max_vitalidade"]) * first / 100) + 1
    elif item == 5:
        cid = {
            "": "enemy_soldado_legiao_ferro",
            "chefe": "enemy_boss_valerius",
            "nova": "mon_costurado_de_lentes",
        }[variant]
        _reseed(state, cid, 2 if variant == "" else 1)
    elif item == 6 and variant == "espolio":
        state["combat"] = {"active": False, "phase": "ended", "round": 0}
        card_piles.activate_deck(state["player"])  # SPEC-387 R21: Forja e Esquecer exigem o baralho
        _reseed_for_reward(state, edk)
        card_rewards.on_long_rest(state["player"])
    elif item == 6:
        _reseed(state, "enemy_degolador_mao_sombria", 2, hand=["sts_dor_surda", g])
    elif item == 7:
        _reseed(state, "enemy_goblin", 2)
    elif item == 12:
        _reseed(state, "enemy_goblin", 1, hand=[g, "bas_san_guarda"], enemy_vitality=1)
    elif item == 13 and variant in {"voto", "condicao_carta"}:
        _recipe_13_extra(state, variant)
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
                "enemy_soldado_legiao_ferro",
                1,
                ["cor_ino_fadiga", "bas_cor_golpe"],
                ("cor_ino_fadiga",),
            ),
            "renegado": ("enemy_renegado_ermo", 1, None, ()),
            "reacao": ("enemy_goblin", 1, ["dev_encaixe", "bas_dev_golpe"], ("dev_encaixe",)),
        }[variant]
        _learn(state, *spec[3])
        _reseed(
            state,
            spec[0],
            spec[1],
            hand=spec[2],
            late_vitality=1 if variant == "reacao" else None,
            folego=4 if variant == "reacao" else None,  # a Reação (custo 2) sobra depois da Guarda
        )
        if variant in {"reacao", "armadura"}:
            _soft(state)
        if variant == "armadura":  # Ruptura do caminho B aplica Armadura Comprometida
            state["player"].setdefault("evolved_cards", {})["cor_ino_fadiga"] = "B"
        if variant == "reacao":
            state["player"]["entropy"] = max(5, int(state["player"].get("entropy", 0) or 0))
    elif item == 15:
        _recipe_15(state)
    elif item == 14:
        if variant == "entrega":
            _place_hero(state, "brekmar", "Brekmar")
            state["world"]["turn_count"] = max(4, int(state["world"].get("turn_count", 0) or 0))
            for other in (state.get("npcs") or {}).values():  # SPEC-389 R8: só a origem em cena
                if isinstance(other, dict):
                    other["in_scene"] = False
            state.setdefault("npcs", {})["Contratante"] = {
                "name": "Contratante",
                "id": "contratante",
                "in_scene": True,
                "relationship": 20,
                "home_location_id": "brekmar",
            }
        state.setdefault("quests", []).append(
            {
                "id": "q368",
                "title": "Caça",
                "status": "active",
                "origin_name": "Contratante",
                "origin_entity_id": "contratante",
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


def _recipe_13_extra(state: dict, variant: str) -> None:
    """SPEC-387 R23: `13 voto` (Ketil aliado ator, presságio mirando Ketil) e `13 condicao_carta`."""
    import party as party_mod
    from services import conflict_scene as cs

    if variant == "condicao_carta":
        _learn(state, "neu1_er_lanca_de_gancho")
        _reseed(state, "enemy_goblin", 1, hand=["neu1_er_lanca_de_gancho", "bas_dev_golpe"])
        _soft(state, 60)
        return
    ketil = party_mod.make_companion_from_npc({"id": "ketil", "name": "Ketil"}, "Ketil")
    state["party"] = [ketil]
    _reseed(
        state,
        "enemy_goblin",
        1,
        hand=["bas_dev_voto", "bas_dev_golpe"],
        allies=[ketil],
        want_alvo="ketil",
    )
    _soft(state, 60)
    scene = state["combat"]["scene"]
    ref = next(iter((scene.get("positions") or {}).values()), {})
    cs.place(scene, "ketil", zone_id=ref.get("zone_id") or "z0", distance_state="proximo")
    cs.freeze(scene)
    scene["allies"] = ["ketil"]


def _place_hero(state: dict, location_id: str, name: str) -> None:
    world = state.setdefault("world", {})
    world["current_location_id"], world["current_location"] = location_id, name
    world["visited"] = list(dict.fromkeys([*(world.get("visited") or []), location_id]))
    plan = state.get("campaign_plan")
    if isinstance(plan, dict) and plan.get("location"):  # SPEC-389 R8: sem region_change espúrio
        plan["location"] = name


def _recipe_15(state: dict) -> None:
    """SPEC-387 R23 (`15 vg_ouro`): mercador de Skallgard; o ouro deixa SALDO FINAL 30 depois da
    Carta mais barata da prateleira (a prosa que diga "últimas moedas" é a prova do V-G da 367)."""
    from services import card_shop

    _place_hero(state, "skallgard", "Skallgard")
    state["player"]["level"] = max(6, int(state["player"].get("level", 1) or 1))
    mid, ids = card_shop.shelf(state)
    assert mid and ids, "Skallgard sem prateleira de Cartas"
    merchant = card_shop.economy.MERCHANTS[mid]
    price = min(card_shop.card_price(state, cid, merchant) for cid in ids)
    state["player"]["gold"] = price + 30


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
    combat_scene = not (item in (14, 15) or (item, variant) in {(1, "rollback"), (6, "espolio")})
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
