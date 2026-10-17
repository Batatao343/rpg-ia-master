-- SPEC-219 R3: cota diaria de turnos/LLM por owner (dia UTC). Contador barato, sem conteudo de jogo.
-- Idempotente. Acesso so pelo backend (RLS enable+force, sem grants a anon/authenticated/rpg_api);
-- o runtime recebe a policy `runtime_all` via app.grant_runtime_access() no fim.
create table if not exists app.owner_daily_counters (
  owner_id uuid not null,
  day date not null,
  class text not null check (class in ('turn','llm_aux')),
  count integer not null default 0 check (count >= 0),
  updated_at timestamptz not null default now(),
  primary key (owner_id, day, class)
);
create index if not exists owner_daily_counters_day_idx on app.owner_daily_counters (day);

alter table app.owner_daily_counters enable row level security;
alter table app.owner_daily_counters force row level security;
revoke all on app.owner_daily_counters from public, anon, authenticated, rpg_api;

-- Incrementa so enquanto count < p_max (tentativa recusada NAO consome). Atomica pelo lock da linha:
-- duas conexoes concorrentes nunca ultrapassam p_max. Retorna (permitido, usado).
create or replace function app.bump_daily_counter(p_owner uuid, p_class text, p_max integer)
returns table(allowed boolean, used integer)
language plpgsql security invoker set search_path = '' as $$
declare v integer;
begin
  if p_max is null or p_max < 1 then
    raise exception 'p_max must be >= 1';
  end if;
  insert into app.owner_daily_counters as c (owner_id, day, class, count)
  values (p_owner, (now() at time zone 'utc')::date, p_class, 1)
  on conflict (owner_id, day, class)
  do update set count = c.count + 1, updated_at = now() where c.count < p_max
  returning c.count into v;
  if v is null then
    select c.count into v from app.owner_daily_counters c
     where c.owner_id = p_owner and c.day = (now() at time zone 'utc')::date and c.class = p_class;
    return query select false, coalesce(v, p_max);
  end if;
  return query select true, v;
end $$;
revoke all on function app.bump_daily_counter(uuid, text, integer) from public, anon, authenticated, rpg_api;

select app.grant_runtime_access();
