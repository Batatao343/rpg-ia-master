#!/usr/bin/env bash
# RAM livre + processos pytest/python órfãos (SPEC-386 R4). Só leitura.
set -uo pipefail
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "$(dirname "${BASH_SOURCE[0]}")/ram.ps1")" | tr -d '\r'
