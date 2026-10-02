# Baseline v1 — 2026-09-30

Esta é a medição factual do build atual após a SPEC-173. Ela não define metas,
não muda produto e não inclui long-run.

## Identidade

- commit: `cadbdd1013022c98f506ee335fa9072efcc9df6c`;
- árvore medida: `sha256:37501dc7b23f5da682fb9252add29e9761763ba4a183ef3dc6ed4faf34dd10c7`;
- working tree: dirty, portanto comparações futuras devem usar o hash da árvore,
  não apenas o commit;
- evaluator: `1.6.0`, registry schema `1`, seed `7`;
- backend: Windows, Python 3.13.14;
- frontend: Windows 11, Node 24.17.0, Playwright 1.55.1, Chromium
  151.0.7922.71, `pt-BR`, `America/Sao_Paulo`, reduced motion.

Os seis hashes de dataset, o hash da seleção, o registry e os artifacts estão
congelados em [manifest.json](manifest.json). Os resultados completos por caso
estão em [baseline-v1.json](baseline-v1.json); o resumo emitido pelo runner está
em [baseline-v1.md](baseline-v1.md). O resultado Playwright original está em
[frontend-playwright-raw.json](frontend-playwright-raw.json) e sua projeção de
métricas em [frontend.json](frontend.json).

## Resultados observados

| Camada | Métrica | Valor observado |
|---|---|---:|
| Estado/regras | `state_transition_pass_rate` | 1.0 |
| Exatidão geral | `exact_match` | 1.0 |
| Roteamento | `route_accuracy` | 1.0 |
| Alvo | `target_accuracy` | 1.0 |
| Memory write | `memory_write_precision` | 1.0 |
| Retrieval | `memory_recall_at_1` | 0.583333 |
| Retrieval | `memory_recall_at_3` | 1.0 |
| Retrieval | `memory_recall_at_5` | 1.0 |
| Retrieval | `memory_mrr` | 0.833333 |
| Contexto | `context_recall_at_5` | 1.0 |
| Contexto | `context_forbidden_leak_rate` | 0.0 |
| Contexto | `secret_leak_count` | 0.0 |
| Contexto | `context_token_budget_violation` | 0.0 |
| Narrativa | `narrative_claim_accuracy` | 1.0 |
| Narrativa | `narrative_hard_contradictions` | 0.0 |
| NPC | `npc_identity_errors` | 0.0 |
| Frontend | `frontend_critical_journey_pass_rate` | 1.0 (16/16) |
| Frontend | page/console/request/5xx/overflow/a11y errors | 0 em todos |

O runner determinístico executou 86 casos, sem erro, skip ou hard failure. O
Playwright executou as 16 jornadas críticas em 176,76 s, sem retry, flake ou
falha. O snapshot visual ficou fora desta execução porque só é válido no
ambiente Chromium/Linux pinado; isso não reduz o denominador das 16 jornadas.

## Escopo deliberadamente ausente

O contrato com provider real não foi executado: o usuário encerrou a execução
paga anterior após o saldo informado ter sido consumido. O gate curto existe e
permanece manual, protegido e limitado; a ausência não deixa esta baseline
pendente. Custo e latência reais não foram inventados nem substituídos por
valores de mock.

Long-run, campanhas de 100/200 turnos e matriz 10×200 não fazem parte da
baseline v1. Nenhum target contínuo foi criado a partir de uma única medição.
