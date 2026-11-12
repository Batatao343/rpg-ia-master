#!/usr/bin/env bash
# Pre-checagens do pouso (SPEC-415): collision, format, ram, review, measure, growth, ci.
#   bash scripts/dev/land_check.sh NNN [--only collision,ram]
exec bash "$(dirname "${BASH_SOURCE[0]}")/py.sh" "$(dirname "${BASH_SOURCE[0]}")/land_check.py" "$@"
