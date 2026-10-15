# SPEC-198 — Publicação Google Play

> **Status:** `draft`
> **Depende de:** SPEC-197 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: checklist/store metadata/Data Safety draft; release técnico revisado por Sol e publicação é humana.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-198` é source of truth para subtarefas/review focus

## Objetivo

Levar o Android validado para Play Console/internal/closed testing e, quando aprovado pelo usuário, produção, sem transformar requisitos de loja em bloqueio das specs técnicas anteriores.

## Requisitos

- **R1** — usuário define/valida nome público, package ID definitivo, developer account e support/privacy URLs antes do primeiro upload definitivo.
- **R2** — enrollment/taxa Google confirmados e pricing recalculado.
- **R3** — Data Safety/permissions coerentes com áudio transitório, auth e pagamentos.
- **R4** — billing products configurados; license testing e internal/closed track passam.
- **R5** — AAB assinado por processo seguro; chave fora do repo.
- **R6** — store screenshots/text podem usar working copy, mas publicação final é humana.
- **R7** — produção só depois de wallet sync/refund/purchase recovery em device real.

### Fora de escopo

App Store/iOS; ASO/marketing.

## Plano

1. `EXTERNAL_ACTION_APPROVAL_REQUIRED`.
2. Criar/configurar Play app e products.
3. Internal testing + license testers.
4. Closed testing se exigido pela conta/política.
5. Release checklist e aprovação humana.
6. Publicar somente quando usuário mandar.

## Critérios de aceite

- [ ] package ID definitivo aprovado antes de ficar imutável na loja.
- [ ] compras reais/teste verificadas server-side.
- [ ] wallet web↔Android sincroniza.
- [ ] app não expõe Stripe link no v1.
- [ ] Data Safety/Privacy/Support preenchidos.
- [ ] publicação explicitamente aprovada pelo usuário.

## Gates / evidência

Play Console artifacts + device smoke + final human approval.

## Gate de fechamento

- [ ] Play Console/account/package ID definitivo existem e foram aprovados pelo usuário antes do primeiro upload irreversível;
- [ ] internal/closed testing executa compra consumível real/test-license -> server verification -> wallet -> consume -> recompra -> recovery após restart;
- [ ] revocation/refund de teste chega à reconciliação quando suporte da conta permitir;
- [ ] Data Safety/Privacy/Support refletem implementação real de áudio temporário, dados de conta e pagamentos;
- [ ] signed AAB e signing secrets ficam fora do repo/harness logs;
- [ ] Sol review independente aprova release evidence;
- [ ] publicação em produção só acontece após comando/aprovação humana explícita.
