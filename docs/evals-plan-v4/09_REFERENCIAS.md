# 09 — Referências e racional

## Literatura acadêmica

### Zheng et al. — Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena

https://arxiv.org/abs/2306.05685

Relevância: documenta position bias, verbosity bias e self-enhancement bias. Sustenta não usar judge como verdade absoluta e preferir protocolos calibrados/pairwise quando julgamento subjetivo for necessário.

### Liu et al. — G-Eval

https://arxiv.org/abs/2303.16634

Relevância: mostra utilidade de LLM para avaliação de NLG, mas também registra viés em direção a textos gerados por LLM. Usado aqui apenas para camada subjetiva.

### Es et al. — RAGAS

https://arxiv.org/abs/2309.15217

Relevância: separa dimensões de retrieval/context e geração. O plano adota a mesma ideia de decompor RAG, mas prefere ground truth por IDs sempre que possível.

### Saad-Falcon et al. — ARES

https://aclanthology.org/2024.naacl-long.20/

Relevância: avaliação de RAG por context relevance, faithfulness e answer relevance; combina automação com um pequeno conjunto humano calibrado. Apoia a estratégia de calibrar judges em vez de confiar neles diretamente.

### Liu et al. — AgentBench

https://arxiv.org/abs/2308.03688

Relevância: agentes precisam ser avaliados em ambientes interativos multi-turno. Reforça preservar o `playtest/` como camada sistêmica, e não avaliar somente respostas isoladas.

### Jimenez et al. — SWE-bench

https://arxiv.org/abs/2310.06770
https://proceedings.iclr.cc/paper_files/paper/2024/hash/edac78c3e300629acfe6cbe9ca88fb84-Abstract-Conference.html

Relevância: usa problemas reais + fail-to-pass tests em ambientes reproduzíveis. Inspira transformar bugs históricos do RPG em casos de regressão permanentes e independentes da solução.

### Survey on LLM-as-a-Judge

https://www.sciencedirect.com/science/article/pii/S2666675825004564

Relevância: consolida vieses e necessidade de meta-avaliar o evaluator.

## Guias técnicos / indústria

### OpenAI — Evaluation best practices

https://developers.openai.com/api/docs/guides/evaluation-best-practices

Relevância: eval-driven development, datasets representativos, métricas estruturadas e avaliação contínua.

### Anthropic — Demystifying evals for AI agents

https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

Relevância: agentes multi-turno exigem mistura de evals, graders e ambientes; reforça avaliar comportamento/trajectory e não só output final.

### LangSmith — Evaluation types

https://docs.langchain.com/langsmith/evaluation-types

Relevância: distingue unit/regression/benchmark e code evaluators vs LLM-as-judge. O plano segue essa taxonomia sem exigir adoção do LangSmith.

### Hugging Face Lighteval

https://huggingface.co/docs/lighteval/main/index
https://huggingface.co/docs/lighteval/main/offline-evaluation

Relevância: tasks/metrics customizadas, datasets locais, sample-level results e execução reproduzível.

## Frontend

### Playwright — Best Practices

https://playwright.dev/docs/best-practices

Princípios incorporados: comportamento visível pelo usuário, isolamento, locators por role/label/text, web-first assertions.

### Playwright — Auto-waiting / locators

https://playwright.dev/docs/actionability
https://playwright.dev/docs/locators

Relevância: reduzir flakiness sem sleeps arbitrários.

### Playwright — Visual comparisons

https://playwright.dev/docs/test-snapshots

Relevância: snapshots só são confiáveis em ambiente de rendering consistente; por isso este plano fixa Chromium/OS/fontes/animação.

### Testing Library — Guiding Principles

https://testing-library.com/docs/guiding-principles/

Relevância: testes mais próximos da maneira que o usuário opera a UI dão mais confiança e evitam acoplamento a internals.

### web.dev — Core Web Vitals

https://web.dev/articles/vitals

Relevância: LCP/INP/CLS como sinais de UX. Neste plano entram inicialmente como observacionais, não gates ultra-estritos em CI local.

## Reddit / experiência prática

Reddit é usado apenas como sinal prático, não como autoridade científica.

### r/LocalLLaMA — RAG quality in production

https://www.reddit.com/r/LocalLLaMA/comments/1rwzr5m/how_do_you_evaluate_rag_quality_in_production/

Insight recorrente: golden dataset com queries onde o chunk correto é conhecido e medição explícita de recall é mais útil que avaliação vaga da resposta final.

### r/LocalLLaMA — LLMs grading other LLMs

https://www.reddit.com/r/LocalLLaMA/comments/1r86i3o/llms_grading_other_llms_2/

