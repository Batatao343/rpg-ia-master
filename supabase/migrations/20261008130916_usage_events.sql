-- SPEC-182: immutable-by-repository usage facts, committed with the operation.
-- Account/game deletion still cascades for user-data erasure.
alter table app.turns alter column llm_cost_usd type numeric(18,9);

create table app.usage_events (
  event_id uuid primary key,
  operation_id uuid not null references app.operations(id) on delete cascade,
  owner_id uuid not null,
  game_id uuid references app.games(id) on delete cascade,
  component text not null check (length(component) between 1 and 80),
  attempt_ordinal integer not null check (attempt_ordinal >= 0),
  category text not null check (category in
    ('llm', 'decision', 'embedding', 'speech_to_text', 'image', 'other')),
  provider text not null check (length(provider) between 1 and 100),
  model text not null check (length(model) between 1 and 150),
  outcome text not null check (length(outcome) between 1 and 40),
  input_units bigint check (input_units >= 0),
  output_units bigint check (output_units >= 0),
  cached_units bigint check (cached_units >= 0),
  audio_units bigint check (audio_units >= 0),
  image_units bigint check (image_units >= 0),
  cost_usd numeric(18,9) not null check (cost_usd >= 0),
  cost_basis text not null check (cost_basis in
    ('provider_reported', 'token_priced', 'rate_card', 'estimated')),
  pricing_version text not null check (length(pricing_version) between 1 and 80),
  billing_exact boolean not null,
  event_sha256 text not null check (length(event_sha256) = 64),
  created_at timestamptz not null default now(),
  unique (operation_id, component, attempt_ordinal)
);

create index usage_events_owner_created_idx on app.usage_events (owner_id, created_at desc);
create index usage_events_game_created_idx on app.usage_events (game_id, created_at desc)
  where game_id is not null;

alter table app.usage_events enable row level security;
alter table app.usage_events force row level security;
revoke all on app.usage_events from public, anon, authenticated;
grant select,insert on app.usage_events to rpg_api;
create policy usage_events_read_own on app.usage_events for select to rpg_api
  using (owner_id=app.current_owner_id());
create policy usage_events_insert_own on app.usage_events for insert to rpg_api
  with check (owner_id=app.current_owner_id());
