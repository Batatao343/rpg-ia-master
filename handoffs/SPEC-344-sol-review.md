# SPEC-344 — revisão sol (review)

> **Veredito:** APPROVED_WITH_FOLLOWUPS
> **Revisor:** Sol (segurança) · **Data:** 2026-10-27 · **Commit revisado:** `2f4fb676`

## Escopo

`git diff main...HEAD`: agents/loot.py, agents/combat.py, corpus.json, tests/test_spec344_prompt_guard.py, web/tests/mdLite.test.mjs, spec. Nada em evals/, services/economy ou conflict_orchestrator.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | tests/test_spec344_prompt_guard.py (loot R6) | Asserções de inventário são frouxas (`corda <= 2`, `q < 999`); não provam que compra inacessível deixa inventário/ouro exatamente iguais. | Follow-up: para itens fora do estoque/sem ouro, assertar `player` igual ao anterior. |
| P2-2 | P2 | agents/combat.py (_narrate) | Entrada embrulhada aparece no system e de novo na HumanMessage (duas tags, não aninhadas, miolo escapado). Sem quebra. | Opcional: manter só no Human. |

Verificações: (1) os 4 sites delimitam e levam PLAYER_INPUT_RULE (provado por testes com Recorder); (2) wrap só ocorre na montagem da mensagem ao LLM; `text`/`intent` crus seguem para economy, resolução de item e busca de alvo, sem regressão; (3) `unwrap_player_input(item_ref)[:60]` presente, MockLLM já desembrulha, testes antigos verdes; (4) corpus JSON válido, kind filtrado, teste de ≥20 casos passa; (5) testes R6 usam LLM obediente e rodam loot_node/_bounded_enemy_groups/parser reais; (6) mdLite cobre img onerror, javascript:, script e &; (7) sem tag dupla aninhada.

## Correções aplicadas

Nenhuma necessária.

## Pendências

P2-1 e P2-2 acima (não bloqueiam).

## Comandos rodados

```text
pytest (6 arquivos, serial) → 107 passed, 0 failed
node --test web/tests/mdLite.test.mjs → 2 pass, 0 fail
```
