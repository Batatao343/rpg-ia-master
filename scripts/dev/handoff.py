"""SPEC-415 R21: handoff de sessao do coordenador em formato fixo (`/estado --handoff`).

handoff.py [--out <caminho>]     grava .tmp/handoff-AAAA-MM-DD.md (o anterior vira .prev.md)
handoff.py --check <caminho>     rc 1 se sobrar <PREENCHER ou faltar uma das 8 secoes
"""

from __future__ import annotations

import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECTIONS = (
    "main",
    "Worktrees e specs ativas",
    "Testes rodados",
    "Decisões do dono nesta sessão",
    "Bloqueios",
    "Próximo passo",
    "Não refazer",
)
_FILL = {
    "Testes rodados": "<PREENCHER: comando → resultado>",
    "Decisões do dono nesta sessão": "<PREENCHER>",
    "Bloqueios": "<PREENCHER>\n\nVer ESTADO_ATUAL.md § Bloqueios.",
    "Próximo passo": "<PREENCHER: 1 a 3 itens>",
    "Não refazer": "<PREENCHER: lições/armadilhas desta sessão>",
}


def render(facts: dict[str, str], now: datetime.datetime) -> str:
    out = [f"# Handoff do coordenador — {now:%Y-%m-%d %H:%M}", ""]
    for name in SECTIONS:
        body = {
            "main": facts.get("main", ""),
            "Worktrees e specs ativas": facts.get("worktrees", ""),
        }.get(name) or _FILL[name]
        out += [f"## {name}", "", body.rstrip(), ""]
    return "\n".join(out)


def check(text: str) -> list[str]:
    problems = [f"falta a secao '## {s}'" for s in SECTIONS if f"## {s}\n" not in text]
    if "<PREENCHER" in text:
        problems.append("sobrou <PREENCHER")
    return problems


def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return out.stdout.strip()


def _spec_status(path: Path) -> str:
    m = re.search(r"^> \*\*Status:\*\*\s*`([^`]+)`", path.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "?"


def gather() -> dict[str, str]:
    ahead = _git("rev-list", "--count", "origin/main..main") or "?"
    facts = {
        "main": f"{_git('log', '-1', '--format=%h %s')}\n\n{ahead} commit(s) à frente de origin/main."
    }
    lines = [_git("worktree", "list")]
    for line in lines[0].splitlines():
        m = re.search(r"\[spec-(\d{3})\]", line)
        spec = next((ROOT / "specs").glob(f"SPEC-{m.group(1)}-*.md"), None) if m else None
        if m and spec:
            lines.append(f"- SPEC-{m.group(1)}: `{_spec_status(spec)}`")
    facts["worktrees"] = "\n".join(lines)
    return facts


def write(out: Path, text: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        prev = out.with_suffix(".prev.md")
        prev.unlink(missing_ok=True)
        out.replace(prev)
    out.write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--check"] and len(argv) == 2:
        problems = check(Path(argv[1]).read_text(encoding="utf-8"))
        print("\n".join(problems) or "handoff ok")
        return 1 if problems else 0
    if argv[:1] == ["--out"] and len(argv) == 2:
        out = Path(argv[1])
    elif not argv:
        out = ROOT / ".tmp" / f"handoff-{datetime.date.today().isoformat()}.md"
    else:
        print("uso: handoff.py [--out <caminho>] | --check <caminho>", file=sys.stderr)
        return 2
    write(out, render(gather(), datetime.datetime.now()))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
