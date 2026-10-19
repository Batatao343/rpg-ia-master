"""SPEC-207: pacote de auditoria (ZIP) de UM jogo, para o operador.

Mesmo builder e mesma redaction do endpoint `POST /game/{id}/audit-export`.
Duas fontes:
  --dsn-env (padrão DATABASE_URL) + --owner  → Postgres owner-scoped (owner explícito)
  --save <arquivo.json>          → save local de fixture/playtest (sem banco)
Zero LLM, zero rede além do Postgres indicado.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from uuid import UUID

from services.dsn_cli import add_dsn_arguments, resolve_dsn


def _build_sha() -> str:
    env = os.getenv("GIT_SHA") or os.getenv("VERCEL_GIT_COMMIT_SHA")
    if env:
        return env
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
            ).stdout.strip()
            or "unknown"
        )
    except Exception:
        return "unknown"


def source_from_save(path: Path):
    from persistence import _raw_to_state
    from services.audit_export import AuditSource

    raw = json.loads(path.read_text(encoding="utf-8"))
    state = _raw_to_state(raw)
    return AuditSource(
        game_id=str(state.get("game_id") or path.stem),
        state=state,
        turns_reason="no_database_local_save",
        usage_reason="no_database_local_save",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("game_id", nargs="?", type=UUID)
    parser.add_argument("--owner", type=UUID)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    add_dsn_arguments(parser)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)
    from services.audit_export import bundle_zip, verify_audit_zip

    if args.save:
        source = source_from_save(args.save)
    else:
        if not (args.game_id and args.owner):
            parser.error("game_id + --owner (+ --dsn-env, ou --save) obrigatórios")
        from infrastructure.audit_source import PostgresAuditSource
        from infrastructure.contracts import Principal
        from infrastructure.postgres import PostgresGameStore, PostgresPool

        pool = PostgresPool(resolve_dsn(parser, args))
        try:
            principal = Principal(args.owner, "export", str(args.owner), local=True)
            source = PostgresAuditSource(pool, PostgresGameStore(pool), principal).load(
                args.game_id
            )
        finally:
            pool.close()
        if source is None:
            raise SystemExit("jogo não encontrado para este owner")
    data = bundle_zip(source, build_sha=_build_sha(), generated_at=args.generated_at)
    problems = verify_audit_zip(data, owner_values=source.owner_values)
    if problems:
        raise RuntimeError(f"pacote inválido: {problems}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(json.dumps({"output": str(args.output), "bytes": len(data), "verify": problems}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
