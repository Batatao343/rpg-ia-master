-- SPEC-184. Commercial balances are account-owned and never live in GameState.
-- The backend DB connection is the only writer; neither PostgREST client roles
-- nor the tenant rpg_api role have table mutation privileges.
create table app.wallet_accounts (
  owner_id uuid primary key,
  available_milli bigint not null default 0 check (available_milli >= 0),
  reserved_milli bigint not null default 0 check (reserved_milli >= 0),
  updated_at timestamptz not null default now()
);

create table app.wallet_reservations (
  reservation_id uuid primary key,
  owner_id uuid not null references app.wallet_accounts(owner_id),
  reference_type text not null check (reference_type in
    ('operation','image','speech_to_text','embedding','other')),
  reference_id text not null check (length(reference_id) between 1 and 160),
  usage_operation_id uuid,
  pricing_version_id text not null references app.pricing_versions(version_id),
  fence_token uuid not null,
  ceiling_milli bigint not null check (ceiling_milli > 0),
  settled_milli bigint not null default 0 check (settled_milli >= 0),
  released_milli bigint not null default 0 check (released_milli >= 0),
  status text not null default 'reserved' check (status in
    ('reserved','effect_started','uncertain','settled','released')),
  usage_event_ids uuid[] not null default '{}',
  reconciliation_reason text,
  created_at timestamptz not null default now(),
  finished_at timestamptz,
  unique (owner_id, reference_type, reference_id),
  check (settled_milli <= ceiling_milli),
  check (released_milli <= ceiling_milli),
  check (settled_milli + released_milli <= ceiling_milli),
  check ((status in ('settled','released') and settled_milli + released_milli = ceiling_milli
          and finished_at is not null)
      or (status in ('reserved','effect_started','uncertain') and settled_milli = 0
          and released_milli = 0 and finished_at is null))
);

create table app.wallet_entries (
  entry_id uuid primary key,
  owner_id uuid not null references app.wallet_accounts(owner_id),
  entry_type text not null check (entry_type in
    ('purchase','reserve','settle','release','refund','reversal','adjustment_admin')),
  reference_type text not null check (length(reference_type) between 1 and 40),
  reference_id text not null check (length(reference_id) between 1 and 160),
  reservation_id uuid references app.wallet_reservations(reservation_id),
  related_entry_id uuid references app.wallet_entries(entry_id),
  pricing_version_id text references app.pricing_versions(version_id),
  sku_id text references app.purchase_skus(sku_id),
  amount_milli bigint not null check (amount_milli > 0),
  available_delta bigint not null,
  reserved_delta bigint not null,
  actor_id uuid,
  reason text,
  created_at timestamptz not null default now(),
  unique (owner_id, entry_type, reference_type, reference_id),
  check (
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
  )
);
create index wallet_entries_owner_time_idx on app.wallet_entries(owner_id, created_at desc);
create index wallet_entries_reservation_idx on app.wallet_entries(reservation_id)
  where reservation_id is not null;
create unique index wallet_purchase_external_key on app.wallet_entries(reference_type,reference_id)
  where entry_type = 'purchase';
create unique index wallet_refund_external_key on app.wallet_entries(reference_type,reference_id)
  where entry_type in ('refund','reversal');
create unique index wallet_purchase_refund_once on app.wallet_entries(related_entry_id)
  where entry_type in ('refund','reversal');

-- Keep a snapshot even if an operation/game is later erased; usage_events has
-- legacy ON DELETE CASCADE. A usage event can fund at most one settlement.
create table app.wallet_settled_usage (
  usage_event_id uuid primary key,
  reservation_id uuid not null references app.wallet_reservations(reservation_id),
  owner_id uuid not null references app.wallet_accounts(owner_id),
  event_sha256 text not null check (event_sha256 ~ '^[0-9a-f]{64}$'),
  cost_usd numeric(18,9) not null check (cost_usd >= 0),
  cost_basis text not null,
  pricing_version text not null,
  created_at timestamptz not null default now()
);

-- Durable dispatch tickets. A ticket is written before calling a paid provider.
-- Its worst-case liability counts toward the ceiling even if the process dies.
create table app.wallet_attempt_tickets (
  ticket_id uuid primary key,
  reservation_id uuid not null references app.wallet_reservations(reservation_id),
  owner_id uuid not null references app.wallet_accounts(owner_id),
  attempt_key text not null check (length(attempt_key) between 1 and 160),
  provider text not null check (length(provider) between 1 and 100),
  model text not null check (length(model) between 1 and 150),
  max_liability_milli bigint not null check (max_liability_milli > 0),
  fence_token uuid not null,
  created_at timestamptz not null default now(),
  unique (reservation_id, attempt_key)
);

