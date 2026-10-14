-- SPEC-190. Durable denial precedes revocation and private-data erasure.
create table app.account_deletions (
  owner_id uuid primary key,
  status text not null default 'deleting' check (status in ('deleting','deleted')),
  blob_keys text[] not null default '{}',
  requested_at timestamptz not null default now(),
  recovery_attempted_at timestamptz,
  sessions_revoked_at timestamptz,
  completed_at timestamptz
);
alter table app.account_deletions enable row level security;
alter table app.account_deletions force row level security;
revoke all on app.account_deletions from public,anon,authenticated,rpg_api;
grant select on app.account_deletions to rpg_api;
create policy account_denial_self on app.account_deletions for select to rpg_api
  using (owner_id=nullif(current_setting('request.jwt.claim.sub',true),'')::uuid);

create or replace function app.current_owner_id() returns uuid
language sql stable security invoker set search_path='' as $$
  select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
  where not exists (select 1 from app.account_deletions
    where owner_id=nullif(current_setting('request.jwt.claim.sub',true),'')::uuid)
$$;

-- No args: only answer whether THIS verified JWT still has its own live session.
-- Read-only definer is required because authenticated has no auth/app schema access.
create function public.rpg_current_session_active() returns boolean
language sql stable security definer set search_path='' as $$
  select auth.uid() is not null and exists (
    select 1 from auth.sessions s where s.user_id=auth.uid()
      and s.id::text=auth.jwt()->>'session_id'
      and (s.not_after is null or s.not_after>now())
  ) and not exists (select 1 from app.account_deletions where owner_id=auth.uid())
$$;
revoke all on function public.rpg_current_session_active() from public,anon,rpg_api;
grant execute on function public.rpg_current_session_active() to authenticated;

-- Keep schema app private. Existing privileged wallet views gain a live-session gate.
create or replace view public.wallet_balance_view with (security_barrier=true) as
  select owner_id,available_milli,reserved_milli,updated_at from app.wallet_accounts
  where owner_id=(select auth.uid()) and public.rpg_current_session_active();
create or replace view public.wallet_history_view with (security_barrier=true) as
  select entry_id,owner_id,entry_type,reference_type,reference_id,amount_milli,
    available_delta,reserved_delta,pricing_version_id,sku_id,created_at from app.wallet_entries
  where owner_id=(select auth.uid()) and public.rpg_current_session_active();

-- Amend the four existing Storage policies, preserving their owner predicates.
alter policy rpg_dynamic_select_own on storage.objects
  using (bucket_id='rpg-dynamic' and (storage.foldername(name))[1]='users'
    and (storage.foldername(name))[2]=(select auth.uid())::text
    and (select public.rpg_current_session_active()));
alter policy rpg_dynamic_insert_own on storage.objects
  with check (bucket_id='rpg-dynamic' and (storage.foldername(name))[1]='users'
    and (storage.foldername(name))[2]=(select auth.uid())::text
    and (select public.rpg_current_session_active()));
alter policy rpg_dynamic_update_own on storage.objects
  using (bucket_id='rpg-dynamic' and (storage.foldername(name))[1]='users'
    and (storage.foldername(name))[2]=(select auth.uid())::text
    and (select public.rpg_current_session_active()))
  with check (bucket_id='rpg-dynamic' and (storage.foldername(name))[1]='users'
    and (storage.foldername(name))[2]=(select auth.uid())::text
    and (select public.rpg_current_session_active()));
alter policy rpg_dynamic_delete_own on storage.objects
  using (bucket_id='rpg-dynamic' and (storage.foldername(name))[1]='users'
    and (storage.foldername(name))[2]=(select auth.uid())::text
    and (select public.rpg_current_session_active()));

create function app.guard_deleted_account_write() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
  if new.owner_id is not null then
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(new.owner_id::text,190));
    if exists (select 1 from app.account_deletions where owner_id=new.owner_id) then
      raise exception 'account_deleted' using errcode='42501';
    end if;
  end if;
  return new;
