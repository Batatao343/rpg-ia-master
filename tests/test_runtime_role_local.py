"""SPEC-197 R-05: o papel `rpg_runtime` (LOGIN de menor privilégio) cobre o runtime e nada além.

Precisa de dois DSNs no lab: RPG_TEST_DATABASE_URL (admin, cria/semeia) e
RPG_TEST_RUNTIME_DATABASE_URL (rpg_runtime com senha definida pelo teste de infra).
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

pytestmark = pytest.mark.infra_local


@pytest.fixture
def conns():
    psycopg = pytest.importorskip("psycopg")
    admin_dsn = os.getenv("RPG_TEST_DATABASE_URL")
    rt_dsn = os.getenv("RPG_TEST_RUNTIME_DATABASE_URL")
    if not admin_dsn or not rt_dsn:
        pytest.skip("RPG_TEST_DATABASE_URL/RPG_TEST_RUNTIME_DATABASE_URL ausentes")
    with psycopg.connect(admin_dsn, autocommit=True) as admin, psycopg.connect(rt_dsn, autocommit=True) as rt:
        if admin.execute("select 1 from pg_roles where rolname='rpg_runtime'").fetchone() is None:
            pytest.skip("migration runtime_login_role não aplicada")
        yield admin, rt


def test_role_attributes_are_least_privilege(conns):
    admin, _ = conns
    row = admin.execute("""select rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolcanlogin
                           from pg_roles where rolname='rpg_runtime'""").fetchone()
    assert row == (False, False, False, False, False, True)


def test_runtime_cannot_ddl_or_write_auth_and_storage(conns):
    import psycopg
    _, rt = conns
    for sql in ("create table public.rt_probe(i int)", "create table app.rt_probe(i int)",
                "create schema rt_probe", "insert into auth.users(id,email) values (gen_random_uuid(),'x@x.test')",
                "update auth.users set email='y@y.test'", "insert into storage.objects(bucket_id,name) values ('rpg-dynamic','x')",
                "create role rt_probe", "select * from auth.users", "delete from auth.sessions"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            rt.execute(sql)


def test_runtime_reads_identity_via_definer_functions_and_storage(conns):
    admin, rt = conns
    owner, session = uuid4(), uuid4()
    admin.execute("insert into auth.users(id,email) values(%s,%s)", (owner, f"{owner}@example.test"))
    admin.execute("insert into auth.sessions(id,user_id) values(%s,%s)", (session, owner))
    try:
        assert rt.execute("select app.runtime_session_active(%s,%s)", (session, owner)).fetchone()[0] is True
        assert rt.execute("select app.runtime_session_active(%s,%s)", (uuid4(), owner)).fetchone()[0] is False
        assert rt.execute("select app.runtime_auth_email(%s)", (owner,)).fetchone()[0] == f"{owner}@example.test"
        assert rt.execute("select count(*) from storage.objects where bucket_id='rpg-dynamic' and starts_with(name,%s)",
                          (f"users/{owner}/",)).fetchone()[0] == 0
        rt.execute("select pg_advisory_xact_lock(hashtextextended(%s,190))", (str(owner),))
        rt.execute("select app.runtime_revoke_auth(%s)", (owner,))
        assert not admin.execute("select 1 from auth.sessions where id=%s", (session,)).fetchone()
    finally:
        admin.execute("delete from auth.users where id=%s", (owner,))


def test_every_app_object_is_covered_by_runtime_grants(conns):
    admin, _ = conns
    tables = admin.execute("""select c.relname, c.relrowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace
        where n.nspname='app' and c.relkind in ('r','p')""").fetchall()
    assert tables
    for name, rls in tables:
        for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert admin.execute("select has_table_privilege('rpg_runtime',%s,%s)", (f"app.{name}", priv)).fetchone()[0], \
                f"{name} sem {priv}: a migração nova deve chamar app.grant_runtime_access()"
        if rls:
            assert admin.execute("select 1 from pg_policies where schemaname='app' and tablename=%s and policyname='runtime_all'",
                                 (name,)).fetchone(), f"{name} (RLS) sem policy runtime_all"
    for fn in admin.execute("""select p.oid::regprocedure::text from pg_proc p join pg_namespace n on n.oid=p.pronamespace
                               where n.nspname='app' and p.prokind='f' and p.proname<>'grant_runtime_access'""").fetchall():
        assert admin.execute("select has_function_privilege('rpg_runtime',%s,'EXECUTE')", (fn[0],)).fetchone()[0], fn[0]
    assert not admin.execute("select has_function_privilege('rpg_runtime','app.grant_runtime_access()','EXECUTE')").fetchone()[0]


def test_runtime_sees_cross_owner_rows_and_append_only_triggers_still_hold(conns):
    import psycopg
    admin, rt = conns
    # leitura de sistema entre owners (worker/cron) funciona via policy runtime_all, sem BYPASSRLS
    rt.execute("select count(*) from app.games")
    rt.execute("select count(*) from app.jobs")
    # tabelas append-only continuam protegidas por trigger mesmo com UPDATE concedido
    if admin.execute("select count(*) from app.wallet_entries").fetchone()[0]:
        with pytest.raises(psycopg.Error):
            rt.execute("update app.wallet_entries set amount_milli = amount_milli")
    # SET ROLE rpg_api é possível (membro) e volta ao escopo owner-limitado
    rt.execute("set role rpg_api")
    rt.execute("reset role")
