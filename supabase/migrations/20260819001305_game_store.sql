create schema if not exists app;

revoke all on schema app from public, anon, authenticated;

create table app.games (
  id uuid primary key,
  owner_id uuid not null,
  schema_version integer not null check (schema_version > 0),
  version bigint not null default 1 check (version > 0),
  state jsonb not null check (jsonb_typeof(state) = 'object'),
  state_sha256 text not null check (length(state_sha256) = 64),
  status text not null check (
    status in ('active', 'death_pending', 'memorial', 'archived', 'simulation')
  ),
  player_name text not null,
  class_name text not null,
  player_level integer not null check (player_level > 0),
  location_name text not null,
  world_day integer not null check (world_day > 0),
  game_over boolean not null,
  combat_simulation boolean not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_action_at timestamptz,
  check ((state->>'game_id')::uuid = id),
  unique (owner_id, id)
);

create index games_owner_updated_idx on app.games (owner_id, updated_at desc);

create table app.game_checkpoints (
  game_id uuid primary key references app.games(id) on delete cascade,
  owner_id uuid not null,
  game_version bigint not null check (game_version > 0),
  canonical_turn integer not null check (canonical_turn >= 0),
  timeline_epoch integer not null check (timeline_epoch >= 0),
  memory_commit_version bigint not null default 0 check (memory_commit_version >= 0),
  state jsonb not null check (jsonb_typeof(state) = 'object'),
  state_sha256 text not null check (length(state_sha256) = 64),
  created_at timestamptz not null default now(),
  foreign key (owner_id, game_id) references app.games(owner_id, id) on delete cascade
);

create index game_checkpoints_owner_idx on app.game_checkpoints (owner_id, game_id);

create table app.game_events (
  game_id uuid not null,
  owner_id uuid not null,
  event_id text not null check (length(event_id) between 1 and 128),
  turn integer not null check (turn >= 0),
  event_type text not null,
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  source text not null,
  event_sha256 text not null check (length(event_sha256) = 64),
  created_at timestamptz not null default now(),
  primary key (game_id, event_id),
  foreign key (owner_id, game_id) references app.games(owner_id, id) on delete cascade
);

create index game_events_owner_game_turn_idx
  on app.game_events (owner_id, game_id, turn, event_id);

create table app.runtime_catalog (
  id uuid primary key default gen_random_uuid(),
  namespace text not null,
  item_key text not null,
  scope text not null check (scope in ('global', 'user', 'game')),
  owner_id uuid,
  game_id uuid references app.games(id) on delete cascade,
  document jsonb not null check (jsonb_typeof(document) = 'object'),
  document_sha256 text not null check (length(document_sha256) = 64),
  version bigint not null default 1 check (version > 0),
  provenance text not null default 'runtime',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (scope = 'global' and owner_id is null and game_id is null) or
    (scope = 'user' and owner_id is not null and game_id is null) or
    (scope = 'game' and owner_id is not null and game_id is not null)
  )
);

create unique index runtime_catalog_global_key
  on app.runtime_catalog (namespace, item_key) where scope = 'global';
create unique index runtime_catalog_user_key
  on app.runtime_catalog (namespace, item_key, owner_id) where scope = 'user';
create unique index runtime_catalog_game_key
  on app.runtime_catalog (namespace, item_key, owner_id, game_id) where scope = 'game';
create index runtime_catalog_game_fk_idx
  on app.runtime_catalog (game_id) where game_id is not null;

revoke all on all tables in schema app from public, anon, authenticated;
