"""Relatório determinístico de cobertura autoral (spec conflito-17)."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.codex_loader import parse_codex_file


ROOT = Path(__file__).resolve().parents[1]
CLASS_FILES = ("devoto", "sangromante", "corruptor", "arcanista", "medico")


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def coverage() -> dict:
    cards = []
    for slug in CLASS_FILES:
        cards.extend(_json(ROOT / "data" / "cards" / f"{slug}.json")["cards"])
    enemy_cards = _json(ROOT / "data" / "cards" / "bestiario.json")["cards"]
    bestiary = _json(ROOT / "data" / "bestiary.json")

    card_rows = defaultdict(Counter)
    for card in cards:
        combo = f"{card['classe']}/{card.get('subclasse') or 'tronco'}"
        card_rows[combo][card.get("patamar", "?")] += 1
        card_rows[combo][f"tipo:{card.get('tipo', '?')}"] += 1

    creature_rows = defaultdict(Counter)
    for creature in bestiary.values():
        for region in creature.get("regions") or ["sem_regiao"]:
            creature_rows[region][f"cat:{creature.get('categoria', '?')}"] += 1
            creature_rows[region][f"arq:{creature.get('arquetipo', '?')}"] += 1

    npc_rows = Counter()
    npc_dir = ROOT / "data" / "codex" / "npcs" / "mundo_vivo"
    if npc_dir.exists():
        for path in npc_dir.glob("*.md"):
            fm, _body = parse_codex_file(str(path))
            npc_rows[str(fm.get("home_location_id", "sem_regiao"))] += 1

    return {
        "cards_total": len(cards),
        "enemy_cards_total": len(enemy_cards),
        "cards": dict(card_rows),
        "creatures_total": len(bestiary),
        "creatures": dict(creature_rows),
        "npcs_total": sum(npc_rows.values()),
        "npcs": dict(npc_rows),
    }


def main() -> int:
    report = coverage()
    print("CARTAS POR CLASSE/SUBCLASSE/PATAMAR")
    print(f"total jogador={report['cards_total']} inimigo={report['enemy_cards_total']}")
    for combo, counts in sorted(report["cards"].items()):
        print(f"- {combo}: {dict(sorted(counts.items()))}")

    print("\nCRIATURAS POR REGIÃO/CATEGORIA/ARQUÉTIPO")
    print(f"total={report['creatures_total']}")
    for region, counts in sorted(report["creatures"].items()):
        print(f"- {region}: {dict(sorted(counts.items()))}")

    print("\nNPCS POR REGIÃO")
    print(f"total novo={report['npcs_total']}")
    for region, count in sorted(report["npcs"].items()):
        print(f"- {region}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
