# Source me: `. scripts/dev/env.sh` (Git Bash). Sets the project shell environment:
#   - repo root as cwd (fixes "No module named ..." when running python from a subdir)
#   - uv on PATH (it lives outside PATH on this Windows machine)
#   - PYTHONUTF8=1 (fixes UnicodeEncodeError 'charmap' on cp1252 consoles)
#   - UV_PROJECT_ENVIRONMENT -> main checkout's .venv when this worktree has none
RPG_ROOT="$(git rev-parse --show-toplevel)"
export PYTHONUTF8=1
unset VIRTUAL_ENV
export PYTHONIOENCODING=utf-8
if [ -n "${APPDATA:-}" ]; then
  export PATH="$(cygpath -u "$APPDATA" 2>/dev/null || echo "$APPDATA")/Python/Python314/Scripts:$PATH"
fi
if [ ! -d "$RPG_ROOT/.venv" ] && [ -z "${UV_PROJECT_ENVIRONMENT:-}" ]; then
  RPG_MAIN="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
  if [ -d "$RPG_MAIN/.venv" ]; then export UV_PROJECT_ENVIRONMENT="$RPG_MAIN/.venv"; fi
fi
cd "$RPG_ROOT" || return 1
