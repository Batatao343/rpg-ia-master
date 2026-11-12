# SPEC-410 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** spec-reviewer (Opus) no papel Sol · **Data:** 2026-11-11 · **Commit revisado:** `cde333f2` (base `main` = `33ac6b58`)

## Escopo

`git diff main...HEAD` da branch `spec-410` (commits `9dd97328` e `cde333f2`, 32 arquivos): migração
`20261111140000`, rollback e runbook (`docs/spec410/`), pgTAP novos (`rls_invariants_test.sql`,
`rls_behavior_test.sql`) e o ajuste em `rls_effective_storage_test.sql`, o código Python (pool, marca de
sistema, flag, evento e métrica, pontos de entrada, scripts) e os testes. Nada de SQL foi executado
(sem Postgres). A revisão do SQL é leitura contra as migrações anteriores e contra a semântica do
Postgres 17. Fora do escopo: SPEC-413 (`20261111130000`), exceto onde as duas interagem no `push`.

## Respostas diretas

- **(i) Seguro pousar o código com a flag `off`: sim.** Uma ressalva (P2-1): `off` não é
  byte-equivalente nos pontos de entrada marcados. Cron, drain, worker, `boot:gamedata` e
  `pool_promote`, quando rodam sem principal, passam a usar o pool admin já em `off`. As permissões
  são equivalentes; o que muda é a credencial e o pool usados.
- **(ii) Seguro aplicar a migração no staging: sim**, com as pré-checagens abaixo. O `push` roda
  cada migração dentro de `conn.transaction()` e grava o histórico na mesma transação
  (`scripts/staging/migrations.py:99-112`). Não existe janela entre o FORCE e a criação da policy, e
  uma falha no meio desfaz tudo.
  - Pré-checagens (somente leitura):
    1. Com o DSN do `push`, `select rolbypassrls from pg_roles where rolname=current_user` deve dar
       `true`. É o mesmo assert de `20261019151000`, já aplicada no staging.
    2. Com `RPG_ADMIN_DATABASE_URL`, `select current_user` deve ser `rpg_admin`, ou `rpg_runtime`, ou
       um papel BYPASSRLS. O rate limiter usa `admin_connection` (`infrastructure/postgres_turns.py:856,885,901`);
       sob outro papel sem policy, `consume` levantaria 42501.
    3. `migrations.py status` deve listar 413 e 410 como pendentes, nessa ordem.
    4. Recomendado: disparar `audit-local.yml` na branch. O `supabase start` aplica a migração num
       Postgres real, e `test_http_idor_local` faz login, o que exercita `rate_limit_buckets` com RLS
       forçada.
  - **Pior caso:**
    - (a) O assert aborta, a transação é desfeita e nada muda.
    - (b) O admin DSN usa um papel sem `admin_all`/`runtime_all` e sem BYPASSRLS. O limite de login
      falha aberto (SPEC-219/246), mas o limite por minuto do turno não tem `try` e dá 500 em todo
      turno até o rollback do R6. É improvável: as tabelas da wallet já têm FORCE RLS e funcionam
      hoje pelo mesmo `admin_connection`, o que prova que esse papel tem policy.
- **(iii) Seguro ligar `shadow`: sim.** Só loga e conta, nunca levanta. O `caller` é `módulo.função`,
  sem PII, calculado só no caminho raro. A métrica tem um rótulo só (`mode`), e o evento está
  registrado em `observability/events.py` e em `docs/operacao/EVENTOS_DE_LOG.md`.

## Conferência por item do pedido

**A. Migração**
1. O assert de BYPASSRLS é idêntico ao de `20261019151000:25`, já aplicada. Ele não é mais estrito que
   a realidade, porque quem aplica é o dono (postgres), não `rpg_runtime`/`rpg_admin`.
2. `app.grant_runtime_access()` está em `20261017120000:40-63`, última definição. Ela itera as tabelas
   com `relrowsecurity` e cria `runtime_all`/`admin_all` (`for all … using (true) with check (true)`)
   quando não existem, além do grant de DML. A ordem é enable, FORCE e depois a chamada, tudo na mesma
   transação. `rpg_api` segue sem grant (`20260819002358:87`). Os leitores e escritores são
   `PostgresRateLimiter.consume/peek/reset`, `account_lifecycle.py:460` e
   `recover_account_deletions.py:48`, todos via `admin_connection`. Nenhuma função SQL nem cron do
   banco toca a tabela.
