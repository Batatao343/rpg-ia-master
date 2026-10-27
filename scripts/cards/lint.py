"""SPEC-336 R3: lint determinístico de um lote de Cartas.

    bash scripts/dev/py.sh scripts/cards/lint.py data/cards/_rascunhos/<lote>.json [--sem-momento] [--json]

Fonte única das regras: ``services/card_lint.py`` (o CI roda as mesmas via
``scripts/validate_content.py``). Exit 1 se houver qualquer ERRO.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services import card_lint  # noqa: E402


def run(path: str, *, exigir_momento: bool = True, embed=None) -> dict:
    batch = card_lint.load_batch(path)
    pool = card_lint.load_pool()
    result = card_lint.lint_batch(batch, pool, exigir_momento=exigir_momento, embed=embed)
    wave = card_lint.lint_wave(batch)
    return {
        "cartas": len(batch),
        "verdes": sorted(cid for cid, iss in result.items() if not card_lint.errors(iss)),
        "reprovadas": {
            cid: [str(i) for i in iss] for cid, iss in result.items() if card_lint.errors(iss)
        },
        "avisos": {
            cid: [str(i) for i in iss if i.level == "warn"]
            for cid, iss in result.items()
            if any(i.level == "warn" for i in iss)
        },
        "onda": [str(i) for i in wave],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("lote")
    ap.add_argument(
        "--sem-momento", action="store_true", help="não exige `momento` (acervo legado)"
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    report = run(args.lote, exigir_momento=not args.sem_momento)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(
            f"{report['cartas']} cartas: {len(report['verdes'])} verdes, {len(report['reprovadas'])} reprovadas"
        )
        for cid, msgs in report["reprovadas"].items():
            print(f"- {cid}")
            for m in msgs:
                print(f"    {m}")
        for m in report["onda"]:
            print(f"- onda: {m}")
    return 1 if report["reprovadas"] or report["onda"] else 0


if __name__ == "__main__":
    sys.exit(main())
