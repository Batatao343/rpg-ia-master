# 11 — Indexação do repositório e grafos para coding agents

## Decisão após revisão da literatura

A recomendação final é **SIM para um índice arquitetural/repo map**, **SIM para grafos pequenos e determinísticos**, e **NÃO para uma grande reorganização física das pastas agora**.

A revisão mudou a proposta original em dois pontos:

1. o grafo não deve tentar ser uma “verdade completa da arquitetura”; deve ser um **instrumento de navegação, localização e análise de impacto**, com proveniência até arquivo/linha;
2. não vale introduzir um graph database nem mover centenas de arquivos antes de provar que isso melhora o trabalho no repositório real.

A evidência mais direta vem de trabalhos de repository-level coding. `RepoGraph` mostrou ganhos ao adicionar um code graph como módulo de navegação em abordagens de SWE-bench; `Repository Intelligence Graph (RIG)` reportou melhoria média de acurácia e grande redução de tempo em perguntas estruturais quando o agente recebia um mapa determinístico e evidence-backed; `Codebase-Memory` mostrou forte redução de tokens/tool calls, mas com pequena perda média de qualidade de resposta comparada a exploração completa de arquivos. A conclusão prática é: **o grafo orienta onde olhar; o código-fonte continua sendo a fonte final**.

Fontes principais estão em `09_REFERENCIAS.md`.

---

## Comparação com o repositório Valoria atual

O `rpg-ia-master` não é um repositório em que “a pasta está bagunçada” seja o problema principal. Ele já possui divisões reconhecíveis:

```text
agents/          nós/agentes LLM
services/        lógica e serviços determinísticos
infrastructure/  persistência/auth/jobs/storage
playtest/        long-run/invariantes/telemetria
web/             frontend React/Vite
specs/           desenvolvimento spec-driven
tests/           regressões
api.py, state.py, rag.py, main.py ...  núcleo/entrypoints
```

O problema para um agente novo é outro: **as relações entre essas áreas não são explícitas em formato consultável**.

Exemplos reais:

- memória atravessa `agents/archivist.py`, `rag.py`, `services/context_builder.py`, `services/memory_provenance.py`, `services/narrative_evidence.py`, persistência e testes;
- um turno atravessa API → executor → LangGraph → agente → finalização → arquivista → persistência;
- `GameState` é central, mas ownership de campos não está representado de forma mecanicamente consultável;
- o repositório tem grande quantidade de conteúdo em `data/codex/**`; indexar isso como se fosse código criaria ruído;
- Python é dinâmico e o roteamento LangGraph também é parcialmente dinâmico; logo um call graph estático não pode ser tratado como completo.

O `AGENTS.md` já serve como mapa humano muito útil. A nova camada deve **complementá-lo**, não duplicá-lo em mais documentação manual.

---

## O que criar

### 1. `project_index/manifest.json`

Gerado, nunca escrito à mão.

Contém:

- commit SHA indexado;
- versão do gerador;
- arquivos incluídos/excluídos;
- hash do índice;
- linguagem/parser usado;
- contagem de nós/arestas por tipo.

Regra de segurança:

```text
manifest.commit_sha != git HEAD
=> índice STALE
=> coding agent não pode tratá-lo como evidência atual
```

### 2. `project_index/domains.yaml`

Curado, pequeno e estável. É um mapa semântico de bounded contexts, não um resumo de cada arquivo.

Exemplo:

```yaml
memory:
  entrypoints:
    - rag.py
    - agents/archivist.py
  core:
    - services/context_builder.py
    - services/memory_provenance.py
    - services/memory_summary.py
    - services/narrative_evidence.py
  state:
    - memory_facts
    - narrative_summary
    - archivist_last_run
  tests:
    - tests/test_npc_memory.py
    - tests/test_memory_provenance.py
    - tests/test_archivist_facts.py
  evals:
    - memory_write_precision
    - retrieval_recall_at_5
    - context_evidence_recall
    - false_memory_rate
```

Esse arquivo deve conter apenas **responsabilidades de alto nível que não podem ser inferidas com segurança pela AST**.

### 3. `project_index/repo_graph.json`

