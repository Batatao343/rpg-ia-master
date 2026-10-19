-- SPEC-256 R3. Consecutive-failure counter per cron task, shared across serverless instances.
-- Count-only data (task name is a closed set; no owner ids). Idempotent. Backend-only access
-- (RLS enable+force, no grants to anon/authenticated/rpg_api); the cron runs on the admin pool.
create table if not exists app.cron_run_state (
  task text primary key check (length(task) between 1 and 80),
  consecutive_failures int not null default 0 check (consecutive_failures >= 0),
  last_outcome text not null check (last_outcome in ('ok', 'failed')),
  updated_at timestamptz not null default now()
);
alter table app.cron_run_state enable row level security;
alter table app.cron_run_state force row level security;
revoke all on app.cron_run_state from public, anon, authenticated, rpg_api;
