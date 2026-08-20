begin;
create extension if not exists pgtap with schema extensions;
select plan(14);

select ok(
  exists(select 1 from pg_roles where rolname = 'rpg_api' and not rolbypassrls),
  'rpg_api exists without BYPASSRLS'
);
select ok(
  not has_database_privilege('rpg_api', current_database(), 'CREATE'),
  'rpg_api cannot create database objects'
);
select ok(
  (select not public from storage.buckets where id = 'rpg-dynamic'),
  'dynamic-art bucket is private'
);
select is(
  (select file_size_limit from storage.buckets where id = 'rpg-dynamic'),
  20971520::bigint,
  'dynamic-art bucket has a 20 MiB limit'
);
select ok(
  (select relrowsecurity and relforcerowsecurity
   from pg_class where oid = 'app.games'::regclass),
  'games forces RLS'
);
select ok(
  (select relrowsecurity and relforcerowsecurity
   from pg_class where oid = 'app.memory_documents'::regclass),
  'memory documents force RLS'
);
select ok(
  (select relrowsecurity and relforcerowsecurity
   from pg_class where oid = 'app.assets'::regclass),
  'asset metadata forces RLS'
);
select is(
  (select count(*)::integer from pg_policies
   where schemaname = 'storage' and tablename = 'objects'
     and policyname like 'rpg_dynamic_%'),
  4,
  'storage has four owner-scoped policies'
);
select ok(
  not has_table_privilege('rpg_api', 'app.rate_limit_buckets', 'SELECT'),
  'tenant role cannot inspect rate-limit buckets'
);
select ok(
  exists(
    select 1 from pg_policies
    where schemaname='app' and tablename='games'
      and policyname='games_update_own'
      and qual is not null and with_check is not null
  ),
  'games update policy has USING and WITH CHECK'
);
select ok(
  exists(
    select 1 from pg_policies
    where schemaname='app' and tablename='assets'
      and policyname='assets_update_own'
      and qual is not null and with_check is not null
  ),
  'assets update policy has USING and WITH CHECK'
);
select ok(
  exists(
    select 1 from pg_policies
    where schemaname='app' and tablename='memory_documents'
      and policyname='memory_update_scoped'
      and qual is not null and with_check is not null
  ),
  'memory update policy has USING and WITH CHECK'
);
select ok(
  not has_schema_privilege('anon', 'app', 'USAGE'),
  'anonymous clients cannot use gameplay schema'
);
select ok(
  not has_schema_privilege('authenticated', 'app', 'USAGE'),
  'authenticated clients cannot use gameplay schema directly'
);

select * from finish();
rollback;
