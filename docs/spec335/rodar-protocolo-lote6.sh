#!/usr/bin/env bash
# SPEC-335 Lote 6 (40 neutras + 16 Cartas de tronco): arena. Na raiz do repo:
#   bash docs/spec335/rodar-protocolo-lote6.sh
# Neutras: cada Carta vira variante de 2 baralhos (Devoto/consagrado e Arcanista/calibrado).
bash scripts/dev/py.sh docs/spec335/arena_neutras_lote6.py --out docs/spec335/sim-lote6.json > /dev/null
# Confirmacao das Cartas perto de +8 pp (sementes 20-99, 320 lutas por braco).
bash scripts/dev/py.sh docs/spec335/arena_neutras_lote6.py --seed-from 20 --seeds 80 \
  --only neu1_br_sabre_de_pirata,neu1_er_aguardente_de_liquen,neu1_br_arpao_de_osso,neu1_sb_corda_de_aranha,neu1_ka_guarda_de_sangue,neu1_er_traje_branco,neu1_br_madeira_de_naufragio,neu1_br_grogue_do_porto,neu1_ka_residuo_sanguineo,neu1_ge_cataplasma_de_resina,neu1_er_emboscada_dos_renegados,neu1_ge_nectar_da_furia,neu1_sb_pavor_do_fundo \
  --out docs/spec335/sim-lote6-confirmacao-sementes20-99.json > /dev/null
# Tronco (R6): por subclasse, 20 sementes e confirmacao 20-99.
bash scripts/dev/py.sh docs/spec335/confirmar_tronco_lote6.py --out docs/spec335/sim-lote6-tronco.json > /dev/null
bash scripts/dev/py.sh docs/spec335/confirmar_tronco_lote6.py --seed-from 20 --seeds 80 \
  --out docs/spec335/sim-lote6-tronco-confirmacao-sementes20-99.json > /dev/null
