"""PreToolUse guard (SPEC-386 R2/R3): barra leituras caras e pytest pesado em subagente.

Stdin: JSON do Claude Code (`tool_name`, `tool_input`, `cwd`, `agent_id` só em subagente).
Nega com `permissionDecision: deny` e um motivo curto que diz o que fazer no lugar.
Qualquer erro interno => permite (hook nunca derruba a sessão).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

MAX_BYTES = 40_000
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".pdf", ".ipynb"}
CAT_CMDS = {"cat", "type", "get-content", "gc"}
GC_CAPS = {"-totalcount", "-tail", "-first", "-head"}
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\n")
CD_RE = re.compile(r"^\s*cd\s+(.+?)\s*$")
XDIST_RE = re.compile(r"(?:^|\s)(?:-n\s*|--numprocesses[=\s]+)(auto|logical|\d+)\b")


def _deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def _norm(path: str) -> str:
    return path.replace("\\", "/").lower()


def _forbidden_transcript(path: str) -> bool:
    p = _norm(path)
    if "/.claude/projects/" in p and p.endswith(".jsonl"):
        return True
    return "/tasks/" in p and p.endswith(".output")


def _size(path: str, cwd: str) -> int:
    if not path:
        return 0
    if re.match(r"^/[a-zA-Z]/", path):  # Git Bash: /c/Users/... -> C:/Users/...
        path = f"{path[1]}:{path[2:]}"
    full = path if os.path.isabs(path) else os.path.join(cwd, path)
    try:
        return os.path.getsize(full) if os.path.isfile(full) else 0
    except OSError:
        return 0


def check_read(ti: dict, cwd: str) -> None:
    path = str(ti.get("file_path") or "")
    if _forbidden_transcript(path):
        _deny(
            "Transcritos .jsonl e tasks/*.output de outros agentes são proibidos (BRIEF_SUBAGENTE)."
        )
    if os.path.splitext(path)[1].lower() in BINARY_EXT:
        return
    if ti.get("offset") is None and ti.get("limit") is None:
        size = _size(path, cwd)
        if size > MAX_BYTES:
            _deny(
                f"{os.path.basename(path)} tem {size // 1024} KB. Use Grep para achar o trecho e "
                "Read com offset/limit (spec: `scripts/spec_index.py show NNN --section <título>`)."
            )


def _split_pipeline(segment: str) -> list[str]:
    return [p for p in re.split(r"(?<!\|)\|(?!\|)", segment) if p.strip()]


def _words(text: str) -> list[str]:
    # Caminho Windows (C:\x\y): posix come a barra invertida; aí divide sem posix e tira aspas.
    posix = "\\" not in text
    try:
        words = shlex.split(text, posix=posix)
    except ValueError:
        words = text.split()
    return words if posix else [w.strip("\"'") for w in words]


def check_shell(command: str, cwd: str, is_subagent: bool) -> None:
    if is_subagent and "pytest" in command:
        m = XDIST_RE.search(command)
        if m and (not m.group(1).isdigit() or int(m.group(1)) > 2):
            _deny(
                "Subagente não roda pytest com -n auto nem -n > 2 (RAM da máquina). "
                "Use `bash scripts/dev/pt.sh <testes>` (já usa -n 2)."
            )
    here = cwd
    for segment in SEGMENT_SPLIT.split(command):
        cd = CD_RE.match(segment)
        if cd:
            target = _words(cd.group(1))
            if target:
                t = target[0]
                if re.match(r"^/[a-zA-Z]/", t):
                    t = f"{t[1]}:{t[2:]}"
                here = t if os.path.isabs(t) else os.path.join(here, t)
            continue
        parts = _split_pipeline(segment)
        if not parts:
            continue
        last = parts[-1]  # só o último da pipeline despeja no contexto
        words = _words(last)
        if not words or words[0].lower() not in CAT_CMDS:
            continue
        if any(w.startswith(">") or w in {">", ">>"} for w in words) or "<<" in last:
            continue
        if any(w.lower() in GC_CAPS for w in words):
            continue
        for arg in words[1:]:
            if arg.startswith("-"):
                continue
            if _forbidden_transcript(arg):
                _deny("Transcritos .jsonl e tasks/*.output de outros agentes são proibidos.")
            size = _size(arg, here)
            if size > MAX_BYTES:
                _deny(
                    f"`{words[0]} {os.path.basename(arg)}` despeja {size // 1024} KB no contexto. "
                    "Use Grep + Read com offset/limit, `sed -n 'A,Bp'` ou `| head -N`."
                )


def main() -> None:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (ValueError, OSError, UnicodeDecodeError):
        return
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    try:
        cwd = data.get("cwd") or os.getcwd()
        if tool == "Read":
            check_read(ti, cwd)
        elif tool in {"Bash", "PowerShell"}:
            check_shell(str(ti.get("command") or ""), cwd, bool(data.get("agent_id")))
    except SystemExit:
        raise
    except Exception:  # silent-ok: hook nunca derruba a sessão
        return


if __name__ == "__main__":
    main()
