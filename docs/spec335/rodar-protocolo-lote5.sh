#!/usr/bin/env bash
# SPEC-335 Lote 5 (Medico de Campo): protocolo de lote (cada Carta isolada, level_req, 20 sementes, encontro padrao).
# Reproduz docs/spec335/sim-lote5-*.json e a taxa da Postura (antes x depois). Na raiz do repo:
#   bash docs/spec335/rodar-protocolo-lote5.sh
# O sim.py sai com 1 quando ha bandeira (por design); nao abortar o laco por isso.
for sub in cirurgiao_trincheira boticario cirurgiao_ferro; do
  bash scripts/dev/py.sh scripts/cards/sim.py \
    --lote "data/cards/posturas/medico_${sub}.json" \
    --protocolo lote --out "docs/spec335/sim-lote5-${sub}.json" > /dev/null || true
done
# Taxa de vitoria da Postura (baralho completo, L1/L3/L5, padrao+elite, 4 criaturas, 20 sementes).
bash scripts/dev/py.sh docs/spec335/arena_postura_medico.py 20 --out docs/spec335/sim-lote5-postura.json > /dev/null
