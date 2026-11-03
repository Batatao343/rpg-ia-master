"""SPEC-371 §6 passo 7 (CPU, offline, MockLLM): custo do saber por rodada, `on` x `off`.

    bash scripts/dev/py.sh docs/spec371/custo_cpu_saber.py [--rounds 240]

Mede, por rodada, o bloco pós-`run_round` do combate real: `absorb` + `stamp_actor` (por inimigo)
+ montagem do presságio (`forecast_round` + `public_round` + `record_promise`). Mesmas lutas e
sementes nos dois modos; só a flag `RPG_FAUNA_SABER` muda. Saída: p50/p95/média em ms e Δ p50.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import statistics
import sys
import time

os.environ.setdefault("RPG_FORCE_MOCK", "1")
sys.path.insert(0, os.getcwd())
for k, v in {"RPG_ENEMY_DECKS": "on", "RPG_ENEMY_INTENT": "on"}.items():
    os.environ[k] = v

spec = importlib.util.spec_from_file_location(
    "as371", os.path.join("scripts", "fauna", "arena_saber.py")
)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402
from services import discovery as disc  # noqa: E402
from services import enemy_decks as edk  # noqa: E402
from services import enemy_intent as ei  # noqa: E402
from services import fauna_saber as fs  # noqa: E402

BID = "mon_arame_vivo"
BK0 = {BID: {"seen": 2, "fought": 2, "defeated": 1, "sinais_vistos": ["rastro", "som"]}}


def medir(mode: str, rounds: int) -> list[float]:
    os.environ["RPG_FAUNA_SABER"] = mode
    A = M._arena()
    times: list[float] = []
    seed = 0
    while len(times) < rounds:
        random.seed(f"cpu|{seed}")
        cls = A.CLASSES[seed % len(A.CLASSES)]
        player = A.hero(cls, 3)
        enemies = A._instances(A.template_by_id(BID, encounter_level=2), 2)
        bk = disc.record_encounter(json.loads(json.dumps(BK0)), enemies, 5)
        actors = {"player": player, **{e["id"]: e for e in enemies}}
        sides = {"hero": ["player"], "ally": [], "enemy": [e["id"] for e in enemies]}
        scene = cs.new_scene()
        for aid in actors:
            cs.place(scene, aid)
        cs.freeze(scene)
        for e in enemies:
            fs.stamp_actor(e, bk)
        rng = random.Random(seed)
        state = {"player": player}
        frozen = ei.forecast_round(scene, actors, sides, rng, scene_state={"_rodada_decisao": 1})
        for _ in range(M.MAX_ROUNDS):
            alive = [e for e in enemies if orch._can_act(e)]
            if not alive:
                break
            out = orch.run_round(
                scene,
                actors,
                sides,
                state,
                declarations={"player": A.hero_decl("cartas", player, alive[0]["id"])},
                rng=rng,
                pressagios=frozen,
            )
            dead = bool(player.get("dead") or out.get("player_dead") or player["vitalidade"] <= 0)
            t0 = time.perf_counter()
            bk, _ = fs.absorb(bk, scene, actors, not dead, 5)
            for e in enemies:
                fs.stamp_actor(e, bk)
            if not (dead or out.get("ended")):
                rnd = cs.tactical_round(scene) + 1
                frozen = ei.forecast_round(
                    scene, actors, sides, rng, scene_state={"_rodada_decisao": rnd}
                )
                rows = ei.public_round(frozen, actors, rnd)
                for row in rows:
                    if row.get("prenuncio") and row.get("actor_id") in actors:
                        edk.record_promise(scene, actors[row["actor_id"]], rnd)
            times.append((time.perf_counter() - t0) * 1000)
            if dead or out.get("ended"):
                break
        seed += 1
    return times


def resumo(xs: list[float]) -> dict:
    xs = sorted(xs)
    return {
        "n": len(xs),
        "p50_ms": round(statistics.median(xs), 3),
        "p95_ms": round(xs[int(0.95 * len(xs)) - 1], 3),
        "media_ms": round(statistics.fmean(xs), 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=240)
    args = ap.parse_args()
    medir("off", 20)  # aquecimento (caches de cartas/bestiário)
    off = medir("off", args.rounds)
    on = medir("on", args.rounds)
    res = {"off": resumo(off), "on": resumo(on)}
    res["delta_p50_ms"] = round(res["on"]["p50_ms"] - res["off"]["p50_ms"], 3)
    print(json.dumps(res, indent=1))
    return 0 if res["delta_p50_ms"] <= 100 else 1


if __name__ == "__main__":
    raise SystemExit(main())
