"""Prepare a protected-eval publication for a one-click owner approval (workspace #8).

Never pushes, never sets GitHub variables, never approves anything. It:

1. classifies ``<base>..HEAD`` with the same rules as CI (``scripts/ci_eval_scope.py``)
   and refuses a mixed change (protected eval files + product code) unless
   ``--allow-mixed``;
2. tells you whether HEAD is already on the remote (push is the caller's call);
3. when the ``eval-gates`` run for HEAD is waiting on ``eval-governance``, prints the
   run link and the exact command the OWNER runs to approve it;
4. with ``--watch``, follows that run once with ``gh run watch --exit-status``.

Usage: ``bash scripts/dev/py.sh scripts/dev/eval_publish.py [--base origin/main] [--watch]``
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ci_eval_scope import classify, git_changed  # noqa: E402

PRODUCT_PREFIXES = ("agents/", "services/", "infrastructure/", "workers/", "web/src/")
PRODUCT_FILES = {"api.py", "main.py", "state.py", "persistence.py", "llm_setup.py"}


def _run(*args: str) -> tuple[int, str]:
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    return result.returncode, result.stdout.strip()


def approval_command(repo: str, run_id: str, environment_id: str) -> str:
    return (
        f"gh api -X POST repos/{repo}/actions/runs/{run_id}/pending_deployments "
        f"-F 'environment_ids[]={environment_id}' -f state=approved "
        "-f comment='protected eval change reviewed'"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--allow-mixed", action="store_true")
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args(argv)

    _, head = _run("git", "rev-parse", "HEAD")
    paths = git_changed(ROOT, args.base, head)
    scope = classify(paths, ROOT / "evals/protected-paths.txt")
    protected = scope["protected_files"]
    product = [p for p in paths if p in PRODUCT_FILES or p.startswith(PRODUCT_PREFIXES)]
    print(f"HEAD {head[:12]} vs {args.base}: {len(paths)} files, {len(protected)} protected")
    if not protected:
        print("no protected eval path changed: eval-governance approval is not needed")
        return 0
    if product and not args.allow_mixed:
        print("refusing: protected eval files changed together with product code:")
        for path in product[:20]:
            print(f"  {path}")
        print("split the evaluator change into its own commit/branch (eval integrity rule)")
        return 1

    code, remote = _run("git", "branch", "-r", "--contains", head)
    if code or not remote:
        print("HEAD is not on the remote yet. After review, push it (coordinator decision), then rerun.")
        return 0

    code, repo = _run("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
    if code:
        print("gh unavailable/unauthenticated; open the eval-gates run in the browser to approve")
        return 0
    code, runs = _run(
        "gh", "run", "list", "--workflow", "eval-gates.yml", "--commit", head,
        "--json", "databaseId,status", "--limit", "1",
    )
    listed = json.loads(runs or "[]") if code == 0 else []
    if not listed:
        print("no eval-gates run for HEAD yet; rerun in a minute")
        return 0
    run_id = str(listed[0]["databaseId"])
    print(f"run: https://github.com/{repo}/actions/runs/{run_id} ({listed[0]['status']})")
    code, pending = _run(
        "gh", "api", f"repos/{repo}/actions/runs/{run_id}/pending_deployments",
        "--jq", '.[] | "\\(.environment.id) \\(.environment.name)"',
    )
    waiting = [line.split(" ", 1) for line in pending.splitlines() if line.strip()] if code == 0 else []
    for environment_id, name in waiting:
        print(f"waiting on environment {name!r}. OWNER approves in the GitHub app/page, or runs:")
        print(f"  {approval_command(repo, run_id, environment_id)}")
    if not waiting:
        print("nothing pending approval on this run")
    if args.watch:
        return subprocess.call(["gh", "run", "watch", run_id, "--exit-status"], cwd=ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
