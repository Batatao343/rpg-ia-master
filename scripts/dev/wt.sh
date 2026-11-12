#!/usr/bin/env bash
# Worktree-per-spec lifecycle (workspace improvements #3/#4/#9).
#
#   scripts/dev/wt.sh new  <NNN|branch>   create worktree from main (outside OneDrive)
#   scripts/dev/wt.sh sync <NNN|branch>   rebase on main + regenerate specs/index.yaml
#                                         ON THE BRANCH (one commit). project_index/ artifacts
#                                         are local and untracked (python -m project_index build)
#   scripts/dev/wt.sh land <NNN|branch>   sync, land_check (all), then fast-forward main
#   scripts/dev/wt.sh ci   <NNN|branch>   push branch + dispatch audit-local (needs RPG_WT_PUSH=1)
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

GENERATED_IDX="project_index/repo_graph.json project_index/manifest.json"

# Rebase on main. A stale branch may carry the old "sync indexes" commit, which
# touches the (now untracked) project_index artifacts and specs/index.yaml: when the
# conflict is ONLY in those three files, drop the artifacts, take main's
# specs/index.yaml (regenerated right after) and continue. Anything else stops.
rebase_main() {
  local max i conflicts extra f
  max=$(( $(git rev-list --count main..HEAD) + 1 ))
  if git rebase -q main; then return 0; fi
  for ((i = 0; i < max; i++)); do
    conflicts="$(git diff --name-only --diff-filter=U)"
    extra=""
    for f in $conflicts; do
      case "$f" in
        project_index/repo_graph.json|project_index/manifest.json|specs/index.yaml) ;;
        *) extra="$extra $f";;
      esac
    done
    if [ -n "$extra" ]; then
      echo "rebase stopped; conflicts outside generated files:$extra (resolve in $WT)" >&2; return 1
    fi
    # -f also deletes the conflict leftovers from the tree: untracked copies would
    # block the next pick. They are generated files (python -m project_index build).
    # shellcheck disable=SC2086
    git rm -qf --ignore-unmatch $GENERATED_IDX
    if echo "$conflicts" | grep -qx "specs/index.yaml"; then
      git checkout --ours specs/index.yaml && git add specs/index.yaml
    fi
    if GIT_EDITOR=true git rebase --continue >/dev/null; then return 0; fi
  done
  echo "rebase still in conflict after $max auto-resolutions; aborting" >&2
  git rebase --abort || true
  return 1
}

sync_branch() {
  cd "$WT"
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "worktree $WT has uncommitted tracked changes; commit them first" >&2; exit 1
  fi
  rebase_main || exit 1
  py "$WT" scripts/spec_index.py build
  # project_index artifacts are local, untracked: never let them back into git.
  # shellcheck disable=SC2086
  git rm -q --cached --ignore-unmatch $GENERATED_IDX
  git add specs/index.yaml
  if ! git diff --cached --quiet; then
    git commit -q -m "chore: sync spec index

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
    echo "synced index: $(git log --oneline -1)"
  else
    echo "index already in sync"
  fi
  py "$WT" scripts/spec_index.py check >/dev/null
  land_check collision
}

# SPEC-415: pre-landing checks (scripts/dev/land_check.py). Branch spec-NNN only.
land_check() {
  case "$BR" in spec-[0-9][0-9][0-9]) ;; *) return 0;; esac
  (cd "$WT" && bash scripts/dev/land_check.sh "${BR#spec-}" ${1:+--only "$1"}) || {
    echo "land_check reprovou: corrija e rode de novo (a branch fica rebaseada, nada foi desfeito)" >&2
    exit 1
  }
}

case "$cmd" in
  new)
    git -C "$MAIN" worktree add -q -b "$BR" "$WT" main
    if [ -d "$MAIN/web/node_modules" ] && [ ! -e "$WT/web/node_modules" ]; then
      powershell.exe -NoProfile -Command "New-Item -ItemType Junction -Path \"$(cygpath -w "$WT/web/node_modules")\" -Target \"$(cygpath -w "$MAIN/web/node_modules")\" | Out-Null" \
        || echo "warning: could not junction web/node_modules" >&2
    fi
    if [ -d "$MAIN/.venv" ]; then
      echo "venv: $MAIN/.venv (não rode \`uv sync\` no worktree)" >&2
    else
      echo "sem venv no principal: rode \`uv sync --all-extras\` em $MAIN" >&2
    fi
    echo "$WT";;
  sync)
    sync_branch;;
  land)
    sync_branch
    land_check
    cd "$MAIN"
    [ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || { echo "main checkout is not on main" >&2; exit 1; }
    git merge -q --ff-only "$BR"
    git log --oneline -3;;
  ci)
    if [ "${RPG_WT_PUSH:-}" != "1" ]; then
      echo "push de branch desligado: precisa de autorização permanente do dono (ver SPEC-415 §7)" >&2
      exit 3
    fi
    git -C "$WT" push --force-with-lease origin "$BR"
    gh workflow run audit-local.yml --ref "$BR"
    sha="$(git -C "$WT" rev-parse "$BR")"
    echo "disparado para $sha; ci-watcher: gh run list --workflow audit-local.yml --branch $BR --json headSha,conclusion,status,event --limit 10";;
  drop)
    # The web/node_modules junction points at MAIN's node_modules: remove the link itself
    # (never its target) first, otherwise `worktree remove` leaves an empty dir behind and
    # the next `wt.sh new` fails with "already exists".
    if [ -e "$WT/web/node_modules" ]; then
      powershell.exe -NoProfile -Command "\$i = Get-Item -LiteralPath \"$(cygpath -w "$WT/web/node_modules")\" -Force; if (\$i.Attributes -match 'ReparsePoint') { \$i.Delete() }" 2>/dev/null || true
    fi
    git -C "$MAIN" worktree remove --force "$WT" 2>/dev/null || true
    [ -d "$WT" ] && [ -z "$(find "$WT" -type f -print -quit 2>/dev/null)" ] && rm -rf "$WT"
    git -C "$MAIN" branch -D "$BR" 2>/dev/null || true;;
  path)
    echo "$WT";;
  *) sed -n '2,15p' "$0"; exit 2;;
esac
