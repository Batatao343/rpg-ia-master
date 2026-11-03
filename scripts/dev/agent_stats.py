"""Métricas de eficiência dos agentes em TODAS as sessões do projeto (SPEC-386 R11).

Complementa `transcript_stats.py` (uma sessão contra as metas): aqui é o agregado por
período, para comparar antes/depois de uma mudança de workspace.

    bash scripts/dev/py.sh scripts/dev/agent_stats.py --since 2026-11-04
    bash scripts/dev/py.sh scripts/dev/agent_stats.py --since 2026-10-01 --until 2026-11-03 --json

Lê os .jsonl linha a linha; imprime só contagens, nunca conteúdo de mensagem.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_DIR = (
    Path.home() / ".claude" / "projects" / "c--Users-guilh-OneDrive--rea-de-Trabalho-rpg-ia-master"
)
XDIST_HEAVY = re.compile(r"pytest[^\n]*(?:-n\s*auto|-nauto|--numprocesses[=\s]+auto)")
CAT_RE = re.compile(r"(?:^|&&|;|\|)\s*cat\s+[^|<>]+$")


def _chars(content: object) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(b.get("text", "")) if isinstance(b, dict) else len(str(b)) for b in content)
    return len(str(content))


def _new() -> dict:
    return {
        "files": 0,
        "result_chars": Counter(),
        "uses": Counter(),
        "big_results": 0,
        "errors": Counter(),
        "edit_unread": 0,
        "read_big_nolimit": 0,
        "pytest_heavy": 0,
        "cat_whole": 0,
        "agent_types": Counter(),
    }


def scan(path: Path, st: dict, since: str, until: str) -> None:
    pending: dict[str, tuple[str, dict]] = {}
    counted = False
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            ts = str(row.get("timestamp") or "")[:10]
            if not ts or ts < since or (until and ts > until):
                continue
            if not counted:
                st["files"] += 1
                counted = True
            msg = row.get("message")
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    name, inp = block.get("name", "?"), block.get("input") or {}
                    pending[block.get("id", "")] = (name, inp)
                    st["uses"][name] += 1
                    cmd = str(inp.get("command", "")) if isinstance(inp, dict) else ""
                    if name in {"Bash", "PowerShell"}:
                        st["pytest_heavy"] += bool(XDIST_HEAVY.search(cmd))
                        st["cat_whole"] += bool(CAT_RE.search(cmd))
                    if name == "Agent" and isinstance(inp, dict):
                        st["agent_types"][inp.get("subagent_type") or "(default)"] += 1
                elif block.get("type") == "tool_result":
                    name, inp = pending.get(block.get("tool_use_id", ""), ("?", {}))
                    size = _chars(block.get("content"))
                    st["result_chars"][name] += size
                    st["big_results"] += size > 20_000
                    if (
                        name == "Read"
                        and size > 40_000
                        and isinstance(inp, dict)
                        and not inp.get("limit")
                    ):
                        st["read_big_nolimit"] += 1
                    if block.get("is_error"):
                        st["errors"][name] += 1
                        if name in {"Edit", "Write"} and "has not been read yet" in str(
                            block.get("content")
                        ):
                            st["edit_unread"] += 1


def report(stats: dict[str, dict]) -> str:
    out = []
    for kind, st in stats.items():
        total = sum(st["result_chars"].values())
        out.append(
            f"## {kind}: {st['files']} transcritos · {total / 1e6:.1f} M chars de tool_result"
        )
        out.append(
            "  por ferramenta: "
            + ", ".join(f"{k} {v / 1e6:.1f}M" for k, v in st["result_chars"].most_common(6))
        )
        out.append(
            f"  resultados > 20 KB: {st['big_results']} · Read > 40 KB sem limit: {st['read_big_nolimit']}"
        )
        out.append(
            f"  cat de arquivo inteiro: {st['cat_whole']} · pytest -n auto: {st['pytest_heavy']}"
        )
        out.append(
            f"  Edit sem Read: {st['edit_unread']} · erros: {dict(st['errors'].most_common(5))}"
        )
        if st["agent_types"]:
            out.append(
                "  Agent por tipo: "
                + ", ".join(f"{k} {v}" for k, v in st["agent_types"].most_common(8))
            )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--since", default="0000-00-00", help="AAAA-MM-DD (inclusive)")
    parser.add_argument("--until", default="", help="AAAA-MM-DD (inclusive)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    stats = {"principal": _new(), "subagentes": _new()}
    for dirpath, _, names in os.walk(args.dir):
        for name in names:
            if name.endswith(".jsonl"):
                path = Path(dirpath) / name
                kind = "principal" if path.parent == args.dir else "subagentes"
                scan(path, stats[kind], args.since, args.until)
    print(json.dumps(stats, default=dict, indent=1) if args.json else report(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
