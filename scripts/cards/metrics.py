"""SPEC-336 R6/R7: tabela por Carta (pick rate, jogadas, vitória) a partir dos logs.

    bash scripts/dev/py.sh scripts/cards/metrics.py logs.jsonl [mais.jsonl] \
        [--resultados partidas.json] [--json]

Lê linhas de log estruturado com os eventos ``cards.card_offered|card_picked|
card_played|card_exhausted`` (staging ou playtest). ``--resultados`` é opcional:
``{"<game_ref>": true|false}`` (a partida foi vencida?) — sem ele a coluna de vitória
fica vazia. Regra de corte/ajuste (R7), só com >= ``MIN_OFERTAS`` ofertas:
pick rate < 5 % -> `reescrever_ou_cortar`; > 60 % -> `nerf`. A mudança é sempre uma NOVA
`versao` da Carta (nunca edição silenciosa).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

MIN_OFERTAS = 200
PICK_BAIXO = 0.05
PICK_ALTO = 0.60
EVENTS = ("cards.card_offered", "cards.card_picked", "cards.card_played", "cards.card_exhausted")


def parse_line(line: str) -> dict | None:
    start = line.find("{")
    if start < 0:
        return None
    try:
        obj = json.loads(line[start:])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) and obj.get("event") in EVENTS else None


def aggregate(lines, resultados: dict | None = None) -> dict[str, dict]:
    rows: dict[str, dict] = defaultdict(
        lambda: {"ofertas": 0, "escolhas": 0, "jogadas": 0, "exaustoes": 0, "jogos": set()}
    )
    for line in lines:
        ev = parse_line(line)
        if not ev or not ev.get("card_id"):
            continue
        row = rows[str(ev["card_id"])]
        name = ev["event"]
        if name == "cards.card_offered":
            row["ofertas"] += 1
            if ev.get("picked") is True:
                row["escolhas"] += 1  # a escolha também chega como card_picked; só conta 1×
        elif name == "cards.card_played":
            row["jogadas"] += 1
            if ev.get("game_ref"):
                row["jogos"].add(str(ev["game_ref"]))
        elif name == "cards.card_exhausted":
            row["exaustoes"] += 1
    out: dict[str, dict] = {}
    for cid, row in sorted(rows.items()):
        jogos = row["jogos"]
        pick = (row["escolhas"] / row["ofertas"]) if row["ofertas"] else None
        venceu = None
        if resultados and jogos:
            conhecidos = [resultados[g] for g in jogos if g in resultados]
            venceu = (
                round(sum(1 for v in conhecidos if v) / len(conhecidos), 3) if conhecidos else None
            )
        acao = ""
        if pick is not None and row["ofertas"] >= MIN_OFERTAS:
            if pick < PICK_BAIXO:
                acao = "reescrever_ou_cortar"
            elif pick > PICK_ALTO:
                acao = "nerf"
        out[cid] = {
            "ofertas": row["ofertas"],
            "escolhas": row["escolhas"],
            "pick_rate": None if pick is None else round(pick, 3),
            "jogadas": row["jogadas"],
            "exaustoes": row["exaustoes"],
            "jogos": len(jogos),
            "vitoria": venceu,
            "acao": acao,
        }
    return out


def render(table: dict[str, dict]) -> str:
    head = "| Carta | Ofertas | Escolhas | Pick rate | Jogadas | Jogos | Vitória | Ação |\n|---|---|---|---|---|---|---|---|\n"
    body = ""
    for cid, r in table.items():
        pick = "-" if r["pick_rate"] is None else f"{r['pick_rate']:.0%}"
        vit = "-" if r["vitoria"] is None else f"{r['vitoria']:.0%}"
        body += f"| {cid} | {r['ofertas']} | {r['escolhas']} | {pick} | {r['jogadas']} | {r['jogos']} | {vit} | {r['acao']} |\n"
    return head + body


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--resultados")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    resultados = None
    if args.resultados:
        with open(args.resultados, encoding="utf-8") as f:
            resultados = json.load(f)

    def lines():
        for path in args.logs:
            with open(path, encoding="utf-8", errors="replace") as f:
                yield from f

    table = aggregate(lines(), resultados)
    print(json.dumps(table, ensure_ascii=False, indent=1) if args.json else render(table))
    return 0


if __name__ == "__main__":
    sys.exit(main())