Insight: calibrar grader em known-good/known-bad e medir concordância com humanos antes de automatizar decisões.

### r/Playwright — brittle selectors

https://www.reddit.com/r/Playwright/comments/1ujpovy/after_months_of_fighting_flaky_tests_the_fix/

Insight: CSS/DOM shape tende a criar flake; roles, accessible names e contratos de usuário são mais robustos.

### r/ExperiencedDevs — E2E-only

https://www.reddit.com/r/ExperiencedDevs/comments/1uxzx4w/frustrations_with_e2eonly_approach_to_automated/

Insight: usar Playwright para workflows completos, mas manter unit/component tests para feedback rápido e estabilidade.

## Síntese aplicada a Valoria

A conclusão das fontes é consistente com o desenho deste pacote:

```text
oráculo estruturado > heurística > judge
component score + trajectory score > só resposta final
golden/regression + holdout > otimizar contra um único corpus aberto
ambiente fixo > retries/sleeps para esconder flake
```


---

# Adendo — repository maps, code graphs e organização arquitetural

## Literatura acadêmica

### Ouyang et al. — RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph (2024)

https://arxiv.org/abs/2410.14684

Relevância: avalia um code graph como módulo plugável em tarefas de engenharia de software e reporta ganhos em SWE-bench/CrossCodeEval. Sustenta usar grafo para **navegação e contexto estrutural**, não uma reorganização física como pré-condição.

### Cherny-Shahar & Yehudai — Repository Intelligence Graph (RIG) (2026)

https://arxiv.org/abs/2601.10112

Relevância: propõe mapa arquitetural determinístico, evidence-backed, especialmente para estrutura de build/teste. Reporta +12,2% de acurácia média e -53,9% de tempo nas tarefas avaliadas com agentes comerciais. O desenho `manifest + provenance + deterministic extraction` foi incorporado ao plano.

### Vogel et al. — Codebase-Memory: Tree-Sitter-Based Knowledge Graphs for LLM Code Exploration via MCP (2026)

https://arxiv.org/abs/2603.27277

Relevância: em 31 repositórios, o grafo usou cerca de 10x menos tokens e 2,1x menos tool calls, mas teve qualidade média inferior à exploração de arquivos (83% vs 92%). Isso é a evidência mais importante contra “grafo substitui source”. No plano, grafo localiza; source confirma.

### Zhang et al. — RepoCoder (2023)

https://arxiv.org/abs/2303.12570

Relevância: retrieval iterativo de contexto do repositório supera contexto apenas do arquivo e RAG vanilla em code completion. Apoia seleção de contexto orientada à tarefa.

### Wu et al. — Repoformer: Selective Retrieval for Repository-Level Code Completion (2024)

https://arxiv.org/abs/2403.10059

Relevância: retrieval invariável pode ser inútil ou prejudicial; retrieval seletivo pode melhorar eficiência. Sustenta query bounded e não enviar o grafo inteiro em toda task.

### Bairi et al. — CodePlan: Repository-level Coding using LLMs and Planning (2023)

https://arxiv.org/abs/2309.12499

Relevância: usa dependency/change-impact analysis para planejar edições repository-level. Sustenta incluir impacto/blast radius como query do índice.

### Yang et al. — SWE-agent (2024)

https://arxiv.org/abs/2405.15793

Relevância: mostra que a interface oferecida ao agente afeta fortemente seu desempenho em navegação/edição/testes. O project index é tratado como parte do harness/ACI, não como produto runtime.

### Xia et al. — Agentless (2024)

https://arxiv.org/abs/2407.01489

Relevância: localização → repair → validation simples pode competir com agentes mais complexos. Sustenta não superarquitetar o project index e manter localização explícita/testável.

### Wang et al. — Improving Code Localization with Repository Memory (2025)

https://arxiv.org/abs/2510.01003

Relevância: conhecimento histórico do repositório pode melhorar localização. Fica como extensão futura; não adicionamos git-history graph à v1.

### Empirical Study of Architectural Change in Open-Source Software Systems (MSR 2015)

https://ieeexplore.ieee.org/document/7180083/

Relevância: discute evolução/decay arquitetural e, crucialmente, a adequação limitada da estrutura de implementação como proxy da arquitetura. Apoia não confundir árvore de pastas/call graph com arquitetura canônica.

### Decoupling Level: A New Metric for Architectural Maintenance Complexity (ICSE 2016)

https://ieeexplore.ieee.org/document/7886929/

