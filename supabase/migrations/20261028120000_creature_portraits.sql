-- SPEC-352: retrato de inimigo pago pelo jogador, com registro compartilhado.
--
-- `app.creature_portraits` (uma linha por `portrait_key`) e o ARBITRO da cobranca unica por chave:
-- a chave primaria decide quem paga quando dois jogadores confirmam a mesma criatura. Nao e por
-- dono (a imagem do tipo vale para todos): o vinculo ao autor e `origin_owner_id`, desvinculado na
-- exclusao de conta (padrao de `app.shared_pool`, SPEC-297 D3). A geracao e privada e pode sumir com
-- a conta, por isso `generation_id` NAO tem FK.
-- Tambem amplia os CHECKs de arte/cotacao com o tipo `monster` e cria o bucket `rpg-shared-art`.
-- Idempotente. NAO aplicar em staging sem o coordenador.

create table if not exists app.creature_portraits (
  portrait_key text primary key check (length(portrait_key) between 1 and 200),
  scope text not null check (scope in ('tipo','unico','npc')),
  status text not null check (status in ('pending','ready','failed','retired')),
  generation_id uuid,
  visibility text not null check (visibility in ('shared','pool','game')),
  pool_entry_id text,
  origin_owner_id uuid,
  origin_game_id uuid,
  store text check (store in ('shared','private')),
  object_keys jsonb not null default '{}'::jsonb check (jsonb_typeof(object_keys) = 'object'),
  sha256 jsonb not null default '{}'::jsonb check (jsonb_typeof(sha256) = 'object'),
  error_code text check (error_code is null or length(error_code) <= 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  version int not null default 1,
  constraint creature_portraits_ready_has_thumb check (
    status <> 'ready' or (object_keys ? 'thumb' and store is not null)),
  -- linha viva sem dono escaparia da exclusao de conta (LGPD): so ready/retired podem ser orfas.
  constraint creature_portraits_owner_required check (
    origin_owner_id is not null or status in ('ready','retired'))
);

create index if not exists creature_portraits_origin_owner_idx
  on app.creature_portraits (origin_owner_id) where origin_owner_id is not null;
create index if not exists creature_portraits_origin_game_idx
  on app.creature_portraits (origin_game_id) where origin_game_id is not null;
create index if not exists creature_portraits_generation_idx
  on app.creature_portraits (generation_id) where generation_id is not null;

alter table app.creature_portraits enable row level security;
alter table app.creature_portraits force row level security;
revoke all on app.creature_portraits from public, anon, authenticated;
grant select on app.creature_portraits to rpg_api;  -- sem insert/update/delete: quem escreve e o sistema

drop policy if exists creature_portraits_read on app.creature_portraits;
create policy creature_portraits_read on app.creature_portraits for select to rpg_api
  using (
    status in ('ready','pending')
    and (visibility = 'shared' or origin_game_id in (select id from app.games))
  );

-- Linha `ready` e imutavel (chave, escopo, visibilidade, objetos, hashes). Excecoes: a promocao
-- `private` -> `shared` (reescreve `object_keys` uma unica vez), a aposentadoria (`retired`) e a
-- exclusao de conta (desvinculo; `failed` de uma copia ainda privada cujo blob vai sumir).
create or replace function app.guard_creature_portrait_immutable() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
  if old.status = 'ready' then
    if new.status = 'retired' then
      return new;
    end if;
    if new.status = 'failed' and old.store = 'private' then
      return new;
    end if;
    if new.status <> 'ready'
       or new.portrait_key is distinct from old.portrait_key
       or new.scope is distinct from old.scope
       or new.visibility is distinct from old.visibility then
      raise exception 'creature_portrait_ready_is_immutable' using errcode = '42501';
    end if;
    if (new.object_keys is distinct from old.object_keys or new.sha256 is distinct from old.sha256
        or new.store is distinct from old.store)
       and not (old.store = 'private' and new.store = 'shared') then
      raise exception 'creature_portrait_ready_is_immutable' using errcode = '42501';
    end if;
  end if;
  return new;
end;
$$;
revoke all on function app.guard_creature_portrait_immutable() from public, anon, authenticated;

drop trigger if exists creature_portrait_immutable on app.creature_portraits;
create trigger creature_portrait_immutable before update on app.creature_portraits
  for each row execute function app.guard_creature_portrait_immutable();

-- Cerca de exclusao de conta (SPEC-222): reaproveita a funcao de `origin_owner_id` da SPEC-297.
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

drop trigger if exists account_write_fence on app.creature_portraits;
create trigger account_write_fence before insert or update on app.creature_portraits
  for each row execute function app.guard_deleted_account_write_origin();

-- Tipo novo `monster`: gatilho `creature_portrait`, assunto `monster`, cotacao `monster`.
alter table app.art_generations drop constraint if exists art_generations_trigger_kind_check;
alter table app.art_generations add constraint art_generations_trigger_kind_check check (
  trigger_kind in ('player_portrait','npc_first_appearance','arc_epic_moment','creature_portrait'));
alter table app.art_generations drop constraint if exists art_generations_subject_type_check;
alter table app.art_generations add constraint art_generations_subject_type_check check (
  subject_type in ('player','npc','scene','monster'));
alter table app.image_quotes drop constraint if exists image_quotes_image_type_check;
alter table app.image_quotes add constraint image_quotes_image_type_check check (
  image_type in ('player','npc','scene','monster'));

-- Bucket privado do registro compartilhado (so service_role; sem policy para clientes). Servido por
-- URL assinada: um bucket publico exporia `unico:{game}` sem controle. Chaves: `shared/creatures/...`
-- (fora de `users/{owner}/`, para sobreviver a exclusao de conta de quem pagou).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('rpg-shared-art', 'rpg-shared-art', false, 20971520, array['image/webp']::text[])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

select app.grant_runtime_access();
