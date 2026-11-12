# SPEC-410 — inventário de checkouts request-scoped e de threads

Gerado por AST (`Call` de `*.connection`, sem `admin_connection`) na árvore de produto
(fora de `tests/`, `docs/`, `web/`, `evals/`, `playtest/`), na `main` de 11/11 (`33ac6b58`). A lista versionada
que reprova chamador novo é `CONNECTION_CALLERS` em `tests/test_rls_runtime_config.py`
(`test_todo_chamador_de_connection_esta_classificado`).

Classes: **(a)** sempre com principal (request de usuário); **(b)** sistema puro, passa a usar
`admin_connection`; **(c)** ambíguo, roda sob request E sob worker/cron: coberto pela marca
`system_caller(reason)` no ponto de entrada; **(d)** pool próprio sem `request_rls` (script), o
modo estrito nunca vale.

## Chamadores de `pool.connection()`

| Local | Símbolo | Classe | Tratamento |
|---|---|---|---|
| `api_core.py:520` | `_failed_pending_operation` | a | usa `current_principal()` |
| `routes/art.py:266` | `confirm_player_art` | a | `_image_finance` exige principal |
| `routes/billing.py:477` | `operation_status` | a | `current_principal()` |
| `services/game_transfer.py:120` | `export_game` | a | recebe `Principal` |
| `infrastructure/postgres.py` (7 sites) | `PostgresGameStore.create/get/list/save/delete/save_checkpoint/get_checkpoint` | a | todos recebem `Principal`; worker de projeção abre `principal_scope(owner)` |
| `infrastructure/postgres_turns.py` (9 sites) | `PostgresTurnCoordinator.claim/commit_*/receipt/is_completed/heartbeat/complete/fail` | a | request; `heartbeat` roda na thread `lease-heartbeat` (copia o contexto) |
| `services/chronicle_repository.py:52,203` | `ChronicleRepository.enqueue_due/overlay` | a | request |
| `services/chronicle_repository.py` | `ChronicleRepository.complete` | **b** | **migrado** para `admin_connection(self.pool)`; único chamador `workers/run_worker.py:183` |
| `infrastructure/pgvector_memory.py:141,283,333` | `PgVectorMemoryStore.stage/query/discard_after` | c | request (arquivista/prefetch) e worker (`embed`, `compress_chronicle`, projeção); marca no worker/cron/drain |
| `infrastructure/postgres_catalog.py:33,44,65` | `PostgresRuntimeCatalogStore.get/list/put` | c | `get/list` globais rodam também em worker (`creature_gen`), no cron e **no import de `gamedata.py:126`** (boot, sem principal): marca `boot:gamedata`; `put(global)` já usa `admin_connection` |
| `infrastructure/postgres_jobs.py:105` | `PostgresJobQueue.enqueue` | c | request (enfileira) e worker (encadeia job); marca no entrypoint |
| `infrastructure/postgres_shared_pool.py:76,109,189,210` | `PostgresSharedPoolStore.insert/get/select/count_submissions` | c | request (turno) e cron `/internal/cron/shared-pool`; marca `cron:shared_pool` |
| `scripts/admin_wallet_adjust.py` (3) | `main` | **b** | **migrado** para `admin_connection` |
| `scripts/admin_wallet_reconcile.py` | `main` | **b** | **migrado** |
| `scripts/recover_account_deletions.py` (3) | `claim_pending`, `run_recovery_batch`, `main` | **b** | **migrado** (também chamado pelo cron de exclusão) |
| `scripts/seed_google_play_skus.py` | `main` | **b** | **migrado** |
| `scripts/chaos_test.py` (4), `scripts/load_test.py`, `scripts/verify_restore.py`, `scripts/staging/synthetic_data.py` | `run`, `seed_wallet` | d | `PostgresPool(dsn)` sem `request_rls`; inalterado |
| `infrastructure/db_roles.py:24` | `admin_connection` (fallback para fakes) | — | infraestrutura |

