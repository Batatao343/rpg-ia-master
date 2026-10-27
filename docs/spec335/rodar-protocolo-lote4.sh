#!/usr/bin/env bash
# SPEC-335 Lote 4 (Corruptor): protocolo de lote (cada Carta isolada, level_req, 20 sementes, encontro padrao).
# Reproduz docs/spec335/sim-lote4-*.json. Na raiz do repo:  bash docs/spec335/rodar-protocolo-lote4.sh
# O sim.py sai com 1 quando ha bandeira (por design); nao abortar o laco por isso.
for sub in biologia alma inorganica; do
  bash scripts/dev/py.sh scripts/cards/sim.py \
    --lote "data/cards/posturas/corruptor_${sub}.json" \
    --protocolo lote --out "docs/spec335/sim-lote4-${sub}.json" > /dev/null || true
done
