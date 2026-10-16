"""SPEC-222 R10: regenera docs/spec222/retencao.md a partir do código."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.retention import retention_markdown  # noqa: E402

TARGET = ROOT / "docs" / "spec222" / "retencao.md"

if __name__ == "__main__":
    TARGET.write_text(retention_markdown(), encoding="utf-8", newline="\n")
    print(f"escrito {TARGET.relative_to(ROOT)}")
