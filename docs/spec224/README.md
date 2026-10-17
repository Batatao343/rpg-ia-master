# SPEC-224 — RLS efetivo, role de menor privilégio e Storage sem escrita do cliente

Status: **in-progress** — código, migration e testes locais prontos; faltam os critérios de staging (abaixo).

## O que mudou
- **Request de usuário** (`pool.connection()` com principal ativo): `SET LOCAL ROLE rpg_api` +
  `set_config('request.jwt.claim.sub'/'request.jwt.claims', …, true)` no início da transação
  (`infrastructure/postgres.py::_apply_request_role`). Um `select`/`update`/`delete` sem `WHERE owner_id`
  só enxerga/altera linhas do owner; `insert` para outro owner falha por policy.
- **Sistema** (`admin_connection(pool)` em `infrastructure/db_roles.py`): worker, cron, wallet, rate limit,
  ciclo de conta, reconciliação, FinOps, kill switch, identidade, agregados cross-owner. Usa o **pool admin**
  (`RPG_ADMIN_DATABASE_URL`, login `rpg_admin`) e **nunca** troca de role. Sem admin pool = mesmo pool, sem role (R9).
- **Config** (`RuntimeConfig`): `RPG_ADMIN_DATABASE_URL`, `RPG_REQUEST_RLS` (default `on`). Em `hosted*` com RLS ligado:
  admin DSN obrigatório, usuário diferente do de request, e o de request não pode ser `postgres`/`supabase_admin`.
  `local`/`portable`: DSN único continua válido (role switch ligado).
- **Migration `20261017120000_rls_effective_storage_no_client_write.sql`**: cria `rpg_admin` (LOGIN, sem BYPASSRLS,
  grants + policy permissiva `admin_all`, paridade com `rpg_runtime`), reafirma o contrato das roles (aborta se
  alguma virar superuser/BYPASSRLS), `grant usage on schema extensions to rpg_api` (consulta pgvector sob `rpg_api`) e
  **remove as 4 policies de Storage** `rpg_dynamic_*_own` (D-B default: RLS sem policy = deny; backend usa service role).
- Perfil de embedding: criado no boot por `PgVectorMemoryStore.ensure_profile()` (admin); no request só lê.
- Staging tooling: `runtime_role.py --role rpg_runtime|rpg_admin`; `vercel_env.py` exige `RPG_ADMIN_DATABASE_URL`
  quando usa o DSN do `rpg_runtime` e, no rollback/sem roles, envia `RPG_REQUEST_RLS=off`; `cloud_doctor` reporta
  `request_rls`, `RPG_ADMIN_DATABASE_URL` (present/missing) e `runtime_db_role` (classe, nunca DSN).

