# SPEC-192 — Vercel staging + topologia de worker

> **Status:** `draft`
> **Depende de:** SPEC-191 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: agregação de métricas/custos/latência; topologia e worker ficam com Sol.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-192` é source of truth para subtarefas/review focus

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

### Fora de escopo

Publicar produção; trocar toda a fila sem benchmark.

## Plano

1. Build/doctor local Vercel.
2. Deploy staging com Supabase staging.
3. C1 API/SSE/auth; C2 DB pool; C3 worker/job; C4 redeploy/retry; C5 bundle/cold start; C6 cost sample.
4. Selecionar topologia pela evidência.
5. Runbook rollback.

## Critérios de aceite

- [ ] 5 turnos sintéticos/curtos via SSE sem perda.
- [ ] job não duplica após redeploy.
- [ ] nenhuma escrita persistente local da Function.
- [ ] preview isolado.
- [ ] custos e limites observados registrados.

## Gates / evidência

Staging real, mas provider LLM pode ser mock na maior parte. Smokes pagos somente com teto aprovado.

## Compatibilidade com SPEC-104

SPEC-104 contém uma preferência antiga por Railway baseada no estado de Vercel de 2026-08-16. Esta spec deve registrar evidência atual e, se Vercel passar os gates, marcar/documentar essa preferência histórica como superseded sem reescrever o passado da spec antiga.

## Gate de fechamento

- [ ] auth/cookies/CSRF/SSE funcionam em preview/staging real same-origin ou há justificativa/teste para desenho alternativo;
- [ ] ao menos um redeploy/crash durante job demonstra fencing/idempotência e recovery;
- [ ] worker escolhido não depende de filesystem persistente local;
- [ ] preview não consegue usar secrets/DB de produção;
- [ ] cold start, streaming, duration/bundle e custo amostral ficam registrados com data/plan;
- [ ] existe fallback operacional se Services/Queues beta falhar;
- [ ] review Sol independente aprova topologia escolhida.
