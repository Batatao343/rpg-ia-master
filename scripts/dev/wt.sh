#!/usr/bin/env bash
# Worktree-per-spec lifecycle (workspace improvements #3/#4/#9).
#
#   scripts/dev/wt.sh new  <NNN|branch>   create worktree from main (outside OneDrive)
#   scripts/dev/wt.sh sync <NNN|branch>   rebase on main + regenerate specs/index.yaml
#                                         and project_index ON THE BRANCH (one commit)
#   scripts/dev/wt.sh land <NNN|branch>   sync, then fast-forward main to the branch
#   scripts/dev/wt.sh drop <NNN|branch>   remove worktree and branch
#   scripts/dev/wt.sh path <NNN|branch>   print the worktree path
#
# A bare number means branch spec-NNN. Worktrees live in $RPG_WT_ROOT
# (default %LOCALAPPDATA%\Temp\claude) as rpg-<branch>. The main checkout is the
# first entry of `git worktree list`; land requires it to be on `main`.
set -euo pipefail

cmd="${1:-}"; name="${2:-}"
[ -n "$cmd" ] && [ -n "$name" ] || { sed -n '2,15p' "$0"; exit 2; }
case "$name" in [0-9]*) BR="spec-$name";; *) BR="$name";; esac

MAIN="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
if [ -n "${RPG_WT_ROOT:-}" ]; then ROOT_DIR="$RPG_WT_ROOT"
elif [ -n "${LOCALAPPDATA:-}" ]; then ROOT_DIR="$(cygpath -u "$LOCALAPPDATA" 2>/dev/null || echo "$LOCALAPPDATA")/Temp/claude"
else ROOT_DIR="${TMPDIR:-/tmp}/claude"; fi
WT="$ROOT_DIR/rpg-$BR"

py() {  # project python inside the given worktree
  (cd "$1" && shift && bash scripts/dev/py.sh "$@")
}

sync_branch() {
  cd "$WT"
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "worktree $WT has uncommitted tracked changes; commit them first" >&2; exit 1
  fi
  git rebase -q main
  py "$WT" scripts/spec_index.py build
  py "$WT" -m project_index build >/dev/null
  git add specs/index.yaml project_index/manifest.json project_index/repo_graph.json
  if ! git diff --cached --quiet; then
    git commit -q -m "chore: sync spec index and project index

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
    echo "synced indexes: $(git log --oneline -1)"
  else
    echo "indexes already in sync"
  fi
  py "$WT" scripts/spec_index.py check >/dev/null
  py "$WT" -m project_index check >/dev/null && echo "project_index check: fresh"
}

case "$cmd" in
  new)
    git -C "$MAIN" worktree add -q -b "$BR" "$WT" main
    if [ -d "$MAIN/web/node_modules" ] && [ ! -e "$WT/web/node_modules" ]; then
      powershell.exe -NoProfile -Command "New-Item -ItemType Junction -Path \"$(cygpath -w "$WT/web/node_modules")\" -Target \"$(cygpath -w "$MAIN/web/node_modules")\" | Out-Null" \
        || echo "warning: could not junction web/node_modules" >&2
    fi
    echo "$WT";;
  sync)
    sync_branch;;
  land)
    sync_branch
    cd "$MAIN"
    [ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || { echo "main checkout is not on main" >&2; exit 1; }
    git merge -q --ff-only "$BR"
    git log --oneline -3;;
  drop)
    git -C "$MAIN" worktree remove --force "$WT" 2>/dev/null || true
    git -C "$MAIN" branch -D "$BR" 2>/dev/null || true;;
  path)
    echo "$WT";;
  *) sed -n '2,15p' "$0"; exit 2;;
esac
