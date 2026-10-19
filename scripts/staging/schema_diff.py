"""Schema parity: normalized catalog snapshot of staging vs the local lab (repo migrations only).

Usage (lab already reset with `npx supabase db reset`):
  uv run python -m scripts.staging.schema_diff --confirm-staging $REF [--local-dsn <dsn>] [--out file]

Staging DSN = RPG_STAGING_DB_URL. Read-only (catalog SELECTs). Objects that belong to migrations the
staging project has not received yet are excluded by marker and listed under `excluded`.
"""

from __future__ import annotations

import argparse
import os
from typing import Any
from collections.abc import Iterable

from scripts.staging import common

SCHEMAS = ("app", "public")
# Markers of repo migrations deliberately NOT yet on staging (empty after SPEC-194..196 were pushed).
PENDING_MARKERS: tuple[str, ...] = ()
# Platform-managed (pg_cron/pg_net/pg_graphql, vector patch level): reported, never fails parity.
INFORMATIONAL = ("extensions",)

QUERIES: dict[str, str] = {
    "columns": """select c.table_schema||'.'||c.table_name||'.'||c.column_name||' '||c.data_type||
                  ' null='||c.is_nullable||' default='||coalesce(c.column_default,'')
                  from information_schema.columns c where c.table_schema = any(%(s)s)""",
    "tables": """select n.nspname||'.'||c.relname||' kind='||c.relkind::text||' rls='||c.relrowsecurity::text||
                 ' force='||c.relforcerowsecurity::text from pg_class c join pg_namespace n on n.oid=c.relnamespace
                 where n.nspname = any(%(s)s) and c.relkind in ('r','p','v','m')""",
    "constraints": """select n.nspname||'.'||t.relname||' '||c.conname||' '||pg_get_constraintdef(c.oid)
                      from pg_constraint c join pg_class t on t.oid=c.conrelid
                      join pg_namespace n on n.oid=t.relnamespace where n.nspname = any(%(s)s)""",
    "indexes": "select schemaname||'.'||tablename||' '||indexdef from pg_indexes where schemaname = any(%(s)s)",
    "policies": """select schemaname||'.'||tablename||' '||policyname||' cmd='||cmd||' roles='||
                   array_to_string(roles,',')||' using='||coalesce(qual,'')||' check='||coalesce(with_check,'')
                   from pg_policies where schemaname = any(%(p)s)""",
    "functions": """select n.nspname||'.'||p.proname||'('||pg_get_function_identity_arguments(p.oid)||
                    ') definer='||p.prosecdef||' config='||coalesce(array_to_string(p.proconfig,','),'')||
                    ' volatility='||p.provolatile::text||' md5='||md5(replace(p.prosrc, chr(13), ''))
                    from pg_proc p join pg_namespace n on n.oid=p.pronamespace
                    where n.nspname = any(%(s)s)
                      and not exists (select 1 from pg_depend d where d.objid=p.oid and d.deptype='e')""",
    "grants": """select n.nspname||'.'||c.relname||' '||
                 coalesce((select rolname from pg_roles where oid=a.grantee),'public')||' '||a.privilege_type
                 from pg_class c join pg_namespace n on n.oid=c.relnamespace,
                      lateral aclexplode(c.relacl) a
                 where n.nspname = any(%(s)s) and c.relkind in ('r','p','v','m','S')""",
    "function_grants": """select n.nspname||'.'||p.proname||'('||pg_get_function_identity_arguments(p.oid)||') '||
                          coalesce((select rolname from pg_roles where oid=a.grantee),'public')||' '||a.privilege_type
                          from pg_proc p join pg_namespace n on n.oid=p.pronamespace,
                               lateral aclexplode(p.proacl) a
                          where n.nspname = any(%(s)s)
                            and not exists (select 1 from pg_depend d where d.objid=p.oid and d.deptype='e')""",
    "triggers": """select n.nspname||'.'||c.relname||' '||pg_get_triggerdef(t.oid)
                   from pg_trigger t join pg_class c on c.oid=t.tgrelid join pg_namespace n on n.oid=c.relnamespace
                   where not t.tgisinternal and n.nspname = any(%(s)s)""",
    "buckets": """select id||' public='||public::text||' limit='||coalesce(file_size_limit::text,'')||
                  ' mime='||coalesce(array_to_string(allowed_mime_types,','),'') from storage.buckets""",
    "extensions": "select extname||' '||extversion from pg_extension",
}


