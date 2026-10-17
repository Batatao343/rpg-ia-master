-- SPEC-236 R1/R2/R10. Idempotent: safe to apply more than once.
-- A provider attempt that FAILED without any usage reading is an auditable fact, not spend:
-- it is recorded with cost_usd=0 and cost_basis='failed_no_usage' and is excluded from every
-- spend sum (daily cap, FinOps, turn cost) through counts_as_spend=false.
alter table app.usage_events
  add column if not exists counts_as_spend boolean not null default true;

alter table app.usage_events drop constraint if exists usage_events_cost_basis_check;
alter table app.usage_events add constraint usage_events_cost_basis_check check (cost_basis in
  ('provider_reported', 'token_priced', 'rate_card', 'estimated',
   'failed_no_usage', 'definitive_no_charge'));

-- A no-spend basis can never carry a cost nor be summed as spend.
alter table app.usage_events drop constraint if exists usage_events_no_spend_basis_check;
alter table app.usage_events add constraint usage_events_no_spend_basis_check check (
  cost_basis not in ('failed_no_usage', 'definitive_no_charge')
  or (counts_as_spend = false and cost_usd = 0));

-- Historical phantom cost: before SPEC-236 a failed attempt without usage was persisted as a
-- US$ 1.00 conservative estimate. Keep the row (append-only facts), only take it out of spend.
-- Owners under account deletion are skipped (their rows are being erased; the write fence
-- would reject the update).
update app.usage_events u set counts_as_spend = false
 where u.pricing_version = 'unknown-conservative-v1'
   and u.outcome not in ('success', 'response', 'ok', 'completed',
                         'invalid_structured', 'invalid_response')
   and coalesce(u.input_units, u.output_units, u.audio_units, u.image_units) is null
   and u.counts_as_spend
   and not exists (select 1 from app.account_deletions d where d.owner_id = u.owner_id);

create index if not exists usage_events_spend_created_idx
  on app.usage_events (created_at) where counts_as_spend;

-- R10: a provider-reported cost above the confirmed ceiling is capped at the ceiling and the
-- excess is recorded once, instead of failing settlement forever.
alter table app.wallet_reservations
  add column if not exists financial_anomaly_milli bigint not null default 0;
alter table app.wallet_reservations drop constraint if exists wallet_reservations_anomaly_check;
alter table app.wallet_reservations add constraint wallet_reservations_anomaly_check
  check (financial_anomaly_milli >= 0);

-- R4: the recovery sweep scans open reservations by age.
create index if not exists wallet_reservations_open_created_idx
  on app.wallet_reservations (created_at)
  where status in ('reserved', 'effect_started', 'uncertain');
