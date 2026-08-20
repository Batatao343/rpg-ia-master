create extension if not exists vector with schema extensions;

create table app.embedding_profiles (
  id text primary key,
  provider text not null,
  model text not null,
  dimensions integer not null check (dimensions > 0),
  metric text not null default 'cosine' check (metric = 'cosine'),
  status text not null check (status in ('building','active','retired','failed')),
  corpus_sha256 text,
  created_at timestamptz not null default now(),
  activated_at timestamptz
);

insert into app.embedding_profiles(id,provider,model,dimensions,status,activated_at)
values ('local-1024','local','deterministic-test',1024,'active',now())
on conflict (id) do nothing;

create table app.memory_documents (
  id text primary key,
  owner_id uuid,
  game_id uuid references app.games(id) on delete cascade,
  npc_id text,
  scope text not null check (scope in ('lore','rules','session','npc','chronicle')),
  content text not null,
  content_sha256 text not null check (length(content_sha256) = 64),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  provenance text,
  confidence text,
  source_id text,
  source_turn integer,
  canonical_entity_ids text[] not null default '{}',
  visibility text not null default 'public' check (visibility in ('public','hidden','secret')),
  timeline_epoch integer not null default 0,
  commit_version bigint,
  embedding_profile_id text references app.embedding_profiles(id),
  embedding extensions.vector(1024),
  embedding_status text not null default 'pending'
    check (embedding_status in ('pending','ready','failed','discarded')),
  search_text tsvector generated always as (to_tsvector('simple', content)) stored,
  discarded_at timestamptz,
  created_at timestamptz not null default now(),
  check (
    (scope in ('lore','rules') and owner_id is null and game_id is null and npc_id is null) or
    (scope in ('session','chronicle') and owner_id is not null and game_id is not null and npc_id is null) or
    (scope='npc' and owner_id is not null and game_id is not null and npc_id is not null)
  )
);

create index memory_embedding_hnsw_idx on app.memory_documents
using hnsw (embedding extensions.vector_cosine_ops)
where embedding_status='ready' and discarded_at is null;
create index memory_scope_idx on app.memory_documents(owner_id,game_id,scope,npc_id)
where discarded_at is null;
create index memory_fts_idx on app.memory_documents using gin(search_text)
where discarded_at is null;
create index memory_game_fk_idx on app.memory_documents(game_id) where game_id is not null;

grant select on app.embedding_profiles to rpg_api;
grant select,insert,update,delete on app.memory_documents to rpg_api;
alter table app.memory_documents enable row level security;
alter table app.memory_documents force row level security;
create policy memory_read_scoped on app.memory_documents for select to rpg_api
  using (
    scope in ('lore','rules') or
    (owner_id = app.current_owner_id() and scope in ('session','npc','chronicle'))
  );
create policy memory_insert_scoped on app.memory_documents for insert to rpg_api
  with check (owner_id = app.current_owner_id() and scope in ('session','npc','chronicle'));
create policy memory_update_scoped on app.memory_documents for update to rpg_api
  using (owner_id = app.current_owner_id() and scope in ('session','npc','chronicle'))
  with check (owner_id = app.current_owner_id() and scope in ('session','npc','chronicle'));
create policy memory_delete_scoped on app.memory_documents for delete to rpg_api
  using (owner_id = app.current_owner_id() and scope in ('session','npc','chronicle'));