def snapshot(dsn: str) -> dict[str, list[str]]:
    import psycopg
    params = {"s": list(SCHEMAS), "p": [*SCHEMAS, "storage"]}
    out: dict[str, list[str]] = {}
    with psycopg.connect(dsn, autocommit=True, prepare_threshold=None) as conn:
        conn.execute("set search_path = ''")  # deparse fully qualified, independent of role search_path
        for name, sql in QUERIES.items():
            out[name] = sorted({r[0] for r in conn.execute(sql, params).fetchall()})
    return out


def split_pending(snap: dict[str, list[str]], markers: Iterable[str] = PENDING_MARKERS
                  ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Pure: separate lines mentioning a pending-migration marker."""
    keep: dict[str, list[str]] = {}
    excluded: dict[str, list[str]] = {}
    for cat, lines in snap.items():
        keep[cat] = [x for x in lines if not any(m in x for m in markers)]
        gone = [x for x in lines if any(m in x for m in markers)]
        if gone:
            excluded[cat] = gone
    return keep, excluded


def diff(staging: dict[str, list[str]], local: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    """Pure: per category lines only in staging / only in local."""
    out: dict[str, dict[str, list[str]]] = {}
    for cat in sorted(set(staging) | set(local)):
        s, l = set(staging.get(cat, [])), set(local.get(cat, []))
        if s != l:
            out[cat] = {"only_staging": sorted(s - l), "only_local": sorted(l - s)}
    return out


def main(argv: list[str] | None = None) -> int:
    common.load_dotenv_quietly()
    p = argparse.ArgumentParser(description="Schema parity staging vs local lab")
    common.add_guard_args(p)
    p.add_argument("--local-dsn", default=os.getenv("RPG_LOCAL_DB_URL")
                   or "postgresql://supabase_admin:postgres@127.0.0.1:55322/postgres")
    p.add_argument("--out")
    a = p.parse_args(argv)
    ref = common.require_staging(a.confirm_staging)
    sdsn = common.env_required("RPG_STAGING_DB_URL")
    common.assert_ref_in(ref, RPG_STAGING_DB_URL=sdsn)
    from urllib.parse import urlparse
    if (urlparse(a.local_dsn).hostname or "") not in {"localhost", "127.0.0.1", "::1"}:
        raise common.GuardError("--local-dsn precisa ser local")
    st, st_excl = split_pending(snapshot(sdsn))
    lo, lo_excl = split_pending(snapshot(a.local_dsn))
    d = diff(st, lo)
    result: dict[str, Any] = {
        "project_ref": ref, "schemas": list(SCHEMAS), "policy_schemas": [*SCHEMAS, "storage"],
        "counts": {c: {"staging": len(st[c]), "local": len(lo[c])} for c in st},
        "excluded_pending_migration": {"markers": list(PENDING_MARKERS), "staging": st_excl,
                                       "local": {k: len(v) for k, v in lo_excl.items()},
                                       "note": "no pending markers: staging has every repo migration (SPEC-194..196)"},
        "diff": {k: v for k, v in d.items() if k not in INFORMATIONAL},
        "informational_diff": {k: v for k, v in d.items() if k in INFORMATIONAL},
        "ok": not any(k not in INFORMATIONAL for k in d),
    }
    print(common.write_evidence("schema_diff", result, a.out))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
