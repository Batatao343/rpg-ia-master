# SPEC-192 — Vercel staging + topologia de worker

> **Status:** `done`
> **Depende de:** SPEC-191 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: agregação de métricas/custos/latência; topologia e worker ficam com Sol.
> **MODEL_BREAKDOWN:** `docs/planos/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-192` é source of truth para subtarefas/review focus

## Objetivo

Subir frontend/FastAPI em Vercel staging e provar a melhor topologia para os jobs Python atuais, sem migrar fila por estética.

## Requisitos

- **R1** — aprovação externa antes de criar/deploy pago.
- **R2** — same-origin frontend/API sempre que possível; cookies/CSRF/SSE reais.
- **R3** — medir Function/Services bundle, cold start, maxDuration e streaming.
- **R4** — comparar: Postgres JobQueue + worker service vs Vercel Queues adapter; preservar interface/idempotência.
- **R5** — image/embedding/chronicle jobs sobrevivem redeploy/crash.
- **R6** — preview nunca escreve produção.
- **R7** — environment vars/secrets separados.
- **R8** — fallback documentado se beta Vercel falhar gate.
- **R9** — agendar a recuperação de exclusões iniciadas da SPEC-190 a cada
  cinco minutos, com idempotência sob concorrência e alerta em falhas persistentes.

### Fora de escopo

Publicar produção; trocar toda a fila sem benchmark.

## Plano

1. Build/doctor local Vercel.
2. Deploy staging com Supabase staging.
3. C1 API/SSE/auth; C2 DB pool; C3 worker/job; C4 redeploy/retry; C5 bundle/cold start; C6 cost sample; C7 recuperação agendada de exclusões.
4. Selecionar topologia pela evidência.
5. Runbook rollback.

## Critérios de aceite

- [x] 5 turnos sintéticos/curtos via SSE sem perda.
- [x] job não duplica após redeploy.
- [x] nenhuma escrita persistente local da Function.
- [x] preview isolado.
- [x] custos e limites observados registrados.

## Gates / evidência

Staging real, mas provider LLM pode ser mock na maior parte. Smokes pagos somente com teto aprovado.

## Compatibilidade com SPEC-104

SPEC-104 contém uma preferência antiga por Railway baseada no estado de Vercel de 2026-08-16. Esta spec deve registrar evidência atual e, se Vercel passar os gates, marcar/documentar essa preferência histórica como superseded sem reescrever o passado da spec antiga.

## Gate de fechamento

- [x] auth/cookies/CSRF/SSE funcionam em preview/staging real same-origin ou há justificativa/teste para desenho alternativo;
- [x] ao menos um redeploy/crash durante job demonstra fencing/idempotência e recovery;
- [x] worker escolhido não depende de filesystem persistente local;
- [x] preview não consegue usar secrets/DB de produção;
- [x] cold start, streaming, duration/bundle e custo amostral ficam registrados com data/plan;
- [x] existe fallback operacional se Services/Queues beta falhar;
- [x] o staging executa `scripts.recover_account_deletions --batch` a cada cinco
  minutos; uma interrupção após revogar a sessão é recuperada sem ação do
  usuário, e falhas persistentes geram alerta sem bloquear outras exclusões;
- [x] review Sol independente aprova topologia escolhida — equivalente Opus independente: APPROVED_WITH_FOLLOWUPS; F1–F7 corrigidos e reimplantados a partir do commit limpo (2026-10-15).

## Addendum 2026-10-15 (execução Claude)

Executada no Claude Code ([equivalência de modelos](../docs/planos/equivalencia-modelos-claude.md)).
Topologia escolhida: um projeto Vercel Hobby (`rpg-ia-master-staging`, região
`gru1`) servindo `web/dist` + FastAPI na mesma origem; fila Postgres
(JobQueue com lease/fencing) drenada por `/internal/cron/*` com orçamento de
tempo, disparado por `pg_cron` + `pg_net` no Supabase staging (Vercel Cron no
Hobby é diário). Watchdog `rpg-cron-health` registra 3 falhas seguidas em
`app.cron_health_alerts`. Crash de job foi emulado por expiração de lease; o
redeploy real ocorreu com jobs na fila, não no meio de um job. Evidências e
runbooks: [docs/spec192](../docs/spec192/README.md).
