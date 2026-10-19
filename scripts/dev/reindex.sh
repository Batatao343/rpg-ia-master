#!/usr/bin/env bash
# Rebuild the Project Index in the CURRENT checkout/worktree and commit it if it
# changed. Since the index hashes tracked files only, no clean clone is needed:
# it just refuses to run with uncommitted tracked changes.
# Normally /spec-land (scripts/dev/wt.sh land) already does this on the branch.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "uncommitted tracked changes; commit or stash first" >&2; exit 1
fi
bash scripts/dev/py.sh -m project_index build >/dev/null
if [ -n "$(git status --porcelain project_index)" ]; then
  git add project_index/manifest.json project_index/repo_graph.json
  git commit -q -m "chore: rebuild project index

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  echo "reindexed: $(git log --oneline -1)"
else
  echo "index already fresh"
fi
bash scripts/dev/py.sh -m project_index check >/dev/null && echo "project_index check: fresh"
