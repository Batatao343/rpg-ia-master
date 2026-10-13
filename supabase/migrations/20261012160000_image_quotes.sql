-- SPEC-188. No commercial rate, wallet credit or enabled provider is seeded.
create table app.image_price_profiles (
  profile_id text primary key,
  pricing_version_id text not null references app.pricing_versions(version_id),
  model text not null,
  size text not null check (size in ('1024x1536','1536x1024')),
  max_provider_usd numeric(18,9) not null check (max_provider_usd > 0),
  source text not null check (length(source) between 1 and 300),
  expires_at timestamptz not null
);
create trigger image_price_profiles_immutable before update or delete on app.image_price_profiles
  for each row execute function app.reject_pricing_mutation();

create table app.image_quotes (
  quote_id uuid primary key,
  owner_id uuid not null,
  game_id uuid not null,
  timeline_epoch integer not null,
  image_type text not null check (image_type in ('player','npc','scene')),
  credits_milli bigint not null check (credits_milli > 0),
  pricing_version_id text not null references app.pricing_versions(version_id),
  price_profile_id text not null references app.image_price_profiles(profile_id),
  image_rate_card_version text not null,
  expires_at timestamptz not null,
  model text not null,
  profile_version text not null,
  prompt_hash text not null check (length(prompt_hash)=64),
  private_brief jsonb not null,
  trigger jsonb not null,
  reformulation boolean not null default false,
  created_at timestamptz not null default now(),
  unique (quote_id,owner_id,game_id)
);
-- Historical quotes remain even if the campaign is deleted; no cascade rewrites finance.
create trigger image_quotes_immutable before update or delete on app.image_quotes
  for each row execute function app.reject_pricing_mutation();
create index image_quotes_owner_game_idx on app.image_quotes(owner_id,game_id);

alter table app.art_generations
  add column image_quote_id uuid unique,
  add column wallet_reservation_id uuid unique references app.wallet_reservations(reservation_id),
  add column financial_anomaly_milli bigint not null default 0 check (financial_anomaly_milli >= 0),
  add constraint art_quote_owner_fk foreign key (image_quote_id,owner_id,game_id)
    references app.image_quotes(quote_id,owner_id,game_id),
  add constraint art_quote_reservation_pair check
    ((image_quote_id is null) = (wallet_reservation_id is null));

alter table app.image_price_profiles enable row level security;
alter table app.image_price_profiles force row level security;
alter table app.image_quotes enable row level security;
alter table app.image_quotes force row level security;
revoke all on app.image_price_profiles, app.image_quotes from public, anon, authenticated;
grant select on app.image_price_profiles to rpg_api;
grant select,insert on app.image_quotes to rpg_api;
create policy image_profiles_backend_read on app.image_price_profiles for select to rpg_api using (true);
create policy image_quotes_read_own on app.image_quotes for select to rpg_api
  using (owner_id=app.current_owner_id());
create policy image_quotes_insert_own on app.image_quotes for insert to rpg_api
  with check (owner_id=app.current_owner_id());
