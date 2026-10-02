"""Fail closed unless a protected eval change passed the guarded environment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def verify(manifest: dict[str, object], approved: str) -> None:
    if not manifest.get("protected"):
        return
    protected = manifest.get("protected_files")
    if not isinstance(protected, list) or not protected:
        raise ValueError("scope manifest marks protected=true without protected_files")
    if approved.strip().lower() != "true":
        raise PermissionError(
            "protected eval paths changed; approve through the eval-governance environment"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--approved", default="")
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    try:
        verify(payload, args.approved)
    except (ValueError, PermissionError) as error:
        print(f"protected eval gate failed: {error}")
        return 1
    print("protected eval gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
