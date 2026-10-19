"""SPEC-192 shared helpers: staging env, synthetic Auth users, evidence output, pure parsers."""

from __future__ import annotations

import json
import os
import re
import secrets
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from scripts.staging import common

BASE = "https://rpg-ia-master-staging.vercel.app"
EVIDENCE = common.ROOT / "docs" / "spec192" / "evidence"
CAPTCHA_TEST = "XXXX.DUMMY.TOKEN.XXXX"
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*")


def load_env() -> dict[str, str]:
    from dotenv import dotenv_values
    merged: dict[str, str] = {}
    for n in (".env", ".env.staging"):
        merged.update({k: v for k, v in dotenv_values(common.ROOT / n).items() if v})
    return merged


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def evidence(name: str, payload: dict) -> Path:
    return common.write_evidence(name, payload, EVIDENCE / f"{name}.json")


def pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    idx = min(len(s) - 1, max(0, -(-int(p * len(s)) // 100) - 1))
    return round(s[idx], 1)


def stats(values: list[float]) -> dict:
    return {"n": len(values), "p50_ms": round(statistics.median(values), 1) if values else None,
            "p95_ms": pct(values, 95), "max_ms": round(max(values), 1) if values else None}


def parse_sse(lines) -> list[dict]:
    """Parse SSE text lines into [{event, data}] (comment/ping lines skipped)."""
    events, ev, data = [], None, []
    for line in lines:
        if line == "":
            if ev is not None:
                raw = "\n".join(data)
                try:
                    payload = json.loads(raw)
                except ValueError:
                    payload = raw
                events.append({"event": ev, "data": payload})
            ev, data = None, []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            ev = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    return events


def cookie_flags(set_cookie_headers: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for h in set_cookie_headers:
        parts = [p.strip() for p in h.split(";")]
        name = parts[0].split("=", 1)[0]
        attrs = {p.split("=", 1)[0].lower(): (p.split("=", 1)[1] if "=" in p else True) for p in parts[1:]}
        out[name] = {"secure": "secure" in attrs, "httponly": "httponly" in attrs,
                     "samesite": str(attrs.get("samesite", "")).lower(), "path": attrs.get("path"),
                     "deleted": attrs.get("max-age") == "0" or "1970" in str(attrs.get("expires", ""))}
    return out


def json_has_bearer(body: object, token_values: list[str]) -> bool:
    """True if a JWT-looking string or a known cookie token value appears in the JSON text."""
    text = json.dumps(body, ensure_ascii=False)
    return bool(_JWT.search(text)) or any(t and t in text for t in token_values)


def sequence_summary(events: list[dict]) -> list[str]:
    seq: list[str] = []
    for e in events:
        if not seq or seq[-1] != e["event"]:
            seq.append(e["event"])
    return seq


class Admin:
    """Synthetic Auth users through the Admin API.

    R-01 (real Turnstile on staging): password login needs a browser-solved captcha, so synthetic users
    are created with ``generate_link`` type ``signup`` (no email is sent) and enter through the SAME path a
    real user takes after clicking the confirmation email: ``POST /auth/verify`` with the token hash (no
    captcha there by design). R-02 (Resend in test mode) is untouched: nothing is mailed to the
    ``@example.invalid`` addresses. Flows that need a captcha (``/auth/reauth``, password login probes)
    use ``RPG_STAGING_SMOKE_CAPTCHA_TOKEN`` when given (fresh, browser-solved) or the dummy token.
    """

    def __init__(self, env: dict[str, str]):
        self.url = env["SUPABASE_URL"].rstrip("/")
        self.key = env["SUPABASE_SERVICE_ROLE_KEY"]
        self.http = httpx.Client(timeout=30)

    @property
    def headers(self) -> dict:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}"}

    def create_user(self) -> dict:
        email = f"spec192-{uuid4().hex[:10]}@example.invalid"
        password = secrets.token_urlsafe(24)
        r = self.http.post(f"{self.url}/auth/v1/admin/generate_link", headers=self.headers,
                           json={"type": "signup", "email": email, "password": password})
        r.raise_for_status()
        body = r.json()
        return {"id": body["id"], "email": email, "password": password, "token_hash": body["hashed_token"]}

    def delete_user(self, uid: str) -> int:
        return self.http.delete(f"{self.url}/auth/v1/admin/users/{uid}", headers=self.headers).status_code

    def user_exists(self, uid: str) -> bool:
        return self.http.get(f"{self.url}/auth/v1/admin/users/{uid}", headers=self.headers).status_code == 200


def smoke_captcha() -> str:
    """Captcha for flows that cannot avoid it: a fresh browser-solved token if exported, else the dummy."""
    return os.environ.get("RPG_STAGING_SMOKE_CAPTCHA_TOKEN") or CAPTCHA_TEST


def app_login(c: httpx.Client, base: str, user: dict) -> httpx.Response:
    """Open an app session (cookies + CSRF) for a synthetic user via the email-confirmation link path."""
    return c.post(f"{base}/auth/verify", headers={"Origin": base, "Content-Type": "application/json"},
                  json={"token_hash": user["token_hash"], "type": "signup"})


def sweep_synthetic_users(env: dict[str, str]) -> int:
    """Remove leftover spec192-* synthetic users (e.g. after a transport error mid-run)."""
    admin = Admin(env)
    n = 0
    with db(env) as conn:
        for row in conn.execute("select id from auth.users where email like 'spec192-%%@example.invalid'").fetchall():
            n += admin.delete_user(str(row["id"])) in (200, 204)
    return n


def db(env: dict[str, str]):
    import psycopg
    from psycopg.rows import dict_row
    last: Exception | None = None
    for attempt in range(5):  # the local network resets pooler connections now and then
        try:
            return psycopg.connect(env["RPG_STAGING_DB_URL"], row_factory=dict_row, autocommit=True, connect_timeout=15)
        except psycopg.OperationalError as exc:
            last = exc
            time.sleep(1 + attempt)
    raise last  # type: ignore[misc]


def query(env: dict[str, str], fn, retries: int = 4):
    """Run ``fn(conn)`` on a fresh connection, retrying transient connection failures."""
    import psycopg
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with db(env) as conn:
                return fn(conn)
        except psycopg.OperationalError as exc:
            last = exc
            time.sleep(2 + attempt)
    raise last  # type: ignore[misc]


def _head_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=common.ROOT, capture_output=True,
                             text=True, timeout=10).stdout.strip().lower()
    except (OSError, subprocess.SubprocessError):
        return ""
    return out if len(out) == 40 and all(c in "0123456789abcdef" for c in out) else ""


def deploy_args(args: list[str], sha: str) -> list[str]:
    """SPEC-261 R3: todo ``vercel deploy`` leva ``GIT_SHA`` (runtime -> /health; build -> bundle web).

    Deploy por CLI de worktree nao define ``VERCEL_GIT_COMMIT_SHA``; antes era ``-e GIT_SHA=`` manual."""
    if not args or args[0] != "deploy" or not sha or any("GIT_SHA=" in a for a in args):
        return list(args)
    return [*args, "-e", f"GIT_SHA={sha}", "--build-env", f"GIT_SHA={sha}"]


def vercel(args: list[str], env: dict[str, str], timeout: int = 900) -> subprocess.CompletedProcess:
    """Run npx vercel with the token injected via subprocess env (never in argv)."""
    args = deploy_args(args, _head_sha())
    e = {**os.environ, "VERCEL_TOKEN": env.get("VERCEL_TOKEN", "")}
    return subprocess.run(["npx.cmd" if os.name == "nt" else "npx", "--yes", "vercel@64.2.0", *args],
                          cwd=common.ROOT, env=e, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def timed(fn):
    t0 = time.perf_counter()
    r = fn()
    return r, (time.perf_counter() - t0) * 1000


__all__ = ["uuid4"]
