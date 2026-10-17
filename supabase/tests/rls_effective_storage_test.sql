-- SPEC-224: roles de login de menor privilégio, RLS efetivo por owner e Storage sem escrita do cliente.
begin;
create extension if not exists pgtap with schema extensions;
select plan(16);

-- Helper de teste (revertido no rollback): linhas afetadas por um DML, executado com o papel corrente.
create function public.spec224_rows(q text) returns integer language plpgsql as $$
declare n integer;
begin execute q; get diagnostics n = row_count; return n; end $$;

-- R1: logins do runtime/sistema sem BYPASSRLS/superuser; rpg_api continua NOINHERIT.
select ok(
  (select count(*) = 2 from pg_roles
    where rolname in ('rpg_runtime', 'rpg_admin') and rolcanlogin
      and not rolsuper and not rolbypassrls and not rolcreaterole and not rolcreatedb and not rolreplication),
  'rpg_runtime and rpg_admin are LOGIN roles without superuser/BYPASSRLS/DDL'
);
select ok(
  pg_has_role('rpg_runtime', 'rpg_api', 'member'),
  'rpg_runtime is a member of rpg_api (SET ROLE target)'
);
select ok(
  exists(select 1 from pg_roles where rolname = 'rpg_api' and not rolinherit and not rolcanlogin),
  'rpg_api is NOLOGIN NOINHERIT: no tenant privilege without an explicit SET ROLE'
);
select ok(
  not pg_has_role('authenticated', 'rpg_runtime', 'member') and not pg_has_role('anon', 'rpg_runtime', 'member'),
  'client roles cannot assume the runtime login'
);

-- Grants do login de request idênticos aos do de sistema nas tabelas app.* (nenhuma lacuna => sem outage).
select is(
  (select count(*)::integer from information_schema.role_table_grants g
    where g.table_schema = 'app' and g.grantee = 'rpg_runtime'
      and not exists (select 1 from information_schema.role_table_grants a
                       where a.table_schema = 'app' and a.table_name = g.table_name
                         and a.privilege_type = g.privilege_type and a.grantee = 'rpg_admin')),
  0,
  'rpg_runtime has no table privilege that rpg_admin lacks'
);
select is(
  (select count(*)::integer from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'app' and c.relkind = 'r' and c.relrowsecurity
      and not exists (select 1 from pg_policies p where p.schemaname = 'app' and p.tablename = c.relname
                       and p.policyname = 'admin_all')),
  0,
  'every RLS table has the explicit admin_all system policy'
);

-- R7 + D-B: o cliente não tem policy alguma em storage.objects para o bucket de arte dinâmica.
select is(
  (select count(*)::integer from pg_policies
    where schemaname = 'storage' and tablename = 'objects' and policyname like 'rpg_dynamic_%'),
  0,
  'no client policy remains on rpg-dynamic'
);
select ok(
  exists(select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
          where n.nspname = 'app' and p.proname = 'guard_storage_account_write'),
  'account-deletion storage guard is untouched'
);

insert into auth.users (id, instance_id, aud, role, email, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
values ('00000000-0000-0000-0000-0000000000a1', '00000000-0000-0000-0000-000000000000', 'authenticated',
        'authenticated', 'spec224-a@example.test', '{}', '{}', now(), now())
on conflict (id) do nothing;

set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a1', true);
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-0000000000a1","role":"authenticated"}', true);

select throws_ok(
  $$insert into storage.objects (bucket_id, name, owner_id) values
    ('rpg-dynamic', 'users/00000000-0000-0000-0000-0000000000a1/games/x/o.webp', '00000000-0000-0000-0000-0000000000a1')$$,
  '42501', null,
  'authenticated cannot INSERT own prefix in rpg-dynamic'
);
select is(
  public.spec224_rows($q$update storage.objects set name = name || '.x' where bucket_id = 'rpg-dynamic'$q$),
  0,
  'authenticated cannot UPDATE objects in rpg-dynamic'
);
-- DELETE direto já é barrado pelo guard nativo do Storage; garante-se também que NENHUMA policy cite o bucket.
select is(
  (select count(*)::integer from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
      and (coalesce(qual, '') || coalesce(with_check, '')) like '%rpg-dynamic%'),
  0,
  'no storage.objects policy references rpg-dynamic (so no client DELETE path either)'
);
select is(
  (select count(*)::integer from storage.objects where bucket_id = 'rpg-dynamic'),
  0,
  'authenticated cannot SELECT objects in rpg-dynamic directly'
);
reset role;

-- R4 no banco: sob rpg_api (assumido pelo runtime), `select` sem filtro só devolve o owner da request.
insert into app.games (id, owner_id, schema_version, state, state_sha256, status, player_name, class_name,
                       player_level, location_name, world_day, game_over, combat_simulation) values
  ('00000000-0000-0000-0000-0000000000b1', '00000000-0000-0000-0000-0000000000a1', 3, '{}', repeat('a', 64),
   'active', 'A', 'Devoto', 1, 'T', 1, false, false),
  ('00000000-0000-0000-0000-0000000000b2', '00000000-0000-0000-0000-0000000000a2', 3, '{}', repeat('b', 64),
   'active', 'B', 'Devoto', 1, 'T', 1, false, false);

set local role rpg_api;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a1', true);
select is(
  (select array_agg(id::text) from app.games where id in
    ('00000000-0000-0000-0000-0000000000b1', '00000000-0000-0000-0000-0000000000b2')),
  array['00000000-0000-0000-0000-0000000000b1'],
  'unfiltered select under rpg_api returns only the request owner rows'
);
select is(
  public.spec224_rows($q$update app.games set player_name = 'hijack'
    where id = '00000000-0000-0000-0000-0000000000b2'$q$),
  0,
  'update of another owner row affects 0 rows'
);
select throws_ok(
  $$insert into app.games (id, owner_id, schema_version, state, state_sha256, status, player_name, class_name,
       player_level, location_name, world_day, game_over, combat_simulation)
     values (gen_random_uuid(), '00000000-0000-0000-0000-0000000000a2', 3, '{}', repeat('c', 64),
       'active', 'X', 'Devoto', 1, 'T', 1, false, false)$$,
  '42501', null,
  'insert for another owner is rejected by policy'
);
select ok(
  not has_table_privilege('rpg_api', 'app.wallet_entries', 'SELECT')
  and not has_table_privilege('rpg_api', 'app.kill_switches', 'SELECT')
  and not has_table_privilege('rpg_api', 'app.rate_limit_buckets', 'SELECT'),
  'tenant role still has no wallet/kill-switch/rate-limit access (system-only)'
);
reset role;

select * from finish();
rollback;
