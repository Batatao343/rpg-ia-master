"""Measure a Claude Code session against the workspace targets (docs/melhorias_workspace/01 §5).

Reads transcripts line by line (never whole) and prints:
- context of the first model call (target < 70 K tokens)
- median / max context of the session (target median < 300 K)
- full-suite pytest runs across the session and its subagents (target < 30 per wave)
- Stop-hook summaries (target 0 without progress)
- share of tool-result volume coming from results >= 10 K chars (target < 15 %)
- subagent count, model mix, `sleep` calls

Usage:
    bash scripts/dev/py.sh scripts/dev/transcript_stats.py <session.jsonl> [--json]

Subagent transcripts are picked up from ``<session-id>/subagents/agent-*.jsonl`` next to
the session file. Only counts are printed — never message content.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path

FULL_SUITE = re.compile(r"\bpytest\b(?![^\n]*(tests/|::|-k\s|--lf|\.py\b))")


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return ""


def scan(path: Path) -> dict[str, object]:
    contexts: list[int] = []
    results: list[int] = []
    models: Counter[str] = Counter()
    stop_hooks = full_suite = sleeps = 0
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = item.get("type")
            if kind == "system" and "stop_hook" in str(item.get("subtype")):
                stop_hooks += 1
            message = item.get("message") or {}
            if kind == "assistant":
                usage = message.get("usage") or {}
                total = (
                    usage.get("input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                )
                if total:
                    contexts.append(total)
                if message.get("model"):
                    models[message["model"]] += 1
                for block in message.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        command = str((block.get("input") or {}).get("command", ""))
                        full_suite += bool(FULL_SUITE.search(command))
                        sleeps += len(re.findall(r"\bsleep\s+\d", command))
            elif kind == "user" and isinstance(message.get("content"), list):
                for block in message["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        results.append(len(_text(block.get("content"))))
    return {
        "calls": len(contexts),
        "first_context": contexts[0] if contexts else 0,
        "median_context": int(statistics.median(contexts)) if contexts else 0,
        "max_context": max(contexts, default=0),
        "stop_hooks": stop_hooks,
        "full_suite_runs": full_suite,
        "sleeps": sleeps,
        "tool_result_chars": sum(results),
        "big_result_chars": sum(size for size in results if size >= 10_000),
        "models": dict(models),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("session", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    session = scan(args.session)
    agents_dir = args.session.with_suffix("") / "subagents"
    agents = (
        [scan(path) for path in sorted(agents_dir.glob("agent-*.jsonl"))]
        if agents_dir.is_dir()
        else []
    )
    total_results = session["tool_result_chars"] + sum(a["tool_result_chars"] for a in agents)
    big = session["big_result_chars"] + sum(a["big_result_chars"] for a in agents)
    report = {
        "first_context_tokens": session["first_context"],
        "median_context_tokens": session["median_context"],
        "max_context_tokens": session["max_context"],
        "model_calls": session["calls"],
        "stop_hook_summaries": session["stop_hooks"],
        "full_suite_runs": session["full_suite_runs"] + sum(a["full_suite_runs"] for a in agents),
        "sleep_calls": session["sleeps"] + sum(a["sleeps"] for a in agents),
        "subagents": len(agents),
        "subagent_models": dict(sum((Counter(a["models"]) for a in agents), Counter())),
        "big_tool_result_share": round(big / total_results, 3) if total_results else 0.0,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        targets = {
            "first_context_tokens": "< 70000",
            "median_context_tokens": "< 300000",
            "full_suite_runs": "< 30/onda",
            "stop_hook_summaries": "0",
            "big_tool_result_share": "< 0.15",
        }
        for key, value in report.items():
            print(f"{key:<24} {value}" + (f"   (meta {targets[key]})" if key in targets else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