create function app.reject_wallet_fact_mutation() returns trigger
language plpgsql set search_path = '' as $$
begin
  raise exception 'wallet facts are append-only' using errcode = '55000';
end;
$$;
create trigger wallet_entries_immutable before update or delete on app.wallet_entries
  for each row execute function app.reject_wallet_fact_mutation();
create trigger wallet_tickets_immutable before update or delete on app.wallet_attempt_tickets
  for each row execute function app.reject_wallet_fact_mutation();
create trigger wallet_settled_usage_immutable before update or delete on app.wallet_settled_usage
  for each row execute function app.reject_wallet_fact_mutation();

-- Deferred check means the account cache and the append-only facts must agree
-- at commit. Repository transactions lock the account before every transfer.
create function app.check_wallet_accounting() returns trigger
language plpgsql set search_path = '' as $$
declare
  account record;
  posted record;
begin
  select available_milli, reserved_milli into account
    from app.wallet_accounts where owner_id = new.owner_id;
  select coalesce(sum(available_delta),0) as available,
         coalesce(sum(reserved_delta),0) as reserved into posted
    from app.wallet_entries where owner_id = new.owner_id;
  if account.available_milli is distinct from posted.available
     or account.reserved_milli is distinct from posted.reserved then
    raise exception 'wallet account/ledger mismatch' using errcode = '23514';
  end if;
  return null;
end;
$$;
create constraint trigger wallet_account_reconciles
  after insert or update on app.wallet_accounts deferrable initially deferred
  for each row execute function app.check_wallet_accounting();
create constraint trigger wallet_entry_reconciles
  after insert on app.wallet_entries deferrable initially deferred
  for each row execute function app.check_wallet_accounting();

create function app.check_wallet_reserved() returns trigger
language plpgsql set search_path = '' as $$
declare
  cached bigint;
  open_sum numeric;
begin
  select reserved_milli into cached from app.wallet_accounts where owner_id = new.owner_id;
  select coalesce(sum(ceiling_milli),0) into open_sum
    from app.wallet_reservations where owner_id = new.owner_id
      and status in ('reserved','effect_started','uncertain');
  if cached is distinct from open_sum then
    raise exception 'wallet reserved/reservations mismatch' using errcode = '23514';
  end if;
  return null;
end;
$$;
create constraint trigger wallet_reservations_reconcile
  after insert or update on app.wallet_reservations deferrable initially deferred
  for each row execute function app.check_wallet_reserved();
create constraint trigger wallet_account_reserved_reconcile
  after insert or update on app.wallet_accounts deferrable initially deferred
  for each row execute function app.check_wallet_reserved();

alter table app.wallet_accounts enable row level security;
alter table app.wallet_accounts force row level security;
alter table app.wallet_reservations enable row level security;
alter table app.wallet_reservations force row level security;
alter table app.wallet_entries enable row level security;
alter table app.wallet_entries force row level security;
alter table app.wallet_attempt_tickets enable row level security;
alter table app.wallet_attempt_tickets force row level security;
alter table app.wallet_settled_usage enable row level security;
alter table app.wallet_settled_usage force row level security;
revoke all on app.wallet_accounts, app.wallet_reservations, app.wallet_entries,
  app.wallet_attempt_tickets, app.wallet_settled_usage
  from public, anon, authenticated, rpg_api;

-- Views execute as the trusted owner, but the predicate uses the verified JWT
-- claim from the current request. No base table grant is exposed to clients.
create view public.wallet_balance_view with (security_barrier = true) as
  select owner_id, available_milli, reserved_milli, updated_at
  from app.wallet_accounts where owner_id = app.current_owner_id();
create view public.wallet_history_view with (security_barrier = true) as
  select entry_id, owner_id, entry_type, reference_type, reference_id,
         amount_milli, available_delta, reserved_delta, pricing_version_id,
         sku_id, created_at
  from app.wallet_entries where owner_id = app.current_owner_id();
revoke all on public.wallet_balance_view, public.wallet_history_view
  from public, anon, authenticated, rpg_api;
grant select on public.wallet_balance_view, public.wallet_history_view to authenticated;
revoke all on function app.reject_wallet_fact_mutation() from public, anon, authenticated, rpg_api;
revoke all on function app.check_wallet_accounting() from public, anon, authenticated, rpg_api;
revoke all on function app.check_wallet_reserved() from public, anon, authenticated, rpg_api;
