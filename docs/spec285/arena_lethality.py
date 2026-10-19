"""SPEC-285 arena de letalidade por nível × categoria (offline, MockLLM, seeded).

Reproduzir:
    bash scripts/dev/py.sh docs/spec285/arena_lethality.py [seeds] [--levels 1,3,5,8] [--bots basico,cartas]

Para cada (nível do herói, categoria do inimigo, classe, criatura, seed) monta:
- herói pela MESMA esteira do playtest (`_build_initial_state`: criação oficial +
  `grant_xp` + escolhas de progressão + Cartas preparadas);
- encontro "piso" de uma espécie, como `fill_encounter` monta um encontro
  sistêmico: 1 criatura + reforços da mesma espécie até `encounter_budget//2`
  no perigo do nível (nível 1→perigo 1, 3→2, 5→3, 8→4); chefe sempre sozinho;
  nível 1 com no máximo 1 elite (`clamp_encounter`);
- proteção de early-game igual ao jogo (iniciativa do herói na 1ª rodada se
  nível ≤ 2 e Vitalidade cheia).

Dois bots do herói:
- `basico`: só ataque básico no primeiro inimigo vivo (piso pessimista, o mesmo
  bot da arena da SPEC-283);
- `cartas` ("razoável", como o agente curioso da SPEC-059/056): cura a si com
  Carta preparada abaixo de 50 % de Vitalidade; senão usa a Carta de ataque
  preparada de maior dano que puder pagar; senão ataque básico.

Métrica: taxa de morte do herói por combate (e `early_deaths`: mortes em ≤ 2 rodadas, SPEC-056 R2b) (morte = Estado Terminal/Vitalidade
0 sem aliado, como na arena da SPEC-283). Saída: JSON em stdout.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import random
import sys
import time

os.environ["RPG_FORCE_MOCK"] = "1"
sys.path.insert(0, os.getcwd())
logging.disable(logging.CRITICAL)

import encounter_budget as eb  # noqa: E402
from agents.bestiary import load_bestiary  # noqa: E402

try:  # SPEC-203+; o fallback permite medir commits antigos (âncora pré-232)
    from agents.bestiary import template_by_id  # noqa: E402
except ImportError:  # pragma: no cover

    def template_by_id(enemy_id: str, *, encounter_level: int = 1) -> dict | None:
        data = dict(load_bestiary().get(enemy_id) or {})
        data["id"] = enemy_id
        data["vitalidade"] = int(data.get("max_vitalidade") or 0)
        data["hp"] = data["max_hp"] = data["vitalidade"]
        data["status"] = "ativo"
        return data


from combat_mechanics import normalize_categoria  # noqa: E402
from playtest.runner import _build_initial_state  # noqa: E402
from services import cards  # noqa: E402
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402
from services import conflict_turn as ct  # noqa: E402

CLASSES = ("Devoto do Abismo", "Sangromante", "Corruptor", "Arcanista Cinzento", "Médico de Campo")
CATEGORIES = ("lacaio", "padrao", "elite", "chefe")
DANGER_BY_LEVEL = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4}
MAX_ROUNDS = 20

_HEROES: dict[tuple[str, int], dict] = {}


def hero(class_name: str, level: int) -> dict:
    key = (class_name, level)
    if key not in _HEROES:
        state = _build_initial_state("arena", 285, class_name=class_name, start_level=level)
        _HEROES[key] = state["player"]
    player = copy.deepcopy(_HEROES[key])
    player["id"] = "player"
    player["is_player"] = True
    return orch.ensure_combat_sheet(player, is_player=True)


def creatures_by_category() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for bid, entry in load_bestiary().items():
        cat = normalize_categoria(entry)
        if cat == "nomeado":
            cat = "chefe"
        if cat in out:
            out[cat].append(bid)
    return {c: sorted(v) for c, v in out.items()}


def group_size(category: str, level: int) -> int:
    if category == "chefe":
        return 1
    cost = eb.CATEGORIA_COST[category]
    budget = eb.encounter_budget(level, DANGER_BY_LEVEL.get(level, 4), 0)
    floor = max(eb.TIER_COST["minion"], budget // 2)
    floor_cost = getattr(eb, "floor_cost", None)  # SPEC-287; commits antigos: linear
    if floor_cost is not None:
        n = 1
        while floor_cost([{"categoria": category}] * n) < floor:
            n += 1
    else:
        n = max(1, -(-floor // cost))
    if level == 1 and category == "elite":
        n = 1
    return n


def _instances(template: dict, count: int) -> list[dict]:
    """Mesmo contrato de `agents.combat._instances` (ids `<base>_<n>`)."""
    out = []
    base = str(template.get("id") or "enemy")
    for i in range(1, count + 1):
        inst = dict(template)
        inst["id"] = f"{base}_{i}"
        inst.setdefault("archetype_id", base)
        inst["name"] = f"{template['name']} {i}" if count > 1 else template["name"]
        out.append(orch.ensure_combat_sheet(inst))
    return out


def _card_kind(card_id: str) -> str:
    return str(((cards.get_card(card_id) or {}).get("efeito") or {}).get("kind") or "")


def _card_damage(card_id: str) -> int:
    efeito = (cards.get_card(card_id) or {}).get("efeito") or {}
    try:
        return int(efeito.get("dano_base") or 0)
    except (TypeError, ValueError):
        return 0


def hero_decl(bot: str, player: dict, target_id: str) -> ct.TurnDeclaration:
    if bot == "cartas":
        prepared = list(player.get("prepared_cards") or [])
        vit = int(player.get("vitalidade", 0) or 0)
        mx = int(player.get("max_vitalidade", 1) or 1)
        if vit * 2 < mx:
            for cid in prepared:
                if _card_kind(cid) == "cura" and cards.can_use_card(player, cid):
                    return ct.TurnDeclaration(
                        actor_id="player",
                        acao=ct.TurnStep(kind="card", card_id=cid, target_id="player"),
                    )
        attacks = [
            cid
            for cid in prepared
            if _card_kind(cid) in ct._ATTACK_EFFECTS and cards.can_use_card(player, cid)
        ]
        if attacks:
            cid = max(attacks, key=lambda c: (_card_damage(c), c))
            return ct.TurnDeclaration(
                actor_id="player", acao=ct.TurnStep(kind="card", card_id=cid, target_id=target_id)
            )
    return ct.TurnDeclaration(
        actor_id="player", acao=ct.TurnStep(kind="attack", target_id=target_id)
    )


def fight(bid: str, n: int, class_name: str, level: int, seed: int, bot: str):
    # SPEC-287: partes do motor ainda usam o `random` global; semeá-lo por luta
    # torna a arena reproduzível (seed de str usa sha512, imune a PYTHONHASHSEED).
    random.seed(f"{bot}|{level}|{class_name}|{bid}|{n}|{seed}")
    player = hero(class_name, level)
    enemies = _instances(template_by_id(bid, encounter_level=DANGER_BY_LEVEL.get(level, 4)), n)
    actors = {"player": player, **{e["id"]: e for e in enemies}}
    sides = {"hero": ["player"], "ally": [], "enemy": [e["id"] for e in enemies]}
    scene = cs.new_scene()
    for aid in actors:
        cs.place(scene, aid)
    cs.freeze(scene)
    rng = random.Random(seed)
    state = {"player": player}
    for rnd in range(1, MAX_ROUNDS + 1):
        alive = [e for e in enemies if orch._can_act(e)]
        if not alive:
            return "win", rnd
        initiator = (
            "heroes"
            if rnd == 1 and level <= 2 and player["vitalidade"] >= player["max_vitalidade"]
            else None
        )
        decl = hero_decl(bot, player, alive[0]["id"])
        out = orch.run_round(
            scene, actors, sides, state, declarations={"player": decl}, initiator=initiator, rng=rng
        )
        if (
            player.get("dead")
            or player.get("estado_terminal")
            or out.get("player_dead")
            or int(player.get("vitalidade", 0) or 0) <= 0
        ):
            return "death", rnd
        if out.get("ended"):
            return "win", rnd
    return "timeout", MAX_ROUNDS


def run(seeds, levels, bots, classes=CLASSES, categories=CATEGORIES) -> dict:
    pool = creatures_by_category()
    result: dict = {}
    for bot in bots:
        for level in levels:
            for cat in categories:
                n = group_size(cat, level)
                cell = {
                    "n": n,
                    "fights": 0,
                    "death": 0,
                    "win": 0,
                    "timeout": 0,
                    "rounds": 0,
                    "early_deaths": 0,
                }
                per_class = {}
                for cls in classes:
                    d = f = 0
                    for bid in pool[cat]:
                        for seed in seeds:
                            outcome, rounds = fight(bid, n, cls, level, seed, bot)
                            cell[outcome] += 1
                            cell["early_deaths"] += outcome == "death" and rounds <= 2
                            cell["fights"] += 1
                            cell["rounds"] += rounds
                            f += 1
                            d += outcome == "death"
                    per_class[cls] = round(d / f, 3) if f else None
                cell["death_rate"] = round(cell["death"] / cell["fights"], 3)
                cell["avg_rounds"] = round(cell["rounds"] / cell["fights"], 2)
                cell["per_class"] = per_class
                result[f"{bot}|L{level}|{cat}"] = cell
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", nargs="?", type=int, default=10)
    ap.add_argument("--levels", default="1,3,5,8")
    ap.add_argument("--bots", default="basico,cartas")
    ap.add_argument("--categories", default=",".join(CATEGORIES))
    args = ap.parse_args()
    t0 = time.time()
    res = run(
        range(args.seeds),
        [int(x) for x in args.levels.split(",")],
        args.bots.split(","),
        categories=args.categories.split(","),
    )
    print(
        json.dumps(
            {"seeds": args.seeds, "elapsed_s": round(time.time() - t0, 1), "cells": res},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
