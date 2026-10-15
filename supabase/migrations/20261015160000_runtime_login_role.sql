-- SPEC-197 R-05: papel de LOGIN de menor privilégio para o runtime serverless.
-- Antes o pooler usava `postgres`. `rpg_runtime` NÃO é superuser/createdb/createrole/replication,
-- NÃO tem BYPASSRLS (policies explícitas abaixo) e NÃO tem DDL. Sem senha aqui: a senha é
-- definida fora da migração (scripts/staging/runtime_role.py). Migrações/tooling seguem em `postgres`.
--
-- Por que policies permissivas e não BYPASSRLS: o backend executa operações de sistema entre
-- owners (worker, wallet, cron, recuperação de exclusão) sobre tabelas com FORCE RLS cujas
-- policies só existem para `rpg_api` (escopo por owner). Em vez de contornar RLS em tudo,
-- o runtime recebe uma policy `runtime_all` por tabela com RLS, visível e auditável.
--
-- CONTRATO: toda migração futura que crie tabela/sequence/função em `app` deve terminar com
-- `select app.grant_runtime_access();` (idempotente).

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'rpg_runtime') then
    create role rpg_runtime login nosuperuser nocreatedb nocreaterole noreplication nobypassrls inherit;
  else
    alter role rpg_runtime login nosuperuser nocreatedb nocreaterole noreplication nobypassrls;
  end if;
end $$;

alter role rpg_runtime set search_path = app, public, extensions;
alter role rpg_runtime set statement_timeout = '60s';
alter role rpg_runtime set idle_in_transaction_session_timeout = '60s';
grant rpg_api to rpg_runtime;

-- Acesso ao schema `auth`: `postgres` não tem USAGE com grant option em auth (dono: supabase_admin),
-- então o runtime NÃO recebe grants diretos em auth.*. Em vez disso, três funções SECURITY DEFINER
-- (dono postgres, search_path travado) expõem exatamente as operações que o backend usa.
create or replace function app.runtime_session_active(p_session uuid, p_user uuid) returns boolean
language sql stable security definer set search_path = pg_catalog as $$
  select exists (select 1 from auth.sessions s where s.id = p_session and s.user_id = p_user
                   and (s.not_after is null or s.not_after > now())
                   and not exists (select 1 from app.account_deletions d where d.owner_id = p_user));
$$;
create or replace function app.runtime_auth_email(p_user uuid) returns text
language sql stable security definer set search_path = pg_catalog as $$
  select u.email::text from auth.users u where u.id = p_user;
$$;
create or replace function app.runtime_revoke_auth(p_user uuid) returns void
language sql security definer set search_path = pg_catalog as $$
  delete from auth.sessions where user_id = p_user;
  delete from auth.refresh_tokens where user_id = p_user::text;
$$;
revoke all on function app.runtime_session_active(uuid, uuid), app.runtime_auth_email(uuid),
  app.runtime_revoke_auth(uuid) from public, anon, authenticated, rpg_api;

create or replace function app.grant_runtime_access() returns void
language plpgsql set search_path = pg_catalog, public as $fn$
declare t record;
begin
  grant usage on schema app, public, extensions to rpg_runtime;
  grant select, insert, update, delete on all tables in schema app to rpg_runtime;
  grant usage, select on all sequences in schema app to rpg_runtime;
  grant execute on all functions in schema app to rpg_runtime;
  grant execute on all functions in schema public to rpg_runtime;
  revoke execute on function app.grant_runtime_access() from rpg_runtime;
  for t in
    select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'app' and c.relkind in ('r', 'p') and c.relrowsecurity
  loop
    if not exists (select 1 from pg_policies p
                    where p.schemaname = 'app' and p.tablename = t.relname and p.policyname = 'runtime_all') then
      execute format('create policy runtime_all on app.%I for all to rpg_runtime using (true) with check (true)',
                     t.relname);
    end if;
  end loop;
end $fn$;

revoke all on function app.grant_runtime_access() from public, anon, authenticated, rpg_runtime;

select app.grant_runtime_access();

-- Storage: leitura de objetos (exclusão de conta enumera chaves; remoção real passa pela Storage API).
grant usage on schema storage to rpg_runtime;
grant select on storage.objects to rpg_runtime;

-- Defaults para objetos futuros criados pelo dono das migrações (reduz esquecimento do contrato).
alter default privileges in schema app grant select, insert, update, delete on tables to rpg_runtime;
alter default privileges in schema app grant usage, select on sequences to rpg_runtime;
alter default privileges in schema app grant execute on functions to rpg_runtime;
