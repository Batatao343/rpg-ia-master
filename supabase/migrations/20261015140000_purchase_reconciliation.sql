-- SPEC-195: cross-channel purchase reconciliation, refund debt (financial hold), fee records.
-- Backend-only tables (forced RLS, no client grants). All facts are append-only; history is
-- never rewritten: refunds/disputes/revocations post compensating entries.

-- 1. Compensating wallet entry types (original types and rows untouched).
alter table app.wallet_entries drop constraint wallet_entries_entry_type_check;
alter table app.wallet_entries add constraint wallet_entries_entry_type_check check (entry_type in
  ('purchase','reserve','settle','release','refund','reversal','adjustment_admin',
   'clawback','claw_release','debt_settlement'));
alter table app.wallet_entries drop constraint wallet_entries_check;
alter table app.wallet_entries add constraint wallet_entries_check check (
    (entry_type = 'purchase' and available_delta = amount_milli and reserved_delta = 0
      and sku_id is not null and pricing_version_id is not null and reservation_id is null)
    or (entry_type = 'reserve' and available_delta = -amount_milli
      and reserved_delta = amount_milli and reservation_id is not null
      and pricing_version_id is not null)
    or (entry_type = 'settle' and available_delta = 0
      and reserved_delta = -amount_milli and reservation_id is not null
      and pricing_version_id is not null)
    or (entry_type = 'release' and available_delta = amount_milli
      and reserved_delta = -amount_milli and reservation_id is not null
      and pricing_version_id is not null)
    or (entry_type in ('refund','reversal') and available_delta = -amount_milli
      and reserved_delta = 0 and reservation_id is null and related_entry_id is not null)
    or (entry_type = 'adjustment_admin' and reserved_delta = 0
      and available_delta in (amount_milli, -amount_milli)
      and actor_id is not null and reason is not null and length(reason) between 1 and 500)
    or (entry_type = 'clawback' and available_delta = -amount_milli and reserved_delta = 0
      and reservation_id is null and related_entry_id is not null)
    or (entry_type = 'claw_release' and available_delta = amount_milli and reserved_delta = 0
      and reservation_id is null and related_entry_id is not null)
    or (entry_type = 'debt_settlement' and available_delta = -amount_milli and reserved_delta = 0
      and reservation_id is null)
);

-- 2. Normalized provider events (dedupe + out-of-order parking).
create table app.purchase_reconciliation_events (
  event_pk uuid primary key,
  provider text not null check (provider in ('stripe','google_play')),
  provider_event_id text not null check (length(provider_event_id) between 1 and 200),
  kind text not null check (kind in ('refund','dispute_open','dispute_won','dispute_lost',
    'voided','revoked','fee_reconciled')),
  purchase_ref text not null check (length(purchase_ref) between 1 and 160),
  amount_cents bigint check (amount_cents >= 0),
  sub_id text,
  provider_created bigint not null default 0,
  reason integer,
  status text not null default 'pending' check (status in ('pending','parked','applied','orphaned')),
  received_at timestamptz not null default now(),
  applied_at timestamptz,
  attempt_count integer not null default 0 check (attempt_count >= 0),
  next_attempt_at timestamptz not null default now(),
  unique (provider, provider_event_id)
);
create index purchase_reconciliation_open_idx on app.purchase_reconciliation_events(next_attempt_at)
  where status in ('pending','parked');
create index purchase_reconciliation_ref_idx on app.purchase_reconciliation_events(provider, purchase_ref);
create function app.protect_reconciliation_event() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'reconciliation events retained' using errcode = '55000';
  end if;
  if (new.event_pk,new.provider,new.provider_event_id,new.kind,new.purchase_ref,new.amount_cents,
      new.sub_id,new.provider_created,new.reason,new.received_at)
     is distinct from
     (old.event_pk,old.provider,old.provider_event_id,old.kind,old.purchase_ref,old.amount_cents,
      old.sub_id,old.provider_created,old.reason,old.received_at)
     or (old.status = 'applied' and new.status <> 'applied') then
    raise exception 'reconciliation event facts immutable' using errcode = '55000';
  end if;
  return new;
end;
$$;
create trigger reconciliation_events_protect before update or delete on app.purchase_reconciliation_events
  for each row execute function app.protect_reconciliation_event();

-- Stripe webhook rows that normalize to no financial effect: marked once, never re-scanned.
create table app.purchase_reconciliation_skips (
  provider text not null check (provider in ('stripe','google_play')),
  provider_event_id text not null check (length(provider_event_id) between 1 and 200),
  reason text not null,
  created_at timestamptz not null default now(),
  primary key (provider, provider_event_id)
);

