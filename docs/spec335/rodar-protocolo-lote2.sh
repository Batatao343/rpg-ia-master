#!/usr/bin/env bash
# SPEC-335 Lote 2 (Sangromante): protocolo de lote (cada Carta isolada, level_req, 20 sementes, encontro padrao).
# Reproduz docs/spec335/sim-lote2-*.json. Na raiz do repo:  bash docs/spec335/rodar-protocolo-lote2.sh
set -e
for sub in exposto avaro silencioso; do
  bash scripts/dev/py.sh scripts/cards/sim.py \
    --lote "data/cards/posturas/sangromante_${sub}.json" \
    --protocolo lote --out "docs/spec335/sim-lote2-${sub}.json" > /dev/null
done
