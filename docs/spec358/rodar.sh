#!/usr/bin/env bash
# SPEC-358: comandos exatos do reprocessamento (na raiz do repo, um processo por vez).
# 0. golden do v1 (ja commitado; so regenerar com o sim.py intocado, em spec propria):
#    bash scripts/dev/py.sh docs/spec358/gerar_golden_v1.py
# 1. equivalencia completa do v1 (main x novo, 15 arquivos, sementes 0-19):
bash scripts/dev/py.sh docs/spec358/equivalencia_v1.py
# 2. reprocessamento v2 (sementes 0-19), confirmacao (20-99), controle R15, relatorio:
bash scripts/dev/py.sh docs/spec358/arena_v2.py --fase 1
bash scripts/dev/py.sh docs/spec358/arena_v2.py --fase 2
bash scripts/dev/py.sh docs/spec358/arena_v2.py --fase 3
bash scripts/dev/py.sh docs/spec358/arena_v2.py --fase relatorio
