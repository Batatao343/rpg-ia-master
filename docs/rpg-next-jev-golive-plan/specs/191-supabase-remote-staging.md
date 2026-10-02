# SPEC-191 — Supabase remoto de staging

> **Status:** `draft`
> **Depende de:** SPEC-190 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: coleta de evidências de staging/advisors/backup; mudanças de segurança são revisadas por Sol.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-191` é source of truth para subtarefas/review focus

## Objetivo

Criar e certificar um projeto Supabase remoto exclusivo de staging, promovendo migrations/adapters já testados localmente.

## Requisitos

- **R1** — aprovação externa antes de criar projeto/recurso.
- **R2** — staging separado de qualquer projeto existente.
- **R3** — migrations via workflow reproduzível; sem editar schema manualmente como fonte de verdade.
- **R4** — Auth/RLS/pgvector/Storage/backups/config com Security/Performance Advisors.
- **R5** — connection pooler/SSL adequado ao Vercel.
- **R6** — email config de staging; custom SMTP pode ficar release gate.
- **R7** — backup/restore/export portátil comprovado com dados sintéticos.
- **R8** — secrets por ambiente.

### Fora de escopo

Produção; dados reais; importar saves pessoais sem consentimento.

## Plano

1. `EXTERNAL_ACTION_APPROVAL_REQUIRED`.
2. Criar/linkar staging.
3. Aplicar migrations.
4. Rodar RLS/pgvector/storage/auth smoke A/B.
5. Advisors e backup/restore.
6. Registrar custos/config sem secrets.

## Critérios de aceite

- [ ] zero Security Advisor error.
- [ ] A não lê B.
- [ ] signed blobs privados.
- [ ] pooler estável.
- [ ] restore testado.
- [ ] produção continua inexistente.

## Gates / evidência

Evidência cloud com IDs não-secretos, comandos e resultados. Sem long-run.

## Gate de fechamento

- [ ] migrations aplicadas a staging reproduzem schema a partir de zero sem edição manual necessária;
- [ ] dois usuários reais de staging passam matriz A/B em Auth + RLS + Storage + pgvector;
- [ ] Security Advisor: zero findings de severidade error/high não justificados; warnings restantes documentados;
- [ ] pooler/SSL testados pela mesma DSN/config que a SPEC-192 consumirá;
- [ ] backup -> restore em ambiente descartável recupera dados sintéticos e objetos necessários;
- [ ] Sol reviewer aprova evidência antes de avançar para Vercel.
