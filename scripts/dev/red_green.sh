#!/usr/bin/env bash
# Reproduz o vermelho->verde dos testes novos da spec (SPEC-415 R18).
#   bash scripts/dev/red_green.sh NNN [--allow-green <nodeid>]... [--equivalence]
exec bash "$(dirname "${BASH_SOURCE[0]}")/py.sh" "$(dirname "${BASH_SOURCE[0]}")/red_green.py" "$@"
