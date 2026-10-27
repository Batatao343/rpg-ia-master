"""SPEC-335 Lote 6 - arena das 40 neutras (R2), contra 2 baralhos de Posturas diferentes.

    bash scripts/dev/py.sh docs/spec335/arena_neutras_lote6.py [--seeds 20] [--first 0] \
        [--out docs/spec335/sim-lote6.json]

As neutras nao pertencem a Postura (`classe: Neutra`), e o `sim.py` monta o baralho pela
`classe` da Carta. Aqui cada neutra vira uma VARIANTE (so na simulacao, nunca gravada) com a
`classe`/`subclasse` de cada baralho de teste e roda o protocolo de lote do `sim.py` (Carta
isolada, `level_req`, encontro padrao, 20 sementes, bracos pareados). Baralhos de teste:
``Devoto do Abismo`` (consagrado: corpo a corpo, Vigilia) e ``Arcanista Cinzento``
(calibrado: mao/Vazao, sem armadura). ``--first N`` roda so as N primeiras; ``--seeds`` troca
as sementes (confirmacao 20-99 = ``--seed-from 20 --seeds 80``).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys

os.environ.setdefault("RPG_FORCE_MOCK", "1")
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "cards"))
import sim  # noqa: E402

from services import card_lint  # noqa: E402

BARALHOS = {
    "devoto": ("Devoto do Abismo", "consagrado"),
    "arcanista": ("Arcanista Cinzento", "calibrado"),
}


def variante(card: dict, classe: str, sub: str) -> dict:
    v = copy.deepcopy(card)
    v["classe"] = classe
    v["subclasse"] = sub
    v.pop("neutra", None)
    return v


def rodar(batch: list[dict], seed_from: int, seeds: int, only: set[str] | None) -> dict:
    out: dict[str, dict] = {}
    for key, (classe, sub) in BARALHOS.items():
        for card in batch:
            if only and card["id"] not in only:
                continue
            v = variante(card, classe, sub)
            level = max(int(v.get("level_req", 1) or 1), 1)
            rep = sim.simulate_batch(
                [v],
                [level],
                sim.PROTOCOLO_LOTE["categories"],
                sim.PROTOCOLO_LOTE["per_cat"],
                list(range(seed_from, seed_from + seeds)),
            )
            out.setdefault(card["id"], {})[key] = rep[card["id"]]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--seed-from", type=int, default=0)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--only", default="", help="ids separados por virgula")
    ap.add_argument("--out", default="docs/spec335/sim-lote6.json")
    args = ap.parse_args()
    batch = card_lint.load_batch("data/cards/valoria_neutras.json")
    if args.first:
        batch = batch[: args.first]
    only = {x for x in args.only.split(",") if x} or None
    rep = rodar(batch, args.seed_from, args.seeds, only)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
        f.write("\n")
    for cid, por in rep.items():
        linha = " | ".join(
            f"{k}: uso {r['taxa_uso']:.0%} d {r['delta_pp']:+.1f}pp {','.join(r['bandeiras'])}"
            for k, r in por.items()
        )
        print(f"{cid}: {linha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
