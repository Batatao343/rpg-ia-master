-- SPEC-410 R12: comportamento de RLS sob `rpg_api` (owner A nao le nem grava linha do owner B).
-- Molde: rls_effective_storage_test.sql. Policies reais (pg_policies) conferidas em 11/11:
--   operations / jobs: `for all to rpg_api` por owner;
--   image_quotes / usage_events: select + insert por owner (sem update/delete);
--   shared_pool: select (promoted ou proprio) + insert so em held/local_only do proprio owner;
--   creature_portraits / account_deletions: so select (sistema escreve).
begin;
create extension if not exists pgtap with schema extensions;
select plan(21);

create function public.spec410_rows(q text) returns integer language plpgsql as $$
declare n integer;
begin execute q; get diagnostics n = row_count; return n; end $$;

-- Linhas inseridas pelo login de sistema (postgres, BYPASSRLS), uma por owner.
insert into app.operations (id, owner_id, kind, status, request_sha256) values
  ('00000000-0000-0000-0000-0000000410a1', '00000000-0000-0000-0000-0000000410c1', 'turn', 'running', repeat('a', 64)),
  ('00000000-0000-0000-0000-0000000410b1', '00000000-0000-0000-0000-0000000410c2', 'turn', 'running', repeat('b', 64));
insert into app.jobs (id, owner_id, kind, dedupe_key, status, payload, max_attempts) values
  ('00000000-0000-0000-0000-0000000410a2', '00000000-0000-0000-0000-0000000410c1', 'spec410', 'spec410-a', 'queued', '{}', 3),
  ('00000000-0000-0000-0000-0000000410b2', '00000000-0000-0000-0000-0000000410c2', 'spec410', 'spec410-b', 'queued', '{}', 3);

set local role rpg_api;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000410c1', true);

-- operations -------------------------------------------------------------------------------------
select is(
  (select array_agg(id::text) from app.operations
    where id in ('00000000-0000-0000-0000-0000000410a1', '00000000-0000-0000-0000-0000000410b1')),
  array['00000000-0000-0000-0000-0000000410a1'],
  'operations: select returns only the request owner rows'
);
select is(
  public.spec410_rows($q$update app.operations set status = 'failed'
    where id = '00000000-0000-0000-0000-0000000410b1'$q$),
  0, 'operations: update of another owner row affects 0 rows'
);
select is(
  public.spec410_rows($q$delete from app.operations where id = '00000000-0000-0000-0000-0000000410b1'$q$),
  0, 'operations: delete of another owner row affects 0 rows'
);
select throws_ok(
  $$insert into app.operations (id, owner_id, kind, status, request_sha256)
    values (gen_random_uuid(), '00000000-0000-0000-0000-0000000410c2', 'turn', 'running', repeat('c', 64))$$,
  '42501', null, 'operations: insert for another owner is rejected by policy'
);

-- jobs -------------------------------------------------------------------------------------------
select is(
  (select array_agg(id::text) from app.jobs
    where id in ('00000000-0000-0000-0000-0000000410a2', '00000000-0000-0000-0000-0000000410b2')),
  array['00000000-0000-0000-0000-0000000410a2'],
  'jobs: select returns only the request owner rows'
);
select is(
  public.spec410_rows($q$update app.jobs set status = 'cancelled'
    where id = '00000000-0000-0000-0000-0000000410b2'$q$),
  0, 'jobs: update of another owner row affects 0 rows'
);
select is(
  public.spec410_rows($q$delete from app.jobs where id = '00000000-0000-0000-0000-0000000410b2'$q$),
  0, 'jobs: delete of another owner row affects 0 rows'
);
select throws_ok(
  $$insert into app.jobs (id, owner_id, kind, dedupe_key, status, payload, max_attempts)
    values (gen_random_uuid(), '00000000-0000-0000-0000-0000000410c2', 'spec410', 'spec410-x', 'queued', '{}', 3)$$,
  '42501', null, 'jobs: insert for another owner is rejected by policy'
);

