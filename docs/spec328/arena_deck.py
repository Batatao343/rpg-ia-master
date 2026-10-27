"""SPEC-328 Etapa 6 - arena `off` x `on` do Baralho de Conflito (offline, MockLLM, seeded).

Reproduzir:
    bash scripts/dev/py.sh docs/spec328/arena_deck.py [seeds] [--levels 1,3,5] [--per-cat 4] \
        [--categories padrao,elite] [--folego 3] [--mao 5]

Reaproveita o esqueleto da arena da SPEC-285 (mesmo heroi da esteira do playtest, mesmo
encontro "piso" por categoria, mesmo `run_round`). Dois bots, ambos "razoaveis":

- `off`: bot `cartas` da SPEC-285 (1 acao por rodada: cura <50 % de Vitalidade, senao a
  Carta de ataque preparada de maior dano que puder pagar, senao ataque basico);
- `on`: bot de baralho - mesma prioridade, mas joga da MAO enquanto houver Folego
  (sem tomar emprestado no Pacto), 1 copia por carta de frequencia `turno`.

Metricas por classe: taxa de vitoria, taxa de morte, rodadas medias por combate.
Criterio da spec: vitoria `on` dentro de +-15 pp do `off`; nenhuma classe < 35 % ou > 80 %
no encontro padrao. Saida: JSON em stdout.
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

from services import card_piles, cards  # noqa: E402
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402
from services import conflict_turn as ct  # noqa: E402

MAX_ROUNDS = 20


def deck_decl(player: dict, piles: dict, target_id: str) -> ct.TurnDeclaration:
    hand = list(piles["mao"])
    steps: list[ct.TurnStep] = []
    vit, mx = int(player.get("vitalidade", 0) or 0), int(player.get("max_vitalidade", 1) or 1)
    played_turn: set[str] = set()

    def try_add(step: ct.TurnStep) -> bool:
        plan = card_piles.plan_plays(piles, player, [*steps, step])
        if plan["ok"] and plan["emprestado"] == 0:
            steps.append(step)
            return True
        return False

    def usable(cid: str) -> bool:
        card = cards.get_card(cid) or {}
        freq = str(card.get("frequencia", "livre"))
        counter = cards.FREQ_COUNTER.get(freq)
        if freq == "turno":
            return cid not in played_turn
        used = int(((player.get("card_usage") or {}).get(cid) or {}).get(counter or "", 0) or 0)
        return not counter or used < 1

    if vit * 2 < mx:
        for cid in hand:
            if A._card_kind(cid) == "cura" and usable(cid):
                if try_add(ct.TurnStep(kind="card", card_id=cid, target_id="player")):
                    played_turn.add(cid)
                    hand.remove(cid)
                    break
    attacks = sorted(
        (c for c in hand if A._card_kind(c) in ct._ATTACK_EFFECTS),
        key=lambda c: (-A._card_damage(c), c),
    )
    for cid in attacks:
        if not usable(cid):
            continue
        if try_add(ct.TurnStep(kind="card", card_id=cid, target_id=target_id)):
            played_turn.add(cid)
    if not steps:
        steps.append(ct.TurnStep(kind="attack", target_id=target_id))
    return ct.TurnDeclaration(actor_id="player", jogadas=steps)


def fight(bid, n, class_name, level, seed, mode):
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
    piles = None
    if mode == "on":
        card_piles.migrate_deck(player)
        piles = card_piles.start_piles(player, seed)
        state.update(_piles=piles, _deck_mode="on")
    for rnd in range(1, MAX_ROUNDS + 1):
        alive = [e for e in enemies if orch._can_act(e)]
        if not alive:
            return "win", rnd
        initiator = (
            "heroes"
            if rnd == 1 and level <= 2 and player["vitalidade"] >= player["max_vitalidade"]
            else None
        )
        if mode == "on":
            decl = deck_decl(player, piles, alive[0]["id"])
        else:
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
        if piles is not None:
            card_piles.begin_round(piles)
    return "timeout", MAX_ROUNDS


def pick(ids: list[str], k: int) -> list[str]:
    if len(ids) <= k:
        return ids
    step = len(ids) / k
    return [ids[int(i * step)] for i in range(k)]


def run(seeds, levels, categories, per_cat) -> dict:
    pool = A.creatures_by_category()
    res: dict = {}
    for mode in ("off", "on"):
        for level in levels:
            for cat in categories:
                n = A.group_size(cat, level)
                per_class = {}
                for cls in A.CLASSES:
                    c = {"fights": 0, "win": 0, "death": 0, "timeout": 0, "rounds": 0}
                    for bid in pick(pool[cat], per_cat):
                        for seed in seeds:
                            outcome, rounds = fight(bid, n, cls, level, seed, mode)
                            c["fights"] += 1
                            c[outcome] += 1
                            c["rounds"] += rounds
                    per_class[cls] = {
                        "win": round(c["win"] / c["fights"], 3),
                        "death": round(c["death"] / c["fights"], 3),
                        "avg_rounds": round(c["rounds"] / c["fights"], 2),
                        "fights": c["fights"],
                    }
                res[f"{mode}|L{level}|{cat}"] = per_class
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", nargs="?", type=int, default=3)
    ap.add_argument("--levels", default="1,3,5")
    ap.add_argument("--categories", default="padrao,elite")
    ap.add_argument("--per-cat", type=int, default=4)
    ap.add_argument("--folego", type=int, default=card_piles.FOLEGO_BASE)
    ap.add_argument("--dano2", type=int, default=cards.DANO_BASE_FOLEGO_2)
    ap.add_argument("--mao", type=int, default=card_piles.MAO_BASE)
    args = ap.parse_args()
    card_piles.FOLEGO_BASE = args.folego
    card_piles.MAO_BASE = args.mao
    cards.DANO_BASE_FOLEGO_2 = args.dano2
    t0 = time.time()
    cells = run(
        range(args.seeds),
        [int(x) for x in args.levels.split(",")],
        args.categories.split(","),
        args.per_cat,
    )
    summary = {}
    for key, per_class in cells.items():
        mode, rest = key.split("|", 1)
        if mode != "on":
            continue
        off = cells[f"off|{rest}"]
        summary[rest] = {
            cls: {
                "win_off": off[cls]["win"],
                "win_on": per_class[cls]["win"],
                "delta_pp": round((per_class[cls]["win"] - off[cls]["win"]) * 100, 1),
                "rounds_off": off[cls]["avg_rounds"],
                "rounds_on": per_class[cls]["avg_rounds"],
            }
            for cls in per_class
        }
    print(
        json.dumps(
            {
                "seeds": args.seeds,
                "folego": args.folego,
                "mao": args.mao,
                "dano2": args.dano2,
                "elapsed_s": round(time.time() - t0, 1),
                "summary": summary,
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
