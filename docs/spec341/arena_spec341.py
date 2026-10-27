"""SPEC-341 — diagnostico e arena do balanco de Cartas (so IMPORTA o avaliador congelado).

    bash scripts/dev/py.sh docs/spec341/arena_spec341.py posturas --seeds 0:20 \
        [--classes "Sangromante" "Corruptor:alma"] [--compare docs/spec339/arena-depois.json] [--out f.json]
    bash scripts/dev/py.sh docs/spec341/arena_spec341.py atribuicao --sub avaro --levels 1,3,5 \
        --seeds 0:20 [--cls Sangromante] [--out f.json]
    bash scripts/dev/py.sh docs/spec341/arena_spec341.py cartas --seeds 20:100 --ids a b c [--out f.json]

`scripts/cards/sim.py` e `docs/spec335/arena_posturas.py` NAO sao tocados (R1).
O relatorio (`RELATORIO.md`) e escrito a mao a partir dos JSON gerados.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

os.environ.setdefault("RPG_FORCE_MOCK", "1")
ROOT = os.getcwd()
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "cards"))
sys.path.insert(0, os.path.join(ROOT, "docs", "spec335"))
import arena_neutras_lote6 as AN  # noqa: E402
import arena_posturas as AP  # noqa: E402
import sim  # noqa: E402

from services import card_lint, cards  # noqa: E402


def _seeds(txt: str) -> range:
    a, b = txt.split(":")
    return range(int(a), int(b))


def _arm_out(arm: dict) -> dict:
    return {
        "celulas": arm,
        "total": AP.rate(arm),
        "padrao": AP.rate(arm, ("padrao",)),
        "elite": AP.rate(arm, ("elite",)),
    }


def posturas(seeds: range, classes: dict[str, list[str]]) -> dict:
    """``classes``: {Postura: [subclasses]}; '' = todas as subclasses (chave ``todas``)."""
    res: dict = {}
    for cls, subs in classes.items():
        res[cls] = {}
        for sub in subs:
            arm = AP.run_arm(cls, seeds, [1, 3, 5], ["padrao", "elite"], 4, sub)
            res[cls][sub or "todas"] = _arm_out(arm)
            print(f"[posturas] {cls}/{sub or 'todas'}: {AP.rate(arm):.1%}", flush=True)
    return res


def _padrao_level(cls: str, sub: str, level: int, seeds: range) -> float:
    arm = AP.run_arm(cls, seeds, [level], ["padrao"], 4, sub)
    return AP.rate(arm, ("padrao",))


def leave_one_out(cls: str, sub: str, levels: list[int], seeds: range) -> dict[str, dict]:
    """{card_id: {"L1": dpp, ...}} onde dpp = baseline - (sem a Carta), em pontos percentuais:
    positivo = a Carta AJUDA a vencer (tirar baixa a taxa). Cartas fora do baralho do nivel = 0."""
    cat = cards._load_cards()
    base = {lv: _padrao_level(cls, sub, lv, seeds) for lv in levels}
    deck_by_level = {lv: set(sim.full_deck(cls, lv, sub)) for lv in levels}
    out: dict[str, dict] = {}
    pool = {
        c["id"]: c
        for c in cards.cards_for_class(cls, sub)
        if c.get("tipo") in cards._DECK_TIPOS and not c.get("apex")
    }
    for cid, card in pool.items():
        row: dict = {
            "origem": "onda" if cid.split("_")[0].endswith("1") else "legada",
            "level_req": int(card.get("level_req", 1) or 1),
        }
        for lv in levels:
            if cid not in deck_by_level[lv]:
                row[f"L{lv}"] = 0.0
                continue
            saved = cat.pop(cid)
            try:
                without = _padrao_level(cls, sub, lv, seeds)
            finally:
                cat[cid] = saved
            row[f"L{lv}"] = round((base[lv] - without) * 100, 1)
        row["padrao"] = round(sum(row[f"L{lv}"] for lv in levels) / len(levels), 1)
        out[cid] = row
        print(f"[atrib] {sub} {cid}: {row}", flush=True)
    out["_baseline"] = {f"L{lv}": base[lv] for lv in levels}
    return out


def _all_cards() -> dict[str, tuple[dict, str, list[dict]]]:
    """id -> (carta, arquivo, lote do arquivo)."""
    out = {}
    for path in sorted(glob.glob("data/cards/**/*.json", recursive=True)):
        if os.path.basename(path).startswith("_"):
            continue
        try:
            batch = card_lint.load_batch(path)
        except Exception:
            continue
        for c in batch:
            out[c["id"]] = (c, path.replace("\\", "/"), batch)
    return out


def cartas(seeds: range, ids: list[str]) -> dict:
    allc = _all_cards()
    res: dict = {}
    seed_list = list(seeds)
    for cid in ids:
        card, path, batch = allc[cid]
        base = cards._load_cards()
        if path.endswith("valoria_neutras.json"):
            por = {}
            for key, (classe, sub) in AN.BARALHOS.items():
                v = AN.variante(card, classe, sub)
                lv = max(int(v.get("level_req", 1) or 1), 1)
                por[key] = sim.simulate_batch(
                    [v],
                    [lv],
                    sim.PROTOCOLO_LOTE["categories"],
                    sim.PROTOCOLO_LOTE["per_cat"],
                    seed_list,
                )[cid]
            res[cid] = por
            print(
                f"[cartas] {cid}: "
                + str({k: (v["delta_pp"], v["bandeiras"]) for k, v in por.items()}),
                flush=True,
            )
            continue
        if "/posturas/" in path:
            ids_lote = {c["id"] for c in batch}
            saved = {i: base.pop(i) for i in ids_lote - {cid} if i in base}
            try:
                lv = max(int(card.get("level_req", 1) or 1), 1)
                res[cid] = sim.simulate_batch(
                    [card],
                    [lv],
                    sim.PROTOCOLO_LOTE["categories"],
                    sim.PROTOCOLO_LOTE["per_cat"],
                    seed_list,
                )[cid]
            finally:
                base.update(saved)
        else:  # legada: protocolo default da 339 (niveis 1,3,5, padrao, 4 criaturas)
            res[cid] = sim.simulate_batch([card], [1, 3, 5], ["padrao"], 4, seed_list)[cid]
        r = res[cid]
        print(
            f"[cartas] {cid}: uso {r['taxa_uso']:.0%} d {r['delta_pp']:+.1f}pp {r['bandeiras']}",
            flush=True,
        )
    return res


def versoes(ids: list[str]) -> dict[str, int]:
    allc = _all_cards()
    return {i: int(allc[i][0].get("versao", 1) or 1) for i in ids}


def _write(path: str | None, obj: dict) -> None:
    if path:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def _classes_arg(items: list[str] | None) -> dict[str, list[str]]:
    if not items:
        return {k: ["", *v] for k, v in AP.POSTURAS.items()}
    out: dict[str, list[str]] = {}
    for it in items:
        cls, _, sub = it.partition(":")
        if sub:
            out.setdefault(cls, []).append(sub)
        else:
            out[cls] = ["", *AP.POSTURAS[cls]]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("posturas")
    p.add_argument("--seeds", default="0:20")
    p.add_argument("--classes", nargs="*")
    p.add_argument("--compare")
    p.add_argument("--versoes", nargs="*", default=[])
    p.add_argument("--out")
    a = sp.add_parser("atribuicao")
    a.add_argument("--cls", default="Sangromante")
    a.add_argument("--sub", required=True)
    a.add_argument("--levels", default="1,3,5")
    a.add_argument("--seeds", default="0:20")
    a.add_argument("--out")
    c = sp.add_parser("cartas")
    c.add_argument("--seeds", default="20:100")
    c.add_argument("--ids", nargs="+", required=True)
    c.add_argument("--out")
    args = ap.parse_args(argv)
    if args.cmd == "posturas":
        rng = _seeds(args.seeds)
        res: dict = {"seeds": [rng.start, rng.stop], "versoes": versoes(args.versoes)}
        res["posturas"] = posturas(rng, _classes_arg(args.classes))
        if args.compare:
            ref = json.load(open(args.compare, encoding="utf-8"))["posturas"]
            bad = [
                f"{k}/{s}/{cell}"
                for k, subs in res["posturas"].items()
                for s, v in subs.items()
                for cell, val in v["celulas"].items()
                if ref[k][s]["celulas"][cell] != val
            ]
            print("COMPARE:", "IDENTICO" if not bad else f"DIVERGE {bad}")
        _write(args.out, res)
    elif args.cmd == "atribuicao":
        levels = [int(x) for x in args.levels.split(",")]
        _write(args.out, leave_one_out(args.cls, args.sub, levels, _seeds(args.seeds)))
    else:
        rng = _seeds(args.seeds)
        res = {"seeds": [rng.start, rng.stop], "versoes": versoes(args.ids)}
        res["cartas"] = cartas(rng, args.ids)
        _write(args.out, res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
