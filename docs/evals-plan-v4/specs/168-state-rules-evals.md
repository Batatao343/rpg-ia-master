# SPEC-168 — State, Rules e Persistence Evals

> **Status:** `draft`
> **Depende de:** SPEC-167 `done`
> **Modelo executor mínimo:** Terra High
> **Revisão:** por escalada

## Objetivo

Formalizar primeiro as dimensões com oráculo 100% estruturado.

## Cobertura

- GameState transitions;
- gold/inventory/unique items;
- lifecycle/downed/death;
- quests/rewards/outcome;
- combat transitions;
- save/load/restore;
- idempotência/replay;
- existing `playtest.invariants` adapter.

## Model routing

Terra escreve casos/evaluators. Luna pode converter bugs históricos em tabela/fixtures quando expected já estiver explícito. Escalar a Sol se ownership/transação cruzar domínios ou se a regra canônica for ambígua.

## Aceite

- [ ] expected é independente da função sob teste;
- [ ] projeções comparadas em vez de blob integral;
- [ ] casos known-bad falham;
- [ ] zero judge LLM.
