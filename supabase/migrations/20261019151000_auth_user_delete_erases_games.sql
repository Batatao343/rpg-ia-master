-- SPEC-280: deleting a user in Supabase Auth (Admin API, dashboard) erases that owner's games, with the
-- semantics of ON DELETE CASCADE, so campaigns never outlive their owner as orphans.
-- Not a FK: owners of the OIDC profiles (SPEC-181) and synthetic test owners do not exist in
-- auth.users, so a FK would refuse their games. Games cascade to their private children; usage_events
-- survive with game_id NULL (SPEC-279) and no financial table references app.games.
-- The SPEC-190 erasure deletes games before the Auth user, so there this is a no-op. Idempotent.

create or replace function app.erase_games_of_deleted_auth_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- An owner with a SPEC-190 tombstone is erased by that flow; touching its games here would make the
  -- cascade (usage_events SET NULL is an UPDATE) hit the account write fence and fail the Auth delete.
  if exists (select 1 from app.account_deletions where owner_id = old.id) then
    return old;
  end if;
  delete from app.games where owner_id = old.id;
  return old;
end;
$$;
revoke all on function app.erase_games_of_deleted_auth_user() from public, anon, authenticated, rpg_api;

do $$
begin
  -- app.games forces RLS: without BYPASSRLS on the definer the delete would silently match 0 rows.
  if not (select rolbypassrls from pg_catalog.pg_roles where rolname = current_user) then
    raise exception 'SPEC-280: apply as a BYPASSRLS role (function owner)';
  end if;
  if to_regclass('auth.users') is not null then
    drop trigger if exists rpg_erase_games_on_auth_delete on auth.users;
    create trigger rpg_erase_games_on_auth_delete after delete on auth.users
      for each row execute function app.erase_games_of_deleted_auth_user();
  end if;
end $$;

select app.grant_runtime_access();
