"""SPEC-373 Etapa 0: snapshot R2 (ensure_combat_sheet off, por hash) e baralhos 332 (on, sementes 0-11).

Gera docs/spec373/base/snapshot-off.json e deck-332-main.json. Rodar na main (antes do R9).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["RPG_FORCE_MOCK"] = "1"


def main() -> None:
    from agents.bestiary import load_bestiary
    from services import conflict_orchestrator as orch
    from services import enemy_decks as edk

    out = ROOT / "docs/spec373/base"
    bestiary = load_bestiary()
    os.environ["RPG_ENEMY_DECKS"] = "off"
    snap = {}
    for bid, entry in sorted(bestiary.items()):
        sheet = orch.ensure_combat_sheet({**json.loads(json.dumps(entry)), "id": bid})
        blob = json.dumps(sheet, sort_keys=True, ensure_ascii=False, default=str)
        snap[bid] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    (out / "snapshot-off.json").write_text(json.dumps(snap, indent=0, sort_keys=True), "utf-8")
    os.environ["RPG_ENEMY_DECKS"] = "on"
    decks = {}
    for bid, entry in sorted(bestiary.items()):
        if entry.get("cartas_autorais"):
            continue
        decks[bid] = [edk.build_enemy_deck({**entry, "id": bid}, s) for s in range(12)]
    (out / "deck-332-main.json").write_text(json.dumps(decks, sort_keys=True), "utf-8")
    print(len(snap), len(decks))


if __name__ == "__main__":
    main()
