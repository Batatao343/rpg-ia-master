# 10 — Checklist de aprovação do sistema de evals

Antes de considerar a infraestrutura pronta:

## Governança

- [ ] métricas possuem definição escrita;
- [ ] cada métrica tem numerador/denominador/exclusões;
- [ ] evaluator tem versão;
- [ ] dataset tem hash;
- [ ] eval paths são protegidos durante otimização;
- [ ] holdout não está no repo público;
- [ ] bug novo vira regression case.

## Backend

- [ ] routing eval independente do router;
- [ ] state transitions usam projeções esperadas;
- [ ] memory write é separada de retrieval;
- [ ] retrieval retorna evidence IDs/ranking;
- [ ] context builder reporta evidence IDs;
- [ ] secret leak tem hard gate 0;
- [ ] narrative hard claims usam estado canônico;
- [ ] LLM judge não bloqueia merge antes de calibração;
- [ ] playtest atual continua funcional.

## Frontend

- [ ] Playwright TS configurado em `web/`;
- [ ] 16 jornadas críticas cobertas ou justificadas;
- [ ] page errors = 0;
- [ ] console errors inesperados = 0;
- [ ] requests 5xx inesperados = 0;
- [ ] mobile 320/390 sem overlap/overflow;
- [ ] keyboard/modal focus testado;
- [ ] axe critical/serious = 0;
- [ ] visual snapshots só de estados estáveis;
- [ ] Chromium/OS/fontes pinados;
- [ ] flake rate é reportada.

## Baseline

- [ ] build SHA registrado;
- [ ] deterministic baseline executada;
- [ ] real-provider short contracts executados;
- [ ] custo registrado;
- [ ] latência registrada;
- [ ] long-run **não** é requisito da baseline e não aparece como pendência quando não solicitado;
- [ ] nenhuma automação dispara 100/200-turn ou matriz 10×200 sem autorização explícita;
- [ ] targets definidos somente após baseline.

## Coding agent

- [ ] recebe uma métrica alvo por ciclo;
- [ ] recebe guardrails;
- [ ] não pode editar evaluator/dataset na mesma tarefa;
- [ ] cada experimento é logado;
- [ ] mudança é revertida se hard guardrail falhar;
- [ ] holdout roda fora do contexto de otimização.


## Project index / repo graph

- [ ] índice registra o commit SHA e detecta staleness;
- [ ] nodes/edges possuem proveniência;
- [ ] arestas dinâmicas/best-effort são rotuladas como tal;
- [ ] `data/codex/**`, assets e artefatos gerados não poluem o symbol graph;
- [ ] agent abre o source real antes de editar;
- [ ] state ownership é curado e não sobrescrito automaticamente;
- [ ] nenhuma graph database foi adicionada sem necessidade demonstrada;
- [ ] reorganização física de pastas não é requisito para baseline-v1;
- [ ] benchmark A/B do índice foi pré-registrado antes de avaliar resultados;
- [ ] decisão de manter/tornar obrigatório o índice usa resultado no próprio Valoria.


## Histórico de specs

- [ ] SPEC-163 atribuiu IDs estáveis 001–162 por criação comprovada no Git;
- [ ] `completed_order` é separado de `SPEC-ID`;
- [ ] `specs/index.yaml` existe e é reproduzível;
- [ ] links internos foram atualizados/testados;
- [ ] IDs não são renumerados quando status muda.

## Model routing

- [ ] cada spec registra execution model/effort;
- [ ] Luna é preferido para inventário/report/transformação mecânica;
- [ ] Terra é executor padrão para implementação bounded;
- [ ] Sol só aparece por complexidade/review documentado;
- [ ] Astra aparece apenas nos checkpoints previstos ou ambiguity escalated;
- [ ] revisão obrigatória usa contexto/execução independente;
- [ ] indisponibilidade gera `MODEL_HANDOFF_REQUIRED`, nunca autoaprovação;
- [ ] gates executáveis prevalecem sobre reviewer model.
