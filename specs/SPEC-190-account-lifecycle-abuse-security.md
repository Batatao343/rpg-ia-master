# SPEC-190 — Lifecycle de conta, recuperação e antiabuso

> **Status:** `approved`
> **Depende de:** SPEC-189 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: data-map e checklist de lifecycle; auth/delete/retention ficam com Sol.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-190` é source of truth para subtarefas/review focus

## Objetivo

Fechar lacunas de conta pública antes do cloud beta: email verification/reset, CAPTCHA/limits, delete account e política de retenção financeira.

## Requisitos

- **R1** — confirmação de email configurável e password reset completo.
- **R2** — CAPTCHA/Turnstile seam em signup/reset e rate limits apropriados.
- **R3** — account deletion revoga sessão, remove gameplay/private data/blob/memory e aplica política separada ao ledger transacional obrigatório.
- **R4** — nenhum free credit.
- **R5** — endpoints sensíveis validam sessão recente quando necessário.
- **R6** — UI Account inclui delete/export/support placeholders.
- **R7** — docs de retenção sem alegar compliance legal não revisado.

### Fora de escopo

MFA obrigatório para jogadores; marketing emails.

## Plano

1. Mapear Supabase Auth flows atuais.
2. Implementar backend/UI sem expor bearer.
3. Account-delete idempotente com jobs/blobs.
4. Abuse tests e auth local.
5. Sol revisa deletion/financial retention boundary.

## Critérios de aceite

- [ ] reset/verify funcionam local/staging config.
- [ ] usuário apagado não continua autenticado.
- [ ] dados privados removidos conforme política; ledger não é corrompido.
- [ ] signup não recebe Estilhas.

## Gates / evidência

Auth local/integration + RLS + browser.

## Gate de fechamento

- [ ] verify/reset não revela existência de e-mail por diferença de mensagem contratual;
- [ ] rate limit/CAPTCHA seam pode ser habilitado sem alterar frontend contract e falha fechado no hosted quando configurado required;
- [ ] delete account é idempotente, revoga sessões primeiro, cancela jobs, remove private gameplay/blob/memory e preserva somente registros financeiros definidos pela policy;
- [ ] export/delete de A nunca toca B;
- [ ] nenhuma rota de signup cria wallet credit gratuito;
- [ ] review Sol independente aprova auth/delete/retention trust boundary.
