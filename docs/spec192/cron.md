# SPEC-192 — Cron interno (jobs, exclusão de contas, operações)

Em serverless (Vercel) não há worker contínuo. O Supabase `pg_cron` + `pg_net`
chama endpoints internos que drenam trabalho com orçamento de tempo. Leases,
heartbeat e fencing do `JobQueue` Postgres são os mesmos do worker local.

## Contrato

| Endpoint | Frequência | Faz |
|---|---|---|
| `POST /internal/cron/jobs` | 1 min | `workers.drain.drain_jobs` (1 job por `run_once`, para no prazo) |
| `POST /internal/cron/account-deletions` | 5 min | `run_recovery_batch` (modo batch explícito, `FOR UPDATE SKIP LOCKED`, max 10) |
| `POST /internal/cron/operations` | 5 min | `recover_expired` (libera operações com lease vencida, max 50) |

- Auth: `Authorization: Bearer <RPG_CRON_SECRET>` (comparação `hmac.compare_digest`).
  Segredo ausente ou < 32 chars -> **503** (fail-closed); header errado -> **401**.
  Sem cookies/CSRF; fora do limitador por usuário.
- Env: `RPG_CRON_SECRET`, `RPG_CRON_BUDGET_SECONDS` (default 50),
  `RPG_CRON_MAX_DURATION_SECONDS` (default 60 = `maxDuration` da função; orçamento
  efetivo = min(budget, maxDuration - 5)), `RPG_CRON_MAX_JOBS` (default 50).
  `account-deletions` exige `RPG_RUNTIME_PROFILE=hosted-supabase`.
- Resposta: só contagens/durações, ex. `{"ok":true,"processed":3,"stopped_reason":"empty","duration_s":1.2}`.
  Falha de tarefa -> HTTP 500: exceção = `cron_task_failed`; falhas contadas (`failed>0`, ex. exclusão de conta)
  = o mesmo corpo só-contagens com `"ok":false` e HTTP 500. Em ambos o pg_net registra status != 2xx.
  401/503 (auth/config) não mudam.
- Um job nunca é iniciado com menos de 15 s de orçamento restante; um job já iniciado
  não é interrompido (a lease/heartbeat protege; se estourar, o próximo worker reassume pelo fence).

## Tempos (F5)
Três limites distintos, mantê-los em ordem: `timeout_milliseconds` do pg_net (58000 ms) < `maxDuration` da função
(vercel.json: 300 s) e `RPG_CRON_MAX_DURATION_SECONDS` (default 60) é o teto *lógico* que o código assume para
calcular o orçamento (`min(RPG_CRON_BUDGET_SECONDS, MAX_DURATION - 5)`). Como o pg_net desiste em 58 s (a requisição
registra `timed_out`, mas a função na Vercel segue até terminar ou 300 s), o orçamento efetivo tem de ficar abaixo de
58 s: o default 50 s cumpre. Se subir `RPG_CRON_MAX_DURATION_SECONDS`/`BUDGET`, suba junto o timeout do pg_net em
`scripts/staging/schedule_cron.py`; `maxDuration` 300 s só serve de rede de segurança.

## Alertas

Cada execução emite o log estruturado `rpg.cron` (`task`, `outcome`, `consecutive_failures`,
`duration_s`). `consecutive_failures >= 3` sobe para nível ERROR. O contador é por instância
(best-effort em serverless); o sinal durável é `net._http_response` (status != 2xx), consultável
com o SQL abaixo — alerte nele.

### Watchdog durável (pg_cron, a cada 15 min)
Como a Vercel não alcança regras Prometheus, o alerta vive no Postgres. Cada job agendado registra o id da requisição
pg_net em `app.cron_requests` (o `net._http_response` não tem URL, então o id é a ligação). A função
`app.cron_health_check()` (migration `20261015125000_cron_health.sql`, RLS forçada, sem grants) olha, por job, as 3
últimas requisições resolvidas (> 90 s) e, se todas forem não-2xx ou `status_code` nulo (timeout), insere uma linha em
`app.cron_health_alerts` (no máximo 1 por job/hora) e emite `RAISE WARNING` no log do Postgres. Agendado idempotentemente
por `scripts/staging/schedule_cron.py` como `rpg-cron-health`. Consulta: `select * from app.cron_health_alerts order by
detected_at desc;`. Linhas de `cron_requests` > 2 dias e alertas > 90 dias são podados.

## Agendamento (pg_cron + pg_net, idempotente)

```sql
create extension if not exists pg_cron;
create extension if not exists pg_net;

-- uma vez (valor = mesmo RPG_CRON_SECRET do Vercel):
-- select vault.create_secret('<RPG_CRON_SECRET>', 'rpg_cron_secret');

do $$
declare
  base text := 'https://<STAGING_BASE_URL>';  -- sem barra final
  j record;
begin
  for j in select * from (values
    ('rpg-cron-jobs',              '* * * * *',   '/internal/cron/jobs'),
    ('rpg-cron-account-deletions', '*/5 * * * *', '/internal/cron/account-deletions'),
    ('rpg-cron-operations',        '*/5 * * * *', '/internal/cron/operations')
  ) as t(name, schedule, path)
  loop
    -- unschedule-safe: ignora job inexistente
    perform cron.unschedule(jobid) from cron.job where jobname = j.name;
    perform cron.schedule(j.name, j.schedule, format($f$
      select net.http_post(
        url := %L,
        headers := jsonb_build_object(
          'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'rpg_cron_secret'),
          'Content-Type', 'application/json'),
        body := '{}'::jsonb,
        timeout_milliseconds := 58000)
    $f$, base || j.path));
  end loop;
end $$;

-- Falhas recentes (alerta):
select id, status_code, created from net._http_response
where status_code is null or status_code >= 300  -- falha de tarefa também chega como HTTP 500
order by created desc limit 20;
```

Rodar `drain` a cada minuto com orçamento de 50 s evita sobreposição longa; se houver
sobreposição, é seguro: leases por job e `SKIP LOCKED` impedem processamento duplo.
