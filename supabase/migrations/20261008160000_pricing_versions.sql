-- SPEC-183: published pricing facts are append-only and never client-authored.
-- No commercial version or SKU is seeded by this migration.
create table app.pricing_versions (
  version_id text primary key check (length(version_id) between 1 and 80),
  shard_budget_unit_brl numeric(20,10) not null check (shard_budget_unit_brl > 0),
  target_margin_rate numeric(8,6) not null default 0.05 check (target_margin_rate = 0.05),
  tax_rate numeric(8,6) not null default 0 check (tax_rate = 0),
  fx_usd_brl numeric(20,10) not null check (fx_usd_brl > 0),
  fx_source text not null check (length(fx_source) between 1 and 300),
  fx_observed_at timestamptz not null,
  fx_max_age_seconds integer not null check (fx_max_age_seconds > 0),
  fx_buffer_rate numeric(8,6) not null check (fx_buffer_rate between 0 and 1),
  rate_card_version text not null check (length(rate_card_version) between 1 and 80),
  rate_card_sha256 text not null check (rate_card_sha256 ~ '^[0-9a-f]{64}$'),
  rate_card_source text not null check (length(rate_card_source) between 1 and 300),
  rate_card_observed_at timestamptz not null,
  rate_card_max_age_seconds integer not null check (rate_card_max_age_seconds > 0),
  -- One atomic version payload; each channel has {percentage, fixed_brl}.
  channel_fees jsonb not null check (jsonb_typeof(channel_fees) = 'object'
                                      and channel_fees <> '{}'::jsonb),
  created_at timestamptz not null default now()
);

create table app.purchase_skus (
  sku_id text primary key check (length(sku_id) between 1 and 120),
  pricing_version_id text not null references app.pricing_versions(version_id),
  channel text not null check (length(channel) between 1 and 40),
  store_product_id text not null check (length(store_product_id) between 1 and 200),
  gross_brl numeric(18,2) not null check (gross_brl > 0),
  shard_milli bigint not null check (shard_milli > 0),
  created_at timestamptz not null default now(),
  unique (channel, store_product_id, pricing_version_id)
);

create function app.validate_pricing_fees() returns trigger
language plpgsql set search_path = '' as $$
declare
  item record;
  percent_text text;
  fixed_text text;
begin
  for item in select key, value from pg_catalog.jsonb_each(new.channel_fees) loop
    if length(item.key) not between 1 and 40 or pg_catalog.jsonb_typeof(item.value) <> 'object'
       or pg_catalog.jsonb_typeof(item.value->'percentage') <> 'string'
       or pg_catalog.jsonb_typeof(item.value->'fixed_brl') <> 'string' then
      raise exception 'invalid channel fee' using errcode = '23514';
    end if;
    percent_text := item.value->>'percentage';
    fixed_text := item.value->>'fixed_brl';
    if percent_text !~ '^[0-9]+(\.[0-9]+)?$'
       or fixed_text !~ '^[0-9]+(\.[0-9]{1,2})?$'
       or percent_text::numeric >= 1 then
      raise exception 'invalid channel fee' using errcode = '23514';
    end if;
  end loop;
  return new;
end;
$$;
create trigger pricing_versions_validate_fees before insert on app.pricing_versions
  for each row execute function app.validate_pricing_fees();

-- Even a privileged routine must publish a new version instead of rewriting
-- the FX, fees, SKU price or granted amount used by a historical purchase.
create function app.reject_pricing_mutation() returns trigger
language plpgsql set search_path = '' as $$
begin
  raise exception 'pricing versions and SKUs are immutable' using errcode = '55000';
end;
$$;
create trigger pricing_versions_immutable before update or delete on app.pricing_versions
  for each row execute function app.reject_pricing_mutation();
create trigger purchase_skus_immutable before update or delete on app.purchase_skus
  for each row execute function app.reject_pricing_mutation();

alter table app.pricing_versions enable row level security;
alter table app.pricing_versions force row level security;
alter table app.purchase_skus enable row level security;
alter table app.purchase_skus force row level security;
revoke all on app.pricing_versions, app.purchase_skus from public, anon, authenticated;
grant select on app.pricing_versions, app.purchase_skus to rpg_api;
create policy pricing_versions_backend_read on app.pricing_versions for select to rpg_api
  using (true);
create policy purchase_skus_backend_read on app.purchase_skus for select to rpg_api
  using (true);
revoke all on function app.reject_pricing_mutation() from public, anon, authenticated;
revoke all on function app.validate_pricing_fees() from public, anon, authenticated;
