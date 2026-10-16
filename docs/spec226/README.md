# SPEC-226 - Contabilidade de recompensas (evidencia)

Status: `done` (offline). Revisao Sol independente: APPROVED_WITH_FOLLOWUPS -> follow-ups R10/R8/R4 fechados no mesmo WT.

## O que mudou
- R1 `agents/combat.py`: XP/`record_kills`/`npc_killed` so para inimigos que viraram mortos NESTA rodada
  (`dead_before` do estado de entrada + marcador `xp_awarded`, campo opcional, sem mudanca de schema).
- R2 `services/event_processor.py`: `quests_completed` so na transicao active->completed; `working["quests"]` atualizado.
- R3 `agents/storyteller.py`: XP de beat compoe sobre rested -> discovery -> state.player (baú nao se perde).
- R4 `agents/campaign_manager.py`: falha do planejador com plano existente -> mantem plano (None, needs_replan).
- R5 `services/exploration.py`: `discover_on_arrival(..., first_visit=)`; achado ambiental so na 1a visita.
- R6 `services/quest_log.py`: `normalize_fingerprint` (NFKD, tokens>=4) + Jaccard < 0,6.
- R7 `combat_mechanics.normalize_categoria`; `progression.xp_for_kills`/`encounter_budget.tier_cost` por categoria.
- R8 dedupe de `faction_impacts` + `event_processor._revert_reputation` (rejeitado -> delta desfeito); R9 `rule_engine.run_rules` carimba `turn` do pai.
- R10 guard `reward_delta` com ganho bruto; ledger por `services/turn_outcome.record_gain` em combat/storyteller/event_processor/loot.
- R4 (Sol): plano antigo so sobrevive a falha do provider na mesma regiao.

## Testes
- Novo: `tests/test_bug_contabilidade_recompensas.py` (27 casos; Sol adicionou save/reload de abate, R4 inter-regiao, R10 integracao beat+quest+bau, loot venda/compra, R8 rejeicao por faccao derrotada). Vermelhos no HEAD (verificado via stash):
  R1, R2, R3, R4, R5, R6, R7, R8, R9, R10; verdes agora.
- Suite completa: `pytest -q --ignore=tests/test_project_index.py` exit 0. Ruff limpo nos arquivos tocados.

## Baseline de XP (playtest offline MockLLM, 50 turnos, seed 7)
Metrica: soma/maximo de `+N XP` do recibo por turno (mock tem aleatoriedade; comparacao indicativa).

| perfil | run antes | xp total / max turno | run depois | xp total / max turno |
|---|---|---|---|---|
| combate | 20261016-014841-802976 | 1500 / 350 | 20261016-014808-920087 | 1900 / 350 |
| quester | 20261016-014845-182617 | 1850 / 350 | 20261016-014812-793384 | 1850 / 350 |
| explorador | 20261016-014849-251501 | 3350 / 350 | 20261016-014816-372436 | 3350 / 350 |

Maximo por turno 350 = beat (150) + quest (200), legitimo; nenhum turno com XP de abate multiplicado.
Diferenca do combate vem do aleatorio do mock (mais abates novos), nao de re-concessao.

## Limites
- Smoke real (secao 6) nao rodado.
- Reforco com id de cadaver reaproveitado perderia XP (sem callsite de producao hoje; registrado na spec §8b).
- Re-medir `first_death_turn`/nivel dos perfis (XP inflado nao existe mais).

## Smoke com LLM real (2026-10-16, coordenador)

- Playtest real `combate`, 10 turnos, seed 11, DeepSeek (`20261016-020643-397885`): 0 erros, 0 violações,
  US$ 0,007; o combate só abriu no turno 9, sem abate dentro da janela.
- §6 passo 1 (abate paga 1×) validado por `test_kill_transition_pays_once_across_save_reload` (rodada
  determinística + round-trip JSON) — falha no HEAD (paga 100) e passa com o fix; o XP de abate é Python puro.
- Passos 2 e 3 cobertos por testes de integração com `storyteller_node` e `process_pending_events` reais.
Revisão Sol independente: APPROVED (R10 alimentado em produção via `record_gain`, R8 revertido na rejeição,
R4 só mantém plano da mesma região).
