-- SPEC-256 R3. Consecutive-failure counter per cron task, shared across serverless instances.
-- Count-only data (task name is a closed set; no owner ids). Idempotent. Backend-only access
-- (RLS enable+force, no grants to anon/authenticated/rpg_api); the cron runs on the admin pool,
-- which gets the `admin_all` policy via app.grant_runtime_access() at the end.
create table if not exists app.cron_run_state (
  task text primary key check (length(task) between 1 and 80),
  consecutive_failures int not null default 0 check (consecutive_failures >= 0),
  last_outcome text not null check (last_outcome in ('ok', 'failed')),
  updated_at timestamptz not null default now()
);
alter table app.cron_run_state enable row level security;
alter table app.cron_run_state force row level security;
revoke all on app.cron_run_state from public, anon, authenticated, rpg_api;

-- rpg_admin/rpg_runtime sao NOBYPASSRLS: cria as policies admin_all/runtime_all (como as migrations vizinhas).
select app.grant_runtime_access();
