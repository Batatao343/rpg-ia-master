-- SPEC-196 F7: persisted FinOps evaluations. Vercel has no Prometheus scrape target, so
-- staleness of POST /internal/cron/finops must be checkable via SQL (pg_cron watchdog).
-- Owner-free by construction: only the cron summary + alert kinds/messages are stored.
create table app.finops_evaluations (
  evaluation_id bigint generated always as identity primary key,
  evaluated_at timestamptz not null default now(),
  blocking_alerts integer not null check (blocking_alerts >= 0),
  alert_count integer not null check (alert_count >= 0),
  summary jsonb not null,
  alerts jsonb not null
);
create index finops_evaluations_at_idx on app.finops_evaluations(evaluated_at desc);

alter table app.finops_evaluations enable row level security;
alter table app.finops_evaluations force row level security;
revoke all on app.finops_evaluations from public, anon, authenticated, rpg_api;
