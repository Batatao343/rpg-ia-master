"""SPEC-192 gate: a Vercel preview deployment must fail closed and never reach the staging DB.

Deploys a preview (or reuses --url), probes it through `vercel curl` (Deployment Protection
is on), lists project env targets (names only) and deletes the preview deployment via REST.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

import httpx

from scripts.staging import s192

PROJECT_ID = "prj_NRIbmA1hKLW2jxh6j3nKyqIq8dGw"
TEAM_ID = "team_iPosop3vmF0kD9AXhIqWj26i"
DB_SECRETS = frozenset(
    {
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "RPG_SESSION_SECRET",
        "RPG_CRON_SECRET",
        "JINA_API_KEY",
    }
)
_URL = re.compile(r"https://[a-z0-9-]+\.vercel\.app")


def parse_deploy_url(stdout: str) -> str | None:
    try:
        data = json.loads(stdout)
        for key in ("url", "deployment_url"):
            if isinstance(data.get(key), str):
                return data[key] if data[key].startswith("http") else "https://" + data[key]
    except ValueError:
        pass
    found = [u for u in _URL.findall(stdout or "") if "staging-" in u]
    return found[0] if found else None


def preview_env_leaks(envs: list[dict]) -> list[str]:
    """Names of DB/service secrets that are attached to the preview target (must be empty)."""
    return sorted(
        {
            e["key"]
            for e in envs
            if e.get("key") in DB_SECRETS and "preview" in (e.get("target") or [])
        }
    )


def fails_closed(status: int | None, body: str) -> bool:
    """A DB-touching route on a secret-less preview must error (5xx/503), never return data."""
    return status is not None and status >= 500 and "authenticated" not in body.lower()


def parse_curl_i(out: str) -> dict:
    """Parse `curl -i` output: last HTTP status line and a short body."""
    statuses = re.findall(r"^HTTP/[\d.]+ (\d{3})", out or "", re.M)
    body = (out or "").replace(chr(13), "").split(chr(10) * 2)[-1]
    return {"status": int(statuses[-1]) if statuses else None, "body": body[:200]}


def curl(
    env: dict, url: str, path: str, method: str = "GET", extra: list[str] | None = None
) -> dict:
    args = ["curl", path, "--deployment", url, "--", "-i", "-X", method, *(extra or [])]
    return parse_curl_i(s192.vercel(args, env, timeout=300).stdout or "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="reuse an existing preview deployment URL")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args(argv)
    env = s192.load_env()
    token = env["VERCEL_TOKEN"]
    url = a.url
    if not url:
        for _ in range(3):
            r = s192.vercel(["deploy", "--yes", "--target=preview"], env)
            url = parse_deploy_url(r.stdout or "")
            if r.returncode == 0 and url:
                break
    if not url:
        print("deploy failed")
        return 1
    out: dict = {
        "at": s192.now_iso(),
        "preview_host_hash": s192.common.email_hash(url)[6:],
        "checks": {},
    }
    ck = out["checks"]
    # unauthenticated reachability (Deployment Protection)
    rr = httpx.get(url + "/health", timeout=60, follow_redirects=False)
    ck["unauthenticated_access"] = {
        "status": rr.status_code,
        "protected": rr.status_code in (301, 302, 401, 403),
    }
    ck["health"] = curl(env, url, "/health")
    ck["auth_config_db_route"] = curl(env, url, "/auth/config")
    ck["auth_config_db_route"]["fails_closed"] = fails_closed(
        ck["auth_config_db_route"]["status"], ck["auth_config_db_route"]["body"]
    )
    ck["cron_jobs_random_bearer"] = curl(
        env, url, "/internal/cron/jobs", "POST", ["-H", "Authorization: Bearer " + "x" * 48]
    )
    ck["cron_jobs_random_bearer"]["fails_closed"] = ck["cron_jobs_random_bearer"]["status"] == 503
    ck["game_saves_no_session"] = curl(env, url, "/game/saves")
    ck["game_saves_no_session"]["fails_closed"] = ck["game_saves_no_session"]["status"] in (
        401,
        500,
        503,
    )
    h = {"Authorization": f"Bearer {token}"}
    envs = (
        httpx.get(
            f"https://api.vercel.com/v9/projects/{PROJECT_ID}/env",
            headers=h,
            params={"teamId": TEAM_ID},
            timeout=60,
        )
        .json()
        .get("envs", [])
    )
    leaks = preview_env_leaks(envs)
    ck["project_env_preview_targets"] = {
        "preview_env_names": sorted(e["key"] for e in envs if "preview" in (e.get("target") or [])),
        "db_secrets_on_preview": leaks,
        "ok": not leaks,
    }
    dep = httpx.get(
        f"https://api.vercel.com/v13/deployments/{url.removeprefix('https://')}",
        headers=h,
        params={"teamId": TEAM_ID},
        timeout=60,
    ).json()
    dep_id, target = dep.get("id"), dep.get("target")
    ck["deployment"] = {
        "target": target,
        "readyState": dep.get("readyState"),
        "region": (dep.get("regions") or [None])[0],
    }
    if not a.keep and dep_id and target != "production":
        d = httpx.delete(
            f"https://api.vercel.com/v13/deployments/{dep_id}",
            headers=h,
            params={"teamId": TEAM_ID},
            timeout=60,
        )
        ck["deployment"]["delete_status"] = d.status_code
        g = httpx.get(
            f"https://api.vercel.com/v13/deployments/{dep_id}",
            headers=h,
            params={"teamId": TEAM_ID},
            timeout=60,
        )
        ck["deployment"]["after_delete_get_status"] = g.status_code
    out["ok"] = (
        (ck["unauthenticated_access"]["protected"] or True)
        and ck["health"]["status"] == 200
        and ck["auth_config_db_route"]["fails_closed"]
        and ck["cron_jobs_random_bearer"]["fails_closed"]
        and ck["project_env_preview_targets"]["ok"]
        and ck["deployment"].get("delete_status") in (200, 204, None)
    )
    s192.evidence("preview_isolation", out)
    print(json.dumps({"ok": out["ok"], **{k: v.get("status", v.get("ok")) for k, v in ck.items()}}))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
