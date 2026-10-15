"""Operator CLI for kill switches (SPEC-196). Dry-run by default.

  uv run python scripts/admin_kill_switch.py list
  uv run python scripts/admin_kill_switch.py off image_generation --actor guilherme --reason "custo anomalo"
  uv run python scripts/admin_kill_switch.py on  image_generation --actor guilherme --reason "normalizado" --apply
"""
from __future__ import annotations

import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parents[1]))

import argparse
import json
import sys
from typing import Sequence

from services.kill_switches import KEY_RE, validate_change


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("audit").add_argument("--limit", type=int, default=50)
    for name in ("on", "off"):
        s = sub.add_parser(name)
        s.add_argument("key")
        s.add_argument("--actor", required=True)
        s.add_argument("--reason", required=True)
        s.add_argument("--apply", action="store_true", help="persist (default is dry-run)")
    return p


def main(argv: Sequence[str] | None = None, *, store=None) -> int:
    args = build_parser().parse_args(argv)
    if store is None:
        from infrastructure.kill_switch_store import PostgresSwitchStore
        from infrastructure.runtime import get_runtime
        store = PostgresSwitchStore(get_runtime().game_store.pool)
    if args.cmd == "list":
        print(json.dumps(store.load(), indent=2, sort_keys=True))
        return 0
    if args.cmd == "audit":
        print(json.dumps(store.audit(args.limit), indent=2, default=str))
        return 0
    enabled = args.cmd == "on"
    try:
        if not KEY_RE.fullmatch(args.key):
            raise ValueError("invalid_switch_key")
        validate_change(args.key, args.actor, args.reason)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    plan = {"key": args.key, "enabled": enabled, "actor": args.actor, "reason": args.reason,
            "mode": "apply" if args.apply else "dry-run"}
    if args.apply:
        store.set(args.key, enabled, actor_id=args.actor, reason=args.reason)
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
