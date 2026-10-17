# SPEC-213 — Arquivista: canônico síncrono e projeções derivadas fora do hot path

> **Status:** `done` — gate §0 atingido em 2026-10-16 (offline, ver `docs/spec213/gate.md`); modo A **17/10:** migration `20261016121500_archive_projection_operations.sql` aplicada no staging (default segue `inline`; nada ativado).
> (`post_response`) em legacy e perfis com banco (outbox `project_archive` em `app.jobs` + execução pela própria
> API após responder; worker/cron e o próximo turno na cerca como fallbacks); revisão Astra independente com
> correções; smokes browser (Chromium 1440) e real (8 turnos DeepSeek, US$ 0,032 est.) executados — evidência em
> `docs/spec213/README.md`. Defaults §8: P1–P5 recomendados; **rollout segue `inline`** (P2 aguarda o dono).
> **Nota de schema (execução 2026-10-16):** sem bump — `projection_state`/`pending_derived` são campos
> aditivos com default no load (regra da onda: `SCHEMA_VERSION` fixo em 8); onde a spec diz "v8→v9", leia
> "normalização aditiva idempotente".
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-16
> **Depende de:** SPEC-200 `done` (baseline/gate), SPEC-228 `done` (ordem save/checkpoint), SPEC-234 `done` (hot path do arquivista corrigido) · referências `done`: SPEC-093, SPEC-107, SPEC-111, SPEC-124, SPEC-170, SPEC-192 (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-214 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 10
> **EXECUTOR_MODEL:** `Sol` (≡ Opus, ver `docs/planos/equivalencia-modelos-claude.md`)
> **REVIEW_MODEL:** `Astra` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` — usa as suítes da SPEC-170 (`memory_write`, `memory_retrieval`, `context_grounding`, `generation_boundary`) como regressão, **sem editá-las**. Os testes novos de corrida/restart são testes unitários/integração do produto, não datasets de eval.
> **Nota de schema (cadeia final 2026-10-15):** ordem dos bumps de `SCHEMA_VERSION` (hoje 8): SPEC-228 primeiro (R9 recusa save de versão mais nova; sem bump) → [SPEC-227 só se D-C = migração; default sem bump] → SPEC-202 → SPEC-203 → SPEC-207 → SPEC-213 → SPEC-215. Nenhuma outra spec 199–236 altera o schema de save (SPEC-228 R7 `needs_replan` e SPEC-231 `scene_allies` usam default/campo existente, sem bump). Cada spec usa o próximo `SCHEMA_VERSION` livre no HEAD ao implementar e encadeia sua migração após a anterior; onde o texto disser "v8→v9", leia "vN→vN+1".

Rótulos: **[F]** fato observado no HEAD `6b94f66` · **[D]** decisão de produto fechada · **[H]** hipótese técnica · **[R]** recomendação.

---

## 0. Gate de entrada (draft → approved)

Esta spec **não sai de `draft`** sem evidência da SPEC-200. O gate é numérico e
pré-registrado (limiar é decisão do dono, seção 8, **P1**):

- **[R]** Aprovar somente se, no baseline offline repetível da SPEC-200 (MockLLM, `--mode virtual`,
  perfis `typical` e `slow-tail`) **e** na amostra real opt-in que a SPEC-200 tiver medido, a
  **parte movível** `movable_ms = phase_ms.archivist − archivist_validate_ms` (campos da linha
  `rpg.turn` definidos pela SPEC-200 R4/R5; `process_pending_events` fica no lado síncrono e, se a
  SPEC-200 não o separar, o valor é tratado como **limite superior** e declarado assim) representar
  **≥ 15 % do p50 de `ttlt_server_ms`** **ou** **≥ 1,5 s no p95** de `ttlt_server_ms`, nos turnos em
  que `_should_archive` disparou. Fórmula, N e perfis gravados em `docs/spec213/gate.md`.
- Abaixo do limiar a spec é arquivada como `draft` com nota "não justificado pelo baseline"; o
  pacote já admite que o ganho pode ser pequeno se o gargalo for o LLM narrativo.
- O gate mede a **parte movível** (derivados), não o nó inteiro: canônico permanece síncrono
  (§2), então só conta o tempo de resumo/crônica/escrita de memória derivada.
- **[F]** Hoje o SSE é pseudo-streaming (SPEC-200 §1: o primeiro `narrative` sai depois do
  archivist), então o ganho de TTFMC e de TTLT é o mesmo `movable_ms`; o relatório usa os nomes da
  SPEC-200 (`ttfmc_server_ms`, `ttlt_server_ms`), não "TTFT".

## 1. Contexto & Objetivo

**[F]** O grafo termina em `… → archivist → turn_finalizer → END` (`main.py:136-137`). O
`archive_node` (`agents/archivist.py:200`) roda inline em todo turno e faz, nesta ordem:
`process_pending_events` (`services/event_processor.py:208`, aplica `pending_world_events` em
`event_log`/`world_projection`), `guard_current_messages` e `build_evidence`
(`services/narrative_evidence.py:113/38`), e então `_archive_node` (`agents/archivist.py:236`),
que — quando `_should_archive` (`:183`) é verdadeiro (evento relevante, `conflict_summary`,
memória pendente, ou a cada `_ARCHIVE_EVERY = 10` turnos) — chama `get_llm(tier=SMART)`
(`:639`) para `narrative_summary`, fatos de memória e `chronicle_entry`, persiste memória
(`_persist_memory_records`, `add_npc_memory`) e anexa prosa à crônica. Depois revalida
`narrative_summary` e a prosa da crônica com `validate_narrative(..., channel='summary'|'chronicle')`.
`turn_finalizer_node` (`agents/turn_finalizer.py`) chama `guard_current_messages` de novo,
verifica `transition_readiness` e grava `last_turn_outcome`.

**[F]** Já existe infraestrutura assíncrona: `app.jobs` (migration `20260819001850_operations_jobs.sql`,
`unique(kind, dedupe_key)`, estados `queued|running|succeeded|retry|dead|cancelled`),
`infrastructure/postgres_jobs.py`, `workers/` (`job_worker.py`, `drain.py`, `embedding_jobs.py`,
`chronicle_jobs.py`, `dynamic_art_jobs.py`), `services/job_fence.py`, `services/lease_heartbeat.py`,
`services/memory_retry.py`, `services/operation_recovery.py`. Em perfil DB, `add_memory_to_session`
(`rag.py:985`; staging em `rag.py:1020`) só faz `store.stage(...)`; o `PgVectorMemoryStore` grava o documento e enfileira
`embed_memory` na mesma transação do commit (`infrastructure/pgvector_memory.py:~106`). A
compressão de crônica é agendada por `api._schedule_chronicle_jobs` (`api.py:2899`), no-op fora
de perfil DB (`_database_profile()`, `api.py:87`). No perfil `legacy`, memória vai a FAISS inline
e turnos do mesmo jogo são serializados por `_game_lock` (`api.py:640`).

**[F]** Lacunas: não há separação explícita canônico × derivado, nem versão/cursor de
projeção, nem estados `pending/stale` visíveis à API/UI. O Codex do jogador **não** é
produzido pelo arquivista: é calculado na leitura (`services.discovery.player_codex`,
`api.py:1937`); bestiário progressivo idem via `services/bestiary_knowledge.py`.

**Objetivo:** o jogador recebe a narração validada sem esperar resumo/crônica/memória derivada,
**sem** que nenhum fato canônico deixe de estar persistido ao fim do turno e sem que o próximo
turno leia derivado inconsistente com o canônico.

## 2. Requisitos

**Partição canônico × derivado**

- **R1** — **[D] D5** Permanecem **síncronos e persistidos antes do evento final do turno**:
  `process_pending_events` (eventos, morte, relação, consumo, combate, presença, reveal de
  segredo), `guard_current_messages` e `validate_narrative` sobre a prosa entregue ao jogador,
  `turn_finalizer` e `last_turn_outcome`. Teste: com o executor de derivados forçado a falhar,
  `event_log`, `world_projection`, NPC morto, relação e item consumido do turno estão no save.
- **R2** — São **derivados** e podem rodar após a resposta: `narrative_summary`, fatos de memória
  extraídos pelo LLM do arquivista (sessão e NPC), entrada de prosa da crônica, compressão da
  crônica e embeddings. Codex/bestiário continuam calculados na leitura (sem mudança).
- **R3** — A cópia de `event_log` para memória (`_event_memory_records`) continua síncrona no
  perfil DB (staging na transação do commit, como hoje); só o embedding é job.

**Versão e estados**

- **R4** — Todo save carrega `projection_state` com `canonical_version` (int monotônico,
  incrementa 1 por turno commitado; **nunca** decresce, nem em restore de checkpoint — não usar
  `world.turn_count`, que volta no rollback [F] `api.py:1261-1280`), `timeline_epoch` (cópia de
  `continuity.timeline_epoch`, SPEC-102) e, por projeção (`summary`, `memory`, `chronicle`), o
  `projected_version` e `status ∈ {pending, completed, failed, stale}`, `action_id`, `attempts`,
  `last_error_code`.
- **R5** — Um derivado calculado a partir do snapshot `v` só é aplicado se `v ≥ projected_version`
  atual da projeção; aplicação com `v < projected_version` é descartada (idempotência e ordem).
  Quando `canonical_version > v` no momento de aplicar, o status final é `stale` (aplicado, mas
  já existe turno mais novo pendente) e uma nova projeção para a versão mais recente é agendada.
- **R6** — **Nunca derivado mais novo que canônico:** `projected_version ≤ canonical_version`
  é invariante (assert no apply e invariante de playtest nova `projection.ahead_of_canonical`).
- **R7** — **Sem reintrodução:** antes de aplicar `narrative_summary`/prosa de crônica derivados,
  roda `validate_narrative` contra o `build_evidence` do **estado canônico atual** (não do
  snapshot); NPC morto/segredo não revelado no canônico atual é removido mesmo que o snapshot
  antigo o permitisse.
- **R7b** — **Rollback de linha do tempo.** Restore de checkpoint/`resolve_death_choice` (que
  incrementa `continuity.timeline_epoch`, [F] `services/checkpoints.py:127`) cancela toda projeção
  `pending/stale` da época anterior; um derivado calculado em época `e` nunca é aplicado a estado
  de época `e' ≠ e` (descartado com `last_error_code="epoch_mismatch"`). No perfil DB, jobs
  `project_archive` da época antiga terminam `cancelled`. Teste:
  `test_restore_cancels_pending_projection_of_old_epoch`.
- **R8** — Idempotência por `action_id`: reexecutar a projeção do mesmo `action_id` não duplica
  memória (FAISS ou `app.memory_documents`), crônica nem rejeições (`dedupe_key =
  f"{game_id}:{timeline_epoch}:{projection}:{action_id}"`).

**Execução**

- **R9** — **Proibido** fire-and-forget em thread/`asyncio.create_task` sem dono durável. Toda
  execução de derivado ocorre: (a) dentro do lock/operação do turno antes de liberá-lo (modo A),
  ou (b) como job em `app.jobs` gravado na mesma transação do commit do turno (modo B).
- **R10** — Perfil `legacy` (sem worker): modo A obrigatório; o próximo turno do mesmo
  `game_id` aguarda a projeção pendente (mesmo `_game_lock`) com teto
  `RPG_PROJECTION_WAIT_SECONDS` (default 20 s); estourou → status `failed`, turno prossegue com
  o derivado anterior.
- **R11** — Modo `inline` (comportamento atual, byte a byte) permanece disponível e é o
  default até aprovação do rollout (`RPG_PROJECTION_MODE=inline|post_response|job`).
- **R12** — Falha do derivado nunca derruba o turno nem apaga o canônico; `failed` é retentado
  no próximo turno (modo A) ou pelo `JobWorker` com backoff (modo B), reaproveitando
  `memory_retry` para memória de NPC.

**API / UI**

- **R13** — `GET /game/state` e o evento final SSE expõem `projections: {summary, memory,
  chronicle: {status, projected_version}}, canonical_version` (só status; nunca conteúdo
  privado). Menus Crônica/Diário exibem selo "atualizando…" para `pending`/`stale` e "não
  atualizado" para `failed`.

**Robustez**

- **R14** — Corrida: duas ações rápidas no mesmo jogo → a 2ª lê canônico do turno 1 completo;
  derivados aplicados na ordem de versão; zero duplicação. SSE cortado após `done` não perde
  a projeção. Dois clientes no mesmo save (perfil DB) → `operations` + fencing existentes
  rejeitam/serializam; nenhum apply com fence velho. Troca de jogo/sessão no cliente durante o
  stream: a projeção pertence ao `game_id` do turno (capturado no início), nunca ao jogo ativo no
  cliente; trocar de jogo não cancela nem redireciona a projeção (teste
  `test_switch_game_mid_stream_projection_stays_with_origin`).
- **R15** — Restart: processo morto com projeção `pending` → no load, `pending` com
  `projected_version < canonical_version` é reagendado (modo A: no início do próximo turno;
  modo B: job continua na fila; `operation_recovery` cobre leases expirados).
- **R16** — Save/load: `projection_state` round-trip; saves `schema_version` 8 (ou anteriores
  migráveis) carregam com `projection_state` inicializado `completed` em
  `canonical_version = continuity.session_action_count` (monotônico, SPEC-102;
  [F] `services/continuity.py:13-30`) e `timeline_epoch = continuity.timeline_epoch`.

### Fora de escopo

- Mover `validate_narrative`/`guard_current_messages` da prosa ao jogador para fora do hot path (D5).
- Streaming real de tokens (D3, avaliado após SPEC-200).
- Cache de cena / hierarquia de memória (SPEC-214).
- Mudar o grafo de fan-out (`RPG_TURN_EXECUTION`, SPEC-143 NO-GO).
- Alterar evaluator/expected/dataset da SPEC-170 ou criar datasets novos.
- Novas tabelas Postgres além de colunas/`kind` necessários; Codex/bestiário (já on-read).

## 3. Design técnico

### 3.1 Comparação de alternativas

| Critério | **A** pós-resposta, antes do próximo turno (in-process) | **B** job + outbox em `app.jobs` | **C** incremental (delta por turno) |
|---|---|---|---|
| Ganho de TTLT percebido | Total (resposta sai antes do resumo) | Total | Parcial (ainda há LLM, menor) |
| Durabilidade em crash | Perde o trabalho; recuperável por R15 (reagenda) | Durável (outbox na transação do commit) | Igual ao modo que hospedar |
| Funciona em `legacy` sem worker | Sim | Não | Sim |
| Funciona em Vercel serverless (SPEC-192) | **[H]** Só via SSE: gerador continua após o evento `done` até concluir; POST não | Sim, via `/internal/cron/jobs`; latência = cadência do cron **[H]** | — |
| Risco de corrida | Baixo (lock do turno segura) | Médio (precisa versão/fence; R5–R7) | Médio |
| Complexidade | Baixa | Média (infra existe) | Alta (resumo incremental muda prompt/qualidade) |

**[R]** Recomendação: **A como padrão em todos os perfis** (`post_response`) + **B apenas para
derivados já assíncronos ou caros e retentáveis** (embeddings e compressão de crônica, que já são
jobs; opcionalmente o resumo SMART em perfil DB quando o worker estiver saudável). **C fica fora**
(muda a qualidade do resumo; reavaliar após SPEC-214). Critérios: (1) zero perda de canônico,
(2) ganho medido no TTLT ≥ ao limiar do gate, (3) nenhuma reintrodução de NPC morto/segredo nos
testes R7/R14, (4) `legacy` sem worker continua funcional.

### 3.2 Arquivos

- **Novo** `services/projections.py` — `ProjectionState`/`ProjectionEntry` TypedDicts,
  `split_archive(state) -> tuple[dict, DerivedPlan]`, `apply_derived(state, plan_result) -> dict`,
  `projection_status_view(state) -> dict`, `pending_projections(state) -> list[str]`.
- **Alterado** `agents/archivist.py` — `archive_node` passa a executar só o canônico (R1/R3) e,
  conforme `RPG_PROJECTION_MODE`, ou chama `_archive_node` inline (modo `inline`, idêntico ao
  atual) ou devolve `pending_derived: DerivedPlan` serializável (snapshot mínimo: mensagens do
  turno, resumo atual, `action_id`, `canonical_version`). `_archive_node` é reaproveitado como
  executor do derivado, sem mudança de prompt.
- **Alterado** `api.py` — após o commit/`_require_saved` e após emitir o evento final SSE/montar a
  resposta POST: executa `run_pending_projection` sob o mesmo lock/operação (modo A), salva de novo
  com `projection_state` atualizado. No início de cada turno: se houver `pending` (R10/R15),
  executa/aguarda antes do grafo. Expõe `projections` em `GameResponse` e `/game/state` (R13).
- **Alterado** `infrastructure/postgres_turns.py` (`commit_game`) — modo B: enfileira
  `kind='project_archive'`, `dedupe_key` de R8, na transação do commit.
- **Novo** `workers/projection_jobs.py` + registro em `workers/run_worker.py:build_handlers` —
  carrega estado sob `require_job_fence`, aplica R5–R7, faz commit de projeção com checagem de
  `canonical_version` (compare-and-set; conflito → `stale` + reagenda).
- **Alterado** `persistence.py` — `SCHEMA_VERSION` 8 → 9 ([F] hoje `= 8`), migração
  `_migrate_v8_to_v9` com default de R16.
- **Alterado** `state.py` — campos `projection_state`, `pending_derived` (transitório; não exposto).
- **Alterado** `playtest/runner.py` + `playtest/invariants.py` — drenagem determinística das
  projeções após cada turno (paridade com `inline`) + invariante `projection.ahead_of_canonical`
  (`error`) e `projection.failed_streak` (`warning`, ≥3 turnos).
- **Alterado** `web/src` (Crônica/Diário) — selo de status (R13); sem nova chamada de rede.

### 3.3 Schemas

```python
class ProjectionEntry(TypedDict):
    status: Literal["pending", "completed", "failed", "stale"]
    projected_version: int
    action_id: str | None
    attempts: int
    last_error_code: str | None   # código fechado, nunca texto do provider

class ProjectionState(TypedDict):
    canonical_version: int        # monotônico; nunca volta em rollback
    timeline_epoch: int           # = continuity.timeline_epoch no último commit
    summary: ProjectionEntry
    memory: ProjectionEntry
    chronicle: ProjectionEntry
```

Contrato API (adição, retrocompatível): `"projections": {"canonical_version": 42, "summary":
{"status": "pending", "projected_version": 41}, ...}`.

### 3.4 State ownership

- Canônico: dono = grafo do turno (`event_processor`, agentes, `turn_finalizer`); escrito só no commit do turno.
- `narrative_summary`, `chronicle[*].entries[kind=prose]`, `memory_facts`/`pending_memory_facts`: dono = executor de projeção; escrito só via `apply_derived` com CAS de versão.
- `projection_state.canonical_version`: incrementado só no commit do turno.

### 3.5 Degradação

Falha/timeout do derivado → `failed` + derivado anterior mantido; contexto do próximo turno usa
canônico + último resumo válido. Worker parado (modo B) → jobs acumulam; ao detectar
`pending` mais velho que `RPG_PROJECTION_WAIT_SECONDS`, a API executa o derivado em modo A
(fallback). LLM em `FallbackLLM` → o guard já existente de `_archive_node` cai no texto plano.

## 4. Plano passo a passo (TDD)

### Etapa 1 — Partição e paridade
1. **Testes** (`tests/test_projections.py`): `test_inline_mode_byte_identical` (mesmo estado
   final que o HEAD para 3 turnos MockLLM); `test_canonical_persisted_when_derived_fails`
   (R1); `test_split_classifies_fields` (R2/R3).
2. **Implementação:** `services/projections.py`, refatorar `archive_node` atrás da flag.

### Etapa 2 — Versão, estados, migração
1. **Testes:** `test_apply_rejects_older_version` (R5), `test_never_ahead_of_canonical` (R6),
   `test_stale_reschedules` (R5), `test_restore_cancels_pending_projection_of_old_epoch` (R7b),
   `test_canonical_version_monotonic_across_restore` (R4), `test_v8_save_loads_with_completed_projection` e round-trip (R16).
2. **Implementação:** `ProjectionState`, migração v9.

### Etapa 3 — Guard de reintrodução
1. **Testes:** `test_dead_npc_not_reintroduced_by_stale_summary`,
   `test_unrevealed_secret_stripped_at_apply` (R7).
2. **Implementação:** `apply_derived` revalida contra `build_evidence(estado atual)`.

### Etapa 4 — Modo A na API
1. **Testes** (`tests/test_projection_api.py`): `test_sse_done_before_summary`,
   `test_two_rapid_actions_serialize` (R14), `test_sse_drop_after_done_completes_projection`,
   `test_restart_pending_rescheduled` (R15), `test_idempotent_by_action_id` (R8),
   `test_wait_timeout_marks_failed` (R10), `test_state_exposes_projection_status` (R13),
   `test_no_thread_spawn` (R9: monkeypatch `threading.Thread.start` falha se chamado pelo módulo).

### Etapa 5 — Modo B (perfil DB, `infra_local`)
1. **Testes** (`-m infra_local`): `test_commit_enqueues_project_archive_in_same_tx`,
   `test_job_apply_cas_conflict_marks_stale`, `test_stale_fence_rejected`,
   `test_worker_down_falls_back_to_mode_a`.

### Etapa 6 — Playtest/UI
1. Invariantes novas + drenagem; selo na UI; `npm run build`.

## 5. Critérios de aceite

- [x] `docs/spec213/gate.md` com `movable_ms`, N, perfis e decisão P1; gate de entrada (§0) registrado com números da SPEC-200 na aprovação.
- [x] R1–R16 (incl. R7b) cobertos pelos testes nomeados; `uv run pytest` verde (números finais e desvios em `docs/spec213/README.md`).
- [x] Regressão SPEC-170 sem edição: `uv run python -m evals --root . run --dataset datasets/regression/memory_context.jsonl --run-id spec213-<modo>` (suítes `memory_write`, `memory_retrieval`, `context_grounding`, `generation_boundary`) em `inline` e `post_response`, com deltas zero nos hard gates (leaks = 0, budget = 0) via `python -m evals compare`.
- [x] `uv run pytest -m infra_local` verde para Etapa 5 (`tests/test_projection_db_local.py`: 8 + e2e HTTP opt-in no perfil `local`; demais infra_local afetados verdes).
- [x] TTLT p50/p95 medido com o harness da SPEC-200 nos modos `inline` vs `post_response`; ganho reportado sem otimismo (mesmo dataset/seed).
- [x] Playtest offline 14 perfis × 30 turnos: zero `projection.ahead_of_canonical`, zero erro.
- [x] Saves v8 carregam; round-trip (campo aditivo, sem bump — regra da onda).
- [x] Nenhum `with_structured_output` novo (se houver, guard FallbackLLM).

## 6. Smoke

Offline (padrão): `uv run pytest tests/test_projections.py tests/test_projection_api.py`;
`uv run python -m playtest run --all --turns 30` com `RPG_PROJECTION_MODE=post_response`.
Browser: Chromium 1440 px, 3 turnos SSE, confirmar narração antes do selo "atualizando…" sumir.
Real (opt-in, autorização explícita, teto 30 requests / US$ 0,05): 10 turnos DeepSeek em
`post_response`, comparando TTLT com a amostra real da SPEC-200.

## 7. Riscos & compatibilidade

- **Saves:** migração v8→v9 aditiva; v9 lido por código antigo não existe (sem downgrade).
- **Prosa não validada:** eliminado por D5 — só derivados saem do hot path.
- **[H] Vercel:** POST síncrono não pode continuar após resposta; em hosted, modo A só via SSE
  (cliente principal) e POST cai em `inline` ou B. Validar no staging antes de habilitar.
- **Resumo defasado no contexto:** o próximo turno pode usar resumo de `v-1`; mitigado por R7 e
  por o contexto já priorizar canônico; medir com SPEC-170 `context_grounding`.
- **Custo:** nenhum request a mais; jobs reaproveitam ledger `usage_events` (SPEC-182).
- **MockLLM:** esconde campos do resumo; smoke real opt-in cobre.

## 8. Pontos de decisão do dono

- **P1 — Limiar do gate.** Default [R]: ≥ 15 % do p50 do TTLT **ou** ≥ 1,5 s p95 da parte movível.
- **P2 — Modo padrão após aprovação.** Default [R]: `post_response` (A) em todos os perfis; B só
  para embeddings/compressão (já existentes). Alternativa: resumo SMART também como job em DB.
- **P3 — Espera máxima do próximo turno por projeção pendente.** Default [R]: 20 s, depois `failed`.
- **P5 — Época no rollback.** Default [R]: cancelar derivados da época antiga (R7b); alternativa (reaplicar o resumo antigo como base) é rejeitada por risco de reintroduzir fato desfeito.
- **P4 — Exibir status de projeção na UI.** Default [R]: selo discreto só em Crônica/Diário; nada no chat.

## 9. Evidência requerida

`docs/spec213/README.md` com: números do gate (SPEC-200) e decisão P1; saída de `uv run pytest`
e `-m infra_local`; resultado das suítes SPEC-170 (hashes de dataset inalterados); tabela TTLT
inline × post_response (offline e, se autorizado, real) com N, p50, p95; summary do playtest
30 turnos; parecer Astra independente.
