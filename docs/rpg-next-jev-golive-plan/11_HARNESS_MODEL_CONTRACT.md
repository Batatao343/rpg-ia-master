# Harness model contract — obrigatório

Este pacote usa roteamento **exato** de modelos. O harness não escolhe o modelo por conveniência, disponibilidade ou custo depois que uma spec começa.

## Preflight obrigatório por spec

Antes de qualquer leitura/edit relevante da spec ativa, o harness deve carregar `examples/spec-model-contract.yaml` e registrar:

```text
spec_id
executor_model
executor_effort
actual_model
actual_effort
run_id/session_id
head_sha
```

Se `actual_model != executor_model` ou `actual_effort < executor_effort`, o harness deve parar com `MODEL_HANDOFF_REQUIRED`. Não pode continuar com modelo inferior **nem superior** silenciosamente: o modelo foi escolhido por custo/risco, e usar Sol/Astra onde Terra foi prescrito é desperdício que o usuário não autorizou.

Se o harness atual estiver rodando num coordenador diferente do executor prescrito, ele pode apenas coordenar/delegar. O patch da spec deve ser produzido pelo executor exato.

## Review obrigatório

Quando `review_required: true`:

1. terminar implementação e gates locais;
2. congelar `HEAD`, diff e resultados;
3. abrir contexto independente no `review_model` exato, com `review_effort` indicado;
4. o reviewer recebe spec, diff, testes/evidência e source mínimo necessário;
5. o reviewer não deve ser o mesmo contexto/session do executor;
6. `CHANGES_REQUESTED` volta ao executor original; após correção, novo review independente;
7. sem review real, status máximo é `review-pending` e a próxima spec não inicia.

Astra é obrigatório somente nas specs marcadas; não usar Astra em outras specs salvo nova aprovação explícita do usuário.

## Delegação Luna

Luna pode executar apenas as subtarefas explicitamente listadas na matriz. Por padrão são read-only/mecânicas: inventário, coleta de logs, hashing, agregação, checklist, formatação e relatórios. Luna não pode decidir semântica de evaluator, arquitetura, auth, transação financeira, webhook, reconciliação, topologia cloud ou policy de release.

Se Luna gerar um arquivo derivado, o executor da spec deve validar o conteúdo antes de commitá-lo.

## Evidência mínima

Cada spec deve registrar em sua evidência/handoff:

```yaml
spec_id: SPEC-xxx
executor:
  model: Terra|Sol|...
  effort: high
  run_id: ...
review:
  required: true|false
  model: Sol|Astra|null
  effort: high|null
  run_id: ...
  decision: APPROVED|CHANGES_REQUESTED|PENDING|null
head_sha_before: ...
head_sha_after: ...
gates: ...
```

Não declarar `APPROVED` por inferência. Não inventar identidade de modelo se o harness não consegue verificá-la.

## Ações externas e humanos

Model routing não substitui aprovação humana. Environment `eval-governance`, criação de cloud, Stripe live, compras reais, Play Console e publicação continuam exigindo os approvals definidos nas specs.

## Long-run

Nenhum modelo, inclusive Astra, recebe permissão implícita para long-run. A política manual-only de `AGENTS.md` continua prevalecendo.
