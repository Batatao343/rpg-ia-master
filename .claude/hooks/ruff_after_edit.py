"""PostToolUse (Edit|Write) — SPEC-386 R1: `ruff format` + `ruff check --fix` no .py editado.

Usa a config do repo (pyproject + ruff-baseline.toml) e `--force-exclude`, então
caminhos excluídos (evals protegidos, data/) nunca são reescritos. `F401`/`F811` não são
corrigidos automaticamente: o import novo de uma edição costuma ser usado na próxima.
Violação restante volta ao agente como `additionalContext` (≤ 10 linhas).
Sem ruff ou fora de um repo com `[tool.ruff]`: não faz nada. Nunca bloqueia.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MAX_LINES = 10
PROTECTED_PREFIXES = ("evals/", "web/e2e/contracts/")


def _repo_root(path: Path) -> Path | None:
    for parent in path.parents:
        cfg = parent / "pyproject.toml"
        if cfg.is_file():
            try:
                return parent if "[tool.ruff" in cfg.read_text(encoding="utf-8") else None
            except OSError:
                return None
    return None


def _ruff(root: Path) -> str | None:
    candidates = [root / ".venv" / "Scripts" / "ruff.exe", root / ".venv" / "bin" / "ruff"]
    try:  # worktree sem .venv: usa o do checkout principal
        common = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        if common:
            main = Path(common).parent
            candidates += [main / ".venv" / "Scripts" / "ruff.exe", main / ".venv" / "bin" / "ruff"]
    except (OSError, subprocess.SubprocessError):
        pass
    for c in candidates:
        if c.is_file():
            return str(c)
    return shutil.which("ruff")


def _run(args: list[str], root: Path) -> str:
    env = {**os.environ, "PYTHONUTF8": "1"}
    out = subprocess.run(
        args, cwd=root, capture_output=True, text=True, timeout=20, env=env, encoding="utf-8"
    )
    return out.stdout


def main() -> None:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (ValueError, OSError, UnicodeDecodeError):
        return
    path = Path(str((data.get("tool_input") or {}).get("file_path") or ""))
    if path.suffix != ".py" or not path.is_file():
        return
    root = _repo_root(path.resolve())
    if root is None:
        return
    rel = path.resolve().relative_to(root).as_posix()
    if rel.startswith(PROTECTED_PREFIXES):  # evals/contratos: hash travado, nunca reescrever
        return
    ruff = _ruff(root)
    if ruff is None:
        return
    target = str(path.resolve())
    try:
        _run([ruff, "format", "--force-exclude", "--quiet", target], root)
        _run(
            [
                ruff,
                "check",
                "--force-exclude",
                "--fix",
                "--unfixable",
                "F401,F811",
                "--quiet",
                target,
            ],
            root,
        )
        left = _run(
            [ruff, "check", "--force-exclude", "--output-format", "concise", "--quiet", target],
            root,
        )
    except (OSError, subprocess.SubprocessError):
        return
    lines = [ln for ln in left.splitlines() if ln.strip()]
    if not lines:
        return
    shown = "\n".join(lines[:MAX_LINES])
    more = f"\n(+{len(lines) - MAX_LINES} violações)" if len(lines) > MAX_LINES else ""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": f"ruff ainda acusa em {path.name}:\n{shown}{more}",
                }
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # silent-ok: hook nunca derruba a sessão
        pass
