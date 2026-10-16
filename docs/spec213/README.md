# SPEC-213 — Arquivista: canônico síncrono, derivados fora do hot path

Status: `done` (revisão Astra independente concluída com correções; smokes browser e real executados).
Rollout segue `inline` por default (P2 aguarda decisão do dono).

## Gate de entrada (§0/P1)

`GO` — ver [gate.md](gate.md). Baseline offline da SPEC-200 (`--mode virtual`, seed 200, 330 turnos
por perfil, 171 com arquivista disparado): `movable_ms` = **59,2 %** do p50 de TTLT (`typical`) e
**57,6 %** (`slow-tail`); p95 4,7 s / 16,9 s. Sem amostra real (a SPEC-200 não executou P5).

## Defaults de decisão usados (§8)

* **P1** ≥ 15 % do p50 ou ≥ 1,5 s p95 — atingido.
* **P2** modo A `post_response` como implementação; **default de rollout segue `inline`** (R11, env
  `RPG_PROJECTION_MODE=inline|post_response`; `job` cai em `inline`). Modo B: nenhum `kind` novo —
  embeddings e compressão da crônica já são jobs.
* **P3** `RPG_PROJECTION_WAIT_SECONDS` = 20 s.
* **P4** selo discreto só na aba Crônica (não há aba "Diário" no frontend atual).
* **P5** derivados da época antiga são cancelados (`epoch_mismatch`).
* **D5** `guard_current_messages`/`validate_narrative` da prosa ao jogador seguem síncronos.

## O que mudou

* `services/projections.py` (novo): `ProjectionState`/`ProjectionEntry`, `stamp_commit` (versão
  canônica monotônica = `max(anterior+1, continuity.session_action_count)`), `reconcile` (R7b),
  `run_pending` (CAS de versão R5/R6, idempotência por `action_id` R8, timeout R10, retry até 3 R12),
  `projection_status_view` (R13), `strip_dead_npc_presence` (R7, só nos derivados adiados),
  `deferral_scope` (janela opt-in; só quem drena sob o lock abre).
* `agents/archivist.py`: com a janela aberta e `_should_archive`, `archive_node` aplica só o canônico
  (eventos, guard da prosa) e devolve `pending_derived` (linha de base: ids dos eventos novos +
  flag de rejeições — nunca texto). `run_derived_projection` reaproveita `_archive_node` (mesmo prompt,
  mesmo LLM SMART) sobre o estado já commitado e revalida contra a evidência canônica ATUAL.
  Sem a janela o caminho é o anterior (inline).
* `api.py`: `stamp_commit` antes do checkpoint/`audit_trace`/commit (SPEC-207 inalterada);
  `_execute_action` drena projeção pendente antes do grafo (R15) e, depois do commit, entrega a
  resposta (SSE: `on_response` → `visual/narrative/state`) e só então drena e regrava o save, sob o
  mesmo `_game_lock` (R9: nenhuma thread nova). `GameResponse.projections` + `/game/state` (R13).
  Leitura sem lock que falhe (save sendo regravado no Windows) é refeita sob o lock.
* `persistence.py`/`state.py`: `projection_state` e `pending_derived` **aditivos, sem bump**
  (`SCHEMA_VERSION` segue 8); save v8 sem a chave nasce `completed` em `session_action_count` (R16).
* `playtest/runner.py`: drenagem determinística após cada turno; `playtest/invariants.py`:
  `projection.ahead_of_canonical` (error) e `projection.failed_streak` (warning).
* `web/src`: selo "atualizando…"/"não atualizado" na Crônica (`aria-live`, sem nova requisição).

## Desvios declarados

1. ~~Perfis com banco ficam `inline`~~ — **resolvido na revisão Astra** (ver "Perfis com banco").
2. **R3 no modo A (legacy):** a cópia `event_log → memória` vai junto com a projeção (o `event_log`
   canônico é salvo no turno; a cópia vetorial é derivada). Em DB (inline) R3 vale como antes.
3. **POST `/game/action`** em `post_response` drena antes de responder (sem ganho; só o SSE ganha).
4. **R7 NPC morto:** `validate_narrative` não tinha regra de NPC morto; criada
   `strip_dead_npc_presence` só para os derivados adiados (inline intocado; evals SPEC-170 inalterados).
