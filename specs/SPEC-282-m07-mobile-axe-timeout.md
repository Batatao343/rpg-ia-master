# SPEC-282 — Timeout das jornadas mobile (M07 axe, M02/M06)

> **Status:** `done` (aprovada pelo dono em 19/10: "tudo que não exige ação externa dele")
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Origem:** achado pós-SPEC-216: M07 mobile-single-pane com timeout (também na main)
> **Depende de:** —
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_REQUIRED:** `false` — só configuração de teste
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## Achado
`web/e2e/mobile-single-pane.spec.ts` M07 dava timeout na analise axe nas duas viewports; M02/M06 falhavam esporadicamente.

## Causa real
Nao e axe lento nem DOM grande nem animacao: sozinho, M07 passa em ~12 s (7 analises axe, <1 s cada; M02 sem axe leva 9,5 s) e nao ha
animacao rodando (o proprio teste afirma 0). O timeout default de 30 s por teste estoura quando a CPU esta disputada (runs paralelos de
outros agentes: o arquivo inteiro levou 2,7 min em vez de 56 s). Sem defeito de a11y/performance do app.

## Correcao
`test.describe.configure({ timeout: 90_000 })` no arquivo. Verificacao de a11y inalterada (serious/critical continuam bloqueando).
Nenhum arquivo protegido tocado.

## Criterios de aceite
- [x] M01-M07 x 2 viewports verdes em repeticoes (ver hand-back).
