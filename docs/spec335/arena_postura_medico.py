"""SPEC-335 Lote 5 - taxa de vitoria da POSTURA Medico de Campo, antes x depois das 36 Cartas.

    bash scripts/dev/py.sh docs/spec335/arena_postura_medico.py [seeds] [--levels 1,3,5]
        [--categories padrao,elite] [--per-cat 4] [--out arquivo.json] [--prefixo med1_]

Mesmo bot e mesma arena de `docs/spec336/arena_folego_full.py` (baralho COMPLETO da Postura,
`sim.full_deck` + `sim.fight`, Folego do catalogo). "antes" = as Cartas do prefixo fora do
catalogo; "depois" = catalogo completo. Roda tambem por subclasse (o jogador real tem uma).
So o Medico: nenhum outro baralho muda com este lote.
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

from services import cards  # noqa: E402

A = sim.A
CLS = "Médico de Campo"
SUBCLASSES = ["", "cirurgiao_trincheira", "boticario", "cirurgiao_ferro"]


def run_arm(seeds, levels, categories, per_cat, sub: str) -> dict:
    pool = A.creatures_by_category()
    out: dict = {}
    for level in levels:
        for cat in categories:
            n = A.group_size(cat, level)
            wins = fights = 0
            for bid in sim.pick(pool[cat], per_cat):
                for seed in seeds:
                    deck = sim.full_deck(CLS, level, sub)
                    outcome, _ = sim.fight(bid, n, CLS, level, seed, deck, "full")
                    wins += outcome == "win"
                    fights += 1
            out[f"L{level} {cat}"] = [wins, fights]
    return out


def total(arm: dict) -> float:
    w = sum(v[0] for v in arm.values())
    n = sum(v[1] for v in arm.values())
    return round(w / n, 3) if n else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", nargs="?", type=int, default=20)
    ap.add_argument("--levels", default="1,3,5")
    ap.add_argument("--categories", default="padrao,elite")
    ap.add_argument("--per-cat", type=int, default=4)
    ap.add_argument("--prefixo", default="med1_")
    ap.add_argument("--out")
    args = ap.parse_args()
    levels = [int(x) for x in args.levels.split(",")]
    cats = args.categories.split(",")
    seeds = range(args.seeds)
    t0 = time.time()
    cat = cards._load_cards()
    novas = {k: cat[k] for k in list(cat) if k.startswith(args.prefixo)}
    res: dict = {
        "seeds": args.seeds,
        "levels": levels,
        "categories": cats,
        "n_cartas_novas": len(novas),
    }
    for sub in SUBCLASSES:
        key = sub or "todas_as_subclasses"
        for k in novas:
            cat.pop(k, None)
        antes = run_arm(seeds, levels, cats, args.per_cat, sub)
        cat.update(novas)
        depois = run_arm(seeds, levels, cats, args.per_cat, sub)
        res[key] = {
            "antes": antes,
            "depois": depois,
            "taxa_antes": total(antes),
            "taxa_depois": total(depois),
        }
    res["elapsed_s"] = round(time.time() - t0, 1)
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt + "\n")
    for key in [s or "todas_as_subclasses" for s in SUBCLASSES]:
        r = res[key]
        print(f"{key}: antes {r['taxa_antes']:.1%} -> depois {r['taxa_depois']:.1%}")
        for cell in r["antes"]:
            a, d = r["antes"][cell], r["depois"][cell]
            print(f"   {cell}: {a[0]}/{a[1]} -> {d[0]}/{d[1]}")


if __name__ == "__main__":
    main()