Gerado automaticamente.

Nós v1:

```text
file
module
class
function/method
test
API endpoint
config/build artifact
```

Arestas v1:

```text
imports
defines
references/calls (best effort)
route_to
contains
likely_test_for
```

Toda aresta deve incluir:

```json
{
  "type": "imports",
  "source": "agents/archivist.py",
  "target": "services.memory_provenance",
  "provenance": {"file": "agents/archivist.py", "line": 42},
  "confidence": "static_exact"
}
```

Para arestas de chamada em Python dinâmico:

```text
confidence = static_best_effort
```

Nunca promover inferência incerta para `static_exact`.

### 4. `project_index/state_ownership.yaml`

**Curado**, não inferido automaticamente como verdade.

É a parte mais importante para Valoria porque o sistema é stateful.

Exemplo:

```yaml
player.gold:
  canonical_domain: economy
  intended_writers:
    - services/economy.py
    - agents/loot.py
    - services/turn_effects.py
  important_readers:
    - agents/storyteller.py
    - services/context_builder.py
    - api.py
  invariants:
    - economy.gold_non_negative
```

A finalidade não é impedir toda escrita fora da lista imediatamente. Primeiro o gerador produz um relatório de writers observados; divergências viram revisão arquitetural.

Não criar um gate que quebre o build só porque a primeira versão do registry está incompleta.

### 5. `project_index/eval_map.yaml`

Liga subsistema → métricas → testes → invariantes → datasets.

Exemplo:

```yaml
memory_retrieval:
  product_paths:
    - rag.py
  metrics:
    - retrieval_recall_at_5
    - retrieval_mrr
  regression_tests:
    - tests/test_npc_memory.py
  datasets:
    - evals/datasets/memory/dev.jsonl
    - evals/datasets/memory/regression.jsonl
```

Esse mapa ajuda o agent a responder:

> “Se eu tocar em `rag.py`, quais evals e testes preciso executar?”

---

## O que NÃO criar na v1

### Não usar Neo4j/graph database

Para este repositório, JSON + SQLite opcional são suficientes inicialmente. Um graph database adicionaria:

- dependência operacional;
- schema e migrações extras;
- mais uma fonte de staleness;
- manutenção que não melhora diretamente o produto.

Só considerar um banco de grafo se queries reais mostrarem que JSON/SQLite deixaram de atender.

### Não indexar todo `data/codex/**` como código

O lore é relevante para o jogo, mas não para localização de software. Na v1:

- `data/codex/**` fica fora do symbol graph;
- loaders/schema/validators que consomem o codex entram normalmente;
- um índice de conteúdo/lore é um problema separado do repo map de engenharia.

### Não gerar documentação LLM como fonte de verdade

Resumos LLM podem ser úteis como cache auxiliar, mas nunca devem criar arestas canônicas sem proveniência verificável.

### Não mover o projeto inteiro para `src/game/...` agora

A literatura sustenta modularidade, baixo acoplamento e alta coesão; ela **não demonstra que uma nova árvore de diretórios por si só melhora maintainability ou desempenho do agente**. Há inclusive evidência de que a estrutura de implementação é um proxy imperfeito da arquitetura.

Além disso, no Valoria uma migração ampla agora afetaria imports, testes, scripts, docs, specs e CI antes da nova baseline de evals. Isso geraria uma mudança gigantesca cujo benefício seria difícil de atribuir.

---

## Reorganização física: quando passa a valer a pena

Depois de `baseline-v1`, usar evidência do próprio projeto.

Abrir uma spec de reestruturação somente se um domínio apresentar repetidamente uma ou mais condições:

1. tarefas do mesmo domínio exigem alterações espalhadas em muitos diretórios sem uma razão arquitetural clara;
2. agentes localizam arquivos errados ou omitem dependências apesar do repo index;
3. alto change coupling entre arquivos indica um módulo implícito ainda não representado;
4. ownership do estado permanece ambíguo e causa regressões;
5. testes/evals de um domínio não conseguem ser executados de forma localizada;
6. uma mudança pequena exige tocar em muitos módulos por acoplamento estrutural.

