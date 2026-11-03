#!/usr/bin/env bash
# Teto de linhas para qualquer comando (SPEC-386 R4): imprime as N primeiras e grava o resto.
#   bash scripts/dev/cap.sh 40 git log --stat
set -uo pipefail
n="${1:?uso: cap.sh N comando...}"; shift
log="${TMPDIR:-${TEMP:-/tmp}}/rpg-cap-$$.log"
"$@" >"$log" 2>&1
rc=$?
total=$(wc -l <"$log")
head -n "$n" "$log"
[ "$total" -gt "$n" ] && echo "… +$((total - n)) linhas omitidas · completo: $log"
exit $rc
