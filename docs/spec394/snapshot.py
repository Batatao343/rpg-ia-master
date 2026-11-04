"""SPEC-394 R6: snapshot por hash de ensure_combat_sheet (off) e baralho (on, sementes 0-11).

Uso: bash scripts/dev/py.sh docs/spec394/snapshot.py --out docs/spec394/base-snapshot.json
Versao enxuta de docs/spec373/snapshot_base.py, com --out e --excluir.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["RPG_FORCE_MOCK"] = "1"


def _hash(obj: object) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def gerar(excluir: set[str]) -> dict[str, dict[str, str]]:
    from agents.bestiary import load_bestiary
    from services import conflict_orchestrator as orch
    from services import enemy_decks as edk

    bestiary = {k: v for k, v in sorted(load_bestiary().items()) if k not in excluir}
    snap: dict[str, dict[str, str]] = {}
    os.environ["RPG_ENEMY_DECKS"] = "off"
    for bid, entry in bestiary.items():
        sheet = orch.ensure_combat_sheet({**json.loads(json.dumps(entry)), "id": bid})
        snap[bid] = {"off": _hash(sheet)}
    os.environ["RPG_ENEMY_DECKS"] = "on"
    for bid, entry in bestiary.items():
        if entry.get("cartas_autorais"):
            continue
        decks = [edk.build_enemy_deck({**entry, "id": bid}, s) for s in range(12)]
        snap[bid]["on"] = _hash(decks)
    return snap


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--excluir", default="", help="ids separados por virgula")
    args = ap.parse_args()
    excluir = {x for x in args.excluir.split(",") if x}
    snap = gerar(excluir)
    Path(args.out).write_text(json.dumps(snap, indent=0, sort_keys=True), "utf-8")
    print(len(snap))


if __name__ == "__main__":
    main()
