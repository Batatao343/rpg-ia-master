"""Auditable discovery-only harness for the SPEC-175 Project Index A/B."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_index.query import impact, lookup_tests, query, state, symbol

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_VERSION = "v6"
BENCHMARK_ROOT = ROOT / f"docs/project-index-benchmark/{BENCHMARK_VERSION}"
SESSION_ROOT = BENCHMARK_ROOT / "sessions"
ATTESTATION = BENCHMARK_ROOT / "attestation.json"
SESSION_RE = re.compile(rf"^[ab][12]-{BENCHMARK_VERSION}$")
TASK_RE = re.compile(r"^B0[1-8]$")
MAX_CALLS_PER_TASK = 12
MAX_SOURCE_BYTES_PER_TASK = 50_000
MAX_WALL_SECONDS_PER_TASK = 300.0
ALLOWED_DIRS = (
    "agents/", "services/", "tests/", "web/src/", "web/e2e/",
    "infrastructure/", "playtest/", "evals/",
)
ALLOWED_DIR_ROOTS = frozenset(path.rstrip("/") for path in ALLOWED_DIRS)
ALLOWED_ROOT_FILES = {
    "api.py", "main.py", "state.py", "persistence.py", "llm_setup.py",
    "rag.py", "world_utils.py", "combat_mechanics.py", "inventory.py",
}
FORBIDDEN_PARTS = {
    ".git", "docs", "specs", "project_index", ".agents", ".claude",
    "ESTADO_ATUAL.md", "ROADMAP.md", "AGENTS.md",
}


class HarnessError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _session_path(session_id: str) -> Path:
    if not SESSION_RE.fullmatch(session_id):
        raise HarnessError("invalid session id")
    return SESSION_ROOT / f"{session_id}.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HarnessError(f"cannot load {path}: {error}") from error
    if not isinstance(payload, dict):
        raise HarnessError(f"{path} must contain an object")
    return payload


def _save_session(payload: dict[str, Any]) -> None:
    path = _session_path(str(payload["session_id"]))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _session(session_id: str, task: str | None = None) -> dict[str, Any]:
    payload = _load_json(_session_path(session_id))
    if payload.get("status") not in {"ready", "running"}:
        raise HarnessError("session is not active")
    if task is not None:
        if payload.get("active_task") != task:
            raise HarnessError(f"task {task} is not active")
        _enforce_time(payload)
    return payload


def _enforce_time(payload: dict[str, Any]) -> None:
    started = payload.get("task_started_at")
    if not started:
        return
    elapsed = (datetime.now(UTC) - datetime.fromisoformat(str(started))).total_seconds()
    if elapsed > MAX_WALL_SECONDS_PER_TASK:
        raise HarnessError(f"task wall budget exceeded ({elapsed:.1f}s)")


def _relative(value: str) -> str:
    raw = value.replace("\\", "/").strip()
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise HarnessError(f"unsafe path: {value}")
    normalized = path.as_posix().lstrip("./")
    if not normalized:
        raise HarnessError("empty path")
    if any(part in FORBIDDEN_PARTS for part in PurePosixPath(normalized).parts):
        raise HarnessError(f"forbidden benchmark path: {normalized}")
    if (
        normalized not in ALLOWED_ROOT_FILES
        and normalized not in ALLOWED_DIR_ROOTS
        and not normalized.startswith(ALLOWED_DIRS)
    ):
        raise HarnessError(f"path outside discovery allowlist: {normalized}")
    return normalized


def _record(
    payload: dict[str, Any], *, task: str, op: str, detail: dict[str, Any],
    source_bytes: int,
) -> None:
    task_rows = payload.setdefault("task_usage", {}).setdefault(
        task, {"discovery_calls": 0, "source_bytes_read": 0, "trace": []}
    )
    next_calls = int(task_rows["discovery_calls"]) + 1
    next_bytes = int(task_rows["source_bytes_read"]) + source_bytes
    if next_calls > MAX_CALLS_PER_TASK:
        raise HarnessError("task discovery-call budget exceeded")
    if next_bytes > MAX_SOURCE_BYTES_PER_TASK:
        raise HarnessError("task source-byte budget exceeded")
    task_rows["discovery_calls"] = next_calls
    task_rows["source_bytes_read"] = next_bytes
    task_rows["trace"].append({
        "sequence": next_calls,
        "at": _now(),
        "op": op,
        "source_bytes": source_bytes,
        **detail,
    })
    _save_session(payload)


def init_session(args: argparse.Namespace) -> int:
    attestation = _load_json(ATTESTATION)
    path = _session_path(args.session)
    if path.exists():
        raise HarnessError("session already exists")
    order = args.order.split(",")
    if sorted(order) != [f"B0{i}" for i in range(1, 9)]:
        raise HarnessError("order must contain B01..B08 exactly once")
    if args.condition not in {"A", "B"}:
        raise HarnessError("condition must be A or B")
    payload = {
        "schema_version": 2,
        "session_id": args.session,
        "condition": args.condition,
        "replicate": args.replicate,
        "model": args.model,
        "effort": args.effort,
        "discovery_budget": {
            "max_calls_per_task": MAX_CALLS_PER_TASK,
            "max_source_bytes_per_task": MAX_SOURCE_BYTES_PER_TASK,
            "max_wall_seconds_per_task": MAX_WALL_SECONDS_PER_TASK,
        },
        "prompt_hash": attestation["prompt_hash"],
        "condition_prompt_hash": attestation["condition_prompt_hashes"][args.condition],
        "session_prompt_hash": attestation["session_prompt_hashes"][args.session],
        "source_tree_hash": attestation["source_tree_hash"],
        "project_index_graph_hash": attestation["project_index_graph_hash"],
        "attestation_hash": attestation["attestation_hash"],
        "order": order,
        "next_task_index": 0,
        "active_task": None,
        "status": "ready",
        "created_at": _now(),
        "task_usage": {},
        "results": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _save_session(payload)
    print(path)
    return 0


def begin_task(args: argparse.Namespace) -> int:
    if not TASK_RE.fullmatch(args.task):
        raise HarnessError("invalid task id")
    payload = _session(args.session)
    expected = payload["order"][int(payload["next_task_index"])]
    if args.task != expected or payload.get("active_task") is not None:
        raise HarnessError(f"expected next task {expected}")
    payload["active_task"] = args.task
    payload["task_started_at"] = _now()
    payload["status"] = "running"
    payload.setdefault("task_usage", {})[args.task] = {
        "discovery_calls": 0, "source_bytes_read": 0, "trace": []
    }
    _save_session(payload)
    print(args.task)
    return 0


def search_source(args: argparse.Namespace) -> int:
    payload = _session(args.session, args.task)
    paths = [_relative(path) for path in args.path]
    if payload["condition"] == "B" and not payload["task_usage"][args.task].get("index_queried"):
        raise HarnessError("condition B must query the index before source discovery")
    command = ["rg", "-n", "-C", str(args.context), "--", args.pattern, *paths]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode not in {0, 1}:
        raise HarnessError(result.stderr.strip() or "rg failed")
    output = result.stdout
    size = len(output.encode("utf-8"))
    _record(
        payload, task=args.task, op="search",
        detail={"pattern": args.pattern, "paths": paths, "context": args.context},
        source_bytes=size,
    )
    print(output, end="")
    return 0


def read_source(args: argparse.Namespace) -> int:
    payload = _session(args.session, args.task)
    relative = _relative(args.path)
    if payload["condition"] == "B" and not payload["task_usage"][args.task].get("index_queried"):
        raise HarnessError("condition B must query the index before source discovery")
    lines = (ROOT / relative).read_text(encoding="utf-8").splitlines()
    start = max(1, args.start)
    selected = lines[start - 1:start - 1 + args.lines]
    output = "\n".join(f"{index}: {line}" for index, line in enumerate(selected, start=start))
    if output:
        output += "\n"
    size = len(output.encode("utf-8"))
    _record(
        payload, task=args.task, op="read",
        detail={"path": relative, "start": start, "lines": args.lines},
        source_bytes=size,
    )
    print(output, end="")
    return 0


def index_query(args: argparse.Namespace) -> int:
    payload = _session(args.session, args.task)
    if payload["condition"] != "B":
        raise HarnessError("condition A cannot use Project Index")
    handlers = {
        "query": query,
        "tests": lookup_tests,
        "state": state,
        "symbol": symbol,
        "impact": impact,
    }
    result = handlers[args.mode](ROOT, args.value, args.limit)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    payload["task_usage"][args.task]["index_queried"] = True
    _record(
        payload, task=args.task, op=f"index:{args.mode}",
        detail={"value": args.value, "limit": args.limit, "output_bytes": len(output.encode("utf-8"))},
        source_bytes=0,
    )
    print(output, end="")
    return 0


def finish_task(args: argparse.Namespace) -> int:
    payload = _session(args.session, args.task)
    try:
        result = json.loads(args.result_json)
    except json.JSONDecodeError as error:
        raise HarnessError(f"invalid result JSON: {error}") from error
    if not isinstance(result, dict) or result.get("id") != args.task:
        raise HarnessError("result must be an object for the active task")
    files = result.get("files")
    tests = result.get("tests")
    resolution = result.get("resolution")
    if not isinstance(files, list) or not 1 <= len(files) <= 5:
        raise HarnessError("result files must contain 1..5 paths")
    if not isinstance(tests, list) or len(tests) > 3:
        raise HarnessError("result tests must contain at most 3 paths")
    if not isinstance(resolution, str) or not resolution.strip():
        raise HarnessError("result resolution is required")
    usage = payload["task_usage"][args.task]
    if payload["condition"] == "B" and not usage.get("index_queried"):
        raise HarnessError("condition B task has no index query")
    started = datetime.fromisoformat(payload["task_started_at"])
    elapsed = round((datetime.now(UTC) - started).total_seconds(), 3)
    result.update({
        "discovery_calls": usage["discovery_calls"],
        "source_bytes_read": usage["source_bytes_read"],
        "wall_seconds": elapsed,
    })
    payload["results"].append(result)
    payload["next_task_index"] = int(payload["next_task_index"]) + 1
    payload["active_task"] = None
    payload.pop("task_started_at", None)
    if payload["next_task_index"] == len(payload["order"]):
        payload["status"] = "complete"
        payload["completed_at"] = _now()
    else:
        payload["status"] = "ready"
    _save_session(payload)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--session", required=True)
    init.add_argument("--condition", required=True)
    init.add_argument("--replicate", type=int, choices=(1, 2), required=True)
    init.add_argument("--order", required=True)
    init.add_argument("--model", required=True)
    init.add_argument("--effort", required=True)
    init.set_defaults(handler=init_session)
    begin = sub.add_parser("begin")
    begin.add_argument("session")
    begin.add_argument("task")
    begin.set_defaults(handler=begin_task)
    search = sub.add_parser("search")
    search.add_argument("session")
    search.add_argument("task")
    search.add_argument("pattern")
    search.add_argument("--path", action="append", required=True)
    search.add_argument("--context", type=int, default=2, choices=range(0, 6))
    search.set_defaults(handler=search_source)
    read = sub.add_parser("read")
    read.add_argument("session")
    read.add_argument("task")
    read.add_argument("path")
    read.add_argument("--start", type=int, default=1)
    read.add_argument("--lines", type=int, default=120, choices=range(1, 301))
    read.set_defaults(handler=read_source)
    index = sub.add_parser("index")
    index.add_argument("session")
    index.add_argument("task")
    index.add_argument("mode", choices=("query", "tests", "state", "symbol", "impact"))
    index.add_argument("value")
    index.add_argument("--limit", type=int, default=12, choices=range(1, 21))
    index.set_defaults(handler=index_query)
    finish = sub.add_parser("finish")
    finish.add_argument("session")
    finish.add_argument("task")
    finish.add_argument("--result-json", required=True)
    finish.set_defaults(handler=finish_task)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.handler(args))
    except (HarnessError, OSError, ValueError) as error:
        print(f"benchmark harness failed: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
