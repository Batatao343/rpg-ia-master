#!/usr/bin/env bash
# Pytest enxuto para agentes (SPEC-386 R4). Log completo em arquivo; na tela só falhas + resumo.
#   bash scripts/dev/pt.sh tests/test_x.py [-k nome] [--lf]
# -n 2 por padrão (regra de RAM); passe -n 0 para serial. Sem -q extra: o pyproject já põe -q.
# PT_LINES muda o teto da saída (padrão 60). Código de saída = o do pytest.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"
log="${TMPDIR:-${TEMP:-/tmp}}/rpg-pt-$$.log"
xdist=(-n 2)
for a in "$@"; do case "$a" in -n|-n*|--numprocesses*) xdist=() ;; esac; done
uv run --frozen python -m pytest -p no:cacheprovider -x --tb=short -W ignore "${xdist[@]}" "$@" >"$log" 2>&1
rc=$?
grep -E "^(FAILED|ERROR)|^E  |Error|^[0-9]+ (passed|failed)|passed|failed|no tests ran" "$log" \
  | grep -v "Warning" | tail -n "${PT_LINES:-60}"
echo "pytest rc=$rc · log completo: $log"
exit $rc