5. **R10:** o teto é aplicado ao fim da execução (resultado tardio é descartado como `timeout`);
   a chamada SMART em si é limitada pelo timeout do provider, não interrompida.
6. Telemetria de LLM da chamada adiada não entra na linha `rpg.turn` daquele turno (legacy não tem
   ledger de uso; DB está em inline).

## Testes

* `tests/test_projections.py` (17) e `tests/test_projection_api.py` (9): partição, paridade
  inline×drenado, canônico persistido com derivado falhando, R5/R6/stale, R7 (NPC morto, segredo),
  R7b, R4 monotônico no restore, R8, R10, R16 + round-trip, SSE `done` antes do derivado, queda do SSE
  após `done`, duas ações concorrentes, restart com pendente, status na API, sem thread, troca de jogo.
* SPEC-170 sem edição: `memory_context.jsonl` em `inline` e `post_response` → passed, `compare`
  sem regressões (deltas zero; leak = 0, budget = 0). Observação: a suíte exercita store/retrieve/
  context por adapters, não o caminho de drenagem da API.

* Suíte completa `pytest -q -p no:warnings --ignore=tests/test_project_index.py`: **exit 0**,
  3082 passed, 175 skipped, 0 falhas. Ruff limpo nos arquivos tocados. `npm run build` verde.
* Playtest offline `RPG_PROJECTION_MODE=post_response`, 14 perfis × 30 turnos (run
  `20261016-101947-109331`): 0 erros, 0 violações (inclui `projection.ahead_of_canonical`), 0 falhas
  de projeção no log.

## TTLT inline × post_response (harness SPEC-200, mesmo dataset/seed)

`--mode virtual` não serve para esta comparação: o relógio virtual é compartilhado e a chamada SMART
adiada (em outra thread) avança o relógio antes do `ttlt` do gerador. Medido em `--mode scaled
--scale 0.1` (sleep real; ms ×10 ≈ escala da injeção), 6 jornadas × 10 reps, N = 110 por run:

| Perfil | Modo | TTLT p50 | TTLT p95 | lock_wait p95 |
|---|---|---|---|---|
| `typical` | inline | 735 | 1013 | 0 |
| `typical` | post_response | 482 (−34 %) | 1110 (+10 %) | 457 |
| `slow-tail` | inline | 802 | 2020 | 0 |
| `slow-tail` | post_response | 780 (−3 %) | 2181 (+8 %) | 641 |

Leitura sem otimismo: o p50 cai onde o arquivista dispara com frequência; o p95 piora porque o
harness envia a próxima ação imediatamente e ela espera a projeção no lock (R10). Com um jogador
humano (tempo de leitura > projeção) essa espera tende a zero, mas isso **não** foi medido.
Modo `inline` com o código novo reproduz os `summary.json` do baseline byte a byte (sha256 iguais).

## Perfis com banco (revisão Astra, 2026-10-16)

* **Outbox (R9b):** `commit_game` enfileira `project_archive` (`dedupe_key` R8
  `{game}:{epoch}:archive:{action_id}`, payload só ids) na MESMA transação; restore (época nova) cancela os
  jobs `queued/retry` da época antiga (`epoch_mismatch`, R7b).
* **Modo A em DB:** após entregar a resposta (fora da cerca do turno, cujo heartbeat não pode mais falhar a
  request), a API arrenda o PRÓPRIO job (`PostgresJobQueue.lease_key`) e o executa com `JobWorker.run_leased`
  (lease/fence/retry normais; nenhuma thread nova). Uso de LLM vai para operação `archive_projection`
  (migration `20261016121500_archive_projection_operations.sql`, aplicada só no Postgres local).
* **Apply (`workers/projection_jobs.py`):** lê o documento, aborta sem LLM se há turno com lease vigente,
  executa o derivado fora de transação e publica com CAS (`version` igual + jogo ocioso + `require_job_fence`);
  conflito → `projection_stale` (retry com backoff); falha retentável → `projection_failed`. Memória staged
  só é publicada no sucesso (ids determinísticos, `on conflict do nothing`).
* **Próximo turno (R10/R15):** se o job está `running`, espera até `RPG_PROJECTION_WAIT_SECONDS` e relê;
  senão drena a pendência DENTRO da própria cerca (memória e custo no commit do turno) antes de a ação nova
  entrar no histórico. Worker parado → fallback modo A. Registrado em `workers/run_worker.py`.
