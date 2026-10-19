"""SPEC-197 release checklist (read-only; never prints secret values).

  uv run python -m scripts.release.checklist --env staging --base-url https://rpg-ia-master-staging.vercel.app
  uv run python -m scripts.release.checklist --env production --base-url https://<prod>   # prod not provisioned -> reported

Writes docs/spec197/evidence/checklist-<sha>.json and a markdown summary next to it.
Exit code 1 when any blocking check fails (status fail). `skip`/`not_provisioned` do not block
by themselves but are listed; `--strict` turns them into failures (use for the final beta gate).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from infrastructure.runtime import FORBIDDEN_IN_HOSTED, HOSTED_REQUIRED_ENV  # noqa: E402

EVIDENCE = ROOT / "docs" / "spec197" / "evidence"
SPEC_RANGE = range(176, 197)
OK_SPEC_STATUSES = {"done"}
# Env NAMES that must exist in the Vercel project (target production) before beta.
REQUIRED_ENV = {
    "staging": (
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "RPG_CRON_SECRET",
        "RPG_RUNTIME_PROFILE",
        "RPG_AUTH_CAPTCHA_MODE",
        "RPG_TURNSTILE_SITE_KEY",
        "RPG_ADMIN_DATABASE_URL",  # SPEC-224: credencial de sistema (rpg_admin), distinta da de request
    )
    + HOSTED_REQUIRED_ENV,  # SPEC-218: lista de seguranca vem de infrastructure.runtime (fonte unica)
}
REQUIRED_ENV["production"] = REQUIRED_ENV["staging"] + (
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "RPG_CHECKOUT_ORIGIN",
    "JINA_API_KEY",
    "DEEPSEEK_API_KEY",
    "GROQ_API_KEY",
    "RPG_DAILY_SPEND_CAP_BRL",
)
# SPEC-218: mock/fake Play/overrides de laboratorio fora de producao; SPEC-225 R8: compras de teste.
FORBIDDEN_IN_PROD = tuple(
    dict.fromkeys(
        (
            *FORBIDDEN_IN_HOSTED,
            "RPG_FORCE_MOCK",
            "RPG_GOOGLE_PLAY_FAKE",
            "RPG_PLAY_ACCEPT_TEST_PURCHASES",
        )
    )
)
RISK_ROW = re.compile(r"^\|\s*(R-\d+)\s*\|(.+)\|\s*$")
CLOSED = (
    "fechado",
    "closed",
    "aceito",
    "accepted",
)  # exact status tokens ("fechado (staging)" does not count)
DRAFT_MARKERS = ("RASCUNHO",)
PLACEHOLDER = re.compile(r"&lt;[^&\n]{1,80}?&gt;")  # built pages escape literal <...>


@dataclass
class Result:
    name: str
    status: str  # pass | fail | skip | not_provisioned
    detail: Any = None
    blocking: bool = True

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "blocking": self.blocking,
            "detail": self.detail,
        }


def _run(args: list[str]) -> tuple[int, str]:
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=120)  # noqa: S603
    return p.returncode, p.stdout


def _http_get(url: str) -> tuple[int, Any]:
    import httpx

    r = httpx.get(url, timeout=15, follow_redirects=False)
    try:
        body: Any = r.json()
    except ValueError:
        body = r.text
    return r.status_code, body


@dataclass
class Deps:
    """Side-effect seams so tests run offline."""

    run: Callable[[list[str]], tuple[int, str]] = field(default=_run)
    http_get: Callable[[str], tuple[int, Any]] = field(default=_http_get)
    remote_migrations: Callable[[str], list[dict] | None] | None = None  # env -> rows | None
    vercel_env_names: Callable[[str], set[str] | None] | None = None  # env -> names | None
    kill_switch_load: Callable[[str], dict | None] | None = None  # env -> {key: enabled} | None
    finops_cron_active: Callable[[str], bool | None] | None = (
        None  # env -> rpg-cron-finops active? | None (no DSN)
    )


# ---------------------------------------------------------------- checks
def check_git(deps: Deps) -> tuple[Result, str]:
    rc, sha = deps.run(["git", "rev-parse", "HEAD"])
    sha = sha.strip()
    if rc != 0 or not sha:
        return Result("git_clean_tree", "fail", "no HEAD"), "unknown"
    _, porcelain = deps.run(["git", "status", "--porcelain"])
    dirty = [ln for ln in porcelain.splitlines() if ln.strip()]
    return Result(
        "git_clean_tree", "pass" if not dirty else "fail", {"sha": sha, "dirty_files": len(dirty)}
    ), sha


def check_specs(index_path: Path = ROOT / "specs" / "index.yaml") -> Result:
    import yaml

    data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    found = {s["id"]: s["status"] for s in data["specs"]}
    bad = {
        f"SPEC-{n}": found.get(f"SPEC-{n}", "missing")
        for n in SPEC_RANGE
        if found.get(f"SPEC-{n}", "missing") not in OK_SPEC_STATUSES
    }
    return Result(
        "specs_176_196_done",
        "pass" if not bad else "fail",
        {"not_done": bad, "checked": len(SPEC_RANGE)},
    )


def check_ci(sha: str, deps: Deps) -> Result:
    rc, out = deps.run(
        [
            "gh",
            "run",
            "list",
            "--commit",
            sha,
            "--json",
            "name,status,conclusion,workflowName,databaseId",
        ]
    )
    if rc != 0:
        return Result("ci_green", "skip", "gh unavailable or unauthenticated")
    runs = json.loads(out or "[]")
    if not runs:
        return Result("ci_green", "fail", "no CI runs for this sha (push + wait required)")
    bad = [
        {
            "workflow": r.get("workflowName") or r.get("name"),
            "status": r.get("status"),
            "conclusion": r.get("conclusion"),
        }
        for r in runs
        if r.get("status") != "completed"
        or r.get("conclusion") not in {"success", "skipped", "neutral"}
    ]
    return Result("ci_green", "pass" if not bad else "fail", {"runs": len(runs), "not_green": bad})


def check_migrations(env: str, deps: Deps, directory: Path | None = None) -> Result:
    from scripts.staging import migrations as mig

    if deps.remote_migrations is None:
        return Result("migrations_drift", "skip", "no remote reader configured")
    try:
        remote = deps.remote_migrations(env)
    except Exception as exc:  # noqa: BLE001
        return Result("migrations_drift", "fail", f"remote read failed: {type(exc).__name__}")
    if remote is None:
        return Result("migrations_drift", "not_provisioned", f"no database target for {env}")
    st = mig.plan_status(mig.local_migrations(directory or mig.MIGRATIONS_DIR), remote)
    return Result(
        "migrations_drift",
        "pass" if st["in_sync"] else "fail",
        {
            k: st[k]
            for k in ("local_count", "remote_count", "pending", "remote_only", "version_mismatch")
        },
    )


def check_eval_locks(deps: Deps) -> Result:
    rc, out = deps.run([sys.executable, "-m", "evals.core.governance", "check", "--root", "."])
    return Result("eval_locks_unchanged", "pass" if rc == 0 else "fail", out.strip()[-300:])


def check_finops_config(
    root: Path = ROOT, env: str = "staging", deps: Deps | None = None
) -> Result:
    need = [
        "observability/alerts/finops.yml",
        "docs/spec196/README.md",
        "services/kill_switches.py",
        "scripts/admin_kill_switch.py",
        "data/finops_fixed_costs.json",
    ]
    missing = [p for p in need if not (root / p).exists()]
    if missing:
        return Result("budget_alert_config_present", "fail", {"missing": missing})
    if deps is None or deps.finops_cron_active is None:
        return Result(
            "budget_alert_config_present",
            "skip",
            "files present; cron.job not verified (no DB reader)",
        )
    try:
        active = deps.finops_cron_active(env)
    except Exception as exc:  # noqa: BLE001
        return Result(
            "budget_alert_config_present", "fail", f"cron.job read failed: {type(exc).__name__}"
        )
    if active is None:
        return Result(
            "budget_alert_config_present", "skip", f"files present; no database target for {env}"
        )
    return Result(
        "budget_alert_config_present",
        "pass" if active else "fail",
        {"missing": [], "rpg_cron_finops_active": active},
    )


def check_kill_switch(env: str, deps: Deps) -> Result:
    if deps.kill_switch_load is None:
        return Result("kill_switch_store_reachable", "skip", "no store reader configured")
    try:
        state = deps.kill_switch_load(env)
    except Exception as exc:  # noqa: BLE001
        return Result(
            "kill_switch_store_reachable", "fail", f"store unreadable: {type(exc).__name__}"
        )
    if state is None:
        return Result(
            "kill_switch_store_reachable", "not_provisioned", f"no database target for {env}"
        )
    return Result(
        "kill_switch_store_reachable",
        "pass",
        {
            "switches_recorded": len(state),
            "switched_off": sorted(k for k, v in state.items() if not v),
        },
    )


def check_health(base_url: str | None, sha: str, deps: Deps) -> Result:
    if not base_url:
        return Result("health_sha", "not_provisioned", "no base url")
    try:
        code, body = deps.http_get(base_url.rstrip("/") + "/health")
    except Exception as exc:  # noqa: BLE001
        return Result("health_sha", "fail", f"unreachable: {type(exc).__name__}")
    got = str(body.get("git_sha") or "") if isinstance(body, dict) else ""
    ok = code == 200 and bool(got) and (sha.startswith(got) or got.startswith(sha))
    return Result(
        "health_sha", "pass" if ok else "fail", {"http": code, "deployed_sha": got, "expected": sha}
    )


def check_env_names(env: str, deps: Deps) -> Result:
    if deps.vercel_env_names is None:
        return Result("vercel_env_names", "skip", "no vercel reader configured")
    try:
        names = deps.vercel_env_names(env)
    except Exception as exc:  # noqa: BLE001
        return Result("vercel_env_names", "fail", f"vercel read failed: {type(exc).__name__}")
    if names is None:
        return Result("vercel_env_names", "not_provisioned", f"no vercel project for {env}")
    missing = [n for n in REQUIRED_ENV[env] if n not in names]
    forbidden = [n for n in FORBIDDEN_IN_PROD if env == "production" and n in names]
    return Result(
        "vercel_env_names",
        "pass" if not missing and not forbidden else "fail",
        {"missing": missing, "forbidden_present": forbidden},
    )


WORKFLOW_DIR = ROOT / ".github" / "workflows"
SHA_USES_LINE = re.compile(r"^\s*-?\s*uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(\S+)")
ENVIRONMENTS_VERIFIED = re.compile(r"ENVIRONMENTS_VERIFIED:\s*(\d{4}-\d{2}-\d{2})")


def check_workflow_hygiene(directory: Path = WORKFLOW_DIR) -> Result:
    """SPEC-225 R9: todo workflow com permissions no topo, sem pull_request_target, actions por SHA."""
    problems: dict[str, list[str]] = {}
    for path in sorted(directory.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        found = []
        if not re.search(r"^permissions:", text, flags=re.M):
            found.append("sem permissions")
        if "pull_request_target" in text:
            found.append("pull_request_target")
        for line in text.splitlines():
            match = SHA_USES_LINE.match(line)
            if match and not re.fullmatch(r"[0-9a-f]{40}", match.group(2).split(" ")[0]):
                found.append(f"action sem SHA: {match.group(1)}")
        if found:
            problems[path.name] = found
    return Result(
        "workflows_permissions_pins",
        "pass" if not problems else "fail",
        {"problems": problems} if problems else {"files": len(list(directory.glob("*.yml")))},
    )


def check_gitleaks_main(deps: Deps) -> Result:
    """SPEC-225 R5/R9: o último run concluído do workflow validate na main (inclui secret-scan) está verde."""
    rc, out = deps.run(
        [
            "gh",
            "run",
            "list",
            "--workflow",
            "validate",
            "--branch",
            "main",
            "--limit",
            "5",
            "--json",
            "status,conclusion,headSha",
        ]
    )
    if rc != 0:
        return Result("gitleaks_main_green", "skip", "gh unavailable or unauthenticated")
    try:
        runs = [r for r in json.loads(out or "[]") if r.get("status") == "completed"]
    except json.JSONDecodeError:
        return Result("gitleaks_main_green", "fail", "gh output unreadable")
    if not runs:
        return Result("gitleaks_main_green", "not_provisioned", "no completed validate run on main")
    last = runs[0]
    return Result(
        "gitleaks_main_green",
        "pass" if last.get("conclusion") == "success" else "fail",
        {"head": str(last.get("headSha", ""))[:12], "conclusion": last.get("conclusion")},
    )


def check_environments_verified(path: Path = ROOT / "docs" / "spec225" / "README.md") -> Result:
    """SPEC-225 R4/R9: Environments (deployment branches = main, reviewers) verificados manualmente, com data."""
    if not path.exists():
        return Result("environments_restricted", "fail", "docs/spec225/README.md ausente")
    match = ENVIRONMENTS_VERIFIED.search(path.read_text(encoding="utf-8"))
    if not match:
        return Result(
            "environments_restricted",
            "fail",
            "verificação manual pendente (ENVIRONMENTS_VERIFIED: AAAA-MM-DD)",
        )
    return Result("environments_restricted", "pass", {"verified_on": match.group(1)})


def check_legal(urls: dict[str, str], deps: Deps, *, allow_draft: bool = False) -> Result:
    if not urls:
        return Result(
            "legal_pages",
            "fail",
            "no privacy/terms/support/refund URLs configured (--legal-url name=url)",
        )
    bad: dict[str, str] = {}
    for name, url in urls.items():
        try:
            code, body = deps.http_get(url)
        except Exception as exc:  # noqa: BLE001
            bad[name] = type(exc).__name__
            continue
        if code != 200:
            bad[name] = f"http {code}"
        elif not allow_draft and isinstance(body, str):
            if any(m in body for m in DRAFT_MARKERS):
                bad[name] = "draft banner (RASCUNHO) still present"
            elif PLACEHOLDER.search(body):
                bad[name] = "unfilled <placeholder> present"
    missing = [n for n in ("privacy", "terms", "support", "refund") if n not in urls]
    if missing:
        bad["missing_names"] = ",".join(missing)
    return Result(
        "legal_pages", "pass" if not bad else "fail", {"urls": sorted(urls), "problems": bad}
    )


def parse_risks(path: Path) -> list[dict]:
    """Table rows: | R-nn | sev | titulo | dono | status | ... |"""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = RISK_ROW.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) >= 4 and cells[0].upper() in {"P0", "P1", "P2"}:
            rows.append(
                {
                    "id": m.group(1),
                    "severity": cells[0].upper(),
                    "title": cells[1],
                    "status": cells[3].lower(),
                }
            )
    return rows


def check_risks(path: Path | None = None) -> Result:
    rows = parse_risks(path or ROOT / "docs" / "spec197" / "risk-register.md")
    if not rows:
        return Result("open_p0_p1", "fail", "risk register missing or empty")
    open_bad = [
        r["id"] for r in rows if r["severity"] in {"P0", "P1"} and r["status"] not in CLOSED
    ]
    open_p2 = [r["id"] for r in rows if r["severity"] == "P2" and r["status"] not in CLOSED]
    return Result(
        "open_p0_p1",
        "pass" if not open_bad else "fail",
        {"open_p0_p1": open_bad, "p2_awaiting_acceptance": open_p2, "total": len(rows)},
    )


# ---------------------------------------------------------------- orchestration
def run_checklist(
    env: str,
    base_url: str | None,
    legal_urls: dict[str, str],
    deps: Deps,
    *,
    strict: bool = False,
    allow_draft_legal: bool = False,
    risk_path: Path | None = None,
) -> dict:
    git, sha = check_git(deps)
    results = [
        git,
        check_specs(),
        check_ci(sha, deps),
        check_migrations(env, deps),
        check_eval_locks(deps),
        check_finops_config(env=env, deps=deps),
        check_kill_switch(env, deps),
        check_health(base_url, sha, deps),
        check_env_names(env, deps),
        check_legal(legal_urls, deps, allow_draft=allow_draft_legal),
        check_risks(risk_path),
        check_workflow_hygiene(),
        check_gitleaks_main(deps),
        check_environments_verified(),
    ]
    failing = [
        r.name
        for r in results
        if r.blocking
        and (r.status == "fail" or (strict and r.status in {"skip", "not_provisioned"}))
    ]
    return {
        "schema": 1,
        "env": env,
        "sha": sha,
        "base_url": base_url,
        "ok": not failing,
        "failing": failing,
        "strict": strict,
        "results": [r.as_dict() for r in results],
    }


def to_markdown(report: dict) -> str:
    icon = {"pass": "OK", "fail": "FALHA", "skip": "PULADO", "not_provisioned": "N/PROVISIONADO"}
    head = f"Resultado: **{'APROVADO' if report['ok'] else 'BLOQUEADO'}**"
    if report["failing"]:
        head += f" (falhas: {', '.join(report['failing'])})"
    lines = [
        f"# Release checklist - {report['env']} @ {report['sha'][:12]}",
        "",
        head,
        "",
        "| check | status | detalhe |",
        "|---|---|---|",
    ]
    for r in report["results"]:
        detail = json.dumps(r["detail"], ensure_ascii=False)[:160].replace("|", "/")
        lines.append(f"| {r['name']} | {icon.get(r['status'], r['status'])} | {detail} |")
    return "\n".join(lines) + "\n"


def write_report(report: dict, out_dir: Path = EVIDENCE) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"checklist-{report['sha'][:12]}" + (
        "" if report["env"] == "staging" else f"-{report['env']}"
    )
    j, m = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    j.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    m.write_text(to_markdown(report), encoding="utf-8")
    return j, m


# ---------------------------------------------------------------- real readers (names/rows only)
def _dotenv() -> dict[str, str]:
    from dotenv import dotenv_values

    merged: dict[str, str] = {}
    for n in (".env", ".env.staging"):
        merged.update({k: v for k, v in dotenv_values(ROOT / n).items() if v})
    return merged


def real_remote_migrations(env: str) -> list[dict] | None:
    dsn = _dotenv().get("RPG_STAGING_DB_URL") if env == "staging" else None
    if not dsn:
        return None  # production not provisioned (docs/spec197/external-inputs.md)
    import psycopg

    from scripts.staging import migrations as mig

    with psycopg.connect(dsn, autocommit=True) as conn:
        return mig.fetch_remote(conn)


def real_vercel_env_names(env: str) -> set[str] | None:
    link = ROOT / ".vercel" / "project.json"
    token = _dotenv().get("VERCEL_TOKEN")
    if env != "staging" or not token or not link.exists():
        return None
    import httpx

    meta = json.loads(link.read_text(encoding="utf-8"))
    r = httpx.get(
        f"https://api.vercel.com/v10/projects/{meta['projectId']}/env",
        params={"teamId": meta["orgId"]},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return {e["key"] for e in r.json().get("envs", []) if "production" in (e.get("target") or [])}


def real_kill_switch_load(env: str) -> dict | None:
    dsn = _dotenv().get("RPG_STAGING_DB_URL") if env == "staging" else None
    if not dsn:
        return None
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        rows = conn.execute("select key, enabled from app.kill_switches").fetchall()
        return {k: bool(v) for k, v in rows}


def real_finops_cron_active(env: str) -> bool | None:
    dsn = _dotenv().get("RPG_STAGING_DB_URL") if env == "staging" else None
    if not dsn:
        return None
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        row = conn.execute(
            "select 1 from cron.job where jobname = 'rpg-cron-finops' and active"
        ).fetchone()
        return row is not None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env", choices=["staging", "production"], default="staging")
    ap.add_argument("--base-url")
    ap.add_argument("--legal-url", action="append", default=[], metavar="NAME=URL")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument(
        "--allow-draft-legal",
        action="store_true",
        help="staging only: accept RASCUNHO banner / <placeholders> in legal pages",
    )
    ap.add_argument("--out-dir", type=Path, default=EVIDENCE)
    a = ap.parse_args(argv)
    legal = dict(x.split("=", 1) for x in a.legal_url if "=" in x)
    deps = Deps(
        remote_migrations=real_remote_migrations,
        vercel_env_names=real_vercel_env_names,
        kill_switch_load=real_kill_switch_load,
        finops_cron_active=real_finops_cron_active,
    )
    report = run_checklist(
        a.env, a.base_url, legal, deps, strict=a.strict, allow_draft_legal=a.allow_draft_legal
    )
    j, m = write_report(report, a.out_dir)
    print(m.read_text(encoding="utf-8"))
    print(f"evidence: {j}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
