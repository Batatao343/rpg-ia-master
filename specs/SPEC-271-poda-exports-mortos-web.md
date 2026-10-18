# SPEC-271 — Apagar exports mortos do cliente web

> **Status:** `draft`
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** —
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Luna` (≡ Haiku) · **REVIEW_MODEL:** — · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Varredura dos 423 `export` de `web/src` contra `web/src`, `web/tests`, `web/e2e`,
`web/scripts` e configs: quatro nomes têm **zero** referência fora da definição.

| Export | Local | Linhas |
|---|---|---|
| `chronicleExportUrl` | `web/src/api.ts:278` | ~2 |
| `LEGACY_ATTACK` | `web/src/combat/targeting.ts:122` | 1 |
| `currentPurchaseAdapter` | `web/src/purchases/index.ts:23` | ~3 |
| `AbilityRef` | `web/src/types.ts:8` | ~5 |

Todas as dependências npm estão em uso (inclusive `@capacitor/core`, peer obrigatório).

## 2. Requisitos

- **R1** — Reconfirmar com `git grep -nw <nome> -- web` e apagar os quatro.
- **R2** — Não mexer nos ~80 exports com uma referência só (podem ser usados no próprio
  arquivo); tirar o `export` desses é ruído, não ganho.

## 5. Critérios de aceite

- [ ] `cd web && npm test && npm run build` (o `tsc -b` acusa uso remanescente)
- [ ] `npm run test:e2e` verde

## 7. Riscos & compatibilidade

Risco **nulo**. Rollback: `git revert`.
