"""SPEC-336 R8: painel `docs/cartas/PAINEL.md` — contagem do acervo (gerado).

    bash scripts/dev/py.sh scripts/cards/painel.py [--stdout]

Contagem de Cartas de jogador por Postura, raridade, tier, kind e palavra-chave, mais
as metas da cadência (1 onda/mês, +60 de jogador e +20 de inimigo por onda).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services import card_effects as fx  # noqa: E402
from services import card_lint  # noqa: E402

META_JOGADOR_POR_ONDA = 60
META_INIMIGO_POR_ONDA = 20
META_12_MESES = 1200
OUT = os.path.join("docs", "cartas", "PAINEL.md")


def _table(title: str, counter: Counter) -> str:
    rows = "\n".join(
        f"| {k} | {v} |" for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))
    )
    return f"### {title}\n\n| Valor | Cartas |\n|---|---|\n{rows}\n"


def build(pool: list[dict] | None = None) -> str:
    pool = card_lint._vigente(pool if pool is not None else card_lint.load_pool())
    jogador = [
        c
        for c in pool
        if c.get("classe") not in ("Inimigo", "", None) and c.get("tipo") != "virtude"
    ]
    inimigo = [c for c in pool if c.get("classe") == "Inimigo"]
    kinds: Counter = Counter()
    kws: Counter = Counter()
    for c in jogador:
        for k in {str(e.get("kind")) for e in fx.normalize(c)}:
            kinds[k] += 1
        for k in fx.card_keyword_ids(c):
            kws[k] += 1
    ondas = Counter(int(c["onda"]) for c in jogador if isinstance(c.get("onda"), int))
    parts = [
        "# Painel do acervo de Cartas\n",
        "> Gerado por `scripts/cards/painel.py` (SPEC-336). Não edite à mão.\n",
        f"- Cartas de jogador: **{len(jogador)}** (meta de 12 meses: ~{META_12_MESES}).",
        f"- Cartas de inimigo: **{len(inimigo)}**.",
        f"- Meta por onda mensal: +{META_JOGADOR_POR_ONDA} de jogador e +{META_INIMIGO_POR_ONDA} de inimigo (cortes permitidos).\n",
        _table("Por Postura", Counter(str(c.get("classe")) for c in jogador)),
        _table("Por raridade", Counter(c.get("raridade") or fx.raridade(c) for c in jogador)),
        _table("Por tier", Counter(int(c.get("tier", 0) or 0) for c in jogador)),
        _table("Por kind de efeito", kinds),
        _table("Por palavra-chave", kws),
        _table("Por onda (cartas com `onda`)", ondas) if ondas else "",
    ]
    return "\n".join(p for p in parts if p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args(argv)
    text = build()
    if args.stdout:
        print(text)
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"escrito {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