Se isso acontecer, a meta da refatoração deve ser medida por:

```text
change locality
coupling
cohesion
blast radius
focused-test selection
agent localization accuracy
```

Não por “ficou mais bonito”.

---

## Como o coding agent deve usar o índice

Fluxo recomendado:

```text
TASK
  ↓
query project_index/domains.yaml
  ↓
retrieve relevant nodes from repo_graph
  ↓
inspect state ownership + eval map
  ↓
ABRIR OS ARQUIVOS-FONTE REAIS
  ↓
formular plano
  ↓
editar
  ↓
rodar testes/evals associados
  ↓
blast-radius query nos símbolos tocados
```

Regra crítica:

> O agente nunca pode justificar uma alteração apenas com informação do índice. Antes de editar um símbolo, deve ler o trecho real correspondente no SHA atual.

---

## Query interface mínima

Criar um CLI simples:

```bash
uv run python -m project_index query "memory recall"
uv run python -m project_index symbol services.context_builder.build_context_pack
uv run python -m project_index impact services.context_builder.build_context_pack
uv run python -m project_index tests services/context_builder.py
uv run python -m project_index state player.gold
```

Saída deve ser curta, evidence-backed e apontar caminhos/linhas.

Evitar entregar o grafo inteiro ao modelo. `Repoformer` e a experiência de repo maps reforçam que retrieval excessivo também pode prejudicar desempenho.

---

## Freshness e CI

O índice é derivado do código.

```text
source code
   ↓
build_project_index
   ↓
manifest + graph
   ↓
validation
```

CI v1:

1. gera o índice em diretório temporário;
2. valida schema e referências;
3. compara artefatos versionados, se decidirmos versioná-los;
4. falha se um node aponta para arquivo inexistente;
5. falha se `manifest.commit_sha` não corresponde ao commit do build;
6. não falha por edge best-effort ausente.

Atualização incremental pode vir depois. Primeiro priorizar determinismo e simplicidade.

---

## Benchmark antes de declarar ganho

A literatura mostra ganhos em benchmarks externos, mas isso não prova benefício no Valoria. Portanto, adicionar um A/B local.

Corpus inicial sugerido: bugs/tarefas históricas já documentadas, por exemplo:

- memória de morte falsa;
- aliases/identidade de NPC;
- reward contradiction;
- ciclo de vida do ator;
- structured output inválido;
- arte dinâmica/persistência;
- logout mobile sobreposto;
- replay/idempotência.

Condição A:

```text
coding agent + ferramentas normais
```

Condição B:

```text
mesmo agent/model/prompt + project_index query
```

Medir:

- task resolved / regression suite;
- arquivo correto localizado antes da primeira edição;
- tool calls até o primeiro arquivo relevante;
- tokens/contexto de descoberta;
- arquivos tocados desnecessariamente;
- testes relevantes escolhidos;
- tempo total (secundário; ambiente pode variar).

Decisão pré-registrada:

- o índice só vira parte obrigatória do harness se **não reduzir a taxa de resolução** e reduzir de forma consistente o custo de localização/descoberta;
- se só ajudar em tarefas cross-file, ele permanece ferramenta seletiva, não contexto obrigatório em toda task.

---

## Conclusão aplicada ao RPG

### Vale fazer agora

```text
SIM  project_index/domains.yaml
SIM  repo graph determinístico e com proveniência
SIM  state ownership registry
SIM  eval coverage map
SIM  freshness/hash por commit
SIM  A/B para provar ganho no Valoria
```

### Não vale fazer agora

```text
NÃO  reorganização massiva de pastas
NÃO  graph database
NÃO  LLM-generated architecture como verdade
NÃO  grafo completo enviado em todo prompt
NÃO  call graph Python tratado como perfeito
```

### Pode valer depois

```text
MAYBE reorganização física por domínio
MAYBE atualização incremental do índice
MAYBE git-history/change-coupling graph
MAYBE summaries semânticos auxiliares
```

A ordem recomendada permanece: **índice primeiro, evals/baseline, medir falhas de localização, e só então decidir se uma migração estrutural de diretórios paga o custo**.