Contagem: 4 sites (a) fora de store + 16 (a) de store + 2 (a) crônica = 22 sites (a); 5 chamadores (b)
(1 método + 4 scripts, 8 sites de script) migrados; 14 sites (c) em 4 módulos; 7 sites (d) em 4 scripts.
Diferença para a contagem preliminar da spec (~24 / 8): o `GameStore` tem 7 e o coordenador 9 sites, e o
catálogo entrou como (c) por causa do boot de `gamedata.py`.

## Pontos de entrada de sistema (`system_caller`)

| Entrypoint | reason | Cobre |
|---|---|---|
| `services/cron_internal.py:_run` | `cron:<task>` | todo `/internal/cron/*` (jobs, operations, account-deletions, reconciliation, finops, shared-pool) |
| `workers/run_worker.py:main` (`_serve`) | `worker` | worker contínuo / `--once` |
| `workers/drain.py:drain_jobs` | `drain` | dreno de jobs (cron e chamadas diretas) |
| `gamedata.py` (import) | `boot:gamedata` | leitura do catálogo global no boot |
| `scripts/pool_promote.py:main` | `script:pool_promote` | promoção do pool (perfil legacy) |

O teste `test_marca_de_sistema_so_nos_pontos_de_entrada` reprova uso da marca fora desta lista. O principal vence a marca:
`workers/projection_jobs.py:69` abre `principal_scope(owner)` por job e continua sob `rpg_api`.

## Threads e contexto (Etapa 0, reexecutado)

`Grep ThreadPoolExecutor|threading.Thread|to_thread|run_in_threadpool|copy_context|ensure_future` em produto:

| Local | Toca banco? | Contexto |
|---|---|---|
| `routes/turn.py:1696` (`contextualize`), `observability/telemetry.py:359` | sim (turno) | copia (conferido) |
| `services/context_prefetch.py:110`, `services/context_sources.py:190,197,218`, `services/creature_gen.py:1460`, `services/encounter_preparation.py:508`, `agents/combat.py:1868`, `llm_setup.py:1659`, `services/jev_rollout.py` | sim (memória/RAG/catálogo) | copiam |
| `services/lease_heartbeat.py:92` | sim (`heartbeat`) | copia; teste `test_lease_heartbeat_thread_inherits_the_request_principal` e novo `..._atravessa_a_thread_do_lease_heartbeat` (marca) |
| `routes/billing.py:279,329` (`run_in_threadpool`), `llm_setup.py:1228` (`asyncio.to_thread`) | sim | copiam |
| **`services/speech_to_text.py:304` (`_run_to_completion`, SPEC-412)** | sim: `finance.begin/admit/finish`, `rate_limiter.consume` | `asyncio.ensure_future(asyncio.to_thread(...))` cria a task com `copy_context()` do request: principal presente. Provado por `test_principal_e_marca_atravessam_threads_do_hosted_em_modo_on` (inclui `run_in_threadpool`) |
| `services/jev_decision.py:417` (`jev-decision-http`) | **não**: só HTTP (`httpx`) | n/a |
| `services/creature_gen_jobs.py:268` (`creature-gen-drain`) | sim (fila em memória do legacy) | **sem propagação**, mas só roda com `api_core._database_profile()` falso (`routes/turn.py:1391`): perfil legacy, sem pool Postgres |
| `scripts/staging/job_survival.py:234`, `smoke_ab.py`, `stt_fallback_smoke.py`, `benchmark_turn_pipeline.py` | scripts de operação | pools diretos (d) |

Nenhuma thread SEM propagação em caminho hosted. `threading.Thread` cru em `on` falha alto (teste), em vez de abrir privilegiado.

## Pendências de medição (precisam do staging, passo do coordenador)

- `/data/*`, `/health`, `/metrics`, webhooks: pela leitura estática não abrem `.connection()` (usam `admin_connection` ou não tocam o banco). Confirmar com `shadow`.
- `load_bestiary`/`_load_npc_db_raw` (catálogo global) são chamados de dentro de turno (principal presente) ou de job (marca). Confirmar com `shadow`.
