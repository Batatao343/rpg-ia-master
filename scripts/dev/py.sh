#!/usr/bin/env bash
# Run project Python from anywhere inside the repo or a worktree:
#   bash scripts/dev/py.sh -m pytest -q tests/test_x.py
#   bash scripts/dev/py.sh scripts/spec_index.py check
# Equivalent to: cd <root>; PYTHONUTF8=1 uv run --frozen python "$@"
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"
exec uv run --frozen python "$@"
