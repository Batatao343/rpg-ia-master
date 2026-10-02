# SPEC-167 — Deterministic Eval Harness

> **Status:** `done`
> **Depende de:** SPEC-166 `done`
> **Modelo executor mínimo:** Terra High
> **Revisão obrigatória:** Sol

## Objetivo

Construir runner, registry e report comuns, reaproveitando os contratos de
`playtest/` e os testes existentes, sem criar um segundo ecossistema duplicado.

## Entregas

- CLI local de eval com saída JSON endereçável;
- schemas de case/result/run já congelados pela SPEC-165 aplicados pelo runner;
- registry explícito de adapters e métricas;
- metadata com SHA do produto, hashes de datasets/ruler/registry e configuração;
- diagnósticos por caso e contabilização completa de erro/skip;
- comparação de baseline com compatibilidade fail-closed;
- adapters para fixture-authored actual e invariantes existentes de `playtest/`.

## Regras de implementação

- o expected vem somente do dataset/fixture, nunca da função sob avaliação;
- cada suite selecionada precisa ter adapter registrado;
- dataset, evaluator bundle e registry são validados antes da execução;
- hard failure, erro de caso ou caso failed termina com exit code não zero;
- seleção vazia, caso sem adapter e baseline incompatível falham fechados;
- `playtest.invariants.check_all` é reutilizado pelo adapter de invariantes;
- nenhum provider, campanha longa ou novo ecossistema de telemetria nesta spec.

## Model routing

Luna pode gerar fixtures derivadas e reportar runs. Terra implementa core. Sol
revisa fronteiras do harness e garante que expected não é calculado pela
implementação sob teste.

## Aceite

- [x] roda sem API key;
- [x] hard fail resulta em exit code não zero;
- [x] relatório traz SHA, hashes de dataset/ruler e evaluator version;
- [x] known-good/known-bad cobrem runner e não só evaluator unitário;
- [x] comparação rejeita baseline incompatível;
- [x] adapter reutiliza invariantes existentes;
- [x] revisão Sol aprovada.

## Execução — 2026-09-28

- Aprovada pelo pedido do usuário para executar as specs draft em ordem, com
  SPEC-104 cloud mantida on hold.
- Implementação iniciada após SPEC-166 `done`.
- Entregue runner/CLI, registry explícito, relatórios JSON/Markdown, comparação
  fail-closed, accounting de caso e adapter de `playtest.invariants.check_all`.
- A semântica da régua subiu para `1.1.0`; o manifest congela também a CLI e os
  dois datasets públicos. `evals/runs/` é artefato local ignorado pelo Git.
- Gates iniciais: governance/lock verdes, smoke offline dos dois casos de
  invariantes, testes focados e Ruff verdes. Nenhum provider ou long-run.
- `MODEL_HANDOFF_REQUIRED: gpt-5.6-sol`; revisão independente solicitada.
- Primeira revisão Sol `SPEC-167-SOL-20260928-01`: `CHANGES_REQUESTED` porque o
  adapter recebia `expected` e o SHA sozinho não identificava worktree dirty.
  A interface agora recebe `AdapterCase` sem expected/oracle; a identidade inclui
  SHA, hash de todos os bytes Git-visible e dirty state. Regressões adversariais
  provam ambos os contratos. Gate atual: **25 testes focados**, governance e Ruff
  verdes; re-review pendente.
- Segunda revisão Sol `SPEC-167-SOL-20260928-02`: `APPROVED`, sem bloqueadores.
  Gate final: **1.841 passed, 35 skipped, 15 deselected**, zero falhas; nenhum
  provider, browser, cloud ou long-run.
