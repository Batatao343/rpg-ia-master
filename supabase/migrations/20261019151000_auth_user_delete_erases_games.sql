-- SPEC-280: deleting a user in Supabase Auth (Admin API, dashboard) erases that owner's games, with the
-- semantics of ON DELETE CASCADE, so campaigns never outlive their owner as orphans.
-- Not a FK: owners of the OIDC profiles (SPEC-181) and synthetic test owners do not exist in
-- auth.users, so a FK would refuse their games. Games cascade to their private children; usage_events
-- survive with game_id NULL (SPEC-279) and no financial table references app.games.
-- The SPEC-190 erasure deletes games before the Auth user, so there this is a no-op. Idempotent.

create or replace function app.erase_games_of_deleted_auth_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  delete from app.games where owner_id = old.id;
  return old;
end;
$$;
revoke all on function app.erase_games_of_deleted_auth_user() from public, anon, authenticated, rpg_api;

do $$
begin
  if to_regclass('auth.users') is not null then
    drop trigger if exists rpg_erase_games_on_auth_delete on auth.users;
    create trigger rpg_erase_games_on_auth_delete after delete on auth.users
      for each row execute function app.erase_games_of_deleted_auth_user();
  end if;
end $$;

select app.grant_runtime_access();
