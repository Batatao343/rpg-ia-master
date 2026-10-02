# 12 — Política de execução por modelo

Esta política existe para otimizar custo **sem usar um modelo fraco para decisões de alto impacto**. O princípio é `minimum sufficient model`: começar no menor tier adequado e escalar somente quando a tarefa exigir.

Modelos-alvo no Codex/Work/API conforme disponibilidade atual:

- **Luna (`gpt-5.6-luna`)** — mais rápido e barato; alto volume, leitura, transformação e execução mecânica.
- **Terra (`gpt-5.6-terra`)** — padrão de implementação quando a spec já fecha arquitetura e critérios de aceite.
- **Sol (`gpt-5.6-sol`)** — código complexo, cross-domain, depuração difícil, concorrência, stateful systems e revisão técnica crítica.
- **Astra (`gpt-6-astra`)** — somente para decisões conceituais/arquiteturais de maior risco e revisão de evaluators que definem a própria régua.

## Regra principal

O coding agent **NÃO deve escolher o modelo pelo prestígio**. Deve escolher pelo menor tier que satisfaça o risco da próxima etapa.

```text
mechanical/read/report        -> Luna
bounded implementation        -> Terra
complex/cross-domain/debug     -> Sol
eval/architecture semantics    -> Astra review
```

Um modelo mais forte pode executar uma tarefa de tier inferior se já estiver ativo, mas isso deve ser registrado como custo não otimizado. Um modelo abaixo do mínimo não pode fingir equivalência.

## Roteamento por tipo de trabalho

### Luna

Use para:

- inventariar arquivos/specs;
- ler histórico Git e extrair metadata;
- gerar relatórios derivados de dados já calculados;
- atualizar tabelas/índices/documentação derivada;
- verificar links, hashes, manifests e listas;
- classificar logs/falhas já estruturadas;
- executar comandos de teste/eval e resumir resultados sem reinterpretar a régua;
- transformações textuais massivas quando o resultado é validado deterministicamente;
- preparação de handoff para outro modelo.

Não use Luna para:

- definir arquitetura nova;
- modificar evaluator semantics;
- decidir state ownership;
- alterar concorrência/transações;
- corrigir falha cross-domain sem causa localizada;
- aprovar uma revisão arquitetural.

### Terra

É o **executor padrão** deste pacote.

Use para:

- implementar specs com design já aprovado;
- scripts de migração e codemods;
- testes determinísticos;
- Playwright/E2E;
- CI e automação;
- project-index extractors e CLIs;
- schemas e runners claramente especificados;
- correções locais com regression test independente.

Escalar para Sol quando:

1. duas tentativas coerentes falharem pelo mesmo motivo não-local;
2. houver alteração simultânea de múltiplos domínios canônicos;
3. houver concorrência, transação, retry/idempotência ou ownership ambíguo;
4. o expected behavior não puder ser derivado da spec/código canônico;
5. a mudança exigir redefinir a arquitetura em vez de implementá-la.

### Sol

Use para:

- mudanças cross-domain;
- RAG/context/memory internals complexos;
- bugs de concorrência/estado persistente;
- desenho/depuração de abstrações centrais;
- revisão independente de specs críticas implementadas por Terra;
- análise de falha quando os gates não identificam a camada causal.

Sol não deve ser usado para reescrever 162 arquivos, atualizar manifests, rodar baseline ou formatar relatórios se Luna/Terra + validação determinística resolvem.

### Astra

Astra é um **reviewer escasso**, não o executor padrão.

Use apenas quando a decisão errada pode contaminar a régua ou toda a arquitetura. Neste pacote, revisão Astra é obrigatória após:

- **SPEC-165 — Eval Governance**;
- **SPEC-170 — Memory/RAG/Context Evals**;
- **SPEC-171 — Narrative/NPC Evals**, especialmente qualquer promoção de LLM-as-judge para blocking.

Astra pode ser solicitado adicionalmente quando Sol declarar `ARCHITECTURE_AMBIGUITY` com evidência concreta.

Não use Astra para implementação rotineira, correção de lint, renome, geração de fixtures, Playwright comum, CI comum ou produção de relatórios.

## Escalation ladder

```text
Luna -> Terra -> Sol -> Astra
```

Escalar um nível por vez. A exceção é uma revisão explicitamente marcada `ASTRA_REVIEW_REQUIRED`.

Não escalar só porque um teste falhou. Primeiro localizar a falha. Escalar quando o problema excede o escopo cognitivo/arquitetural do tier atual.

## Review não é implementação duplicada

Reviewer recebe somente:

```text
spec
relevant diff
relevant source/context
commands + results
eval report
known risks/open questions
```

Não pedir ao reviewer para reimplementar tudo. O objetivo é detectar erro conceitual, leakage, contrato enfraquecido, ownership incorreto ou solução que passa testes pelo motivo errado.

## Independência da revisão

Se uma spec exige revisão Sol/Astra:

- preferir outra execução/contexto de agente;
- registrar `review_model`, `review_run_id` e decisão;
- o executor não pode declarar a própria revisão independente.

Se o ambiente não permitir trocar/invocar o modelo requerido:

```text
MODEL_HANDOFF_REQUIRED: <model>
```

O agente deve gerar `handoffs/SPEC-xxx-<model>-review.md` com diff, testes, riscos e perguntas. A spec permanece `review-pending`; não fingir que um reviewer inexistente aprovou.

## Gate > modelo

O modelo nunca substitui evidência executável. Prioridade:

```text
oráculo determinístico
> regression test
> integration/browser gate
> calibrated evaluator
> reviewer model
> opinião do executor
```

Uma saída de Astra não autoriza ignorar teste determinístico vermelho.

## Registro mínimo por spec

No relatório de execução:

```yaml
execution_model: gpt-5.6-terra
execution_effort: high
escalations:
  - from: terra
    to: sol
    reason: "cross-domain state ownership ambiguity"
reviews:
  - model: gpt-6-astra
    status: approved
    run_id: "..."
```

## Política de custo

1. nunca usar Astra por padrão;
2. nunca usar Sol para tarefa puramente mecânica;
3. preferir Luna para leitura/transformação/reporting;
4. preferir Terra para implementação bounded;
5. usar testes/evals para reduzir necessidade de revisão cara;
6. registrar escaladas para medir depois se realmente aumentam first-pass success.
