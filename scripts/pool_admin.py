"""Moderação do dono sobre o pool compartilhado (SPEC-297 R21).

Uso (legacy; em hosted, rodar com a conexão de sistema configurada no runtime):
  bash scripts/dev/py.sh scripts/pool_admin.py list [--status held] [--since 2026-10-01]
  bash scripts/dev/py.sh scripts/pool_admin.py show <entry_id>
  bash scripts/dev/py.sh scripts/pool_admin.py veto <entry_id> --reason "texto"
  bash scripts/dev/py.sh scripts/pool_admin.py restore <entry_id>
  bash scripts/dev/py.sh scripts/pool_admin.py retire <entry_id>

Cada ação gera o log `pool.admin_action` (sem conteúdo). O veto só tira a entrada do
pool para jogos NOVOS: cópias já materializadas em saves ficam (decisão D2).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime

sys.path.insert(0, ".")

from services import shared_pool  # noqa: E402


def _row(entry) -> dict:
    return {
        "entry_id": entry.entry_id,
        "namespace": entry.namespace.value,
        "status": entry.status.value,
        "name": entry.name,
        "region_id": entry.region_id,
        "created_at": entry.created_at.isoformat(),
    }


def main(argv: list[str] | None = None, store=None) -> int:
    parser = argparse.ArgumentParser(prog="pool_admin")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list")
    p_list.add_argument("--status")
    p_list.add_argument("--since")
    for name in ("show", "restore", "retire"):
        sub.add_parser(name).add_argument("entry_id")
    p_veto = sub.add_parser("veto")
    p_veto.add_argument("entry_id")
    p_veto.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    store = store or shared_pool.get_store()

    if args.cmd == "list":
        from services.shared_pool_models import PoolStatus

        statuses = [PoolStatus(args.status)] if args.status else None
        since = datetime.fromisoformat(args.since).replace(tzinfo=UTC) if args.since else None
        rows = [
            _row(e)
            for e in store.select(statuses=statuses)
            if since is None or e.created_at >= since
        ]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif args.cmd == "show":
        entry = store.get(args.entry_id)
        if entry is None:
            print("não encontrada", file=sys.stderr)
            return 1
        print(entry.model_dump_json(indent=2, exclude={"embedding", "input_shingles"}))
    elif args.cmd == "veto":
        print(_row(shared_pool.admin_veto(store, args.entry_id, args.reason)))
    elif args.cmd == "restore":
        print(_row(shared_pool.admin_restore(store, args.entry_id)))
    elif args.cmd == "retire":
        print(_row(shared_pool.admin_retire(store, args.entry_id)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
