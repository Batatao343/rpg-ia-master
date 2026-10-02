# SPEC-168 — State, Rules e Persistence Evals

> **Status:** `done`
> **Depende de:** SPEC-167 `done`
> **Modelo executor mínimo:** Terra High
> **Revisão:** por escalada

## Objetivo

Formalizar primeiro as dimensões com oráculo 100% estruturado.

## Cobertura

- GameState transitions e projeções selecionadas;
- gold, inventory e unique items;
- lifecycle, downed/death e combate ativo;
- quests, rewards e outcome;
- save/load, migrations e restore;
- idempotência/replay;
- adapter existente de `playtest.invariants`.

## Regras

- expected permanece somente no dataset;
- adapters produzem actual por APIs do produto e não recebem expected/oracle;
- comparar apenas campos declarados no contrato do caso;
- IDs/UUIDs e relógio das fixtures são fixos;
- zero LLM/judge/provider;
- escalar somente se ownership ou regra canônica ficar ambígua.

## Aceite

- [x] expected independente da função sob teste;
- [x] projeções comparadas em vez de blob integral;
- [x] casos known-bad falham;
- [x] transições cobrem os domínios listados;
- [x] zero judge LLM.

## Execução — 2026-09-28

- Aprovada pelo pedido do usuário para executar as specs draft em ordem, com
  SPEC-104 cloud mantida on hold.
- Implementação iniciada após SPEC-167 `done`.
- Entregue `ProjectionEvaluator`, adapter `state_rules` e corpus de 12 casos para
  eventos, regras, ouro/inventário/item único, quest/recompensa, lifecycle,
  combate, restore, migração, save/load e replay/idempotência.
- Smoke do dataset: `state_transition_pass_rate=1.0` e `exact_match=1.0`;
  known-bad candidate ficou vermelho sem acesso ao expected.
- 120 testes focados e Ruff verdes; Project Index fresco com 5.341 nodes e
  13.667 edges. Suíte final: **1.845 passed, 35 skipped, 15 deselected**, zero
  falhas. Nenhum provider/judge/long-run.
- A revisão era somente por escalada; nenhuma ambiguidade de ownership ou regra
  canônica foi encontrada, portanto não houve handoff adicional.
