#!/usr/bin/env bash
# Suíte completa local (SPEC-414 R1) — só coordenador; subagente usa pt.sh.
#   bash scripts/dev/full.sh [args extras da pytest]
# -n pela RAM livre (full_plan.py); FULL_N=<n> força. Piso de RAM => rc 3.
# Worker morto (xdist) é re-rodado em série; rc = o da pytest (ou o veredito do rerun), nunca o de um filtro.
# FULL_PYTEST troca o comando da pytest (só para teste).
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"
plan() { uv run --frozen python scripts/dev/full_plan.py "$@"; }
tmp="${TMPDIR:-${TEMP:-/tmp}}"
log="$tmp/rpg-full-$$.log"
rlog="$tmp/rpg-full-$$-rerun.log"
eval "pytest_cmd=(${FULL_PYTEST:-uv run --frozen python -m pytest -p no:cacheprovider --tb=short -W ignore})"
show() { grep -E "^(FAILED|ERROR)|^E  |^[0-9]+ (passed|failed)|passed|failed|no tests ran" "$1" | grep -v "Warning" | tail -n "${FULL_LINES:-60}"; }

n="$(plan workers)"; rc=$?
if [ $rc -ne 0 ]; then echo "full rc=$rc · n=0 · mortos=0 · não rodou"; exit $rc; fi

"${pytest_cmd[@]}" -n "$n" "$@" >"$log" 2>&1
prc=$?
show "$log"
final=$prc; mortos=0
if [ $prc -ne 0 ]; then
  mapfile -t ids < <(plan crashed "$log" | grep -v '^$')
  mortos=${#ids[@]}
  if [ "$mortos" -gt 20 ]; then
    echo "full: $mortos workers morreram: RAM; rode com FULL_N menor"; final=1
  elif [ "$mortos" -ge 1 ]; then
    "${pytest_cmd[@]}" -n 0 -p no:cacheprovider "${ids[@]}" >"$rlog" 2>&1
    rrc=$?
    show "$rlog"
    plan verdict "$log" "$rrc" >/dev/null; final=$?
    echo "full: $mortos worker(s) morto(s); rerun serial de ${#ids[@]} id(s) -> rc=$rrc"
  fi
fi
echo "full rc=$final · n=$n · mortos=$mortos · log: $log"
exit $final
