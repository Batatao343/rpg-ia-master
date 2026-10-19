"""Regenera docs/operacao/CODIGOS_DE_ERRO.md e web/src/lib/errorCodes.json a partir de
services/error_codes.py (SPEC-242 R6 / SPEC-243 R2)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.error_codes import CODES, render_markdown  # noqa: E402

if __name__ == "__main__":
    (ROOT / "docs/operacao/CODIGOS_DE_ERRO.md").write_text(
        render_markdown(), encoding="utf-8", newline="\n")
    (ROOT / "web/src/lib/errorCodes.json").write_text(
        json.dumps(sorted(CODES), indent=2) + "\n", encoding="utf-8", newline="\n")
