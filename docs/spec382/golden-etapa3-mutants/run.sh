#!/usr/bin/env bash
# Roda o golden da SPEC-382 contra cada copia mutada (nunca edita o worktree).
#   py.sh docs/spec382/golden-etapa3-mutants/make.py . <scratch>/src   # gera as copias
#   git show 0fdb2a85:tests/fixtures/spec382_node_golden.json > <scratch>/golden_before.json
#   bash docs/spec382/golden-etapa3-mutants/run.sh <worktree> <scratch> [nome...]
# Sem nome = CONTROL (sem plugin) + todas as copias de <scratch>/src. Serial (-n 0).
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WT="$1"; SP="$2"; shift 2
cd "$WT" || exit 1
names=("$@")
if [ ${#names[@]} -eq 0 ]; then
  names=(CONTROL)
  for f in "$SP"/src/*.py; do names+=("$(basename "$f" .py)"); done
fi
for n in "${names[@]}"; do
  d="$SP/dump/$n"; rm -rf "$d"
  if [ "$n" = CONTROL ]; then unset MUT_MODULE MUT_FILE; else
    kind="${n%%__*}"
    if [ "$kind" = orch ]; then export MUT_MODULE=services.conflict_orchestrator; else export MUT_MODULE=agents.combat; fi
    export MUT_FILE="$SP/src/$n.py"
  fi
  PYTHONPATH="$HERE" SPEC382_DUMP="$d" bash scripts/dev/py.sh -m pytest -p mutplug -p no:cacheprovider -n 0 -q \
    --maxfail=999 -W ignore tests/test_spec382_node_golden.py >"$SP/log_$n.txt" 2>&1
  loaded=$(grep -c "\[mutplug\]" "$SP/log_$n.txt")
  score=$(bash scripts/dev/py.sh "$HERE/score.py" "$d" tests/fixtures/spec382_node_golden.json "$SP/golden_before.json")
  echo "$n | loaded=$loaded | $score"
done
