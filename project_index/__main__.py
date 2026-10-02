"""CLI for building and querying the Valoria project index."""

from __future__ import annotations

import argparse
from pathlib import Path

from project_index.generator import ProjectIndexError, build_index, check_index, freshness_status
from project_index.query import dumps, impact, lookup_tests, query, state, symbol


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build")
    commands.add_parser("check")
    for name in ("query", "symbol", "impact", "tests", "state"):
        command = commands.add_parser(name)
        command.add_argument("value")
        command.add_argument("--limit", type=int, default=12)
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = args.root.resolve()
    try:
        if args.command == "build":
            graph, manifest = build_index(root)
            print(dumps({"nodes": len(graph["nodes"]), "edges": len(graph["edges"]), **manifest}))
        elif args.command == "check":
            graph, manifest = check_index(root)
            status = freshness_status(root, manifest)
            print(dumps({"status": status, "nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "commit_sha": manifest["commit_sha"], "source_tree_hash": manifest["source_tree_hash"], "warning": "commit SHA drift; source tree is byte-identical" if status != "fresh" else None}))
        elif args.command == "query":
            print(dumps(query(root, args.value, args.limit)))
        elif args.command == "symbol":
            print(dumps(symbol(root, args.value, args.limit)))
        elif args.command == "impact":
            print(dumps(impact(root, args.value, args.limit)))
        elif args.command == "tests":
            print(dumps(lookup_tests(root, args.value, args.limit)))
        else:
            print(dumps(state(root, args.value, args.limit)))
    except ProjectIndexError as error:
        print(f"project index error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
