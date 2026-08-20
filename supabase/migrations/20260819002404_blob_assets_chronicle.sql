create table app.assets (
  id uuid primary key,
  owner_id uuid not null,
  game_id uuid not null references app.games(id) on delete cascade,
  entity_id text not null,
  asset_kind text not null check (asset_kind in ('player','npc','location','item','monster','epic')),
  variant text not null check (variant in ('full','thumb')),
  status text not null check (status in ('pending_upload','processing','ready','rejected','delete_pending','deleted','orphaned')),
  visibility text not null check (visibility in ('public','hidden','secret')),
  bucket text not null,
  object_key text not null unique,
  mime_type text not null,
  bytes bigint not null check (bytes >= 0),
  width integer not null check (width > 0),
  height integer not null check (height > 0),
  sha256 text not null check (length(sha256)=64),
  source_provider text,
  source_model text,
  prompt_sha256 text,
  moderation jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  ready_at timestamptz,
  deleted_at timestamptz,
  unique (owner_id,game_id,entity_id,variant,sha256)
);
create index assets_owner_game_idx on app.assets(owner_id,game_id,status);
create index assets_game_fk_idx on app.assets(game_id);
grant select,insert,update,delete on app.assets to rpg_api;
alter table app.assets enable row level security;
alter table app.assets force row level security;
create policy assets_select_own on app.assets for select to rpg_api
  using (owner_id=app.current_owner_id());
create policy assets_insert_own on app.assets for insert to rpg_api
  with check (owner_id=app.current_owner_id());
create policy assets_update_own on app.assets for update to rpg_api
  using (owner_id=app.current_owner_id()) with check (owner_id=app.current_owner_id());
create policy assets_delete_own on app.assets for delete to rpg_api
  using (owner_id=app.current_owner_id());

create table app.chronicle_digests (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null,
  game_id uuid not null references app.games(id) on delete cascade,
  timeline_epoch integer not null default 0,
  chapter_id text not null,
  source_hash text not null check (length(source_hash)=64),
  profile_version text not null,
  status text not null check (status in ('pending','ready','failed','extractive_fallback')),
  digest jsonb not null check (jsonb_typeof(digest)='object'),
  created_at timestamptz not null default now(),
  unique(game_id,timeline_epoch,chapter_id,source_hash,profile_version)
);
create index chronicle_digests_game_idx on app.chronicle_digests(owner_id,game_id,timeline_epoch);
grant select,insert,update,delete on app.chronicle_digests to rpg_api;
alter table app.chronicle_digests enable row level security;
alter table app.chronicle_digests force row level security;
create policy chronicle_digests_own on app.chronicle_digests for all to rpg_api
  using (owner_id=app.current_owner_id()) with check (owner_id=app.current_owner_id());

create table app.art_generations (
  generation_id uuid primary key,
  owner_id uuid not null,
  game_id uuid not null references app.games(id) on delete cascade,
  timeline_epoch integer not null default 0,
  arc_instance_id text,
  trigger_kind text not null check (trigger_kind in ('player_portrait','npc_first_appearance','arc_epic_moment')),
  trigger_instance_id text not null,
  subject_type text not null check (subject_type in ('player','npc','scene')),
  subject_id text not null,
  status text not null check (status in ('pending','generating','ready','failed_retryable','failed','refused','rejected_quality','superseded')),
  model text not null,
  profile_version text not null,
  prompt_hash text not null check(length(prompt_hash)=64),
  anchor_hash text not null check(length(anchor_hash)=64),
  private_brief jsonb not null default '{}'::jsonb,
  asset_id uuid references app.assets(id) on delete set null,
  attempt_count integer not null default 0 check(attempt_count between 0 and 3),
  usage_json jsonb not null default '{}'::jsonb,
  cost_usd numeric(12,6),
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(game_id,timeline_epoch,trigger_kind,trigger_instance_id,profile_version)
);
create index art_generations_owner_game_idx on app.art_generations(owner_id,game_id,status);
grant select,insert,update,delete on app.art_generations to rpg_api;
alter table app.art_generations enable row level security;
alter table app.art_generations force row level security;
create policy art_generations_own on app.art_generations for all to rpg_api
  using(owner_id=app.current_owner_id()) with check(owner_id=app.current_owner_id());
