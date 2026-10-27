"""SPEC-336 - arena `off` x `on` (baralho COMPLETO) para calibrar o Folego da SPEC-328.

    bash scripts/dev/py.sh docs/spec336/arena_folego_full.py [seeds] [--folego 2,3] [--levels 1,3,5]
        [--categories padrao,elite] [--per-cat 4]

`off` = bot `cartas` da SPEC-285 (1 acao/rodada, Preparacao). `on` = `sim.full_deck_decl`
(baralho completo da Postura: basicas + Acervo ate o nivel; cura <50 %, defesa <75 %,
golpes de maior dano enquanto houver Folego, sem Pacto). Mesma metrica de vitoria por celula.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "cards"))
import sim  # noqa: E402

from services import card_piles  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "arena_deck", os.path.join("docs", "spec328", "arena_deck.py")
)
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)  # type: ignore[union-attr]
A = sim.A


def run(seeds, levels, categories, per_cat, folego) -> dict:
    card_piles.FOLEGO_BASE = folego
    pool = A.creatures_by_category()
    out: dict = {}
    for level in levels:
        for cat in categories:
            n = A.group_size(cat, level)
            cell: dict = {}
            for cls in A.CLASSES:
                c = {"off": [0, 0, 0], "on": [0, 0, 0]}  # vitorias, lutas, rodadas
                for bid in sim.pick(pool[cat], per_cat):
                    for seed in seeds:
                        os.environ["RPG_CARD_DECK"] = "off"
                        o, r = D.fight(bid, n, cls, level, seed, "off")
                        c["off"][0] += o == "win"
                        c["off"][1] += 1
                        c["off"][2] += r
                        o, r = sim.fight(
                            bid, n, cls, level, seed, sim.full_deck(cls, level), "full"
                        )
                        c["on"][0] += o == "win"
                        c["on"][1] += 1
                        c["on"][2] += r
                cell[cls] = c
            out[f"L{level} {cat}"] = cell
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", nargs="?", type=int, default=3)
    ap.add_argument("--folego", default="2,3")
    ap.add_argument("--levels", default="1,3,5")
    ap.add_argument("--categories", default="padrao,elite")
    ap.add_argument("--per-cat", type=int, default=4)
    args = ap.parse_args()
    t0 = time.time()
    rows = []
    for f in [int(x) for x in args.folego.split(",")]:
        res = run(
            range(args.seeds),
            [int(x) for x in args.levels.split(",")],
            args.categories.split(","),
            args.per_cat,
            f,
        )
        tot = {"off": [0, 0, 0], "on": [0, 0, 0]}
        for cell, per_class in res.items():
            w = {m: sum(c[m][0] for c in per_class.values()) for m in ("off", "on")}
            n = {m: sum(c[m][1] for c in per_class.values()) for m in ("off", "on")}
            r = {m: sum(c[m][2] for c in per_class.values()) for m in ("off", "on")}
            for m in tot:
                tot[m][0] += w[m]
                tot[m][1] += n[m]
                tot[m][2] += r[m]
            rows.append(
                {
                    "folego": f,
                    "celula": cell,
                    "vit_off": round(w["off"] / n["off"], 3),
                    "vit_on": round(w["on"] / n["on"], 3),
                    "rod_off": round(r["off"] / n["off"], 2),
                    "rod_on": round(r["on"] / n["on"], 2),
                    "lutas": n["on"],
                    "por_classe_on": {
                        k: round(v["on"][0] / v["on"][1], 2) for k, v in per_class.items()
                    },
                }
            )
        rows.append(
            {
                "folego": f,
                "celula": "todas",
                "vit_off": round(tot["off"][0] / tot["off"][1], 3),
                "vit_on": round(tot["on"][0] / tot["on"][1], 3),
                "rod_off": round(tot["off"][2] / tot["off"][1], 2),
                "rod_on": round(tot["on"][2] / tot["on"][1], 2),
                "lutas": tot["on"][1],
            }
        )
    print(
        json.dumps(
            {"seeds": args.seeds, "elapsed_s": round(time.time() - t0, 1), "rows": rows},
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
