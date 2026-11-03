"""SPEC-352 R13: retira um retrato de criatura compartilhado (moderação pelo operador).

Passa `ready` -> `retired`, apaga os objetos compartilhados e libera a chave para uma nova cotação.
Só `rpg_admin` (o runtime de sistema). Sem UI. Uso:

    bash scripts/dev/py.sh scripts/retire_creature_portrait.py "tipo:enemy_goblin" --reason "imagem imprópria"

Staging (fora da Vercel): `python -m scripts.retire_creature_portrait "tipo:X" --reason "..."
--env-file .env.staging --dsn-env RPG_STAGING_DB_URL [--dry-run]`.
"""

from __future__ import annotations

import argparse
import json

from infrastructure.db_roles import admin_connection
from infrastructure.runtime import build_runtime
from services.creature_portraits import PostgresPortraitRegistry


def retire(runtime, portrait_key: str, reason: str) -> dict:
    registry = PostgresPortraitRegistry(runtime.game_store.pool)
    keys = registry.retire(portrait_key=portrait_key, reason=reason)
    shared = getattr(runtime, "shared_blob_store", None)
    deleted = 0
    failed: list[str] = []
    for key in keys:
        if shared is not None and shared.delete(key):
            deleted += 1
        else:
            failed.append(key)
    return {
        "portrait_key": portrait_key,
        "status": "retired",
        "objects_deleted": deleted,
        "objects_failed": failed,
    }


def _dry_report(runtime, portrait_key: str) -> dict:
    """SPEC-367 R12: o que a retirada faria, sem mudar nada (só leitura)."""
    with admin_connection(runtime.game_store.pool) as connection:
        row = connection.execute(
            "select status, store, object_keys from app.creature_portraits where portrait_key=%s",
            (portrait_key,),
        ).fetchone()
    if not row:
        return {"portrait_key": portrait_key, "status_atual": None, "objetos": []}
    keys = [str(v) for v in (row["object_keys"] or {}).values()]
    return {
        "portrait_key": portrait_key,
        "status_atual": row["status"],
        "objetos": keys if row["store"] == "shared" else [],
    }


def _ops_runtime(dsn: str, values: dict[str, str]):
    """Banco direto pelo DSN (como o kill switch) + bucket compartilhado; sem montar o app hosted."""
    from types import SimpleNamespace

    from infrastructure.supabase_blob import SupabaseBlobStore
    from scripts.staging.ops_pool import open_ops_pool

    url = values.get("SUPABASE_URL", "")
    key = values.get("SUPABASE_SERVICE_ROLE_KEY", "")
    shared = (
        SupabaseBlobStore(url, key, bucket="rpg-shared-art", shared=True) if url and key else None
    )
    return SimpleNamespace(
        game_store=SimpleNamespace(pool=open_ops_pool(dsn)), shared_blob_store=shared
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("portrait_key")
    parser.add_argument("--reason", required=True, help="motivo da retirada (vai para o registro)")
    parser.add_argument(
        "--env-file", help="dotenv com as variáveis do runtime (override=False; nada é impresso)"
    )
    parser.add_argument(
        "--dsn-env",
        help="variável com o DSN de sistema do banco alvo (ex.: RPG_STAGING_DB_URL); usa o pool "
        "de operação e SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY em vez de montar o runtime",
    )
    parser.add_argument("--dry-run", action="store_true", help="mostra o que faria; não muda nada")
    args = parser.parse_args()
    if not args.reason.strip():
        parser.error("--reason não pode ser vazio")
    if args.env_file:
        from pathlib import Path

        if not Path(args.env_file).is_file():
            parser.error("--env-file não encontrado")
        from dotenv import load_dotenv

        load_dotenv(args.env_file, override=False)
    if args.dsn_env:
        import os

        values = {k: os.getenv(k, "") for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")}
        dsn = os.getenv(args.dsn_env, "")
        if not dsn:
            parser.error(f"{args.dsn_env} vazio")
        runtime = _ops_runtime(dsn, values)
    else:
        runtime = build_runtime()
    try:
        if args.dry_run:
            report = _dry_report(runtime, args.portrait_key)
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            return 0
        if args.dsn_env and runtime.shared_blob_store is None:
            parser.error("retirada pelo --dsn-env exige SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY")
        result = retire(runtime, args.portrait_key, args.reason.strip())
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if not result["objects_failed"] else 2
    finally:
        if args.dsn_env:
            runtime.game_store.pool.close()


if __name__ == "__main__":
    raise SystemExit(main())
