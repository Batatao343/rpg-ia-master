"""SPEC-346 Etapa 8 - arena por Postura com a emboscada (D4): inimigos agem primeiro na rodada 1.

Usa o avaliador congelado da SPEC-341 SEM alterá-lo; só embrulha ``run_round`` para forçar
``initiator="enemy"`` na 1ª rodada de cada simulação (pior caso: toda luta é uma emboscada,
inclusive nos níveis 1-2, onde a proteção de herói novo daria a iniciativa ao jogador).

    bash scripts/dev/py.sh docs/spec346/arena_spec346.py --seeds 20:100 --out docs/spec346/arena-ambush.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.getcwd()
sys.path.insert(0, os.path.join(ROOT, "docs", "spec341"))
import arena_spec341 as B  # noqa: E402

from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402

_orig = orch.run_round


def _ambush_round(scene, actors, sides, state=None, **kw):
    if cs.tactical_round(scene) == 0:
        kw["initiator"] = "enemy"
    return _orig(scene, actors, sides, state, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="20:100")
    ap.add_argument("--classes", nargs="*")
    ap.add_argument("--out")
    args = ap.parse_args()
    orch.run_round = _ambush_round
    rng = B._seeds(args.seeds)
    res = {"seeds": [rng.start, rng.stop], "cenario": "emboscada: inimigos primeiro na rodada 1"}
    res["posturas"] = B.posturas(rng, B._classes_arg(args.classes))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
