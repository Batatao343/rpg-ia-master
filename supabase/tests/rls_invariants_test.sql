-- SPEC-410 R11: invariantes de RLS/privilegio do schema `app` (defesa em profundidade).
-- Falham se uma tabela nova de `app` nascer sem RLS forcada ou com grant para cliente/PUBLIC.
begin;
create extension if not exists pgtap with schema extensions;
select plan(9);

-- (i) toda tabela de `app` com RLS habilitada E forcada (particoes filhas herdam do pai).
select is(
  (select coalesce(string_agg(c.relname, ', ' order by c.relname), '')
     from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'app' and c.relkind in ('r', 'p') and not c.relispartition
      and not (c.relrowsecurity and c.relforcerowsecurity)),
  '',
  'every app table has row level security enabled AND forced'
);

-- (ii) nenhum privilegio de tabela para PUBLIC, anon ou authenticated em relacao alguma de `app`.
select is(
  (select coalesce(string_agg(c.relname, ', ' order by c.relname), '')
     from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'app' and c.relkind in ('r', 'p', 'v', 'm', 'f')
      and exists (select 1 from aclexplode(c.relacl) a where a.grantee = 0)),
  '',
  'no app relation grants anything to PUBLIC'
);
select is(
  (select coalesce(string_agg(c.relname || ':' || r.rolname, ', ' order by c.relname, r.rolname), '')
     from pg_class c
     join pg_namespace n on n.oid = c.relnamespace
     cross join (select rolname from pg_roles where rolname in ('anon', 'authenticated')) r
    where n.nspname = 'app' and c.relkind in ('r', 'p', 'v', 'm', 'f')
      and has_table_privilege(r.rolname, c.oid,
            'select, insert, update, delete, truncate, references, trigger')),
  '',
  'anon and authenticated have no privilege on any app relation (PUBLIC included)'
);

-- (iii) clientes sem USAGE em `app` e sem CREATE em `public`.
select ok(
  not has_schema_privilege('anon', 'app', 'USAGE') and not has_schema_privilege('authenticated', 'app', 'USAGE'),
  'anon/authenticated have no USAGE on schema app'
);
select ok(
  not has_schema_privilege('anon', 'public', 'CREATE') and not has_schema_privilege('authenticated', 'public', 'CREATE'),
  'anon/authenticated cannot CREATE in schema public'
);

-- (iv) rate_limit_buckets: acesso so de sistema, com as duas policies explicitas.
select is(
  (select array_agg(policyname::text order by policyname) from pg_policies
    where schemaname = 'app' and tablename = 'rate_limit_buckets'),
  array['admin_all', 'runtime_all'],
  'rate_limit_buckets has exactly the runtime_all and admin_all system policies'
);
select ok(
  not has_table_privilege('rpg_api', 'app.rate_limit_buckets', 'select, insert, update, delete'),
  'rate_limit_buckets stays system-only (no rpg_api privilege)'
);

-- (v) a carteira sobrevive a `delete`, ate para o login de sistema (retencao financeira de 5 anos).
insert into app.wallet_accounts (owner_id) values ('00000000-0000-0000-0000-0000000041a1');
select throws_ok(
  $$delete from app.wallet_accounts where owner_id = '00000000-0000-0000-0000-0000000041a1'$$,
  '55000', null,
  'delete on wallet_accounts is rejected (errcode 55000)'
);
-- wallet_reservations: o gatilho BEFORE DELETE FOR EACH ROW existe e esta ativo (a linha exige
-- pricing_versions + contabilidade; o comportamento e o mesmo gatilho provado acima).
select ok(
  exists(select 1 from pg_trigger t
          where t.tgrelid = 'app.wallet_reservations'::regclass and not t.tgisinternal
            and t.tgenabled = 'O' and (t.tgtype & 1) = 1 and (t.tgtype & 2) = 2 and (t.tgtype & 8) = 8
            and t.tgfoid = 'app.reject_wallet_fact_mutation()'::regprocedure),
  'wallet_reservations has an enabled BEFORE DELETE row trigger that rejects the mutation'
);

select * from finish();
rollback;
