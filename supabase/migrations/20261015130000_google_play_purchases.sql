-- SPEC-194: Google Play consumable fulfillment ledger. Backend-only table.
create table app.google_play_purchases (
  purchase_id uuid primary key,
  owner_id uuid not null,
  product_id text not null check (length(product_id) between 1 and 128),
  sku_id text not null references app.purchase_skus(sku_id),
  pricing_version_id text not null references app.pricing_versions(version_id),
  token_sha256 text not null unique check (token_sha256 ~ '^[0-9a-f]{64}$'),
  -- Needed for idempotent consume retries; never granted to any client role.
  purchase_token text not null check (length(purchase_token) between 16 and 2048),
  order_id text not null unique check (length(order_id) between 1 and 128),
  purchased_at timestamptz,
  google_state jsonb not null,
  state text not null default 'fulfilled'
    check (state in ('fulfilled','fulfilled_unconsumed','consumed','consume_failed')),
  -- poison consume (400/404/410 while still unconsumed at Google): terminal after 8 attempts
  consume_attempts integer not null default 0 check (consume_attempts >= 0),
  -- SPEC-195 placeholders: refund/voided-purchase reconciliation.
  voided_at timestamptz,
  void_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index google_play_purchases_pending_idx on app.google_play_purchases(updated_at)
  where state in ('fulfilled','fulfilled_unconsumed');
create function app.protect_google_play_purchase() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'google play purchases retained' using errcode = '55000';
  end if;
  if (new.purchase_id,new.owner_id,new.product_id,new.sku_id,new.pricing_version_id,
      new.token_sha256,new.purchase_token,new.order_id,new.created_at)
     is distinct from
     (old.purchase_id,old.owner_id,old.product_id,old.sku_id,old.pricing_version_id,
      old.token_sha256,old.purchase_token,old.order_id,old.created_at)
     or (old.state in ('consumed','consume_failed') and new.state <> old.state) then
    raise exception 'google play purchase authority immutable' using errcode = '55000';
  end if;
  return new;
end;
$$;
create trigger google_play_purchases_authority before update or delete on app.google_play_purchases
  for each row execute function app.protect_google_play_purchase();
create trigger account_write_fence before insert or update on app.google_play_purchases
  for each row execute function app.guard_deleted_account_write();
alter table app.google_play_purchases enable row level security;
alter table app.google_play_purchases force row level security;
revoke all on app.google_play_purchases from public,anon,authenticated,rpg_api;
revoke all on function app.protect_google_play_purchase() from public,anon,authenticated;
