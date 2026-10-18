# SPEC-271 — Apagar exports mortos do cliente web

> **Status:** `done` · **Revisão independente 2026-10-18:** SAFE WITH CHANGES (`currentPurchaseAdapter` sai da lista; ver §8)
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
| `AbilityRef` | `web/src/types.ts:8` | ~5 |

Todas as dependências npm estão em uso (inclusive `@capacitor/core`, peer obrigatório).

## 2. Requisitos

- **R1** — Reconfirmar com `git grep -nw <nome> -- web` e apagar os **três** restantes.
  *(revisão)* `currentPurchaseAdapter` **fica**: é a única porta de entrada de
  `selectPurchaseAdapter`/`AndroidPlayAdapter` no app (SPEC-194 entregou os adapters; a
  `AccountScreen` ainda chama o checkout Stripe direto). Ligar a compra nativa na UI é trabalho da
  SPEC-198 (`in-progress`), mesmo caso do `wallet_spend_scope` que o relatório preserva. Apagar
  também deixaria `import { clientPlatform }` (`purchases/index.ts:1`) órfão, e o
  `noUnusedLocals: true` de `web/tsconfig.json:16` quebraria o build.
- **R2** — Não mexer nos ~80 exports com uma referência só (podem ser usados no próprio
  arquivo); tirar o `export` desses é ruído, não ganho.

## 5. Critérios de aceite

- [ ] `cd web && npm test && npm run build` (o `tsc -b` acusa uso remanescente)
- [ ] `npm run test:e2e` verde

## 7. Riscos & compatibilidade

Risco **nulo**. Rollback: `git revert`.

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: SAFE WITH CHANGES.**

- `chronicleExportUrl`: a UI monta a URL inline (`Hud.tsx:304`); seguro.
- `LEGACY_ATTACK`, `AbilityRef`: zero referências em `web/`, `scripts/`, `evals/`; seguros.
- **`currentPurchaseAdapter` sai da lista**: é o ponto de entrada planejado da compra nativa (SPEC-198
  `in-progress`); apagá-lo também deixa `clientPlatform` importado e não usado, e `noUnusedLocals`
  quebra o `tsc -b`.
