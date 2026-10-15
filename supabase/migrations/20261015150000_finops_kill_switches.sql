-- SPEC-196 R4: persistent, auditable, backend-only kill switches.
-- A missing row means "enabled" (fail-safe). Rows only turn features OFF/ON explicitly.
create table app.kill_switches (
  key text primary key check (key ~
    '^(image_generation|stt_fallback_expensive|model:[A-Za-z0-9._/-]{1,200}|decision_backend:[a-z0-9_]{1,40}|new_purchases(:[a-z_]{1,40})?)$'),
  enabled boolean not null,
  reason text not null check (length(reason) between 1 and 500),
  actor_id text not null check (length(actor_id) between 1 and 120),
  updated_at timestamptz not null default now()
);
create table app.kill_switch_audit (
  audit_id bigint generated always as identity primary key,
  key text not null,
  previous_enabled boolean,
  enabled boolean not null,
  reason text not null check (length(reason) between 1 and 500),
  actor_id text not null check (length(actor_id) between 1 and 120),
  created_at timestamptz not null default now()
);
create trigger kill_switch_audit_immutable before update or delete on app.kill_switch_audit
  for each row execute function app.reject_wallet_fact_mutation();

-- Only path to change a switch: state + audit row in the same transaction.
create function app.set_kill_switch(p_key text, p_enabled boolean, p_actor text, p_reason text)
returns void language plpgsql security definer set search_path = '' as $$
declare prev boolean;
begin
  select enabled into prev from app.kill_switches where key = p_key for update;
  insert into app.kill_switches(key, enabled, reason, actor_id, updated_at)
    values (p_key, p_enabled, p_reason, p_actor, now())
    on conflict (key) do update set enabled = excluded.enabled, reason = excluded.reason,
      actor_id = excluded.actor_id, updated_at = excluded.updated_at;
  insert into app.kill_switch_audit(key, previous_enabled, enabled, reason, actor_id)
    values (p_key, prev, p_enabled, p_reason, p_actor);
end;
$$;

alter table app.kill_switches enable row level security;
alter table app.kill_switches force row level security;
alter table app.kill_switch_audit enable row level security;
alter table app.kill_switch_audit force row level security;
revoke all on app.kill_switches, app.kill_switch_audit from public, anon, authenticated, rpg_api;
revoke all on function app.set_kill_switch(text, boolean, text, text)
  from public, anon, authenticated, rpg_api;
