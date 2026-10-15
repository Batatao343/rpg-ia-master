-- SPEC-191. Supabase Security Advisor flags definer-style public views over app.*.
-- Replace them with narrow security-definer functions; schema app stays private.
drop view if exists public.wallet_balance_view;
drop view if exists public.wallet_history_view;

create or replace function public.rpg_wallet_balance()
returns table (owner_id uuid, available_milli bigint, reserved_milli bigint, updated_at timestamptz)
language sql stable security definer set search_path='' as $$
  select w.owner_id, w.available_milli, w.reserved_milli, w.updated_at
  from app.wallet_accounts w
  where w.owner_id=(select auth.uid()) and public.rpg_current_session_active()
$$;

create or replace function public.rpg_wallet_history(p_limit int default 50)
returns table (entry_id uuid, owner_id uuid, entry_type text, reference_type text,
  reference_id text, amount_milli bigint, available_delta bigint, reserved_delta bigint,
  pricing_version_id text, sku_id text, created_at timestamptz)
language sql stable security definer set search_path='' as $$
  select e.entry_id, e.owner_id, e.entry_type, e.reference_type, e.reference_id,
    e.amount_milli, e.available_delta, e.reserved_delta, e.pricing_version_id, e.sku_id, e.created_at
  from app.wallet_entries e
  where e.owner_id=(select auth.uid()) and public.rpg_current_session_active()
  order by e.created_at desc
  limit greatest(1, least(coalesce(p_limit, 50), 200))
$$;

revoke all on function public.rpg_wallet_balance() from public, anon, rpg_api;
revoke all on function public.rpg_wallet_history(int) from public, anon, rpg_api;
grant execute on function public.rpg_wallet_balance() to authenticated;
grant execute on function public.rpg_wallet_history(int) to authenticated;
