create schema if not exists app;

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'rpg_api') then
    create role rpg_api nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end $$;

-- A role de conexão do backend assume o papel tenant somente após validar o JWT.
-- `rpg_api` continua NOLOGIN/NOBYPASSRLS e não pode ser usada diretamente.
grant rpg_api to postgres;

create or replace function app.current_owner_id()
returns uuid
language sql
stable
security invoker
set search_path = ''
as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;

grant usage on schema app to rpg_api;
grant execute on function app.current_owner_id() to rpg_api;

grant select, insert, update, delete on
  app.games, app.game_checkpoints, app.game_events, app.runtime_catalog,
  app.operations, app.turns, app.jobs, app.rate_limit_buckets
to rpg_api;

alter table app.games enable row level security;
alter table app.games force row level security;
create policy games_select_own on app.games for select to rpg_api
  using (owner_id = app.current_owner_id());
create policy games_insert_own on app.games for insert to rpg_api
  with check (owner_id = app.current_owner_id());
create policy games_update_own on app.games for update to rpg_api
  using (owner_id = app.current_owner_id())
  with check (owner_id = app.current_owner_id());
create policy games_delete_own on app.games for delete to rpg_api
  using (owner_id = app.current_owner_id());

alter table app.game_checkpoints enable row level security;
alter table app.game_checkpoints force row level security;
create policy checkpoints_own on app.game_checkpoints for all to rpg_api
  using (owner_id = app.current_owner_id())
  with check (owner_id = app.current_owner_id());

alter table app.game_events enable row level security;
alter table app.game_events force row level security;
create policy events_own on app.game_events for all to rpg_api
  using (owner_id = app.current_owner_id())
  with check (owner_id = app.current_owner_id());

alter table app.runtime_catalog enable row level security;
alter table app.runtime_catalog force row level security;
create policy catalog_read_scoped on app.runtime_catalog for select to rpg_api
  using (scope = 'global' or owner_id = app.current_owner_id());
create policy catalog_write_scoped on app.runtime_catalog for insert to rpg_api
  with check (scope <> 'global' and owner_id = app.current_owner_id());
create policy catalog_update_scoped on app.runtime_catalog for update to rpg_api
  using (scope <> 'global' and owner_id = app.current_owner_id())
  with check (scope <> 'global' and owner_id = app.current_owner_id());
create policy catalog_delete_scoped on app.runtime_catalog for delete to rpg_api
  using (scope <> 'global' and owner_id = app.current_owner_id());

alter table app.operations enable row level security;
alter table app.operations force row level security;
create policy operations_own on app.operations for all to rpg_api
  using (owner_id = app.current_owner_id())
  with check (owner_id = app.current_owner_id());

alter table app.turns enable row level security;
alter table app.turns force row level security;
create policy turns_own on app.turns for all to rpg_api
  using (owner_id = app.current_owner_id())
  with check (owner_id = app.current_owner_id());

alter table app.jobs enable row level security;
alter table app.jobs force row level security;
create policy jobs_own on app.jobs for all to rpg_api
  using (owner_id = app.current_owner_id())
  with check (owner_id = app.current_owner_id());

-- Buckets de rate limit podem conter IP/owner; somente o backend com role de
-- manutenção os manipula. A role tenant não recebe acesso direto.
revoke all on app.rate_limit_buckets from rpg_api;
