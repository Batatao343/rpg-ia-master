create table app.operations (
  id uuid primary key,
  owner_id uuid not null,
  game_id uuid references app.games(id) on delete cascade,
  kind text not null check (
    kind in ('new_game','turn','death','equip','levelup','delete','account_delete')
  ),
  status text not null check (status in ('running','completed','failed','abandoned')),
  base_game_version bigint,
  committed_game_version bigint,
  lease_token uuid,
  lease_until timestamptz,
  heartbeat_at timestamptz,
  request_sha256 text not null check (length(request_sha256) = 64),
  receipt jsonb,
  error_code text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  unique (owner_id, id)
);

create index operations_game_status_idx on app.operations (game_id, status, lease_until);
create index operations_owner_started_idx on app.operations (owner_id, started_at desc);

alter table app.games
  add column active_operation_id uuid references app.operations(id) on delete set null,
  add column active_lease_token uuid,
  add column active_lease_until timestamptz;

create index games_active_operation_idx
  on app.games (active_operation_id) where active_operation_id is not null;

create table app.turns (
  operation_id uuid primary key references app.operations(id) on delete cascade,
  game_id uuid not null references app.games(id) on delete cascade,
  owner_id uuid not null,
  sequence bigint not null check (sequence > 0),
  timeline_epoch integer not null check (timeline_epoch >= 0),
  route text,
  input_sha256 text not null check (length(input_sha256) = 64),
  state_version_before bigint not null check (state_version_before > 0),
  state_version_after bigint check (state_version_after > 0),
  latency_ms integer check (latency_ms >= 0),
  llm_cost_usd numeric(12,6) check (llm_cost_usd >= 0),
  unique (game_id, sequence)
);

create index turns_owner_game_idx on app.turns (owner_id, game_id, sequence);
create index turns_game_fk_idx on app.turns (game_id);

create table app.jobs (
  id uuid primary key,
  owner_id uuid,
  game_id uuid references app.games(id) on delete cascade,
  kind text not null,
  dedupe_key text not null,
  status text not null check (
    status in ('queued','running','succeeded','retry','dead','cancelled')
  ),
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  result jsonb,
  attempts integer not null default 0 check (attempts >= 0),
  max_attempts integer not null check (max_attempts between 1 and 100),
  available_at timestamptz not null default now(),
  lease_token uuid,
  lease_owner text,
  lease_until timestamptz,
  last_error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (kind, dedupe_key)
);

create index jobs_claim_idx on app.jobs (status, available_at, created_at)
  where status in ('queued','retry','running');
create index jobs_game_fk_idx on app.jobs (game_id) where game_id is not null;
create index jobs_owner_idx on app.jobs (owner_id, status) where owner_id is not null;

create table app.rate_limit_buckets (
  bucket_key text primary key,
  window_started_at timestamptz not null,
  window_seconds integer not null check (window_seconds > 0),
  request_count integer not null check (request_count >= 0),
  updated_at timestamptz not null default now()
);

revoke all on app.operations, app.turns, app.jobs, app.rate_limit_buckets
  from public, anon, authenticated;
