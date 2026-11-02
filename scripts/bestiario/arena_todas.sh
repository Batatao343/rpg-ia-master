#!/usr/bin/env bash
# SPEC-349 R26: arena final (40 seeds, off e on) de todas as regiões, em série (uma por vez: RAM).
# Uso: bash scripts/bestiario/arena_todas.sh [seeds]
set -u
SEEDS="${1:-40}"
cd "$(git rev-parse --show-toplevel)"
for r in nova_arcadia pantano_melancolia pradaria_ruinas brekmar deserto_zhur costa_negra \
         montanhas_afiadas floresta_sussurros selva_xylos skallgard aethelgard ophidia; do
  bash scripts/dev/py.sh scripts/bestiario/arena.py --regiao "$r" --seeds "$SEEDS" \
    --baseline docs/spec349/arena-slots-baseline.json \
    --json "docs/spec349/arena-$r.json" --md "docs/spec349/arena-$r.md" > "/tmp/arena_$r.log" 2>&1
  echo "$r: $(grep -c '^OK' "/tmp/arena_$r.log") ok / $(grep -c '^FORA' "/tmp/arena_$r.log") fora"
done
