# SPEC-190 — Lifecycle de conta, recuperação e antiabuso

> **Status:** `done`
> **Depende de:** SPEC-189 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: data-map e checklist de lifecycle; auth/delete/retention ficam com Sol.
> **MODEL_BREAKDOWN:** `docs/planos/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-190` é source of truth para subtarefas/review focus

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

- [x] reset/verify funcionam na stack local GoTrue; configuração hosted será comprovada na SPEC-191.
- [x] usuário apagado não continua autenticado.
- [x] dados privados removidos conforme política; ledger não é corrompido.
- [x] signup não recebe Estilhas.

## Gates / evidência

Auth local/integration + RLS + browser.

## Gate de fechamento

- [x] verify/reset não revela existência de e-mail por diferença de mensagem contratual;
- [x] rate limit/CAPTCHA seam pode ser habilitado sem alterar frontend contract e falha fechado no hosted quando configurado required;
- [x] delete account é idempotente, revoga sessões primeiro, cancela jobs, remove private gameplay/blob/memory e preserva somente registros financeiros definidos pela policy;
- [x] export/delete de A nunca toca B;
- [x] nenhuma rota de signup cria wallet credit gratuito;
- [x] review Sol independente aprova auth/delete/retention trust boundary.

**Fechamento (13/10/2026):** implementação `9453a8e`; revisão independente Sol High **APPROVED** em `handoffs/SPEC-190-SOL-independent-review.md`. Gate Python completo: 2.159 passed, 126 skipped, 15 deselected; Chromium: 53 passed, 1 skipped; Node: 18 passed; build, Ruff, lint de conteúdo e Project Index verdes. O smoke real de Auth foi local com GoTrue e PostgreSQL; configuração hosted, CAPTCHA nativo e scheduler são gates das SPEC-191/192. Evidência e limites em `docs/spec190/README.md`.
