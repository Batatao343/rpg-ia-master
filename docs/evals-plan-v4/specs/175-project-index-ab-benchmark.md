# SPEC-175 — Benchmark A/B do Project Index com coding agents

> **Status:** `draft`
> **Depende de:** SPEC-174 `done`
> **Modelo executor mínimo:** Terra High
> **Delegação:** Luna para agregação mecânica de resultados
> **Revisão obrigatória:** Sol

## Pergunta

O project index melhora localização/resolução no Valoria ou só adiciona complexidade?

## Dataset

Tarefas históricas cross-file com ground truth conhecido: morte falsa, aliases NPC, reward/outcome, lifecycle, structured output, art persistence, replay idempotente, mobile logout.

## A/B

A = ferramentas atuais.
B = mesmas ferramentas + project_index.
Mesmo model/effort/prompt/budget em A e B.

## Métricas

- resolved;
- localization_hit_before_edit;
- irrelevant_files_touched;
- relevant_tests_selected;
- discovery tool calls;
- source bytes/tokens read before first edit;
- wall time observacional.

## Model routing

Terra executa os runs controlados. Luna agrega logs e calcula métricas definidas. Sol revisa metodologia/conclusão e impede cherry-picking pós-hoc.

## Aceite

- [ ] ground-truth patch não é visível ao agente;
- [ ] order/session contamination controlados;
- [ ] thresholds pré-registrados;
- [ ] Sol review aprovada;
- [ ] decisão final pode ser: obrigatório, seletivo ou remover o índice.