3. Os nomes do `revoke` conferem com as tabelas existentes. É inofensivo.
4. `app.reject_wallet_fact_mutation()` (`20261008170000:114`) é `returns trigger` e levanta 55000 sem
   olhar `TG_OP`. Os gatilhos novos são `for each row`, e `TRUNCATE` não é coberto (está documentado).
   Não há FK com cascade apontando para `wallet_accounts`/`wallet_reservations` (nem de `auth.users`),
   e `image_quotes`/`art_generations` são filhas, então apagá-las não toca a reserva. `PRIVATE_TABLES`
   não inclui wallet. Busca ampla, sem achado de `delete from app.wallet_(accounts|reservations)` nem
   de `truncate` em produto, scripts ou testes; os deletes dinâmicos foram conferidos um a um:
   - `account_lifecycle.py:552` usa só `PRIVATE_TABLES`.
   - `test_spec279_usage_retention_local.py:166` também usa só `PRIVATE_TABLES`.
   - `job_survival.py`: as tabelas de wallet saíram da lista.
5. O `search_path` é seguro. Não há objeto homônimo em `public` e `extensions`; `vector` está
   qualificado (`pgvector_memory.py:245,308-311`, `postgres_shared_pool.py:133`). As três funções de
   `public` têm nomes próprios. As SECURITY DEFINER fixam o próprio `search_path`.
   `gen_random_uuid` está em `pg_catalog`. Conexões antigas do pooler mantêm a ordem velha, que é
   equivalente; não é problema.
6. `comment on role` está dentro de um `DO … exception when insufficient_privilege`, que só captura
   42501 (é um subbloco com savepoint, sem efeito no resto). O texto tem uma imprecisão (P3-1).
7. A migração é idempotente: enable/force, `grant_runtime_access`, `drop trigger if exists` + `create`,
   `alter role`, `comment`. Ela é transacional junto com o histórico, então uma reaplicação depois de
   falha começa do zero.

**B. Rollback.** A ordem está certa: `no force`, `disable`, `drop policy`; o FORCE nunca fica sem
policy. Ele restaura o `search_path` antigo e retira os gatilhos e o comentário. Não diz que deve ir
como migração nova (P3-4) e não foi testado (está declarado).

**C. pgTAP**
- O `plan` bate: 9/9 em `rls_invariants` e 21/21 em `rls_behavior`. Os dois usam `begin … rollback`
  e o mesmo molde de `rls_effective_storage_test.sql` (helper `public.specNNN_rows`,
  `set local role rpg_api` + claim).
- `has_table_privilege` com lista dá `true` se houver qualquer um dos privilégios, que é o correto
  para a invariante.
- As invariantes (i) a (iii) passam no staging depois da migração, dados os fatos (só
  `rate_limit_buckets` estava sem RLS/FORCE; nenhum grant de cliente ou PUBLIC em `app`).
- WITH CHECK antes das constraints: no `ExecInsert`, os gatilhos BEFORE ROW rodam primeiro, depois
  `ExecWithCheckOptions` (RLS), depois `ExecConstraints` (CHECK e NOT NULL); as FKs são gatilhos
  AFTER. A afirmação do executor está correta.
- Os gatilhos BEFORE INSERT do caminho (`account_write_fence`, que é invoker e só enxerga o próprio
  tombstone, e `operations_refuse_reused_id`) passam nesses inserts.
- Asserções frágeis: P3-2 (`42501` ambíguo) e o (iii) `CREATE` em `public`, que depende da imagem
  local do Supabase.

**D. Python**
1. `off`, sem marca: idêntico ao comportamento anterior (`_system_routed` devolve `False` e o
   `_checkout` não muda). Com marca: muda (P2-1).
2. `system_caller` usa `ContextVar.set` e `reset(token)` em `finally`
   (`infrastructure/request_context.py:59-68`). Isso inclui `gamedata.py:128`: o `with` envolve só a
   chamada `runtime_catalog.list`, então a marca não fica ativa depois do import e não vaza para os
   requests (Starlette roda cada request num contexto copiado). Os demais pontos de entrada também
   usam `with`: `cron_internal._run:150`, `drain.py:69`, `run_worker.main:246` e
   `pool_promote.py:24`. O principal vence a marca (`postgres.py:167`).
3. Nenhuma rota de usuário aciona a marca. `drain_jobs` só é chamado por `/internal/cron/jobs`
   (autorizado pelo segredo do cron), e `post_response`/arquivista inline não marcam. O
   `authorize()` do cron, que roda antes de `_run`, não abre conexão.