end;
$$;
-- No persistent private writer may resurrect state after the durable denial.
do $$ declare table_name text; begin
  foreach table_name in array array['games','game_checkpoints','game_events','runtime_catalog',
    'operations','turns','jobs','memory_documents','assets','chronicle_digests','art_generations','image_quotes',
    'usage_events'] loop
    execute format('create trigger account_write_fence before insert or update on app.%I
      for each row execute function app.guard_deleted_account_write()',table_name);
  end loop;
end $$;
revoke all on function app.guard_deleted_account_write() from public,anon,authenticated;

-- Storage service_role bypasses RLS. Fence metadata publication at its actual
-- commit point, so a timed-out/crashed HTTP uploader cannot publish after delete.
create function app.guard_storage_account_write() returns trigger
language plpgsql security definer set search_path='' as $$
declare owner uuid;
begin
  if new.bucket_id='rpg-dynamic' then
    if split_part(new.name,'/',1)<>'users' then
      raise exception 'invalid private object owner' using errcode='42501';
    end if;
    owner := split_part(new.name,'/',2)::uuid;
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(owner::text,190));
    if exists(select 1 from app.account_deletions where owner_id=owner) then
      raise exception 'account_deleted' using errcode='42501';
    end if;
    if tg_op='UPDATE' and old.bucket_id='rpg-dynamic' and exists (
      select 1 from app.account_deletions where owner_id=split_part(old.name,'/',2)::uuid
    ) then
      raise exception 'account_deleted' using errcode='42501';
    end if;
  end if;
  return new;
end;
$$;
revoke all on function app.guard_storage_account_write() from public,anon,authenticated,rpg_api,service_role;
create trigger account_storage_publication_fence before insert or update on storage.objects
  for each row execute function app.guard_storage_account_write();

-- Quotes carry private briefs; financial snapshots already live in the wallet.
create function app.protect_private_quote() returns trigger
language plpgsql set search_path='' as $$
begin
  if tg_op='DELETE' and exists(select 1 from app.account_deletions where owner_id=old.owner_id) then
    return old;
  end if;
  raise exception 'quote immutable outside account erasure' using errcode='55000';
end;
$$;
drop trigger image_quotes_immutable on app.image_quotes;
create trigger image_quotes_immutable before update or delete on app.image_quotes
  for each row execute function app.protect_private_quote();
revoke all on function app.protect_private_quote() from public,anon,authenticated,rpg_api;

create function app.sanitize_deleted_account_payment() returns trigger
language plpgsql set search_path='' as $$
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(new.owner_id::text,190));
  if exists(select 1 from app.account_deletions where owner_id=new.owner_id) then
    if tg_op='INSERT' then
      raise exception 'account_deleted' using errcode='42501';
    end if;
    new.checkout_url := null; -- late Checkout response cannot restore a private URL
  end if;
  return new;
end;
$$;
create trigger account_payment_sanitize before insert or update on app.payment_orders
  for each row execute function app.sanitize_deleted_account_payment();
revoke all on function app.sanitize_deleted_account_payment() from public,anon,authenticated,rpg_api;
alter table app.payment_orders add column checkout_closed_at timestamptz;
alter table app.payment_financial_events drop constraint payment_financial_events_kind_check;
alter table app.payment_financial_events add constraint payment_financial_events_kind_check
  check (kind in ('refund','dispute','dispute_closed','fee_reconciled','late_paid_after_delete'));
create index rate_limit_auth_retention_idx on app.rate_limit_buckets(updated_at)
  where bucket_key like 'auth:%';
-- Existing holds/settlements remain reconcilable, but no new paid dispatch starts.
create trigger account_ticket_fence before insert on app.wallet_attempt_tickets
  for each row execute function app.guard_deleted_account_write();
create trigger account_reservation_fence before insert on app.wallet_reservations
  for each row execute function app.guard_deleted_account_write();
-- A zero-balance wallet shell may still be ensured by verified late payment/
-- refund reconciliation. It grants no credit; reservation/ticket dispatch is fenced.
