# 01 — Princípios e governança

## 1. Determinístico primeiro

A hierarquia de preferência deve ser:

1. igualdade/exatidão de estado;
2. schema/contrato tipado;
3. invariantes e propriedades;
4. métricas de ranking/retrieval com ground truth (`Recall@K`, `MRR`, `nDCG`);
5. classificação com labels (`accuracy`, `precision`, `recall`, `F1`);
6. testes metamórficos/propriedade;
7. comparação semântica controlada;
8. LLM-as-judge;
9. revisão humana.

Um critério não deve subir na lista se puder ser resolvido por um nível anterior.

Exemplo: “o jogador comprou uma poção?” deve ser avaliado por delta de inventário + ouro. Nunca por análise da narração.

## 2. Separar pipeline em componentes

Uma resposta ruim pode nascer em pelo menos quatro pontos:

`input -> roteamento -> recuperação/contexto -> regra/estado -> geração -> apresentação`

Por isso, nunca medir apenas a resposta final.

Para cada caso deve ser possível responder:

- a rota escolhida foi correta?
- as evidências relevantes foram recuperadas?
- as evidências proibidas foram excluídas?
- a transição de estado foi correta?
- a prosa contradisse o estado?
- o frontend apresentou o resultado correto?

## 3. Evals não são editáveis pelo agente que está sendo otimizado

Durante uma tarefa de otimização, o agente pode alterar produto, mas não a régua.

Paths protegidos sugeridos:

```text
evals/core/
evals/datasets/regression/
evals/evaluators/
evals/manifest.lock.json
web/e2e/contracts/
```

Alteração desses paths exige tarefa separada de “evaluator change”, com revisão humana.

## 4. Três conjuntos de casos

### dev

Casos que o agente vê e executa durante desenvolvimento. Servem para debugging.

### regression

Bugs reais já encontrados. Devem ser visíveis e permanentes. Cada bug corrigido relevante vira um caso de regressão.

### holdout

Casos não usados para escolher a implementação. Como o repo é público, holdout verdadeiro não deve morar em `main`.

Estratégia recomendada:

- repositório público: `evals/dev` + `evals/regression`;
- companion privado: `rpg-ia-evals-private` com holdout + seeds privadas;
- GitHub Action do projeto recebe apenas resultado agregado do holdout;
- nenhuma saída de CI imprime input/expected completos dos casos privados.

Sem holdout privado, ainda é possível trabalhar, mas a métrica deve ser chamada de `development score`, não de generalização.

## 5. Versionar tudo que muda a medição

Todo resultado deve carregar:

- SHA do produto;
- SHA/hash do dataset;
- versão do evaluator;
- seed;
- provider/modelo/rota;
- temperatura/configuração;
- versão do embedding;
- sistema operacional/browser quando frontend;
- timestamp;
- custo/latência quando aplicável.

## 6. Não começar com targets arbitrários

Primeiro medir o build atual. Depois definir target.

Exceções: contratos de correção binária podem exigir 100% desde o início, por exemplo:

- estado impossível;
- secret leak;
- replay duplicando ação;
- jornada crítica quebrada;
- uncaught frontend exception;
- navegação que leva à tela incorreta.

Para métricas contínuas, usar baseline + ratchet.

Exemplo:

```text
baseline Recall@5 = 0.71
primeiro target = >= 0.76
regression floor = >= 0.70
```

## 7. Métrica alvo + guardrails

Nunca otimizar uma métrica isolada.

Uma tarefa deve conter:

```text
TARGET
memory_recall_at_5: 0.71 -> >= 0.78

GUARDRAILS
state_invariant_errors = 0
action_route_accuracy >= baseline - 1pp
context_secret_leaks = 0
p95_latency <= baseline * 1.10
cost_per_100_turns <= baseline * 1.15
frontend_critical_journeys = 100%
```

## 8. LLM-as-judge só para o irreduzivelmente subjetivo

Uso permitido inicialmente:

- persona/voz de NPC;
- qualidade de prosa;
- sensação de agência quando não há sinal estrutural suficiente;
- repetição semântica avançada.

Uso proibido quando há ground truth estruturado.

Quando usado:

- rubric binária ou com poucos níveis claramente definidos;
- judge diferente do modelo sendo avaliado quando possível;
- outputs cegos quanto a baseline/candidato;
- ordem invertida em pairwise para detectar position bias;
- judge calibrado em exemplos humanos conhecidos;
- score inicialmente informativo, não blocking;
- promover a blocking somente após meta-eval demonstrar concordância aceitável.


## 9. Long-run é opt-in

Playtests longos não fazem parte do fluxo padrão de desenvolvimento, baseline, PR ou otimização.

Não executar campanhas longas, matriz 10×200, 100/200 turnos ou provider real de longa duração automaticamente. Long-run só roda quando:

1. o usuário pedir explicitamente; ou
2. uma spec futura aprovada pelo usuário exigir explicitamente comportamento de horizonte longo.

Mesmo nesses casos, long-run complementa — nunca substitui — evals determinísticas focadas. Uma correção de routing, memória, estado ou frontend deve primeiro provar o contrato no menor teste reproduzível que cobre a mudança.