4. `shadow`: o `caller` vem de `sys._getframe` e só é calculado quando falta principal e marca. O
   filtro `startswith("infrastructure.postgres")` também pula `postgres_catalog`/`_jobs`/`_shared_pool`,
   então o `caller` aponta quem chamou a store, como pede a spec. Sem PII, cardinalidade limitada.
5. O teste AST pega chamador novo em arquivo novo e cobre a árvore inteira, exceto
   `tests/docs/web/evals/playtest`. Não pega um chamador novo dentro de um arquivo já listado (P3-3).
6. Os testes de contrato não foram enfraquecidos. `test_request_connection_sets_role_and_owner_only_with_principal`
   ganhou o assert do rótulo `user`, e o teste do 343 passou a afirmar a migração. Em
   `test_rls_effective.py`, o teste de `off` ficou intacto e os dois `infra_local` novos são coerentes
   com `_pools(**kwargs)`.
7. Threads: todo `ThreadPoolExecutor`/`Thread` em caminho hosted propaga o contexto (`copy_context`
   ou `contextualize`, que faz `ctx.copy().run`). Conferi `context_prefetch:110`,
   `context_sources:190-197`, `creature_gen:1460`, `encounter_preparation:508`, `combat:1868`,
   `jev_rollout:404,515`, `llm_setup:1675` e `routes/turn.py:1696`.
   `creature_gen_jobs.drenar_em_segundo_plano` é só `legacy` (`routes/turn.py:1389`: volta cedo quando
   `_database_profile()`). `jev_decision:417` só faz HTTP.

**E. Runbook.** A ordem (migração, código em `shadow`, janela, `on`) e o critério objetivo (0
ocorrências na janela inteira, que reinicia a cada ocorrência) estão corretos. Os rollbacks de código
e de banco estão descritos. A interação com a 413 é implícita (P3-5).

**F. Regras.**
- `ruff check`/`format --check`, `size_budget` e `dup_helpers` estão limpos.
- Flag registrada (`kind: release`, `expires`). Funções novas ≤ 60 linhas.
- Nada em `docs/guias`, `AGENTS.md`, `staging_flags.json` nem `evals/`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `infrastructure/postgres.py:153,169`; spec R4; `docs/spec410/README.md` | Em `off`, a marca de sistema já desvia cron, drain, worker, `boot:gamedata` e `pool_promote` para o pool admin, quando antes eles usavam o pool de request sem role. A spec diz que `off` é o "comportamento de hoje", mas §3.2 põe a marca acima do modo. As permissões são equivalentes (`rpg_admin` ≡ `rpg_runtime`, inclusive `storage.objects`). O que muda: credencial (`RPG_ADMIN_DATABASE_URL`), carga no pool admin (máx. 4 por instância) e pares aninhados que antes se dividiam entre dois pools e agora caem os dois no admin. | Registrar na spec (R4) e no README que a marca roteia em todos os modos, e que pousar o código já muda o cron e o worker. No smoke pós-deploy, mesmo em `off`, rodar `verify_cron.py` e `job_survival.py` e olhar `db.checkout_failed pool=admin`. Alternativa: só rotear quando `mode != off` (perde a correção da SPEC-224 R3 em `off`). |
| P3-1 | P3 | `supabase/migrations/20261111140000_…sql:54-58`; `supabase/tests/rls_effective_storage_test.sql:24` | O comentário afirma que `rpg_runtime e rpg_admin (inherit) sao membros` de `rpg_api`. Pelas migrações, só `rpg_runtime` (e `postgres`) recebem `grant rpg_api` (`20261015160000:26`, `20261017120000:34`). R10 existe justamente para o comentário ser honesto. | Como a migração ainda não foi aplicada em lugar nenhum, corrigir o texto agora ("rpg_runtime (inherit) é membro; rpg_runtime e rpg_admin têm runtime_all/admin_all") e a mensagem do pgTAP ("the request login role is a member"). |
| P3-2 | P3 | `supabase/tests/rls_behavior_test.sql:45,67,78,97,104` | `throws_ok(…, '42501')` não distingue violação de RLS, "permission denied for table" (sem grant) e o `account_deleted` do `guard_deleted_account_write`, que também é 42501. Hoje os grants existem e não há tombstone, então o teste passa pelo motivo certo; uma revogação futura o faria passar pelo motivo errado. | Usar `throws_like(…, '%row-level security%', …)`, ou `throws_ok` com `errmsg` `'new row violates row-level security policy for table "…"'`. |
| P3-3 | P3 | `tests/test_rls_runtime_config.py:547` | O inventário AST trabalha por arquivo: um `.connection()` novo num arquivo já classificado (por exemplo, rota nova em `routes/billing.py`) passa sem revisão. O `shadow`/`on` é o backstop. | Follow-up: chavear por `arquivo::símbolo` (função ou método que contém a chamada). |
| P3-4 | P3 | `docs/spec410/README.md:46` | O rollback de banco é SQL avulso. Rodá-lo à mão deixa `supabase_migrations.schema_migrations` dizendo que `20261111140000` está aplicada, com o banco revertido (deriva; um `db reset`/branch reaplica). O SQL também não foi executado. | Dizer que o rollback entra como migração nova (`…_revert_spec410_r6.sql`, por item) e rodá-lo uma vez no banco local ou no `audit-local` antes de depender dele. |
| P3-5 | P3 | `docs/spec410/README.md:24-29,76` | (a) O passo 2 sugere `npx supabase test db` sem dizer onde. Contra o staging, o teste de comportamento cria `pgtap` e uma função em `public` e insere linhas (tudo desfeito no rollback, mas é escrita no staging). (b) O runbook não diz que o `push` aplica primeiro a 413 (`20261111130000`), que tem smoke próprio (404 PGRST202). | (a) pgTAP só local/CI; no staging, só as consultas de leitura de `rls_invariants_test.sql`. (b) Acrescentar ao passo 2: o `status` lista 413 e 410; depois do `push`, rodar o smoke da 413 e o `security_wave_smoke`. |
| P3-6 | P3 | evidência (spec §Evidência; `docs/spec410/shadow-suite.md`) | Migração, pgTAP e `test_rls_effective.py` (`infra_local`) nunca rodaram. O CI não roda pgTAP. | Antes do staging, disparar `audit-local.yml` (workflow_dispatch) na branch: o `supabase start` aplica a migração e `test_http_idor_local` faz login com `rate_limit_buckets` forçada. Se possível, acrescentar ao job `supabase test db` e `tests/test_rls_effective.py`. |