## Inventário R5 (user x admin)
| Classe | Módulos |
|---|---|
| **user** (`rpg_api`, RLS por owner) | `postgres.py` (games/checkpoints/events), `postgres_turns.py::PostgresTurnCoordinator` (games/operations/turns/assets/jobs), `postgres_catalog.py` (leitura; escrita `user`/`game`), `pgvector_memory.py` (memory_documents), `postgres_jobs.py::enqueue`, `chronicle_repository.py`, `game_transfer.py`, `api.py` (3 consultas em operations/art_generations) |
| **admin** (`rpg_admin`, sem role switch) | `postgres_turns.py::PostgresRateLimiter`, `postgres_jobs.py` (lease/complete/fail/…), `postgres_catalog.put(scope="global")`, `pgvector_memory` (profile/migrate/set_embedding), wallet, usage_events, image_quotes, dynamic_art, account_lifecycle, account_read_model, audit_source, finops_reader, kill_switch_store, reconciliation, stripe/google_play, speech_finance, supabase_blob/identity, operation_recovery, wallet_recovery, retention, workers/*, `api.py` (3: métricas cross-owner, retry de exclusão, wallet join) |

Desvio da spec (R5): `image_quotes`, `usage_events` e `account_read_model` ficam no pool de **sistema**. Eles tocam
`wallet_*`/`kill_switches`, que por desenho (migrations de wallet/FinOps) `rpg_api` não acessa; o filtro por owner
continua em Python, como antes. O teste `tests/test_rls_runtime_config.py` trava essa classificação (AST): módulo de
sistema nunca abre conexão de request, e todo módulo novo que abra conexão precisa ser classificado.

## Testes
- `tests/test_rls_effective.py` (`infra_local`, Postgres local): isolamento cross-owner com o pool real
  (`select` sem filtro, `update`/`delete` de outro owner = 0 linhas, `insert` de outro owner bloqueado), role não vaza entre
  conexões reaproveitadas, `RPG_REQUEST_RLS=off`, admin pool, e um runtime completo (`build_database_runtime`) com
  game store/catálogo/fila/rate limit sob `rpg_api` + worker no pool admin.
- `tests/test_rls_runtime_config.py` (offline): validação de credenciais, roteamento user/admin, inventário AST.
- `supabase/tests/rls_effective_storage_test.sql` (pgTAP, 16 asserts): roles, grants, storage sem escrita/leitura do cliente.
- `RPG_TEST_REQUEST_RLS=1` (em `tests/conftest.py`): roda **toda** a suíte `infra_local` com `request_rls=True` e escopo de principal
  nos métodos dos stores — prova que nenhum caminho de usuário depende de privilégio além de `rpg_api`.

## Rollback
1. Aplicação (imediato, sem banco): `RPG_REQUEST_RLS=off` (+ `DATABASE_URL` do `postgres` se necessário; `vercel_env.py --use-admin-dsn` faz as duas coisas). Volta ao comportamento pré-SPEC-224.
2. Banco (raramente necessário; aditivo): `DROP ROLE rpg_admin` após `REASSIGN/DROP OWNED`; para restaurar Storage reaplicar as policies de `20260820113242_dynamic_storage_bucket_rls.sql`.
O deploy desta versão em `hosted*` **sem** `RPG_ADMIN_DATABASE_URL` falha no boot (fail-closed, R2): defina a env antes do deploy ou use o rollback.

## Revisão Astra (2026-10-17) — APPROVED com 4 correções
Parecer: `handoffs/SPEC-224-ASTRA-independent-review.md`.
- **Bloqueante corrigido:** o confirm de quote de imagem (efeito diferido no commit do turno) e a liberação de
  reserva no `restore_effects` rodavam sob `rpg_api` e tocavam `image_quotes … for update`/`wallet_*` →
  `InsufficientPrivilege`. Novo `db_roles.system_scope(connection)`: eleva só o bloco (`SET LOCAL ROLE NONE`),
  checa os gatilhos diferidos da wallet ainda elevado e volta a `rpg_api`.
- Heartbeat de lease herda o principal (thread com `copy_context`).
- Boot `hosted*` recusa DSN de request com role de plataforma (`supabase_*`, `authenticator`, …) ou `rpg_admin`.
- Role + claims num único `set_config` (R8): overhead local **+0,74–0,96 ms p50/transação** (antes +1,3 ms).
- Ataque SQL direto (`rpg_api` + claim A) em 41 tabelas `app.*`: 0 linhas de outro owner lidas/alteradas/apagadas.

Gates (revisão): suíte offline **3530 passed, 223 skipped, 15 deselected** (exit 0); `-m infra_local`
**140 passed / 13 skipped** e com `RPG_TEST_REQUEST_RLS=1` **139 passed / 14 skipped** — a única falha nos dois
modos é `test_owner_tables_inventory` por `owner_daily_counters`, tabela da SPEC-219 aplicada no Supabase local
compartilhado (não existe nesta branch); pgTAP **16/16** + **14/14**; ruff verde. `test_image_quotes_local.py`
tem 2 falhas que se reproduzem idênticas no HEAD sem esta spec (estado/data do banco compartilhado).

## Pendente (passo do dono, staging/produção)
Ver critérios não marcados em `specs/SPEC-224-rls-efetivo-role-minimo-storage.md` §5.
