#!/usr/bin/env bash
# SPEC-335 Lote 1: protocolo de lote (cada Carta isolada, level_req, 20 sementes, encontro padrao).
# Reproduz docs/spec335/sim-lote1-*.json. Na raiz do repo:  bash docs/spec335/rodar-protocolo-lote1.sh
set -e
for sub in calibrado descoberto improvisador; do
  bash scripts/dev/py.sh scripts/cards/sim.py \
    --lote "data/cards/posturas/arcanista_cinzento_${sub}.json" \
    --protocolo lote --out "docs/spec335/sim-lote1-${sub}.json" > /dev/null
done
