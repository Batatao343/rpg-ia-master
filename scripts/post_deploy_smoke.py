"""Bounded post-deploy read-only smoke with commit identity verification."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx


def run(
    base_url: str,
    expected_sha: str,
    timeout: float = 15.0,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, object]:
    parsed = urlparse(base_url)
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("post-deploy smoke requires HTTPS outside localhost")
    if len(expected_sha) < 7:
        raise ValueError("EXPECTED_GIT_SHA must contain at least seven characters")
    checks: dict[str, str] = {}
    with httpx.Client(
        base_url=base_url.rstrip("/"),
        timeout=timeout,
        follow_redirects=False,
        transport=transport,
    ) as client:
        health = client.get("/health")
        health.raise_for_status()
        body = health.json()
        actual_sha = str(body.get("git_sha") or health.headers.get("x-git-sha") or "")
        if not actual_sha.startswith(expected_sha) and not expected_sha.startswith(actual_sha):
            raise RuntimeError(f"deployed SHA mismatch: expected {expected_sha}, got {actual_sha or 'missing'}")
        checks["health"] = "passed"
        checks["git_sha"] = actual_sha
        for path in ("/auth/config", "/data/options", "/data/map"):
            response = client.get(path)
            response.raise_for_status()
            checks[path] = "passed"
    return {
        "schema_version": 1,
        "mode": "read-only",
        "base_origin": f"{parsed.scheme}://{parsed.netloc}",
        "expected_git_sha": expected_sha,
        "checks": checks,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("PROD_BASE_URL", ""))
    parser.add_argument("--expected-git-sha", default=os.getenv("EXPECTED_GIT_SHA", ""))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = run(args.base_url, args.expected_git_sha)
    except (ValueError, RuntimeError, httpx.HTTPError, json.JSONDecodeError) as error:
        print(f"post-deploy smoke failed: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
