# SPEC-175 — Benchmark A/B do Project Index com coding agents

> **Status:** `done`
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

Terra é o mínimo para os runs controlados. Como esse tier não estava disponível
na execução confirmatória, Sol High foi pré-registrado antes das sessões e usado
simetricamente nas quatro réplicas, conforme a política de tier superior. Luna
agrega logs e calcula métricas definidas. Sol revisa metodologia/conclusão e
impede cherry-picking pós-hoc.

## Aceite

- [x] ground-truth patch não é visível ao agente;
- [x] order/session contamination controlados;
- [x] thresholds pré-registrados;
- [x] Sol review aprovada;
- [x] decisão final pode ser: obrigatório, seletivo ou remover o índice.

## Execução — 2026-09-30

- Aprovada pelo pedido do usuário para executar as specs draft em ordem, com
  SPEC-104 cloud mantida on hold.
- Iniciada somente após congelar e validar a baseline v1 da SPEC-174.
- Metodologia, tarefas, ordem cruzada, métricas, thresholds e o hash do ground
  truth foram pré-registrados em `docs/project-index-benchmark/` antes dos runs.

## Resultado confirmatório — 2026-10-01

- V1–v5 foram preservadas como histórico e excluídas antes dos runs v6. V5 foi
  invalidada ainda parcial (A1=5, A2=4, B1=B2=0); nenhuma sessão completa v6 foi
  descartada.
- V6 selou pré-registro, compromisso, ciphertext, attestation e prompts no
  commit Git local `aa50ca35af7e0f7c3785e7405b04c23ee68ab326` antes de criar as sessões. O
  ground truth AES-256-GCM foi revelado somente após 4/4 sessões e 32/32
  observações completas; hashes de ciphertext, plaintext e JSON canônico
  conferiram.
- A/B usou duas réplicas por condição, ordens cruzadas, Sol High em todas as
  sessões, prompts selados e os mesmos budgets. A não consultou o índice; cada
  tarefa B começou por `index:query`; traces, contadores e budgets reconciliaram.
- Métricas mecânicas: localização A/B `16/16` e `16/16`; arquivos irrelevantes
  `18` e `12`; recall de testes `0,6042` e `0,6458`; medianas de calls `5` e `8`,
  bytes `24.676` e `30.999,5`, wall `38,907s` e `58,2535s`. B obteve `0/8`
  vitórias de custo. Sol pontuou `resolved` estrito em A `5/16` e B `9/16`.
- Revisão independente Sol **APPROVED** no run
  `SPEC-175-SOL-20261001-V6-01`; evidência em
  `handoffs/SPEC-175-SOL-review-v6.md`.
- Decisão congelada: **remover o Project Index do fluxo/contexto padrão**. O
  código permanece disponível para consultas explícitas e seletivas; todo
  achado continua sujeito à confirmação no source.
- Gate final offline: **1.895 passed, 35 skipped, 15 deselected**; Ruff verde e
  `project_index check` fresco em 5.507 nós/14.056 arestas. Nenhum provider
  pago, cloud ou long-run foi executado.
