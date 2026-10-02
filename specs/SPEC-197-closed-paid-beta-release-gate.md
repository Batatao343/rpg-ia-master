# SPEC-197 — Closed paid beta — release gate

> **Status:** `approved`
> **Depende de:** SPEC-196 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: evidence bundle/checklist e relatórios; decisão técnica de release é revisada por Sol e aprovada pelo humano.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-197` é source of truth para subtarefas/review focus

## Objetivo

Preparar o beta pago pequeno sem publicação ampla, com staging→produção, políticas mínimas e checklists reproduzíveis.

## Requisitos

- **R1** — criar produção Supabase/Vercel somente com aprovação explícita.
- **R2** — Stripe test→live separado; SKUs ainda podem ficar somente web até Play internal testing.
- **R3** — Privacy/Terms/refund/support URLs/placeholders resolvidos antes de público externo.
- **R4** — custom SMTP/email confirmation ou risco aceito explicitamente.
- **R5** — backup/restore produção e rollback testados.
- **R6** — smoke: signup/login, buy web, wallet sync, text turn, voice turn, image quote/generate, logout/delete.
- **R7** — budget alerts e daily spend cap.
- **R8** — sem long-run automático.

### Fora de escopo

Marketing/public launch; iOS.

## Plano

1. Release checklist automatizado onde possível.
2. Produção via promotion, não rebuild manual diferente.
3. Stripe live small-value smoke aprovado.
4. 2-user isolation.
5. Incident/rollback drill.

## Critérios de aceite

- [ ] zero P0/P1 aberto.
- [ ] pagamentos/ledger reconciliam.
- [ ] recovery/delete/privacy/support mínimos existem.
- [ ] budget kill switches ativos.
- [ ] usuário aprova abrir beta.

## Gates / evidência

Checklist + evidence bundle por SHA/env; Luna pode compilar relatório, Terra corrige plumbing.

## Gate de fechamento

- [ ] SPEC-176..196 `done` e reviews obrigatórios aprovados;
- [ ] branch/commit candidato tem CI obrigatório verde e zero drift de migrations/locks;
- [ ] smoke de dois usuários cobre isolamento, compra web test/live autorizada, wallet, texto, voz, image quote, refresh/logout/delete;
- [ ] produção tem budget alert/kill switch e runbook de rollback/incident;
- [ ] Stripe live small-value smoke só ocorre após approval humano e valor explícito;
- [ ] zero P0/P1 aberto; P2 conhecido precisa de risk acceptance documentado;
- [ ] review Sol independente retorna release recommendation e o usuário dá aprovação final para abrir beta.