* Hosted/Vercel: POST drena antes de responder; SSE pode congelar após `done` → o job expira e o cron
  `/internal/cron/jobs` ou o próximo turno concluem.

## Achados e correções da revisão Astra

1. **DB não implementado** (critério §5 `infra_local`) → implementado acima.
2. **Baseline perdida:** projeção que falhou e aguarda retry era sobrescrita pelo plano do turno seguinte
   (eventos do turno antigo sumiam da memória) → `archive_node` une as linhas de base.
3. **Duplicação no timeout (R8):** o executor não é interrompível; no timeout a memória FAISS já estava gravada
   e o retry duplicava fatos → timeout marca `failed` e NÃO reexecuta.
4. **R4 frágil:** o restore só preservava `canonical_version` se `session_action_count` andasse 1:1 →
   `carry_over_restore` herda a versão viva e cancela a projeção da época antiga (chamado em `checkpoints`).
5. Verificado sem achado: `validate_narrative`/guard da prosa síncronos (D5); derivado roda sobre o estado
   commitado e é revalidado contra a evidência canônica atual (R7); dois turnos rápidos serializam no lock /
   na cerca; SSE cortado após `done` conclui; troca de jogo não redireciona; save/reload round-trip.
6. Limite aceito: o selo da Crônica fica "atualizando…" até a próxima resposta ou recarga (R13 proíbe nova
   chamada de rede); leituras sem lock em outros endpoints legacy seguem o risco pré-existente do Windows.

## Testes (revisão)

* `tests/test_projections.py` +3 (baseline unida, timeout sem retry, restore herda versão);
  `tests/test_projection_db_local.py` (novo, `infra_local`): outbox na mesma transação, CAS+idempotência,
  conflito → `projection_stale`, fence velho rejeitado, turno ativo bloqueia apply (dois clientes), restore
  cancela jobs, worker parado → fallback na cerca, API executa o próprio job + operação `archive_projection`,
  e2e HTTP perfil `local` (Auth+Postgres reais, SSE 3 turnos, jobs `succeeded`, 3 linhas em `app.turns`).
* infra_local afetados (jobs, recovery, reclaim, crash, multiworker, crônica, restore pgvector, migration): verdes.

## Suíte final (revisão)

* `pytest -q -p no:warnings --ignore=tests/test_project_index.py`: **exit 0**, 3085 passed, 184 skipped, 0 falhas
  (1ª execução teve 2 flakes de timing/leitura Windows fora do escopo — SSE hardening e Jev deadline —, verdes
  isolados e na reexecução). Ruff limpo nos arquivos tocados; `npm run build` verde.

## Smokes

* **Browser** (Chromium 1440 px, API legacy MockLLM, `post_response`, 6 turnos SSE): narração visível com o selo
  "atualizando…" logo após cada stream, servidor `completed` em seguida; após recarga o selo some
  (`completed`). 0 erros de console/página.
* **Real** (8 turnos DeepSeek `deepseek-v4-flash`, saves isolados, embeddings desligados, `.env` copiado e
  removido): 27 tentativas de rede, **US$ 0,032 est.** (rate card conservador). Turnos 2–8: TTLT p50 6,7 s /
  máx 16,1 s; projeção concluída p50 11,3 s / máx 20,6 s; tempo tirado do caminho do jogador p50 3,8 s
  (2,6–4,7 s). Resposta sempre `pending`, save `completed` com `projected == canonical`. Sem amostra real da
  SPEC-200 para comparar; turno 1 teve timeouts DeepSeek (fallback do produto).

## Conflitos prováveis ao integrar na `main` (203/204/207/221/223)

* `web/src/components/Hud.tsx`: SPEC-204 removeu o `Hud` com abas; `ChronicleTab` é exportado e montado em
  `web/src/workspace/ContextSurface.tsx` → manter o prop `projectionStatus` e passá-lo lá.
* `api.py` (SPEC-221 alterou ~200 linhas): conferir `_execute_action`, `_run_turn*`, `_stream_turn_events`,
  `get_current_state`. `styles.css` também mudou na 204. archivist/persistence/state sem mudanças na main.

## Pendências

* Decisão de rollout (`inline` → `post_response`) pelo dono; aplicar a migration nova no staging no deploy.
