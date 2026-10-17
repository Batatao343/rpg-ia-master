-- SPEC-224: RLS efetivo no runtime + Storage sem escrita do cliente.
--
-- Contexto: `20261015160000_runtime_login_role.sql` (SPEC-197 R-05) ja criou o login `rpg_runtime`
-- (NOBYPASSRLS, sem DDL) e `grant rpg_api to rpg_runtime`. Aqui fechamos o resto:
--  1. `rpg_admin`: login de SISTEMA (workers/cron/wallet/ciclo de conta/rate limit). Mesmo conjunto de
--     grants/policies permissivas que `rpg_runtime` (o `postgres` do Supabase nao cria BYPASSRLS), mas
--     credencial DISTINTA, para o app separar "request de usuario" de "sistema" (RPG_ADMIN_DATABASE_URL).
--  2. O backend passa a executar `SET LOCAL ROLE rpg_api` + `request.jwt.claim.sub` em toda transacao de
--     request; `rpg_api` e a role das policies por owner. `rpg_runtime` e membro de `rpg_api`, mas
--     `rpg_api` e NOINHERIT: sem o SET ROLE explicito nenhum privilegio de tenant vale.
--  3. Storage: o cliente (`authenticated`) NAO escreve nem le `rpg-dynamic` diretamente. Backend usa a
--     service role (Storage API); download assinado futuro reintroduz uma policy de SELECT propria.
--
-- ROLLBACK (aplicacao): RPG_REQUEST_RLS=off + remover RPG_ADMIN_DATABASE_URL volta ao comportamento anterior
-- (rpg_runtime com policies permissivas) sem tocar no banco. ROLLBACK (banco): ver docs/spec224/README.md.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'rpg_admin') then
    create role rpg_admin login nosuperuser nocreatedb nocreaterole noreplication nobypassrls inherit;
  else
    alter role rpg_admin login nocreatedb nocreaterole;
  end if;
  -- SUPERUSER/BYPASSRLS/REPLICATION so o superuser altera (PG16+): aqui apenas se afirma o contrato.
  if exists (select 1 from pg_roles where rolname in ('rpg_runtime', 'rpg_admin', 'rpg_api')
              and (rolsuper or rolbypassrls or rolreplication)) then
    raise exception 'rpg_runtime/rpg_admin/rpg_api nao podem ser superuser, BYPASSRLS ou replication';
  end if;
end $$;

alter role rpg_admin set search_path = app, public, extensions;
alter role rpg_admin set statement_timeout = '60s';
alter role rpg_admin set idle_in_transaction_session_timeout = '60s';
grant rpg_api to rpg_runtime;
-- pgvector: a consulta de memoria do request referencia o tipo/operadores em `extensions`.
grant usage on schema extensions to rpg_api;

-- Mesma funcao de grants do runtime, agora para as DUAS roles de login. Policies permissivas por role
-- (`runtime_all`/`admin_all`) mantem o sistema funcionando sobre tabelas FORCE RLS sem BYPASSRLS.
create or replace function app.grant_runtime_access() returns void
language plpgsql set search_path = pg_catalog, public as $fn$
declare t record; r record;
begin
  for r in select * from (values ('rpg_runtime', 'runtime_all'), ('rpg_admin', 'admin_all')) as v(role_name, policy_name)
  loop
    execute format('grant usage on schema app, public, extensions to %I', r.role_name);
    execute format('grant select, insert, update, delete on all tables in schema app to %I', r.role_name);
    execute format('grant usage, select on all sequences in schema app to %I', r.role_name);
    execute format('grant execute on all functions in schema app to %I', r.role_name);
    execute format('grant execute on all functions in schema public to %I', r.role_name);
    execute format('revoke execute on function app.grant_runtime_access() from %I', r.role_name);
    for t in
      select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
       where n.nspname = 'app' and c.relkind in ('r', 'p') and c.relrowsecurity
    loop
      if not exists (select 1 from pg_policies p
                      where p.schemaname = 'app' and p.tablename = t.relname and p.policyname = r.policy_name) then
        execute format('create policy %I on app.%I for all to %I using (true) with check (true)',
                       r.policy_name, t.relname, r.role_name);
      end if;
    end loop;
  end loop;
end $fn$;

revoke all on function app.grant_runtime_access() from public, anon, authenticated, rpg_runtime, rpg_admin;

select app.grant_runtime_access();

-- Funcoes SECURITY DEFINER de sessao/auth usadas pelo backend (runtime e admin; nunca rpg_api/clientes).
do $$
declare f text;
begin
  foreach f in array array['app.runtime_session_active(uuid, uuid)', 'app.runtime_auth_email(uuid)',
                           'app.runtime_revoke_auth(uuid)']
  loop
    execute format('grant execute on function %s to rpg_admin', f);
  end loop;
end $$;

grant usage on schema storage to rpg_admin;
grant select on storage.objects to rpg_admin;

alter default privileges in schema app grant select, insert, update, delete on tables to rpg_admin;
alter default privileges in schema app grant usage, select on sequences to rpg_admin;
alter default privileges in schema app grant execute on functions to rpg_admin;

-- Storage (R7 + D-B): nenhuma policy de cliente em `rpg-dynamic`. RLS sem policy = deny.
drop policy if exists rpg_dynamic_select_own on storage.objects;
drop policy if exists rpg_dynamic_insert_own on storage.objects;
drop policy if exists rpg_dynamic_update_own on storage.objects;
drop policy if exists rpg_dynamic_delete_own on storage.objects;
