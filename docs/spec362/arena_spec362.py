"""SPEC-362 - diagnostico e arena do balanco do Arcanista (so IMPORTA o avaliador congelado).

    bash scripts/dev/py.sh docs/spec362/arena_spec362.py decompor --seeds 0:20 --out f.json
    bash scripts/dev/py.sh docs/spec362/arena_spec362.py atribuicao --seeds 0:20 --out f.json [--legadas]
    bash scripts/dev/py.sh docs/spec362/arena_spec362.py passo --seeds 0:20 --out f.json --ids a b

`sim.py`, `arena_posturas.py` e `arena_spec341.py` NAO sao tocados (R1). O monkeypatch do
``decompor`` e sempre restaurado no ``finally``.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.getcwd()
sys.path.insert(0, os.path.join(ROOT, "docs", "spec341"))
import arena_spec341 as B  # noqa: E402

from services import card_piles, cards  # noqa: E402

CLS = "Arcanista Cinzento"
SUBS = ["", "calibrado", "descoberto", "improvisador"]
LEVELS = [1, 3, 5]


def _arcanista(seeds: range) -> dict:
    return B.posturas(seeds, {CLS: SUBS})[CLS]


def decompor(seeds: range) -> dict[str, dict]:
    """Tres bracos no mesmo processo: atual / raio_cinza no pool / utilitarias na compra."""
    out: dict[str, dict] = {"atual": _arcanista(seeds)}

    saved_pool = cards.EXEMPLO_FORA_DO_POOL
    cards.EXEMPLO_FORA_DO_POOL = frozenset(saved_pool - {"raio_cinza"})
    try:
        out["com_raio_cinza"] = _arcanista(seeds)
    finally:
        cards.EXEMPLO_FORA_DO_POOL = saved_pool

    orig = card_piles.start_piles

    def start_piles_antigo(player, seed, rng=None):
        """Comportamento anterior ao R11 da 355 so para Cartas do Arcanista."""
        real_get = cards.get_card

        def get_card(cid):
            c = real_get(cid)
            if c and c.get("tipo") == "utilitaria" and c.get("classe") == CLS:
                return {**c, "tipo": "acao"}  # so para o filtro de start_piles
            return c

        card_piles.cards.get_card = get_card
        try:
            return orig(player, seed, rng)
        finally:
            card_piles.cards.get_card = real_get

    card_piles.start_piles = start_piles_antigo
    try:
        out["utilitarias_na_compra"] = _arcanista(seeds)
    finally:
        card_piles.start_piles = orig
    return out


def atribuicao(seeds: range, legadas: bool = False) -> dict:
    """Leave-one-out na leitura TOTAL (padrao+elite), por nivel, por subclasse."""
    cat = cards._load_cards()
    out: dict = {}
    for sub in SUBS:
        sub_key = sub or "todas"
        deck_by_level = {lv: set(B.sim.full_deck(CLS, lv, sub)) for lv in LEVELS}
        base = {
            lv: B.AP.run_arm(CLS, seeds, [lv], ["padrao", "elite"], 4, sub) for lv in LEVELS
        }
        ids = sorted(set().union(*deck_by_level.values()))
        for cid in ids:
            card = cat.get(cid) or {}
            onda = cid.split("_")[0].endswith("1")
            if card.get("basica") or (not onda and not legadas) or card.get("classe") != CLS:
                continue
            row: dict = {"onda": onda, "no_baralho": [lv for lv in LEVELS if cid in deck_by_level[lv]]}
            tot_w = tot_n = pad_w = pad_n = 0
            bw = bn = bpw = bpn = 0
            for lv in row["no_baralho"]:
                saved = cat.pop(cid)
                try:
                    arm = B.AP.run_arm(CLS, seeds, [lv], ["padrao", "elite"], 4, sub)
                finally:
                    cat[cid] = saved
                b = base[lv]
                row[f"L{lv}"] = round((B.AP.rate(b) - B.AP.rate(arm)) * 100, 1)
                bw += sum(v[0] for v in b.values())
                bn += sum(v[1] for v in b.values())
                tot_w += sum(v[0] for v in arm.values())
                tot_n += sum(v[1] for v in arm.values())
                for k, v in b.items():
                    if k.endswith("padrao"):
                        bpw += v[0]
                        bpn += v[1]
                for k, v in arm.items():
                    if k.endswith("padrao"):
                        pad_w += v[0]
                        pad_n += v[1]
            row["total"] = round((bw / bn - tot_w / tot_n) * 100, 1) if bn else 0.0
            row["padrao"] = round((bpw / bpn - pad_w / pad_n) * 100, 1) if bpn else 0.0
            out.setdefault(cid, {})[sub_key] = row
            print(f"[atrib] {sub_key} {cid}: {row}", flush=True)
    return out


def uso(seeds: range) -> dict:
    """Uso real do bot no baralho `todas`: copias no baralho, vezes na mao e jogadas, por nivel."""
    pool = B.AP.A.creatures_by_category()
    out: dict = {}
    for level in LEVELS:
        deck = B.sim.full_deck(CLS, level, "")
        seen: dict = {}
        wins = n_f = 0
        for cat in ("padrao", "elite"):
            size = B.AP.A.group_size(cat, level)
            for bid in B.sim.pick(pool[cat], 4):
                for seed in seeds:
                    o, _ = B.sim.fight(bid, size, CLS, level, seed, B.sim.full_deck(CLS, level, ""), "full", seen)
                    wins += o == "win"
                    n_f += 1
        rows = {}
        for cid in sorted(set(deck)):
            h, j = seen.get(cid, [0, 0])
            rows[cid] = {"copias": deck.count(cid), "na_mao": h, "jogada": j}
        out[f"L{level}"] = {"vitorias": [wins, n_f], "cartas": rows}
    return out


def passo(seeds: range, ids: list[str]) -> dict:
    res: dict = {"seeds": [seeds.start, seeds.stop], "versoes": B.versoes(ids)}
    res["arcanista"] = _arcanista(seeds)
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("decompor")
    a = sp.add_parser("atribuicao")
    a.add_argument("--legadas", action="store_true")
    sp.add_parser("uso")
    p = sp.add_parser("passo")
    p.add_argument("--ids", nargs="*", default=[])
    for s in (d, a, p, sp.choices["uso"]):
        s.add_argument("--seeds", default="0:20")
        s.add_argument("--out")
    args = ap.parse_args(argv)
    rng = B._seeds(args.seeds)
    if args.cmd == "decompor":
        res: dict = decompor(rng)
    elif args.cmd == "atribuicao":
        res = atribuicao(rng, args.legadas)
    elif args.cmd == "uso":
        res = uso(rng)
    else:
        res = passo(rng, args.ids)
    B._write(args.out, res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