Relevância: bugs e mudanças são mais localizáveis quando módulos conseguem ser desacoplados. Sustenta avaliar eventual reorganização por **localidade/coupling**, não por estética da árvore.

### Change Impact Analysis baseado em dependências

https://ieeexplore.ieee.org/document/6104718/
https://ieeexplore.ieee.org/document/7781799/

Relevância: dependency/program graphs são úteis para estimar ripple effects, mas possuem trade-offs de precisão/recall. No Valoria, `impact` é ferramenta de orientação com confidence, não prova completa.

## Prática/indústria

### Aider — Repository Map

https://aider.chat/docs/repomap.html
https://aider.chat/2023/10/22/repomap.html

Relevância: Tree-sitter extrai símbolos e um grafo de dependências/PageRank seleciona apenas o contexto que cabe no budget. É referência prática direta para `repo_graph + bounded query`.

### Martin Fowler — Domain-Driven Design / modular architecture

https://martinfowler.com/bliki/DomainDrivenDesign.html
https://martinfowler.com/articles/linking-modular-arch.html

Relevância: complexidade de domínio se beneficia de bounded contexts/cohesion, mas disciplina de fronteiras importa mais que simplesmente criar diretórios. Para Valoria, isso apoia `domains.yaml` agora e reestruturação física apenas quando houver evidência.

### Sourcegraph — code navigation / agentic coding

https://sourcegraph.com/blog/cross-repository-code-navigation
https://sourcegraph.com/blog/agentic-coding

Relevância: find references/callers e blast radius são perguntas naturais de manutenção. Usado como sinal prático; não substitui evidência acadêmica.

## Reddit / experiência prática

Reddit permanece evidência anedótica, utilizada para descobrir failure modes e perguntas úteis, não para definir arquitetura.

### Graph-based repo context para coding agents

https://www.reddit.com/r/ClaudeCode/comments/1ums3k9/is_a_graphbased_repo_context_layer_actually/

Ponto útil da discussão: grafos são particularmente valiosos para perguntas relacionais (`quem chama`, `quais testes`, `qual blast radius`); são fracos quando a tarefa é apenas explicar um arquivo. Isso reforça uso seletivo.

### Persistent code graph / token discovery

https://www.reddit.com/r/ClaudeCode/comments/1rqx4xe/added_a_persistent_code_graph_to_my_mcp_server_to/

Ponto útil: discovery repetido consome contexto. É motivação prática para cache/index persistente, mas números de posts individuais não entram como evidência de performance no Valoria.

### Organização física / modularização

https://www.reddit.com/r/ExperiencedDevs/comments/1i0rjox/thoughts_on_abstraction_modularization_and_code/
https://www.reddit.com/r/ExperiencedDevs/comments/1ipqskk/is_there_a_threshold_after_which_you_need_to_consider_modularizing_a_large_repo/

Ponto útil: não há consenso de que modularizar ou aprofundar hierarquia seja universalmente benéfico; custo de abstração/fragmentação aparece repetidamente. Isso é consistente com a decisão de medir change locality antes de mover Valoria.

## Síntese específica para Valoria

Após revisar as fontes, a recomendação anterior foi ajustada para:

```text
repo map / project index       SIM, agora
repo graph com proveniência    SIM, v1 pequena
state ownership registry       SIM, curado
eval coverage map              SIM
graph DB                       NÃO agora
reorganização física           NÃO antes da baseline
grafo substitui source         NÃO
call graph Python = verdade    NÃO
A/B no próprio repo            SIM antes de tornar obrigatório
```

A maior correção em relação à proposta inicial é separar **arquitetura curada** de **estrutura inferida do código**. O grafo gerado é evidence-backed e útil para navegação; `domains.yaml`/`state_ownership.yaml` carregam intenção arquitetural que a AST não consegue descobrir com segurança.


## Model selection — fontes oficiais OpenAI (consultadas em 2026-09-26)

- OpenAI API Models: https://developers.openai.com/api/docs/models
  - recomenda Astra para trabalho mais difícil, Terra para equilíbrio inteligência/custo e Luna para workloads de alto volume/custo sensível.
- OpenAI Help — GPT-5.6 and GPT-6 Pro in ChatGPT/Codex: https://help.openai.com/en/articles/20001354-gpt-56-and-gpt-6-pro-in-chatgpt
  - documenta disponibilidade de Sol/Terra/Luna no Codex e caracteriza Terra como equilíbrio e Luna como mais rápido/menor custo da família 5.6.
- OpenAI Model Guidance: https://developers.openai.com/api/docs/guides/latest-model
  - descreve Astra como modelo mais forte para workflows difíceis e multi-step.
