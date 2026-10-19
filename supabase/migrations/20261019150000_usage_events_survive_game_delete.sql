-- SPEC-279: a usage fact survives the deletion of its campaign/operation.
-- Before: usage_events.{operation_id,game_id} cascaded from app.operations/app.games, so deleting a
-- campaign erased its spend from the daily cap, FinOps and the 13-month retention (SPEC-222 R7).
-- After: game_id becomes NULL and operation_id stays as an opaque id; owner/created_at/cost stay.
-- Account erasure (SPEC-190) still deletes usage_events explicitly (PRIVATE_TABLES). Idempotent.

-- R3: snapshot of the operation kind, so FinOps/account history keep counting a deleted campaign.
alter table app.usage_events add column if not exists operation_kind text;

-- Backfill. Owners under account erasure are skipped: their write fence rejects updates and their
-- rows are being erased anyway.
update app.usage_events u set operation_kind = o.kind
  from app.operations o
 where o.id = u.operation_id
   and u.operation_kind is null
   and not exists (select 1 from app.account_deletions d where d.owner_id = u.owner_id);

-- The kind always comes from the canonical operation, never from the inserting client.
create or replace function app.validate_usage_attribution() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  canonical_owner uuid;
  canonical_game uuid;
  canonical_kind text;
begin
  select owner_id,game_id,kind into canonical_owner,canonical_game,canonical_kind
    from app.operations where id=new.operation_id;
  if canonical_owner is null or canonical_owner <> new.owner_id
     or canonical_game is distinct from new.game_id then
    raise exception 'usage attribution mismatch' using errcode='23514';
  end if;
  new.operation_kind := canonical_kind;
  return new;
end;
$$;
revoke all on function app.validate_usage_attribution() from public, anon, authenticated;

-- R1: deleting the campaign/operation no longer erases the fact.
-- operation_id keeps its value as an opaque historical id (same as wallet_settled_usage /
-- wallet_reservations.usage_operation_id, which never had a FK): turn counts and the
-- (operation_id, component, attempt_ordinal) idempotency key stay meaningful. The insert trigger
-- above still proves the operation exists and matches owner/game at write time.
alter table app.usage_events drop constraint if exists usage_events_operation_id_fkey;
-- game_id is detached (NULL): the campaign no longer exists.
alter table app.usage_events drop constraint if exists usage_events_game_id_fkey;
alter table app.usage_events add constraint usage_events_game_id_fkey
  foreign key (game_id) references app.games(id) on delete set null;

-- An operation id is a client idempotency key. After its operation is deleted, its usage facts
-- keep the id; reusing it would make the new attempt's usage collide with the old facts
-- (unique key / replay digest) and escape metering. A reused id is silently not inserted, which
-- every claimer already treats as "idempotency key unavailable" (insert ... on conflict do nothing).
create or replace function app.refuse_reused_operation_id() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if exists (select 1 from app.usage_events where operation_id = new.id) then
    return null;
  end if;
  return new;
end;
$$;
revoke all on function app.refuse_reused_operation_id() from public, anon, authenticated, rpg_api;
drop trigger if exists operations_refuse_reused_id on app.operations;
create trigger operations_refuse_reused_id before insert on app.operations
  for each row execute function app.refuse_reused_operation_id();

select app.grant_runtime_access();
