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
XDIST_RE = re.compile(r"^(?:-n=?|--numprocesses=?)(auto|logical|\d+)?$")
PYTEST_TOKENS = {"pytest", "py.test", "pt.sh", "full.sh"}
UNTYPED = {"", "general-purpose", "claude"}
REASON_RE = re.compile(r"^\s*Motivo sem tipo:\s*(\S.{9,})$", re.MULTILINE)


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


def _base(word: str) -> str:
    name = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _after_pytest(words: list[str]) -> list[str] | None:
    """Palavras depois do token de pytest (`pytest`, `-m pytest`, `pt.sh`...); None = não é pytest."""
    for i, w in enumerate(words):
        if _base(w) in PYTEST_TOKENS:
            return words[i + 1 :]
    return None


def _xdist_value(rest: list[str]) -> str | None:
    for i, w in enumerate(rest):
        m = XDIST_RE.match(w)
        if not m:
            continue
        value = m.group(1) or (rest[i + 1] if i + 1 < len(rest) else "")
        if re.fullmatch(r"auto|logical|\d+", value):
            return value
    return None


def _heavy_xdist(segment: str) -> bool:
    for part in _split_pipeline(segment):
        rest = _after_pytest(_words(part))
        value = _xdist_value(rest) if rest else None
        if value and (not value.isdigit() or int(value) > 2):
            return True
    return False


def _runs_full_suite(segment: str) -> bool:
    for part in _split_pipeline(segment):
        words = _words(part)
        for i, w in enumerate(words):
            if _base(w) == "full.sh" and (i == 0 or _base(words[i - 1]) in {"bash", "sh", "."}):
                return True
    return False


# SPEC-416 R28: script de baseline -> flag que SOBE o teto (ruff_baseline: tudo exceto os flags livres).
BASELINE_SCRIPTS = {
    "size_budget": ("--update",),
    "clock_asserts": ("--update",),
    "type_gate": ("--update",),  # SPEC-418 D-418-6
    "ruff_baseline": (),
}
RUNNERS = {"py.sh", "python", "python3", "-m"}


def _script_name(word: str) -> str:
    name = _base(word)
    name = name.rsplit(".", 1)[-1] if name.startswith("scripts.dev.") else name
    return name[:-3] if name.endswith(".py") else name


def _raises_baseline(words: list[str]) -> bool:
    """O comando executa um script de baseline pedindo para subir o teto (só o coordenador)."""
    for i, w in enumerate(words):
        script = _script_name(w)
        if script not in BASELINE_SCRIPTS or not (i == 0 or _base(words[i - 1]) in RUNNERS):
            continue
        rest = words[i + 1 :]
        if script == "ruff_baseline":
            return not {"--check", "--tighten"} & set(rest)
        return any(flag in rest for flag in BASELINE_SCRIPTS[script])
    return False


def _check_subagent(command: str) -> None:
    for seg in SEGMENT_SPLIT.split(command):
        if any(_raises_baseline(_words(part)) for part in _split_pipeline(seg)):
            _deny(
                "Subir baseline é do coordenador: extraia o código ou peça no hand-back "
                "com o motivo (`--tighten` e o check continuam livres)."
            )
        if _runs_full_suite(seg):
            _deny(
                "Suíte completa é do coordenador; use `bash scripts/dev/pt.sh <testes>` "
                "(já usa -n 2)."
            )
        if _heavy_xdist(seg):
            _deny(
                "Subagente não roda pytest com -n auto nem -n > 2 (RAM da máquina). "
                "Use `bash scripts/dev/pt.sh <testes>` (já usa -n 2)."
            )


def check_shell(command: str, cwd: str, is_subagent: bool) -> None:
    if is_subagent:
        _check_subagent(command)
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


def check_agent(ti: object) -> None:
    """SPEC-414 R6: `Agent` sem tipo (ou general-purpose/claude) exige `Motivo sem tipo: <motivo>`."""
    if not isinstance(ti, dict):
        return
    stype = str(ti.get("subagent_type") or "").strip().lower()
    if stype not in UNTYPED:
        return
    prompt = ti.get("prompt")
    if isinstance(prompt, str) and REASON_RE.search(prompt):
        return
    _deny(
        "Agent sem tipo exige linha `Motivo sem tipo: <por quê>` no prompt. Tipos do repo: "
        "spec-executor, spec-reviewer, spec-author, code-locator, audit-reader, ci-watcher "
        "(ver CLAUDE.md)."
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
        elif tool in {"Agent", "Task"}:
            check_agent(ti)
        elif tool in {"Bash", "PowerShell"}:
            check_shell(str(ti.get("command") or ""), cwd, bool(data.get("agent_id")))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - hook nunca derruba a sessão (falha aberto)
        # Falha aberto, mas com sinal: bug do próprio hook não pode virar "sem proteção" calado.
        print(f"guard_tools: erro interno, guarda inativa: {exc!r}", file=sys.stderr)
        return


if __name__ == "__main__":
    main()
