# 06 — CI/CD e gates

## Estado atual

`.github/workflows/validate.yml` já executa:

- sync deps;
- Ruff;
- content validator;
- pytest;
- `npm test`;
- `npm run build`.

`.github/workflows/audit-local.yml` existe como workflow manual de infra/browser.

A mudança proposta é adicionar níveis, não colocar 2.000 turnos em cada PR.

## Gate A — todo PR / push

Tempo alvo: poucos minutos.

```text
ruff
content validation
pytest default
frontend unit/component tests
backend deterministic evals dev+regression
frontend Playwright critical smoke (subset)
eval integrity hash check
```

Blocking.

## Gate B — PR que altera IA/RAG/agents

Executar quando paths relevantes mudarem:

```text
agents/**
rag.py
services/context_*.py
services/memory_*.py
services/narrative_*.py
llm_setup.py
```

Rodar:

- routing dataset completo;
- memory write/retrieval;
- context grounding;
- narrative deterministic checks;
- offline playtest 10×3/10×10 conforme custo local.

Blocking.

## Gate C — PR que altera frontend

Paths `web/**`, API presentation/session/history.

Rodar:

- Node/Vitest/RTL;
- Playwright critical journeys contra local deterministic server;
- 320/390/768/1440 responsive subset;
- accessibility;
- console/network gate;
- snapshots estáveis.

Blocking.

## Gate D — contrato real curto

Manual ou ambiente protegido. Não em todo commit.

Usar provider real para poucos casos por feature onde MockLLM não prova o contrato.

Critérios:

- orçamento máximo explícito;
- request count máximo;
- zero terminal fallback;
- nenhum hard deterministic failure;
- resultado persistido como artifact.

## Long-run manual — fora dos gates automáticos

A matriz long-run real **não é Gate E do fluxo normal**. Nenhum PR, baseline-v1, otimização ou deploy deve iniciá-la automaticamente.

Executar a matriz existente 10×200 apenas quando o usuário pedir explicitamente ou quando uma spec aprovada pelo usuário for especificamente sobre comportamento de horizonte longo.

Quando executada, comparar pareado:

- mesmas seeds;
- mesmos perfis/classes/níveis;
- mesma route profile;
- mesma configuração de provider/modelo;
- candidate vs baseline compatível.

Ausência de long-run não deixa uma baseline ou mudança em estado `pending`.

## Gate E — post-deploy smoke

Entrada:

```text
PROD_BASE_URL
EXPECTED_GIT_SHA
SMOKE_TEST_USER credentials via protected environment
```

Não usar dados pessoais.

Jornadas mínimas:

1. `/health`;
2. auth;
3. abrir/criar jogo sintético;
4. carregar state/history;
5. uma ação controlada, se permitido pelo orçamento/provider;
6. reload;
7. deletar fixture quando API permitir.

Se produção não deve gastar LLM no smoke, usar apenas endpoints determinísticos/read-only e manter o contrato real LLM no ambiente de staging.

## Integridade das evals

No mesmo PR de otimização, falhar se houver mudança em paths protegidos.

Pseudo-regra:

```bash
git diff --name-only origin/main...HEAD | grep '^evals/core\|^evals/evaluators\|^evals/datasets/regression'
```

Se houver mudança, exigir workflow separado `evaluator-change` com aprovação manual.

## Política de retries

Retry não converte falha em sucesso silencioso.

- deterministic test: sem retry;
- browser: no máximo 1 retry em CI para diagnóstico, mas build continua marcado como flaky/failed se passou apenas no retry até a causa ser tratada;
- provider real: retry deve seguir política do produto, e cada tentativa entra na telemetria.

Criar métrica `flake_rate` por teste. Teste com flake recorrente é bug do harness, não ruído descartável.
