# SPEC-420 — revisão terra (review)

> **Veredito:** `APPROVED`
> **Revisor:** Sonnet (terra) · **Data:** 2026-11-22 · **Commit revisado:** `24021c4c`

## Escopo

`git diff main...HEAD -- web/` (App.tsx, pendingOperation.ts, pending.test.mjs, turn-preflight.spec.ts, ajustes em critical-journeys F20 e turn-retry). Servidor, `resumeSession`, `useSaves`, `retryTurnInner` não alterados (confirmado no diff). Não rodei e2e completo nem staging.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| 1 | P3 | web/e2e/turn-preflight.spec.ts:81-86 | A spec previa que "eco único após falha" falharia na main com 2 ecos depois da retomada; na main falha já em "0 ecos após a falha" (1 eco). Falha pelo motivo certo (R5), só diferente do roteiro da Etapa 0. | Nenhuma; opcional registrar no hand-back do executor. |
| 2 | P3 | web/src/App.tsx:476-479 | `opId`/`echoId` com `let` fora do try: correto, mas `opId` só serve à guarda do catch; ok. | Nenhuma. |

Sem P1/P2.

Pontos pedidos:
1. `created`: só `true` quando `loadPending` devolveu null na leitura síncrona e o id foi gerado ali (pendingOperation.ts:32-45). Retry ("Tentar de novo", App.tsx:624/653), "Consultar / retomar" (:805), reload, outra aba e troca de partida leem o pending gravado (chave por owner+game) e voltam `created=false`, portanto consultam. `handleAction` só é chamado por esses 3 pontos + envio normal; nenhum repassa `created`. Storage bloqueado: fallback em memória também devolve `false` na 2ª chamada (teste unit).
2. Idempotência: `action_id = operation.operation_id` (App.tsx:486) em stream e fallback; `created` não está em `row` (teste `created is not persisted`); e2e verifica `action_id` do stream = id do pending e reenvio com o mesmo id.
3. Eco: `pushLog` antes de qualquer rede no caminho novo (e2e com consulta pendurada passa; na main falha). Catch externo remove só `echoId` pelo id, com guarda `active()` (fluxo invalidado por `turnToken` não mexe), `!narrativeShown` e pending ainda gravado do mesmo `opId`; recusa definitiva mantém o eco. Retry com stream pendurado: F-3 remove por texto, teste turn-retry acrescentou eco = 1 e passa.
4. Cartas/combate: mesmo `handleAction`; F20 afirma 0 consultas e passa.
5. Vermelho/verde: ver abaixo.
6. App.tsx = 961 linhas (limite 965 da spec, gate 1000); typecheck e lint verdes.

## Evidência verificada

`red_green.sh` é só pytest; usei `git checkout main -- web/src` (e restaurei com `git checkout HEAD -- web/src`), `--workers=1`.

| teste | main (web/src) | branch | veredito |
|---|---|---|---|
| pending.test.mjs (4 novos) | 4 fail (export inexistente) | 11/11 pass | OK |
| turn-preflight: envio novo 0 consultas | FAIL (1 consulta) | pass | OK |
| turn-preflight: eco antes da rede | FAIL (eco 0) | pass | OK |
| turn-preflight: eco único após falha e retomada | FAIL (1 eco após falha) | pass | OK |
| turn-preflight: pending existente consulta 1 vez | pass | pass | OK (controle esperado) |

Também verdes na branch: turn-retry (7), pending-discard (5), turn-wait (20), critical-journeys `-g "F20|F14|F15"` (3).

## Correções aplicadas

Nenhuma necessária.

## Pendências

Smoke §6 em staging (itens 1, 3, 4) continua para o coordenador após o deploy. e2e completo no pouso.

## Comandos rodados

```text
npm run typecheck / npm run lint → verdes
node --test tests/pending.test.mjs → 11 pass (branch); 4 fail (main)
playwright turn-preflight --workers=1 → 4 pass (branch); 3 fail, 1 pass (main)
playwright turn-retry, pending-discard, turn-wait, critical-journeys F20|F14|F15 → todos pass
size_budget.py → sem erro; nenhum servidor deixado rodando
```
