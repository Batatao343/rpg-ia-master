"""SPEC-197 R-05: define/rotaciona a senha do papel `rpg_runtime` no staging e monta a DATABASE_URL do runtime.

A migração `20261015160000_runtime_login_role.sql` cria o papel sem senha. Este script (precisa de `--apply`)
gera uma senha aleatória de 48 caracteres, aplica via ALTER ROLE e grava SOMENTE no `.env.staging`
(`RPG_RUNTIME_DB_PASSWORD` e `RPG_RUNTIME_DATABASE_URL`). Nada secreto é impresso.
"""

from __future__ import annotations

import argparse
import re
import secrets
import string
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

from scripts.staging import common, s192

ROLE = "rpg_runtime"
ENV_FILE = common.ROOT / ".env.staging"


def new_password(n: int = 48) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def runtime_dsn(admin_dsn: str, ref: str, password: str) -> str:
    """Pooler transacional (6543) com tenant `rpg_runtime.<ref>`; reaproveita o host do DSN admin."""
    host = urlsplit(admin_dsn).hostname or ""
    if not host.endswith(".pooler.supabase.com"):
        raise common.GuardError("DATABASE_URL de staging não é um pooler compartilhado; recusado")
    return f"postgresql://{ROLE}.{ref}:{quote(password, safe='')}@{host}:6543/postgres?sslmode=require"


def upsert_env(path: Path, values: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    for key, value in values.items():
        line = f"{key}={value}"
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
        text = pattern.sub(lambda _m: line, text) if pattern.search(text) else text.rstrip("\n") + "\n" + line + "\n"
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    common.add_guard_args(ap)
    ap.add_argument("--apply", action="store_true", help="obrigatório para alterar o banco/.env.staging")
    a = ap.parse_args(argv)
    env = s192.load_env()
    ref = common.require_staging(a.confirm_staging, env)
    common.assert_ref_in(ref, RPG_STAGING_DB_URL=env["RPG_STAGING_DB_URL"], DATABASE_URL=env["DATABASE_URL"])
    if not a.apply:
        print("dry-run: use --apply para definir a senha de rpg_runtime e gravar .env.staging")
        return 0
    from psycopg import sql
    password = new_password()
    with s192.db(env) as conn:
        if conn.execute("select 1 from pg_roles where rolname=%s", (ROLE,)).fetchone() is None:
            print("papel rpg_runtime ausente: aplique a migração primeiro", file=sys.stderr)
            return 1
        conn.execute(sql.SQL("alter role {} with login password {}").format(sql.Identifier(ROLE), sql.Literal(password)))
        attrs = dict(conn.execute("""select rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls
                                     from pg_roles where rolname=%s""", (ROLE,)).fetchone())
    dsn = runtime_dsn(env["DATABASE_URL"], ref, password)
    upsert_env(ENV_FILE, {"RPG_RUNTIME_DB_PASSWORD": password, "RPG_RUNTIME_DATABASE_URL": dsn})
    print("ok: senha de rpg_runtime rotacionada; RPG_RUNTIME_DATABASE_URL gravada em .env.staging",
          "| atributos:", ",".join(f"{k}={v}" for k, v in attrs.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
