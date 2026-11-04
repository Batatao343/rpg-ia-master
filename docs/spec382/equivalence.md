# SPEC-382 — equivalência W2 (coordenador, 04/11)

Base `3cd58353` (worktree destacado) × ponta `7c880a02` (Etapas 0–2 e 4; Etapa 3 pendente por W1 com `spec-373`).

| Oráculo | Resultado |
|---|---|
| `evals run` 12 suítes do `eval-gates.yml`, `--seed 7` + `evals compare` | `passed: true`, `regressions: []`, todos os deltas 0 |
| `playtest run --all --turns 10 --seed 0` | 14 perfis, assinatura idêntica (turnos, erros, violações, mortes, nível, ouro, rotas, replans) |
| `playtest run --all --turns 10 --seed 1` | idem |
| Catálogo de eventos (`gen_event_catalog.py` + `ruff format`) | byte-igual; `git diff --exit-code` vazio |
| Golden `tests/fixtures/spec382_node_golden.json` (53 casos) | verde em cada commit (executor) e no HEAD (revisão Sol, também com `agents/` da base) |
| Equivalência por AST (revisão Sol) | nós reconstruídos inline idênticos à base, salvo `_early`, `_fm_view/_fm_apply` e aliases do desvio 3 |

## Smoke real §6 (local, DeepSeek)

| Perfil | Turnos | Erros | Violações | Locais | Rotas | Custo USD | Mock |
|---|---|---|---|---|---|---|---|
| explorador (viagem) | 4 | 0 | 0 | 4 | storyteller 4 | 0,0052 | não |
| combate (`RPG_CARD_DECK=on`) | 8 | 0 | 0 | 3 | storyteller 4, combat_agent 4 | 0,0031 | não |

Runs: `playtest_runs/20261104-090842-794465`, `playtest_runs/20261104-091037-736101` (não versionados).
Providers: deepseek (17 + 11 requests), groq 1. Latência local do turno do explorador p50 24 s (rede/LLM;
o caminho de chamadas é o mesmo da base pelo golden e pelos evals).
`check_reproducibility()` e hashes de `mech_log` por campanha ficam cobertos pelas 8 campanhas de 30 turnos do golden.

## Etapa 3 (`_run_round`) — W2 (coordenador, 04/11)

Base `0fdb2a85` (worktree destacado) × ponta `cef757dc` (Etapa 3 + golden reforçado `485e506d`).

| Oráculo | Resultado |
|---|---|
| `evals run` 13 suítes do `eval-gates.yml`, `--seed 7` + `evals compare` | `passed: true`, `regressions: []`, métricas idênticas |
| `playtest run --all --turns 10 --seed 0` / `--seed 1` (mock) | 16 perfis, linhas por perfil byte-iguais nas duas sementes |
| Golden reforçado (66 casos, partes `calls`/`order` estritas) | verde em cada commit (executor) e no HEAD (revisão Sol `handoffs/SPEC-382-sol-etapa3-review.md`, 3 mutações pegas) |
| Smoke real (`--profile combate --turns 8 --real`, `RPG_CARD_DECK=on`) | 8 turnos, 0 erro, 0 violação; storyteller 4, combat_agent 4; deepseek 12, groq 2; ≈ US$ 0,0042 (`playtest_runs/20261104-194258-258229`, não versionado) |
