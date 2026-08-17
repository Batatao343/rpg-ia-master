# SPEC — Autoridade da memória e quests verificáveis

> **Status:** `done`
> **Criada:** 2026-08-13 · **Atualizada:** 2026-08-13
> **Depende de:** `objetivo-publico-ciclo-quests`, `continuidade-memoria-morte`

## 1. Contexto & objetivo

Nas duas seeds reais, o ledger global terminou 100% especulativo. Relatos foram
gravados no índice privado do NPC, mas não no ledger auditável. Uma quest chegou
ao alvo, recebeu várias ações explícitas e não concluiu porque dependia de um
`quest_completed` espontâneo da LLM.

## 2. Requisitos

- **R1** — Relato persistido de NPC também entra em `memory_facts` como
  `npc_claim/reported`, sem virar confirmado.
- **R2** — Eventos canônicos continuam confirmados e rollback restaura ambos os
  ledgers de forma transacional.
- **R3** — Inferências especulativas com 20+ turnos são omitidas do contexto
  ativo, mas preservadas no ledger/telemetria para auditoria.
- **R4** — Quest no local-alvo registra ações verificáveis de investigação;
  duas ações distintas deixam `completion_ready`.
- **R5** — `completion_ready` produz evento canônico `quest_completed` em Python;
  recompensa permanece idempotente.

## 3. Design e plano

`quest_log.sync_action_progress`; storyteller aplica progresso antes de retornar.
Archivist espelha `npc_claim`; context builder filtra especulação velha.

## 4. Aceite

- [x] Relato aparece no ledger como `reported`.
- [x] Especulação antiga não entra no prompt.
- [x] Quest exige local + duas ações e conclui uma vez.
- [x] `uv run pytest` verde.

## 5. Riscos

O motor reconhece apenas verbos fechados de investigação e menção à missão;
nenhum texto livre decide recompensa ou fato canônico.

## 6. Evidência

Longrun `20260813-085903-974550`: oito quests criadas, oito concluídas, autoridade
final de memória 100% e zero especulação velha ativa.
