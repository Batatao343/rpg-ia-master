# 04 — Datasets e oráculos

## Fonte dos primeiros casos

Não pedir a uma IA para inventar todo o benchmark. Começar por evidência do próprio projeto.

Prioridade:

1. bugs reais documentados em `ESTADO_ATUAL.md` e `docs/`;
2. regressões existentes em `tests/`;
3. casos canônicos derivados de `data/graph`, `data/codex`, `world_map`, classes, cartas e itens;
4. casos de fronteira escritos manualmente;
5. casos sintéticos apenas para ampliar cobertura depois.

## Tamanho inicial

Não há vantagem em começar com milhares de casos fracos.

Primeira versão sugerida:

```text
routing                 80 casos
state transitions       60 casos
memory write            60 casos
memory retrieval        80 queries
context grounding       60 casos
narrative claims        80 casos
frontend journeys       15-20 jornadas
```

Total pequeno o bastante para auditar manualmente.

## Split

Durante construção:

```text
60% dev
20% regression/manual adversarial
20% holdout privado
```

Regressão não precisa ser aleatória: bugs históricos devem ficar permanentemente no conjunto de regressão.

## Schema mínimo do caso

Ver `examples/eval_case.schema.json`.

Campos obrigatórios:

- `id` imutável;
- `suite`;
- `description`;
- `fixture`;
- `input`;
- `expected`;
- `tags`;
- `oracle`;
- `source` (manual, regression, canonical, synthetic);
- `created_from` (issue/spec/test quando houver).

## Freeze

Gerar `manifest.lock.json` com hash por arquivo.

Exemplo:

```json
{
  "schema_version": 1,
  "datasets": {
    "routing.dev.jsonl": "sha256:...",
    "memory.regression.jsonl": "sha256:..."
  }
}
```

O runner deve abortar se o hash não corresponder em uma execução de baseline/comparação.

## Independência do oráculo

Regra crítica: o código que decide a resposta correta não pode chamar a função de produção que está sendo testada.

Ruim:

```python
expected = product.normalize_action(input)
actual = product.normalize_action(input)
```

Bom:

```python
expected = fixture["expected_route"]
actual = router(state, input).route
```

## Metamorphic tests

Usar propriedades quando enumerar expected completo é desnecessário.

Exemplos:

- replay da mesma `operation_id` não muda o estado uma segunda vez;
- save -> load preserva identidade/outcome;
- ordem de aliases equivalentes não muda entidade final;
- adicionar espaço/pontuação não muda rota;
- retrieval nunca retorna `secret` acima da visibility permitida;
- reduzir token budget pode reduzir recall, mas não pode introduzir evidence proibida;
- refresh concorrente continua single-flight.

## Holdout real

Como o repositório é público, qualquer arquivo commitado é visível ao coding agent.

Para medir generalização:

1. criar repo privado `rpg-ia-evals-private`;
2. manter apenas datasets/seeds e um pequeno adapter de CI;
3. checkout desse repo em job protegido;
4. executar contra SHA do candidato;
5. publicar somente métricas agregadas + IDs abstratos de falha;
6. revelar um caso ao dev somente quando virar regressão depois da correção.

Esse ciclo cria um funil saudável:

```text
holdout fail -> análise humana -> caso revelado -> regression corpus
```
