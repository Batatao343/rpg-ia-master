"""SPEC-335 criterio final - taxa de vitoria de CADA Postura com o baralho completo.

    bash scripts/dev/py.sh docs/spec335/arena_posturas.py [seeds] [--levels 1,3,5]
        [--categories padrao,elite] [--per-cat 4] [--out arquivo.json]

Generaliza `arena_postura_medico.py` (mesmo bot, mesma arena, `sim.full_deck` + `sim.fight`),
so o braco "depois" (catalogo completo), para as 5 Posturas e suas subclasses.

Vies de ordem do `sim.full_deck`: o baralho e preenchido por `(-tier, id)` ate `DECK_MAX`.
Dentro do mesmo tier os ids `*1_` (cartas da onda 1) vem ANTES dos legados `*_...` ('1' < '_'),
entao com o baralho cheio as cartas novas entram primeiro e as legadas do mesmo tier sao
cortadas. A taxa mede o baralho "tier mais alto + onda 1", nao a escolha de um jogador real.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "cards"))
import sim  # noqa: E402

A = sim.A
POSTURAS = {
    "Devoto do Abismo": ["consagrado", "zeloso", "enlutado"],
    "Sangromante": ["exposto", "avaro", "silencioso"],
    "Corruptor": ["biologia", "alma", "inorganica"],
    "Arcanista Cinzento": ["calibrado", "descoberto", "improvisador"],
    "Médico de Campo": ["cirurgiao_trincheira", "boticario", "cirurgiao_ferro"],
}


def run_arm(cls, seeds, levels, categories, per_cat, sub) -> dict:
    pool = A.creatures_by_category()
    out: dict = {}
    for level in levels:
        for cat in categories:
            n = A.group_size(cat, level)
            wins = fights = 0
            for bid in sim.pick(pool[cat], per_cat):
                for seed in seeds:
                    deck = sim.full_deck(cls, level, sub)
                    outcome, _ = sim.fight(bid, n, cls, level, seed, deck, "full")
                    wins += outcome == "win"
                    fights += 1
            out[f"L{level} {cat}"] = [wins, fights]
    return out


def rate(arm: dict, cats: tuple[str, ...] | None = None) -> float:
    sel = [v for k, v in arm.items() if cats is None or k.split(" ", 1)[1] in cats]
    w, n = sum(v[0] for v in sel), sum(v[1] for v in sel)
    return round(w / n, 3) if n else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", nargs="?", type=int, default=20)
    ap.add_argument("--levels", default="1,3,5")
    ap.add_argument("--categories", default="padrao,elite")
    ap.add_argument("--per-cat", type=int, default=4)
    ap.add_argument("--out")
    args = ap.parse_args()
    levels = [int(x) for x in args.levels.split(",")]
    cats = args.categories.split(",")
    seeds = range(args.seeds)
    t0 = time.time()
    res: dict = {"seeds": args.seeds, "levels": levels, "categories": cats}
    for cls, subs in POSTURAS.items():
        res[cls] = {}
        for sub in ["", *subs]:
            arm = run_arm(cls, seeds, levels, cats, args.per_cat, sub)
            key = sub or "todas_as_subclasses"
            res[cls][key] = {
                "celulas": arm,
                "taxa_total": rate(arm),
                "taxa_padrao": rate(arm, ("padrao",)),
            }
            print(
                f"{cls} / {key}: total {rate(arm):.1%} | padrao {rate(arm, ('padrao',)):.1%}",
                flush=True,
            )
    res["elapsed_s"] = round(time.time() - t0, 1)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(res, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
