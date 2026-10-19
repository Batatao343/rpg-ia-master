"""Bounded post-deploy read-only smoke with commit identity verification."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx


def _origin(base_url: str) -> str:
    """scheme://host[:port] sem userinfo/path/query (a URL pode carregar credencial)."""
    try:
        parsed = urlparse(base_url or "")
        port = f":{parsed.port}" if parsed.port else ""
        return (
            f"{parsed.scheme}://{parsed.hostname}{port}"
            if parsed.scheme and parsed.hostname
            else ""
        )
    except ValueError:
        return ""


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
    detail: dict[str, dict[str, object]] = {}
    failed: list[str] = []
    state: dict[str, object] = {"actual_sha": ""}

    def check(name: str, path: str, client: httpx.Client, extra=None) -> None:
        started = time.monotonic()
        entry: dict[str, object] = {"status": "passed", "http_status": None}
        try:
            response = client.get(path)
            entry["http_status"] = response.status_code
            response.raise_for_status()
            if extra is not None:
                extra(response)
        except (RuntimeError, httpx.HTTPError, ValueError) as error:
            entry["status"] = "failed"
            entry["error_type"] = type(error).__name__
            failed.append(name)
        entry["latency_ms"] = int((time.monotonic() - started) * 1000)
        detail[name] = entry

    def health_extra(response: httpx.Response) -> None:
        body = response.json()
        actual = str(body.get("git_sha") or response.headers.get("x-git-sha") or "")
        state["actual_sha"] = actual
        if not actual.startswith(expected_sha) and not expected_sha.startswith(actual):
            raise RuntimeError("deployed SHA mismatch")
        # SPEC-218 R9: deploy exposto nunca pode estar em legacy nem sem hardening.
        if body.get("profile") in (None, "legacy") or body.get("hardened") is not True:
            raise RuntimeError("deployed profile is not hardened (SPEC-218)")

    with httpx.Client(
        base_url=base_url.rstrip("/"),
        timeout=timeout,
        follow_redirects=False,
        transport=transport,
    ) as client:
        check("health", "/health", client, health_extra)
        for path in ("/auth/config", "/data/options", "/data/map"):
            check(path, path, client)
    first = failed[0] if failed else None
    return {
        "schema_version": 2,
        "mode": "read-only",
        "status": "failed" if failed else "passed",
        "failed_check": first,
        "failed_checks": failed,
        "http_status": detail[first]["http_status"] if first else 200,
        "base_origin": _origin(base_url),
        "expected_git_sha": expected_sha,
        "actual_git_sha": state["actual_sha"],
        "checks": detail,
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
    except (ValueError, httpx.HTTPError) as error:
        # Falha de configuracao/rede antes de qualquer check: evidencia minima.
        payload = {
            "schema_version": 2,
            "mode": "read-only",
            "status": "failed",
            "failed_check": "setup",
            "failed_checks": ["setup"],
            "base_origin": _origin(args.base_url),
            "http_status": None,
            "error_type": type(error).__name__,
            "expected_git_sha": args.expected_git_sha,
            "actual_git_sha": "",
            "checks": {},
            "generated_at": datetime.now(UTC).isoformat(),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
