#!/usr/bin/env bash
# SPEC-335 Lote 3 (Devoto): protocolo de lote (cada Carta isolada, level_req, 20 sementes, encontro padrao).
# Reproduz docs/spec335/sim-lote3-*.json. Na raiz do repo:  bash docs/spec335/rodar-protocolo-lote3.sh
set -e
for sub in consagrado zeloso enlutado; do
  bash scripts/dev/py.sh scripts/cards/sim.py \
    --lote "data/cards/posturas/devoto_${sub}.json" \
    --protocolo lote --out "docs/spec335/sim-lote3-${sub}.json" > /dev/null
done
