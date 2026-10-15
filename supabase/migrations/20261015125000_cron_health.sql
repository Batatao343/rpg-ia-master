-- SPEC-192 F1. Durable cron alerting without an external scraper (Vercel has no Prometheus).
-- pg_cron jobs log each pg_net request id in app.cron_requests; a 15-minute watchdog
-- (app.cron_health_check) raises a row in app.cron_health_alerts when the last 3 resolved
-- requests of the same job were all non-2xx / timed out. Count-only data, no owner ids.
create table if not exists app.cron_requests (
  request_id bigint primary key,
  job_name text not null check (length(job_name) between 1 and 80),
  created_at timestamptz not null default now()
);
create index if not exists cron_requests_job_created_idx on app.cron_requests (job_name, created_at desc);

create table if not exists app.cron_health_alerts (
  id bigint generated always as identity primary key,
  job_name text not null check (length(job_name) between 1 and 80),
  consecutive_failures int not null check (consecutive_failures >= 3),
  last_status_codes int[] not null,
  detected_at timestamptz not null default now()
);
create index if not exists cron_health_alerts_job_detected_idx on app.cron_health_alerts (job_name, detected_at desc);

alter table app.cron_requests enable row level security;
alter table app.cron_requests force row level security;
alter table app.cron_health_alerts enable row level security;
alter table app.cron_health_alerts force row level security;
revoke all on app.cron_requests from public, anon, authenticated, rpg_api;
revoke all on app.cron_health_alerts from public, anon, authenticated, rpg_api;

create or replace function app.cron_health_check()
returns int language plpgsql security definer set search_path='' as $$
declare
  j record;
  codes int[];
  raised int := 0;
begin
  for j in select distinct job_name from app.cron_requests loop
    select array_agg(coalesce(r.status_code, 0) order by q.created_at desc) into codes
    from (select request_id, created_at from app.cron_requests
          where job_name = j.job_name and created_at < now() - interval '90 seconds'
          order by created_at desc limit 3) q
    join net._http_response r on r.id = q.request_id;
    if codes is not null and array_length(codes, 1) = 3
       and not exists (select 1 from unnest(codes) c where c between 200 and 299)
       and not exists (select 1 from app.cron_health_alerts a
                       where a.job_name = j.job_name and a.detected_at > now() - interval '1 hour') then
      insert into app.cron_health_alerts (job_name, consecutive_failures, last_status_codes)
      values (j.job_name, 3, codes);
      raise warning 'rpg.cron_health job=% consecutive_failures=3 statuses=%', j.job_name, codes;
      raised := raised + 1;
    end if;
  end loop;
  delete from app.cron_requests where created_at < now() - interval '2 days';
  delete from app.cron_health_alerts where detected_at < now() - interval '90 days';
  return raised;
end $$;
revoke all on function app.cron_health_check() from public, anon, authenticated, rpg_api;
