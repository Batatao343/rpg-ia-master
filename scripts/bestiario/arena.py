"""SPEC-349 R26: arena por criatura de uma região (offline, MockLLM, seeded).

Reproduzir:
    bash scripts/dev/py.sh scripts/bestiario/arena.py --regiao nova_arcadia --seeds 40 \
        --md docs/spec349/arena-nova_arcadia.md --json docs/spec349/arena-nova_arcadia.json

Reaproveita a arena da SPEC-285 (mesmo herói da esteira do playtest, mesmo encontro "piso"
por categoria, ``run_round``, bot "cartas") pelo recorte da SPEC-332 (``fight``). Para cada
criatura da região mede a vitória do herói nas 5 Posturas, com ``RPG_ENEMY_DECKS=off`` e ``on``.

Critério (D11): 45-85 % por criatura nos dois modos; para reinventadas/adotadas, |delta| <= 8 pp
contra o slot ANTES (``--baseline``: JSON gerado por este mesmo script antes de a mecânica
mudar, nas mesmas seeds). Nível-alvo único: lacaio/padrão/elite L3 e chefe L5 (L1 não discrimina: 1 lacaio contra herói
de L1 vence ~100 %, mesmo nos controles do legado).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

os.environ["RPG_FORCE_MOCK"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

_spec = importlib.util.spec_from_file_location(
    "arena332", ROOT / "docs" / "spec332" / "arena_familias.py"
)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)  # type: ignore[union-attr]
A = M.A

from services import bestiary_lint as bl  # noqa: E402

LEVELS = {"lacaio": (3,), "padrao": (3,), "elite": (3,), "chefe": (5,)}
FAIXA = (0.45, 0.85)
DELTA_MAX_PP = 8.0


def medir(bid: str, categoria: str, seeds: int, modos: list[str]) -> dict:
    out: dict = {}
    for level in LEVELS[categoria]:
        n = A.group_size(categoria, level)
        for modo in modos:
            wins = fights = 0
            for cls in A.CLASSES:
                for seed in range(seeds):
                    outcome, _ = M.fight(bid, n, cls, level, seed, modo)
                    fights += 1
                    wins += outcome == "win"
            out[f"L{level}|{modo}"] = round(wins / fights, 3)
    os.environ.pop("RPG_ENEMY_DECKS", None)
    return out


def veredito(cells: dict, base: dict | None) -> tuple[bool, list[str]]:
    motivos = []
    for key, w in cells.items():
        if not FAIXA[0] <= w <= FAIXA[1]:
            motivos.append(f"{key} {w:.0%} fora de 45-85%")
        # o delta só vale quando o slot ANTES estava na faixa (senão a faixa manda, D11)
        if (
            base
            and key in base
            and FAIXA[0] <= base[key] <= FAIXA[1]
            and round(abs(w - base[key]) * 100, 1) > DELTA_MAX_PP
        ):
            motivos.append(f"{key} delta {abs(w - base[key]) * 100:.1f} pp > {DELTA_MAX_PP:.0f}")
    return (not motivos), motivos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--regiao", default="nova_arcadia")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--modo", default="off,on")
    ap.add_argument("--ids", default="", help="só estes ids (separados por vírgula)")
    ap.add_argument("--json", help="grava o resultado bruto")
    ap.add_argument("--baseline", help="JSON do slot ANTES (mesmas seeds) para o delta")
    ap.add_argument("--md", help="grava o relatório Markdown (R26)")
    args = ap.parse_args(argv)

    modos = args.modo.split(",")
    fichas = [f for f in bl.load_fichas(args.regiao).values() if f.get("status") != "retro"]
    if args.ids:  # ids fora das fichas (controle: criaturas do legado) usam o bestiário
        keep = args.ids.split(",")
        por_id = {f["id"]: f for f in fichas}
        best = json.loads((ROOT / "data" / "bestiary.json").read_text(encoding="utf-8"))
        fichas = [
            por_id.get(i)
            or {
                "id": i,
                "nome": best[i]["name"],
                "categoria": best[i]["categoria"],
                "status": "controle",
            }
            for i in keep
        ]
    base_all = json.loads(Path(args.baseline).read_text(encoding="utf-8")) if args.baseline else {}
    t0 = time.time()
    res: dict = {}
    for f in fichas:
        bid, cat = f["id"], f["categoria"]
        cells = medir(bid, cat, args.seeds, modos)
        base = (base_all.get("criaturas") or {}).get(bid) if f.get("substitui") else None
        ok, motivos = veredito(cells, base.get("cells") if base else None)
        res[bid] = {
            "nome": f["nome"],
            "categoria": cat,
            "status": f["status"],
            "cells": cells,
            "ok": ok,
            "motivos": motivos,
        }
        print(f"{'OK ' if ok else 'FORA'} {bid:38s} {cells} {motivos}", flush=True)
    payload = {
        "regiao": args.regiao,
        "seeds": args.seeds,
        "heroes": list(A.CLASSES),
        "elapsed_s": round(time.time() - t0, 1),
        "criaturas": res,
    }
    if args.json:
        Path(args.json).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    if args.md:
        Path(args.md).write_text(relatorio(payload, base_all), encoding="utf-8")
    return 0 if all(r["ok"] for r in res.values()) else 1


def relatorio(payload: dict, base_all: dict) -> str:
    keys = sorted({k for r in payload["criaturas"].values() for k in r["cells"]})
    linhas = [
        f"# Arena SPEC-349 - {payload['regiao']}",
        "",
        f"{payload['seeds']} seeds x {len(payload['heroes'])} Posturas por célula; MockLLM; "
        f"herói da esteira do playtest; bot `cartas`. Faixa 45-85 %; reinventadas com |delta| <= "
        f"{DELTA_MAX_PP:.0f} pp contra o slot antes. Gerado por `scripts/bestiario/arena.py`.",
        "",
        "| Criatura | Cat. | Status | " + " | ".join(keys) + " | Delta vs slot antes | OK |",
        "|---|---|---|" + "---|" * len(keys) + "---|---|",
    ]
    for bid, r in payload["criaturas"].items():
        base = (base_all.get("criaturas") or {}).get(bid)
        if base and r["status"] != "nova":
            deltas = [
                f"{k}: {(r['cells'][k] - base['cells'][k]) * 100:+.1f}"
                for k in keys
                if k in r["cells"] and k in base["cells"]
            ]
            delta = "; ".join(deltas)
        else:
            delta = "-"
        cels = " | ".join(f"{r['cells'][k]:.0%}" if k in r["cells"] else "-" for k in keys)
        linhas.append(
            f"| {r['nome']} (`{bid}`) | {r['categoria']} | {r['status']} | {cels} | {delta} | "
            f"{'sim' if r['ok'] else 'NAO: ' + '; '.join(r['motivos'])} |"
        )
    return "\n".join(linhas) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