-- image_quotes: select + insert por owner; sem update/delete. A policy WITH CHECK roda antes das
-- constraints/FKs, entao o insert de outro owner falha com 42501 sem precisar de pricing_versions.
select throws_ok(
  $$insert into app.image_quotes (quote_id, owner_id, game_id, timeline_epoch, image_type, credits_milli,
       pricing_version_id, price_profile_id, image_rate_card_version, expires_at, model, profile_version,
       prompt_hash, private_brief, trigger)
     values (gen_random_uuid(), '00000000-0000-0000-0000-0000000410c2', gen_random_uuid(), 0, 'player', 1,
       'v', 'p', 'r', now(), 'm', 'pv', repeat('d', 64), '{}', '{}')$$,
  '42501', null, 'image_quotes: insert for another owner is rejected by policy'
);
select ok(
  not has_table_privilege('rpg_api', 'app.image_quotes', 'UPDATE')
  and not has_table_privilege('rpg_api', 'app.image_quotes', 'DELETE'),
  'image_quotes: tenant has no UPDATE/DELETE privilege'
);
select ok(
  (select bool_and(qual like '%current_owner_id%') from pg_policies
    where schemaname = 'app' and tablename = 'image_quotes' and policyname = 'image_quotes_read_own'),
  'image_quotes: read policy is scoped by current_owner_id()'
);

-- shared_pool: so insere held/local_only do proprio owner; sem update/delete.
select throws_ok(
  $$insert into app.shared_pool (entry_id, namespace, status, name, name_fold, name_origin, document,
       origin_owner_id, promote_after)
     values ('spec410-b1', 'location', 'held', 'N', 'n', 'engine', '{}',
       '00000000-0000-0000-0000-0000000410c2', now())$$,
  '42501', null, 'shared_pool: insert with another origin owner is rejected by policy'
);
select throws_ok(
  $$insert into app.shared_pool (entry_id, namespace, status, name, name_fold, name_origin, document,
       origin_owner_id, promote_after)
     values ('spec410-p1', 'location', 'promoted', 'N', 'n', 'engine', '{}',
       '00000000-0000-0000-0000-0000000410c1', now())$$,
  '42501', null, 'shared_pool: tenant cannot self-promote on insert'
);
select ok(
  not has_table_privilege('rpg_api', 'app.shared_pool', 'UPDATE')
  and not has_table_privilege('rpg_api', 'app.shared_pool', 'DELETE'),
  'shared_pool: tenant has no UPDATE/DELETE privilege (nobody self-promotes)'
);

-- Tabelas so de sistema (ou so de leitura) para o tenant: negativo de privilegio.
select ok(
  not has_table_privilege('rpg_api', 'app.creature_portraits', 'INSERT')
  and not has_table_privilege('rpg_api', 'app.creature_portraits', 'UPDATE')
  and not has_table_privilege('rpg_api', 'app.creature_portraits', 'DELETE'),
  'creature_portraits: tenant is read-only (system writes)'
);
select ok(
  has_table_privilege('rpg_api', 'app.creature_portraits', 'SELECT'),
  'creature_portraits: tenant reads through its policy'
);
select ok(
  not has_table_privilege('rpg_api', 'app.account_deletions', 'INSERT')
  and not has_table_privilege('rpg_api', 'app.account_deletions', 'UPDATE')
  and not has_table_privilege('rpg_api', 'app.account_deletions', 'DELETE'),
  'account_deletions: tenant cannot write (system only)'
);
select is(
  public.spec410_rows($q$select 1 from app.account_deletions
    where owner_id = '00000000-0000-0000-0000-0000000410c2'$q$),
  0, 'account_deletions: tenant sees no other owner tombstone'
);
select ok(
  not has_table_privilege('rpg_api', 'app.usage_events', 'UPDATE')
  and not has_table_privilege('rpg_api', 'app.usage_events', 'DELETE'),
  'usage_events: tenant has no UPDATE/DELETE privilege'
);
select ok(
  (select bool_and((coalesce(qual, '') || coalesce(with_check, '')) like '%current_owner_id%')
     from pg_policies
    where schemaname = 'app' and tablename = 'usage_events' and 'rpg_api' = any (roles)),
  'usage_events: every tenant policy is scoped by current_owner_id()'
);
select is(
  (select count(*)::integer from pg_policies
    where schemaname = 'app' and tablename = 'usage_events' and 'rpg_api' = any (roles)),
  2,
  'usage_events: exactly the own-read and own-insert policies for the tenant'
);
reset role;

select * from finish();
rollback;
