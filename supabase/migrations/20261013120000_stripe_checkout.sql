-- SPEC-189 test-mode only. No SKU, price or commercial activation is seeded.
create table app.payment_orders (
  order_id uuid primary key,
  owner_id uuid not null,
  request_id uuid not null,
  sku_id text not null references app.purchase_skus(sku_id),
  pricing_version_id text not null references app.pricing_versions(version_id),
  gross_cents bigint not null check (gross_cents > 0),
  currency text not null default 'brl' check (currency = 'brl'),
  shard_milli bigint not null check (shard_milli > 0),
  estimated_fee_cents bigint not null check (estimated_fee_cents >= 0),
  allocated_budget_brl numeric(30,10) not null check (allocated_budget_brl >= 0),
  actual_fee_cents bigint check (actual_fee_cents >= 0),
  actual_contribution_margin_brl numeric(30,10),
  stripe_session_id text unique,
  stripe_payment_intent text unique,
  checkout_url text,
  status text not null default 'created' check (status in
    ('created','checkout_pending','paid','refunded','disputed','reconciliation_required','expired')),
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_id,request_id)
);
create table app.stripe_events (
  event_id text primary key check (length(event_id) between 5 and 160),
  event_type text not null,
  body_sha256 text not null check (body_sha256 ~ '^[0-9a-f]{64}$'),
  provider_created bigint not null,
  -- Sanitized references/financial numbers only; no raw customer/PII payload.
  facts jsonb not null,
  received_at timestamptz not null default now()
);
create table app.payment_financial_events (
  financial_id uuid primary key,
  order_id uuid not null references app.payment_orders(order_id),
  stripe_event_id text references app.stripe_events(event_id),
  kind text not null check (kind in ('refund','dispute','dispute_closed','fee_reconciled')),
  provider_reference text not null,
  amount_cents bigint check (amount_cents >= 0),
  currency text,
  outcome text not null,
  created_at timestamptz not null default now(),
  unique (order_id,kind,provider_reference)
);
create function app.protect_payment_order() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'payment orders retained' using errcode = '55000';
  end if;
  if (new.order_id,new.owner_id,new.request_id,new.sku_id,new.pricing_version_id,
      new.gross_cents,new.currency,new.shard_milli,new.estimated_fee_cents,new.allocated_budget_brl,new.expires_at,new.created_at)
     is distinct from
     (old.order_id,old.owner_id,old.request_id,old.sku_id,old.pricing_version_id,
      old.gross_cents,old.currency,old.shard_milli,old.estimated_fee_cents,old.allocated_budget_brl,old.expires_at,old.created_at)
     or (old.stripe_session_id is not null and new.stripe_session_id is distinct from old.stripe_session_id)
     or (old.stripe_payment_intent is not null and new.stripe_payment_intent is distinct from old.stripe_payment_intent) then
    raise exception 'payment order authority immutable' using errcode = '55000';
  end if;
  return new;
end;
$$;
create trigger payment_orders_authority before update or delete on app.payment_orders
  for each row execute function app.protect_payment_order();
create trigger stripe_events_append_only before update or delete on app.stripe_events
  for each row execute function app.reject_wallet_fact_mutation();
create trigger financial_events_append_only before update or delete on app.payment_financial_events
  for each row execute function app.reject_wallet_fact_mutation();
alter table app.payment_orders enable row level security;
alter table app.payment_orders force row level security;
alter table app.stripe_events enable row level security;
alter table app.stripe_events force row level security;
alter table app.payment_financial_events enable row level security;
alter table app.payment_financial_events force row level security;
revoke all on app.payment_orders,app.stripe_events,app.payment_financial_events from public,anon,authenticated,rpg_api;
grant select on app.payment_orders,app.payment_financial_events to rpg_api;
create policy payment_orders_owner_read on app.payment_orders for select to rpg_api
  using (owner_id = app.current_owner_id());
create policy financial_events_owner_read on app.payment_financial_events for select to rpg_api
  using (exists (select 1 from app.payment_orders o where o.order_id=payment_financial_events.order_id
    and o.owner_id=app.current_owner_id()));
revoke all on function app.protect_payment_order() from public,anon,authenticated;
