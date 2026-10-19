"""SPEC-192: smoke do staging na Vercel. Evidência sem segredos em docs/spec192/evidence/smoke.json."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone, UTC
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = "https://rpg-ia-master-staging.vercel.app"
HDRS = (
    "content-type",
    "cache-control",
    "x-vercel-cache",
    "x-vercel-id",
    "server",
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
    "content-security-policy",
    "referrer-policy",
)


def _req(client: httpx.Client, method: str, url: str, retries: int = 3, **kw):
    """(response|None, ms, erro). Repete falha de transporte (rede local instável)."""
    last = None
    for _ in range(retries):
        t0 = time.perf_counter()
        try:
            r = client.request(method, url, **kw)
            return r, round((time.perf_counter() - t0) * 1000), None
        except httpx.HTTPError as exc:
            last = type(exc).__name__
    return None, 0, last


def _hdrs(r) -> dict:
    return {k: r.headers[k] for k in HDRS if k in r.headers}


def run(base: str, secret: str) -> dict:
    out: dict = {"base": base, "at": datetime.now(UTC).isoformat(), "checks": {}}
    c = httpx.Client(timeout=90, follow_redirects=False)
    ck = out["checks"]
    r, ms, err = _req(c, "GET", f"{base}/health", retries=1)  # 1a request = cold (se frio)
    out["first_request_ms"] = ms
    ck["health"] = {
        "ok": bool(r is not None and r.status_code == 200),
        "status": getattr(r, "status_code", None),
        "ms": ms,
        "error": err,
        "headers": _hdrs(r) if r is not None else {},
    }
    warm = []
    for _ in range(10):
        r2, ms2, _e = _req(c, "GET", f"{base}/health")
        if r2 is not None and r2.status_code == 200:
            warm.append(ms2)
    out["warm_ms"] = {
        "n": len(warm),
        "p50": statistics.median(warm) if warm else None,
        "max": max(warm) if warm else None,
    }
    r, ms, err = _req(c, "GET", f"{base}/")
    ck["static_index"] = {
        "ok": bool(r is not None and r.status_code == 200 and "<html" in r.text.lower()),
        "status": getattr(r, "status_code", None),
        "ms": ms,
        "error": err,
        "headers": _hdrs(r) if r is not None else {},
    }
    for path in ("jobs", "account-deletions", "operations"):
        url = f"{base}/internal/cron/{path}"
        r0, _, e0 = _req(c, "POST", url)
        r1, ms1, e1 = _req(c, "POST", url, headers={"Authorization": f"Bearer {secret}"})
        body = {}
        if r1 is not None:
            try:
                body = {
                    k: v for k, v in r1.json().items() if isinstance(v, (int, float, str, bool))
                }
            except ValueError:
                body = {}
        ck[f"cron_{path}"] = {
            "noauth_status": getattr(r0, "status_code", e0),
            "auth_status": getattr(r1, "status_code", e1),
            "ms": ms1,
            "body": body,
            "ok": bool(
                r0 is not None
                and r0.status_code == 401
                and r1 is not None
                and r1.status_code == 200
            ),
        }
    out["ok"] = all(v["ok"] for v in ck.values())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--out", default=str(ROOT / "docs/spec192/evidence/smoke.json"))
    a = ap.parse_args(argv)
    secret = dotenv_values(ROOT / ".env.staging").get("RPG_CRON_SECRET", "")
    result = run(a.base, secret)
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": result["ok"],
                "first_request_ms": result["first_request_ms"],
                "warm_ms": result["warm_ms"],
                "checks": {
                    k: (v["ok"], v.get("auth_status", v.get("status")))
                    for k, v in result["checks"].items()
                },
            }
        )
    )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
