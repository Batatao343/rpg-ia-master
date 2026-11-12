-- SPEC-413: schema `public` (the only schema exposed by the Data API) holds no app function.
begin;
create extension if not exists pgtap with schema extensions;
select plan(3);

select ok(
  not exists (
    select 1 from pg_proc p
    where p.pronamespace = 'public'::regnamespace and p.prosecdef
      and (has_function_privilege('anon', p.oid, 'EXECUTE')
        or has_function_privilege('authenticated', p.oid, 'EXECUTE'))
  ),
  'no SECURITY DEFINER function in public is executable by anon/authenticated'
);

select ok(
  not exists (
    select 1 from pg_proc p
    where p.pronamespace = 'public'::regnamespace
      and not exists (select 1 from pg_depend d
        where d.classid = 'pg_proc'::regclass and d.objid = p.oid and d.deptype = 'e')
  ),
  'public contains no function that does not belong to an extension'
);

select ok(
  to_regprocedure('public.rpg_wallet_balance()') is null
    and to_regprocedure('public.rpg_wallet_history(integer)') is null
    and to_regprocedure('public.rpg_current_session_active()') is null,
  'the three legacy wallet/session RPCs are gone'
);

select * from finish();
rollback;
