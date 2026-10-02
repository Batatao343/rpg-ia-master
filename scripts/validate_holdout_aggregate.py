"""Validate a redacted aggregate emitted by the private holdout companion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FORBIDDEN_KEYS = {"input", "expected", "fixture", "prompt", "cases", "case_results", "transcript"}


def validate(payload: dict[str, Any]) -> None:
    required = {"schema_version", "product_sha", "evaluator_version", "dataset_hash", "case_count", "metrics"}
    if payload.keys() & FORBIDDEN_KEYS:
        raise ValueError("holdout aggregate exposes case-level data")
    if not required <= payload.keys() or payload.get("schema_version") != 1:
        raise ValueError("invalid holdout aggregate schema")
    if not isinstance(payload["case_count"], int) or payload["case_count"] <= 0:
        raise ValueError("holdout case_count must be positive")
    if not isinstance(payload["metrics"], dict) or not payload["metrics"]:
        raise ValueError("holdout metrics must be a non-empty object")
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in payload["metrics"].values()):
        raise ValueError("holdout metrics must be numeric aggregates")
    encoded = json.dumps(payload, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > 65_536:
        raise ValueError("holdout aggregate is unexpectedly large")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("aggregate", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.aggregate.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("holdout aggregate must be an object")
        validate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"holdout aggregate failed: {error}")
        return 1
    print("holdout aggregate valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
