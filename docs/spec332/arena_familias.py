"""SPEC-332 arena por família: `RPG_ENEMY_DECKS=off` x `on` (offline, MockLLM, seeded).

Reproduzir:
    bash scripts/dev/py.sh docs/spec332/arena_familias.py [seeds] [--levels 3,5] [--per-family 3]

Reaproveita a arena da SPEC-285 (mesmo herói da esteira do playtest, mesmo encontro "piso"
por categoria, mesmo `run_round`, bot "cartas"). Para cada família (arquétipo; `abissal` por
sinal explícito) escolhe `--per-family` criaturas não-chefe espalhadas pelo pool, e mede a taxa
de vitória do herói por família/nível. Critério da spec: 45-85 % por família no nível-alvo; o
`off` é a régua (a arena da SPEC-328 já mostrou o `off` fora de 35-80 % em vários nichos).
Saída: JSON em stdout.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
import time

os.environ["RPG_FORCE_MOCK"] = "1"
sys.path.insert(0, os.getcwd())

_spec = importlib.util.spec_from_file_location(
    "arena285", os.path.join("docs", "spec285", "arena_lethality.py")
)
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)  # type: ignore[union-attr]

from agents.bestiary import load_bestiary  # noqa: E402
from combat_mechanics import normalize_categoria  # noqa: E402
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402
from services import enemy_decks as edk  # noqa: E402

MAX_ROUNDS = 20


def families() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {f: [] for f in edk.FAMILIAS}
    for bid, entry in sorted(load_bestiary().items()):
        cat = normalize_categoria(entry)
        if cat in ("chefe", "nomeado"):
            continue
        fam = edk.family_key({**entry, "id": bid})
        if fam:
            out[fam].append(bid)
    return out


def pick(ids: list[str], k: int) -> list[str]:
    if len(ids) <= k:
        return ids
    step = len(ids) / k
    return [ids[int(i * step)] for i in range(k)]


def fight(bid: str, n: int, class_name: str, level: int, seed: int, mode: str) -> tuple[str, int]:
    os.environ["RPG_ENEMY_DECKS"] = mode
    A.random.seed(f"{mode}|{level}|{class_name}|{bid}|{n}|{seed}")
    player = A.hero(class_name, level)
    enemies = A._instances(
        A.template_by_id(bid, encounter_level=A.DANGER_BY_LEVEL.get(level, 4)), n
    )
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
        decl = A.hero_decl("cartas", player, alive[0]["id"])
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", nargs="?", type=int, default=2)
    ap.add_argument("--levels", default="3,5")
    ap.add_argument("--per-family", type=int, default=3)
    ap.add_argument("--only", default="", help="familias separadas por virgula")
    args = ap.parse_args()
    t0 = time.time()
    fams = families()
    cat_of = {b: normalize_categoria(e) for b, e in load_bestiary().items()}
    res: dict = {}
    for fam, ids in fams.items():
        if not ids or (args.only and fam not in args.only.split(",")):
            continue
        for level in (int(x) for x in args.levels.split(",")):
            row: dict = {}
            for mode in ("off", "on"):
                c = {"fights": 0, "win": 0, "death": 0, "timeout": 0, "rounds": 0}
                for bid in pick(ids, args.per_family):
                    n = A.group_size(cat_of[bid] if cat_of[bid] in A.CATEGORIES else "padrao", level)
                    for cls in A.CLASSES:
                        for seed in range(args.seeds):
                            outcome, rounds = fight(bid, n, cls, level, seed, mode)
                            c["fights"] += 1
                            c[outcome] += 1
                            c["rounds"] += rounds
                row[mode] = {
                    "win": round(c["win"] / c["fights"], 3),
                    "death": round(c["death"] / c["fights"], 3),
                    "avg_rounds": round(c["rounds"] / c["fights"], 2),
                    "fights": c["fights"],
                }
            row["delta_pp"] = round((row["on"]["win"] - row["off"]["win"]) * 100, 1)
            res[f"{fam}|L{level}"] = row
    os.environ.pop("RPG_ENEMY_DECKS", None)
    print(
        json.dumps(
            {"seeds": args.seeds, "elapsed_s": round(time.time() - t0, 1), "cells": res},
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
