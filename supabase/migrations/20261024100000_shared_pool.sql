-- SPEC-297: pool compartilhado entre mundos (NPCs, criaturas, itens, locais gerados em jogo).
--
-- Quarentena em duas camadas: o tenant (`rpg_api`) so INSERE em 'held'/'local_only' e so LE as
-- proprias linhas + as 'promoted'; QUEM muda `status` e o job de sistema (admin/runtime).
-- A tabela nao e por-owner (o conteudo promovido e do mundo): o vinculo ao autor e
-- `origin_owner_id`, desvinculado (NULL) na exclusao de conta quando a entrada foi promovida
-- (decisao D3). Idempotente. NAO aplicar em staging sem o coordenador.

create table if not exists app.shared_pool (
  entry_id text primary key check (length(entry_id) between 8 and 64),
  namespace text not null check (namespace in ('npc_template','bestiary_template','custom_artifact','location')),
  status text not null check (status in ('held','local_only','promoted','rejected','vetoed','retired')),
  region_id text not null default '',
  name text not null check (length(name) between 1 and 60),
  name_fold text not null,
  name_origin text not null check (name_origin in ('narrator','player','engine')),
  document jsonb not null check (jsonb_typeof(document) = 'object'),
  legend text not null default '' check (length(legend) <= 160),
  seed jsonb,
  seed_signature text not null default '',
  origin_owner_id uuid,
  origin_game_id text,
  input_shingles text[] not null default '{}' check (cardinality(input_shingles) <= 200),
  embedding_profile text,
  embedding extensions.vector(1024),
  created_at timestamptz not null default now(),
  promote_after timestamptz not null,
  attempts int not null default 0 check (attempts >= 0),
  evaluation jsonb,
  evaluated_at timestamptz,
  duplicate_of text,
  veto_reason text check (veto_reason is null or length(veto_reason) <= 200),
  version int not null default 1
);

create index if not exists shared_pool_ns_status_region_idx
  on app.shared_pool (namespace, status, region_id);
create index if not exists shared_pool_promoted_name_idx
  on app.shared_pool (namespace, name_fold) where status = 'promoted';
create index if not exists shared_pool_signature_idx
  on app.shared_pool (namespace, seed_signature) where seed_signature <> '';
create index if not exists shared_pool_due_idx
  on app.shared_pool (status, promote_after);
create index if not exists shared_pool_origin_game_idx
  on app.shared_pool (origin_game_id, namespace) where origin_game_id is not null;
create index if not exists shared_pool_origin_owner_idx
  on app.shared_pool (origin_owner_id, created_at) where origin_owner_id is not null;

alter table app.shared_pool enable row level security;
alter table app.shared_pool force row level security;
revoke all on app.shared_pool from public, anon, authenticated;
grant select, insert on app.shared_pool to rpg_api;  -- sem update/delete: ninguem se autopromove

drop policy if exists shared_pool_read on app.shared_pool;
create policy shared_pool_read on app.shared_pool for select to rpg_api
  using (status = 'promoted' or origin_owner_id = app.current_owner_id());

drop policy if exists shared_pool_insert_own on app.shared_pool;
create policy shared_pool_insert_own on app.shared_pool for insert to rpg_api
  with check (
    status in ('held', 'local_only')
    and origin_owner_id is not null
    and origin_owner_id = app.current_owner_id()
  );

-- Entrada promovida e imutavel (R26): so `status`, `veto_reason`, `evaluation`,
-- `evaluated_at`, `attempts`, `promote_after`, `embedding*`, `origin_*`, `input_shingles` e
-- `duplicate_of` podem mudar (vinculo/desvinculo, veto, restauracao).
create or replace function app.guard_shared_pool_immutable() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
  if old.status = 'promoted' and (
       new.document is distinct from old.document
    or new.name is distinct from old.name
    or new.name_fold is distinct from old.name_fold
    or new.legend is distinct from old.legend
    or new.seed is distinct from old.seed
    or new.seed_signature is distinct from old.seed_signature
    or new.namespace is distinct from old.namespace
    or new.region_id is distinct from old.region_id
  ) then
    raise exception 'shared_pool_promoted_is_immutable' using errcode = '42501';
  end if;
  return new;
end;
$$;
revoke all on function app.guard_shared_pool_immutable() from public, anon, authenticated;

drop trigger if exists shared_pool_immutable on app.shared_pool;
create trigger shared_pool_immutable before update on app.shared_pool
  for each row execute function app.guard_shared_pool_immutable();

-- Cerca de exclusao de conta (SPEC-222): nenhum escritor privado ressuscita estado depois
-- da negacao duravel. A tabela usa `origin_owner_id` (nao `owner_id`), logo funcao propria.
create or replace function app.guard_deleted_account_write_origin() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
  if new.origin_owner_id is not null then
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(new.origin_owner_id::text, 190));
    if exists (select 1 from app.account_deletions where owner_id = new.origin_owner_id) then
      raise exception 'account_deleted' using errcode = '42501';
    end if;
  end if;
  return new;
end;
$$;
revoke all on function app.guard_deleted_account_write_origin() from public, anon, authenticated;

drop trigger if exists account_write_fence on app.shared_pool;
create trigger account_write_fence before insert or update on app.shared_pool
  for each row execute function app.guard_deleted_account_write_origin();

-- rpg_admin/rpg_runtime sao NOBYPASSRLS: cria as policies admin_all/runtime_all.
select app.grant_runtime_access();
