"""SPEC-335 R6 (tronco do Lote 6) - arena das 15 Cartas de tronco, por subclasse.

    bash scripts/dev/py.sh docs/spec335/confirmar_tronco_lote6.py \
        [--seed-from 0 --seeds 20] [--out arquivo.json]

As Cartas de tronco (``data/cards/posturas/*_tronco.json``, 3 por Postura) nao tem subclasse:
valem para as tres. O `sim.py` monta o baralho pela `subclasse` da Carta, e com subclasse vazia
o baralho "sem" mistura as tres (fica mais fraco e infla o delta: a Centelha Ressoante deu
+11 pp assim). Aqui cada Carta vira uma VARIANTE por subclasse (so na simulacao) e roda o
protocolo de lote (Carta isolada, `level_req`, encontro padrao). Padrao: sementes 0-19;
confirmacao: ``--seed-from 20 --seeds 80``.
"""

from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import sys

os.environ.setdefault("RPG_FORCE_MOCK", "1")
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "cards"))
import sim  # noqa: E402

from services import card_lint  # noqa: E402

SUBCLASSES = {
    "Devoto do Abismo": ["consagrado", "zeloso", "enlutado"],
    "Sangromante": ["exposto", "avaro", "silencioso"],
    "Corruptor": ["biologia", "alma", "inorganica"],
    "Arcanista Cinzento": ["calibrado", "descoberto", "improvisador"],
    "Médico de Campo": ["cirurgiao_trincheira", "boticario", "cirurgiao_ferro"],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed-from", type=int, default=0)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--only", default="", help="ids separados por virgula")
    ap.add_argument("--out", default="docs/spec335/sim-lote6-tronco.json")
    args = ap.parse_args()
    only = {x for x in args.only.split(",") if x}
    batch: list[dict] = []
    for path in sorted(glob.glob("data/cards/posturas/*_tronco.json")):
        batch += card_lint.load_batch(path)
    out: dict[str, dict] = {}
    for card in batch:
        if only and card["id"] not in only:
            continue
        for sub in SUBCLASSES[card["classe"]]:
            v = copy.deepcopy(card)
            v["subclasse"] = sub
            rep = sim.simulate_batch(
                [v],
                [max(int(v.get("level_req", 1) or 1), 1)],
                sim.PROTOCOLO_LOTE["categories"],
                sim.PROTOCOLO_LOTE["per_cat"],
                list(range(args.seed_from, args.seed_from + args.seeds)),
            )
            out.setdefault(card["id"], {})[sub] = rep[card["id"]]
        linha = " | ".join(
            f"{s}: uso {r['taxa_uso']:.0%} {r['delta_pp']:+.1f}pp {','.join(r['bandeiras'])}"
            for s, r in out[card["id"]].items()
        )
        print(f"{card['id']}: {linha}")
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
