"""SPEC-360 R4: CLI do lint de fauna (`services/fauna_lint.py` e a fonte unica das regras).

Uso: `bash scripts/dev/py.sh scripts/fauna/lint.py [--regiao nova_arcadia]`.
Sem `--regiao`, roda todas as regioes com `data/bestiario/fauna/<regiao>.yaml`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from services import fauna_lint as fl

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--regiao", action="append", default=None)
    args = ap.parse_args(argv)
    regions = args.regiao or fl.covered_regions()
    total = 0
    for region in regions:
        errs = fl.lint_file(region)
        total += len(errs)
        print(f"{region}: {len(errs)} erro(s)")
        for e in errs:
            print(f"  {e}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
