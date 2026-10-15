from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "examples" / "spec-model-contract.yaml"
SPEC_DIR = ROOT / "specs"


def fail(message: str) -> None:
    print(f"model-contract invalid: {message}")
    raise SystemExit(1)


def main() -> int:
    payload = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))
    specs = payload.get("specs") or {}
    files = sorted(SPEC_DIR.glob("*.md"))
    numbers = [int(path.name.split("-", 1)[0]) for path in files]
    if numbers != list(range(176, 199)):
        fail(f"expected SPEC-176..198 exactly, got {numbers}")

    for path in files:
        number = int(path.name.split("-", 1)[0])
        spec_id = f"SPEC-{number}"
        contract = specs.get(spec_id)
        if not isinstance(contract, dict):
            fail(f"missing model matrix entry for {spec_id}")
        text = path.read_text(encoding="utf-8")
        executor = str(contract["executor_model"]).capitalize()
        effort = str(contract["executor_effort"]).capitalize()
        if f"**EXECUTOR_MODEL obrigatório:** `{executor}`" not in text:
            fail(f"{spec_id} executor header differs from matrix")
        if f"**EXECUTOR_EFFORT obrigatório:** `{effort}`" not in text:
            fail(f"{spec_id} effort header differs from matrix")
        if contract.get("review_required"):
            reviewer = str(contract["review_model"]).capitalize()
            if f"**REVIEW_MODEL obrigatório:** `{reviewer}`" not in text:
                fail(f"{spec_id} reviewer header differs from matrix")
            if "**REVIEW_REQUIRED:** `true`" not in text:
                fail(f"{spec_id} review flag differs from matrix")
        if "SUBSTITUIÇÃO DE MODELO" not in text:
            fail(f"{spec_id} lacks no-substitution contract")
        if len(re.findall(r"^- \[ \]", text, re.MULTILINE)) < 4:
            fail(f"{spec_id} has fewer than four observable close gates")

    print("model-contract valid: SPEC-176..198 exact model matrix and close gates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