-- 3. Derived per-purchase state (audit of the closed state machine).
create table app.purchase_reconciliation_state (
  provider text not null check (provider in ('stripe','google_play')),
  purchase_ref text not null,
  owner_id uuid not null,
  state text not null,
  target_milli bigint not null check (target_milli >= 0),
  updated_at timestamptz not null default now(),
  primary key (provider, purchase_ref)
);
-- Poll watermark per provider (Google voided purchases): only ever moves forward.
create table app.purchase_reconciliation_cursors (
  provider text primary key check (provider in ('stripe','google_play')),
  watermark_ms bigint not null check (watermark_ms >= 0),
  updated_at timestamptz not null default now()
);
-- Append-only transition history (the state row above is only the latest snapshot).
create table app.purchase_reconciliation_transitions (
  transition_id uuid primary key,
  provider text not null check (provider in ('stripe','google_play')),
  purchase_ref text not null,
  old_state text not null,
  new_state text not null,
  created_at timestamptz not null default now()
);
create index purchase_reconciliation_transitions_idx
  on app.purchase_reconciliation_transitions(provider, purchase_ref, created_at);
create trigger purchase_reconciliation_transitions_immutable
  before update or delete on app.purchase_reconciliation_transitions
  for each row execute function app.reject_wallet_fact_mutation();

-- 4. Refund debt ledger (append-only; balance = sum(debt_delta) >= 0).
create table app.wallet_debt_entries (
  debt_entry_id uuid primary key,
  owner_id uuid not null,
  kind text not null check (kind in ('open','settle','release','forgive','forgive_close')),
  purchase_key text,
  amount_milli bigint not null check (amount_milli > 0),
  debt_delta bigint not null,
  reference_id text not null check (length(reference_id) between 1 and 300),
  wallet_entry_id uuid references app.wallet_entries(entry_id),
  actor_id uuid,
  reason text check (reason is null or length(reason) between 1 and 500),
  created_at timestamptz not null default now(),
  unique (owner_id, kind, reference_id),
  -- forgive_close: a release that hit already-forgiven debt; it closes the forgive, moves no money.
  check ((kind = 'open' and debt_delta = amount_milli)
      or (kind = 'forgive_close' and debt_delta = 0)
      or (kind not in ('open','forgive_close') and debt_delta = -amount_milli)),
  check (kind <> 'forgive' or (actor_id is not null and reason is not null))
);
create index wallet_debt_owner_idx on app.wallet_debt_entries(owner_id, created_at);
create trigger wallet_debt_immutable before update or delete on app.wallet_debt_entries
  for each row execute function app.reject_wallet_fact_mutation();
create function app.check_wallet_debt() returns trigger
language plpgsql set search_path = '' as $$
declare total numeric;
begin
  select coalesce(sum(debt_delta),0) into total from app.wallet_debt_entries where owner_id = new.owner_id;
  if total < 0 then
    raise exception 'wallet debt cannot be negative' using errcode = '23514';
  end if;
  return null;
end;
$$;
create constraint trigger wallet_debt_nonnegative
  after insert on app.wallet_debt_entries deferrable initially deferred
  for each row execute function app.check_wallet_debt();

-- Financial hold: no NEW paid reservation/ticket while debt exists. Free reads are untouched;
-- existing reservations stay reconcilable (settle/release do not insert reservations).
create function app.guard_financial_hold() returns trigger
language plpgsql set search_path = '' as $$
begin
  if exists (select 1 from app.wallet_debt_entries where owner_id = new.owner_id
             group by owner_id having sum(debt_delta) > 0) then
    raise exception 'financial_hold' using errcode = '42501';
  end if;
  return new;
end;
$$;
create trigger financial_hold_reservation before insert on app.wallet_reservations
  for each row execute function app.guard_financial_hold();
create trigger financial_hold_ticket before insert on app.wallet_attempt_tickets
  for each row execute function app.guard_financial_hold();

-- 5. Real payment fees as separate records (original purchase never rewritten).
create table app.purchase_fee_records (
  fee_id uuid primary key,
  provider text not null check (provider in ('stripe','google_play')),
  purchase_ref text not null,
  provider_event_id text not null,
  fee_cents bigint not null check (fee_cents >= 0),
  created_at timestamptz not null default now(),
  unique (provider, provider_event_id)
);
create trigger purchase_fee_records_immutable before update or delete on app.purchase_fee_records
  for each row execute function app.reject_wallet_fact_mutation();

do $$ declare t text; begin
  foreach t in array array['purchase_reconciliation_events','purchase_reconciliation_state',
    'purchase_reconciliation_skips','purchase_reconciliation_cursors','purchase_reconciliation_transitions','wallet_debt_entries','purchase_fee_records'] loop
    execute format('alter table app.%I enable row level security', t);
    execute format('alter table app.%I force row level security', t);
    execute format('revoke all on app.%I from public,anon,authenticated,rpg_api', t);
  end loop;
end $$;
-- No account_write_fence on debt: a late refund for a deleted account is a financial fact
-- that must still be recordable (SPEC-190 zero-balance shell rule).
revoke all on function app.protect_reconciliation_event(), app.check_wallet_debt(),
  app.guard_financial_hold() from public,anon,authenticated,rpg_api;
