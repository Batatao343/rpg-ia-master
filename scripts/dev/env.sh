# Source me: `. scripts/dev/env.sh` (Git Bash). Sets the project shell environment:
#   - repo root as cwd (fixes "No module named ..." when running python from a subdir)
#   - uv on PATH (it lives outside PATH on this Windows machine)
#   - PYTHONUTF8=1 (fixes UnicodeEncodeError 'charmap' on cp1252 consoles)
#   - UV_PROJECT_ENVIRONMENT -> main checkout's .venv in a worktree whose uv.lock equals
#     the main one (even if the worktree has its own .venv; SPEC-414 R4.1)
RPG_ROOT="$(git rev-parse --show-toplevel)"
export PYTHONUTF8=1
unset VIRTUAL_ENV
export PYTHONIOENCODING=utf-8
if [ -n "${APPDATA:-}" ]; then
  export PATH="$(cygpath -u "$APPDATA" 2>/dev/null || echo "$APPDATA")/Python/Python314/Scripts:$PATH"
fi
if [ -z "${UV_PROJECT_ENVIRONMENT:-}" ]; then
  RPG_MAIN="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
  if [ -n "$RPG_MAIN" ] && [ "$(cd "$RPG_MAIN" && pwd -P)" != "$(cd "$RPG_ROOT" && pwd -P)" ]; then
    if cmp -s "$RPG_ROOT/uv.lock" "$RPG_MAIN/uv.lock" && [ -d "$RPG_MAIN/.venv" ]; then
      [ -d "$RPG_ROOT/.venv" ] && echo "env: ignorando $RPG_ROOT/.venv; venv do principal" >&2
      export UV_PROJECT_ENVIRONMENT="$RPG_MAIN/.venv"
    elif ! cmp -s "$RPG_ROOT/uv.lock" "$RPG_MAIN/uv.lock"; then
      echo "env: uv.lock difere do principal: este worktree usa venv próprio; rode \`uv sync --all-extras --frozen\` aqui" >&2
    fi
  fi
fi
cd "$RPG_ROOT" || return 1