Nenhum P0/P1. Também verificados, sem achado: guard de structured output (não se aplica, nada de
LLM), valor de LLM sem validação (não se aplica), writer persistente novo (não há; os gatilhos só
restringem), segredo em log (o `caller` é `módulo.função`, sem DSN nem id), `except` largo
(`pool_scope.py:70` tem `silent-ok`; `gamedata.py` mantém o `except` pré-existente).

## Correções aplicadas

Nenhuma (revisão só de leitura; o executor decide sobre P2-1 e P3-1, de preferência antes de aplicar
a migração, porque ela ainda não foi aplicada).

## Pendências

- P2-1: documentar na spec e no README, e observar o pool admin no smoke pós-deploy (coordenador).
- P3-1: corrigir o texto do comentário antes do `push` (executor, nesta spec).
- P3-2, P3-4, P3-5: ajuste barato nesta spec ou follow-up de testes/runbook (executor).
- P3-3: follow-up (inventário por símbolo), spec própria ou junto da D6 (promover `on`).
- P3-6: `audit-local.yml` na branch antes do staging (coordenador).

## Comandos rodados

```text
git diff main...HEAD --stat → 32 arquivos, +1192/-41
uv run ruff check . → All checks passed
uv run ruff format --check . → 1982 files already formatted
bash scripts/dev/py.sh scripts/dev/size_budget.py → rc=0
bash scripts/dev/py.sh scripts/dev/dup_helpers.py --diff main...HEAD → nenhuma função nova com nome já usado
bash scripts/dev/pt.sh -n 2 tests/test_rls_runtime_config.py tests/test_spec343_security.py tests/test_flag_registry.py tests/test_log_event_registry.py tests/test_size_budget.py tests/test_cron_logging.py tests/test_spec192_cron_endpoints.py tests/test_boot_log.py tests/test_boot_policy.py tests/test_runtime_profiles.py tests/test_hosted_supabase_contract.py tests/test_pgvector_memory.py tests/test_chronicle_advanced.py tests/test_speech_api.py tests/test_speech_to_text.py tests/test_rls_effective.py → 317 passed, 11 skipped (rc=0; test_rls_effective coleta e pula sem banco)
bash scripts/dev/pt.sh -n 2 tests/test_account_deletion_recovery_cli.py tests/test_job_logging.py tests/test_spec374_job_janela.py tests/test_worker_lease_lifecycle.py tests/test_spec192_staging_scripts.py tests/test_spec194_native_backend.py tests/test_spec195_followups.py tests/test_spec195_reconciliation.py tests/test_latency_metrics_compat.py tests/test_dynamic_art_jobs.py tests/test_spec297_flag_off.py → 128 passed, 8 skipped (rc=0)
```
