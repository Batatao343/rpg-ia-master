-- SPEC-222 (privacidade/LGPD): minimização Google Play + índices de retenção.
-- R4: purchase_token só existe enquanto o consume pode ser retentado. Ao chegar em
-- estado terminal ('consumed'/'consume_failed') ou na exclusão da conta, vira NULL;
-- token_sha256 (único) segue garantindo idempotência. google_state fica no
-- subconjunto financeiro.
alter table app.google_play_purchases alter column purchase_token drop not null;

create or replace function app.minimize_google_state(p_state jsonb) returns jsonb
language sql immutable set search_path = '' as $$
  select coalesce(pg_catalog.jsonb_object_agg(e.key, e.value), '{}'::jsonb)
  from pg_catalog.jsonb_each(coalesce(p_state, '{}'::jsonb)) as e(key, value)
  where e.key in ('purchase_state', 'consumption_state', 'purchase_type', 'quantity')
$$;

create or replace function app.protect_google_play_purchase() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'google play purchases retained' using errcode = '55000';
  end if;
  if (new.purchase_id,new.owner_id,new.product_id,new.sku_id,new.pricing_version_id,
      new.token_sha256,new.order_id,new.created_at)
     is distinct from
     (old.purchase_id,old.owner_id,old.product_id,old.sku_id,old.pricing_version_id,
      old.token_sha256,old.order_id,old.created_at)
     or (old.state in ('consumed','consume_failed') and new.state <> old.state) then
    raise exception 'google play purchase authority immutable' using errcode = '55000';
  end if;
  -- The token may only be cleared, never replaced or restored.
  if new.purchase_token is not null and new.purchase_token is distinct from old.purchase_token then
    raise exception 'google play purchase authority immutable' using errcode = '55000';
  end if;
  if new.state in ('consumed','consume_failed') then
    new.purchase_token := null;
    new.google_state := app.minimize_google_state(new.google_state);
  end if;
  return new;
end;
$$;
revoke all on function app.protect_google_play_purchase() from public, anon, authenticated;
revoke all on function app.minimize_google_state(jsonb) from public, anon, authenticated;

-- Backfill: terminal rows and rows of already-deleted owners. The account write
-- fence would deny the latter, so it is suspended only for this statement.
alter table app.google_play_purchases disable trigger account_write_fence;
update app.google_play_purchases
   set purchase_token = null, google_state = app.minimize_google_state(google_state)
 where purchase_token is not null
   and (state in ('consumed','consume_failed')
        or owner_id in (select d.owner_id from app.account_deletions d));
alter table app.google_play_purchases enable trigger account_write_fence;

-- R7: purge por data no cron /internal/cron/operations (services/retention.py).
create index if not exists operations_terminal_finished_idx on app.operations (finished_at)
  where status in ('completed','failed','abandoned');
create index if not exists jobs_terminal_updated_idx on app.jobs (updated_at)
  where status in ('succeeded','dead','cancelled');
create index if not exists usage_events_created_idx on app.usage_events (created_at);
create index if not exists account_deletions_completed_idx on app.account_deletions (completed_at)
  where status = 'deleted';

select app.grant_runtime_access();
