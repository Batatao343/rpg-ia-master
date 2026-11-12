# SPEC-410 — rls-sem-falha-aberta

> **Status:** `in-progress` (11/11: código, migração, rollback, testes Python e runbook entregues; **pendentes do coordenador**: aplicar a migração no staging, flag `shadow` -> `on`, smoke §6, rodar pgTAP e `infra_local`, revisão `spec-reviewer`). Antes `approved` (aprovada pelo coordenador por delegação do dono, "o resto é nois"; decisões do §8 = recomendações do autor; veto do dono segue possível). Evidência e runbook: `docs/spec410/`.
> **Criada:** 2026-11-11 · **Atualizada:** 2026-11-11
> **Depende de:** SPEC-224 `done` (RLS efetivo por request), SPEC-343 `done` (deixou o follow-up de `rate_limit_buckets`)
> **Desbloqueia:** nada. Irmã de SPEC-409/411/412 (follow-ups da varredura de segurança de 11/11), sem dependência entre elas.
> **Risco:** `alto` (persistência/estado: pool de banco, RLS, migração) → `spec-reviewer` (Opus) obrigatório; revisor foca no inventário de chamadores e nas threads.
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet), uma etapa por vez. Não pede Sol: todo ponto de thread do produto que toca banco já propaga o contexto (inventário em §3.4), então não há desenho novo de concorrência; o que resta é pego pelo modo `shadow`. Se a Etapa 0 achar thread SEM propagação que toque banco no hosted, escalar para Sol antes da Etapa 3.
> **REVIEW_MODEL:** `spec-reviewer` (Opus), obrigatório nas Etapas 2, 3 e 5.
> **EVAL_AUTHORING_REQUIRED:** `false` (nenhum evaluator, expected, dataset ou baseline de `evals/` é tocado).
> **Evidência:** (1) testes que falham antes: checkout request-scoped sem principal hoje devolve conexão privilegiada (`infrastructure/postgres.py:133-139`); a invariante pgTAP "toda tabela de `app` com RLS forçada" hoje acusa `rate_limit_buckets`. (2) Oráculo de não-regressão: suíte de API + `supabase/tests` + `tests/test_rls_effective.py` (infra_local) + smoke §6 no staging (cron, worker de crônica, pool compartilhado, memória pgvector, rate limit) com contador `checkout_without_principal` zerado antes de ligar o modo estrito.

---

## 1. Contexto & Objetivo

A varredura de segurança de 11/11/2026 (revisão Sonnet de RLS, conferência no banco do staging e revisão independente) **não achou caminho de ataque demonstrado**. Achou defesa em profundidade faltando numa área de risco alto. O ponto central é de código: no checkout request-scoped, se `active_principal()` é `None`, a conexão volta como o login `rpg_runtime` **sem** `set role rpg_api` (`infrastructure/postgres.py:133-139`). `rpg_runtime` tem a policy `runtime_all using (true)` em toda tabela com RLS e `execute` nas funções de `app` (`supabase/migrations/20261017120000_rls_effective_storage_no_client_write.sql:40-63`). Ou seja, a RLS **falha aberta** quando falta o principal (rota esquecida, thread que não herdou o contextvar, boundary que não cobre o path). A SPEC-224 R3 diz "sem principal (worker) usa o pool admin" (`specs/SPEC-224-rls-efetivo-role-minimo-storage.md:33`), e o código não faz isso: o próprio teste fixa o comportamento antigo como "health/boot" (`tests/test_rls_runtime_config.py:148`; `tests/test_rls_effective.py:117-118`).

A correção ingênua ("levantar erro sem principal no hosted") **derruba produção**: chamadores de sistema dependem hoje do caminho aberto. Exemplos conferidos: `ChronicleRepository.complete` (`services/chronicle_repository.py:115`, chamado de `workers/run_worker.py:183`, sem principal), `PostgresSharedPoolStore.insert/get/select/count_submissions` (`infrastructure/postgres_shared_pool.py:76,109,189,210`, chamados também pelo cron `/internal/cron/shared-pool`), `PostgresJobQueue.enqueue` (`infrastructure/postgres_jobs.py:105`), `PgVectorMemoryStore.stage/query/discard_after` (`infrastructure/pgvector_memory.py:141,283,333`) e quatro scripts de operação que abrem `runtime.game_store.pool.connection()` (`scripts/admin_wallet_adjust.py:61,78,92`, `scripts/admin_wallet_reconcile.py:53`, `scripts/recover_account_deletions.py:19,46,107`, `scripts/seed_google_play_skus.py:62`). A ordem é obrigatória: **medir, migrar os chamadores de sistema, só então falhar fechado**, com rollout por flag de três estados (`off`/`shadow`/`on`).

O mesmo trabalho fecha a fila de higiene de banco confirmada no staging: `app.rate_limit_buckets` é a única das 44 tabelas de `app` sem RLS (follow-up explícito, nunca feito, da SPEC-343: `specs/SPEC-343-seguranca-auth-reauth-login.md:103`, `tests/test_spec343_security.py:158-160`); quatro tabelas sem `revoke` explícito para `anon`/`authenticated`; `wallet_reservations` e `wallet_accounts` sem trava contra `delete`; `search_path` dos logins com `public` antes de `extensions`; e um comentário de `rpg_api` que dá falsa sensação de isolamento (`20260819002358_auth_rls.sql:9-10` e `20261017120000...sql:9-10` afirmam que sem `SET ROLE` nenhum privilégio de tenant vale, mas `rpg_runtime` é `inherit` e membro de `rpg_api`).

Princípio: mecânica e autorização são Python/SQL determinísticos, nunca LLM; falhar fechado é preferível a "funciona por acidente" (AGENTS.md § Convenções). Nenhuma mudança de comportamento no perfil `legacy` (sem pool) nem no `local`.

## 2. Requisitos

Linhas citadas = estado da `main` em `0514cafa`; o executor refaz o grep na Etapa 0 porque a `main` anda.

### Parte A — falha fechada no pool

- **R1 — Inventário (evidência antes de mexer).** Etapa 0 produz `docs/spec410/inventario.md`: tabela `arquivo:linha · símbolo · classe · tratamento` para TODO chamador de `pool.connection()` / `*.connection()` request-scoped (grep + AST, incluindo `api_core.py`, `routes/`, `services/`, `infrastructure/`, `workers/`, `scripts/`; testes ficam de fora). Classes: **(a)** sempre com principal (request de usuário); **(b)** sistema puro (worker/cron/webhook/script); **(c)** ambíguo (o mesmo método roda sob request E sob worker/cron); **(d)** pool próprio sem `request_rls` (inalterado). Contagem preliminar do autor (o executor refaz): ~24 sites (a), 1 + 8 em 4 scripts (b), 8 (c), 3 scripts (d: `chaos_test.py`, `load_test.py`, `verify_restore.py` constroem `PostgresPool(dsn)` sem `request_rls`). Um teste novo (`tests/test_rls_runtime_config.py`, sucessor de `test_every_module_that_opens_connections_is_classified`, `:232`) varre a árvore de produto inteira por AST contra uma lista versionada e reprova chamador novo não classificado.
- **R2 — Modo `shadow` medido.** O pool conta e loga todo checkout request-scoped sem principal e sem marca de sistema: evento `pool.checkout_without_principal` (registrar em `observability/events.py`, campos `caller`, `mode`) + contador no registry de métricas existente. `caller` = módulo e função do primeiro frame fora de `infrastructure/postgres*.py` (calculado só no caminho raro). Sem levantar. Medição na suíte: a instrumentação roda na suíte de API e de workers (fakes) e na suíte `infra_local` com `RPG_TEST_REQUEST_RLS=1` (`tests/conftest.py:129-195`), e o resultado entra em `docs/spec410/shadow-suite.md`. Isso é a lista de chamadores a migrar.
- **R3 — Migrar chamadores de sistema.** (b) → `admin_connection(pool)` (`infrastructure/db_roles.py:21`): `ChronicleRepository.complete` (`services/chronicle_repository.py:115`) e os 4 scripts de operação. (c) → marca explícita de chamador de sistema nos pontos de entrada, não método a método (ver §3.2): `services/cron_internal.py:_run` (`:144`, cobre `/internal/cron/*`, inclusive o drain de jobs de `:192` e o shared-pool de `:225-243`), `workers/run_worker.py:main` (`:234-251`), `workers/drain.py` (`:59-63`) e `scripts/pool_promote.py` se existir. A marca roteia para o pool admin sem trocar de role (mesma garantia de `admin_connection`) e **perde** para um principal presente (`workers/projection_jobs.py:69` abre `principal_scope(owner)` por job: continua sob `rpg_api`).
- **R4 — Falha fechada, três estados.** Flag nova `RPG_RLS_STRICT_PRINCIPAL` ∈ {`off`, `shadow`, `on`} (§3.3). `off` = comportamento de hoje. `shadow` = R2. `on` = checkout request-scoped sem principal e sem marca de sistema levanta `RlsScopeError` (tipo novo, `RuntimeError`, **não** `Unauthorized`: não pode virar 401 silencioso). Só vale quando `PostgresPool` é construído por `build_runtime` com perfil `hosted`/`hosted-supabase` e `request_rls` ligado (`infrastructure/runtime.py:343,751-763`). `legacy` (sem pool), `local` e pools diretos de script/teste não mudam. Recomendação: **usar a flag** (justificativa em §8 D1). Padrão da flag no código: `off`; o staging recebe `shadow` e depois `on` pelo `staging_flags.json`.
- **R5 — Testes que viram contrato novo.** Os testes que fixam o comportamento aberto são reescritos como o contrato correto, sem enfraquecer: `tests/test_rls_runtime_config.py:148-150` e `tests/test_rls_effective.py:110-125` passam a testar (modo `off`: inalterado; modo `on`: `RlsScopeError`; marca de sistema: pool admin, sem `ROLE`).

### Parte B — migração de banco (arquivo novo; nunca editar as antigas)

- **R6 — RLS em `app.rate_limit_buckets`.** `enable` + `force row level security` seguido de `select app.grant_runtime_access();`. Conferido no source (`20261017120000_...sql:40-63`): a função cria `runtime_all` e `admin_all` (`for all ... using (true) with check (true)`) para toda tabela de `app` com `relrowsecurity` e sem a policy, e já dá `grant select, insert, update, delete` a `rpg_runtime`/`rpg_admin`. Sem a chamada o rate limit quebra (FORCE RLS sem policy = deny). O acesso é só de sistema: `PostgresRateLimiter` não abre `.connection()` (`tests/test_rls_runtime_config.py:250-253`) e `rpg_api` perdeu o grant (`20260819002358_auth_rls.sql:87`). A migração termina com `revoke all ... from public, anon, authenticated`. Remover `RLS_EXCEPTIONS` de `tests/test_spec343_security.py:158-160` (vira `set()`).
- **R7 — `revoke` explícito nas 4 tabelas.** `revoke all on app.assets, app.chronicle_digests, app.art_generations, app.memory_documents from public, anon, authenticated` (hoje zero grants no banco — F4 —, mas sem a linha na migração: `20260819002404:26,44,64`, `20260819002401:56-57`). Os grants de `rpg_api` NÃO mudam.
- **R8 — Trava contra `delete` na carteira.** `before delete ... for each row execute function app.reject_wallet_fact_mutation()` (função existente, `20261008170000:114-119`, errcode `55000`) em `app.wallet_reservations` e `app.wallet_accounts`. **Decidido com evidência: sobrevive à exclusão de conta.** `AccountLifecycle.finish` apaga só `PRIVATE_TABLES` (`infrastructure/account_lifecycle.py:12-25,548-552`); `wallet_accounts` e `wallet_reservations` estão em `FINANCIAL_TABLES` e `RETAINED_WITH_REASON` (retenção de 5 anos, `:26-53`). `wallet_entries`, `wallet_attempt_tickets` e `wallet_settled_usage` já são imutáveis (`20261008170000:120-125`); o gatilho `check_wallet_reserved` só dispara em insert/update (`:170-175`), por isso `delete` passava. Único deletor encontrado: o loop genérico de limpeza sintética `scripts/staging/job_survival.py:60-78` (`delete from app.{t}` em toda tabela com `owner_id`, dentro de `except Exception: pass`); passará a pular essas duas tabelas sem erro visível, aceitável (o dado sintético já não era apagável quando havia `wallet_entries`). `TRUNCATE` não dispara trigger de linha: fora de escopo (não há `truncate` no produto nem na suíte). Quando existir expurgo de 5 anos, ele terá de desabilitar o gatilho explicitamente (anotar em `docs/spec410/README.md`).
- **R9 — `search_path` dos logins.** `alter role rpg_runtime set search_path = app, extensions, public` e idem `rpg_admin` (hoje `app, public, extensions`: `20261015160000:23`, `20261017120000:31`). Evidência de que é seguro: nenhum SQL do produto qualifica `public.` (grep em `infrastructure/`: só `oidc_identity.py`, Python); as funções `SECURITY DEFINER` fixam o próprio `search_path` (`''` ou `pg_catalog`); `extensions.vector` é qualificado nas queries de memória e o operador `<=>` continua resolvido porque `extensions` segue no caminho. Efeito só em sessões novas (o pooler recicla): o teste abre conexão nova. Se a Etapa 0 achar objeto de `public` resolvido sem qualificação, esse item sai da spec e vai para o hand-back.
- **R10 — Comentário e teste que enganam.** Nova migração faz `comment on role rpg_api is '...'` com o fato correto: `rpg_api` é NOLOGIN/NOINHERIT, mas `rpg_runtime` e `rpg_admin` herdam dele e têm `runtime_all`/`admin_all`; o isolamento por owner depende de o app fazer `SET LOCAL ROLE rpg_api` (SPEC-224), por isso a falha aberta do R4 importa. Reescrever a mensagem do 3º assert de `supabase/tests/rls_effective_storage_test.sql:22-25` para não prometer "no tenant privilege without SET ROLE" (a role `rpg_api` é NOINHERIT; a role de login não é). Não editar as migrações antigas.

### Parte C — testes de banco

- **R11 — Invariantes pgTAP** (arquivo novo `supabase/tests/rls_invariants_test.sql`): (i) nenhuma relação `relkind in ('r','p')` de `app` sem `relrowsecurity and relforcerowsecurity` (partições filhas: excluir `relispartition` se aparecerem); (ii) nenhuma relação de `app` com privilégio de tabela para `anon`/`authenticated`/`PUBLIC` (usar `has_table_privilege(role, oid, 'select,insert,update,delete,truncate,references,trigger')` por relação, que enxerga `PUBLIC`); (iii) `anon`/`authenticated` sem `USAGE` em `app` e sem `CREATE` em `public` (reforça `valoria_rls_test.sql:75-82`); (iv) `rate_limit_buckets` tem `runtime_all` e `admin_all`; (v) delete em `wallet_reservations`/`wallet_accounts` falha com `55000` mesmo para o login de sistema.
- **R12 — pgTAP de comportamento de RLS** para ao menos `image_quotes`, `operations`, `jobs`, `shared_pool`: sob `set local role rpg_api` com `request.jwt.claim.sub = A`, A não lê e não grava linha de B (leitura devolve só as próprias; `update`/`delete` de linha de B = 0 linhas; `insert` com `owner_id` de B = `42501`). Molde: `rls_effective_storage_test.sql:99-135`. Para `creature_portraits`, `account_deletions` e `usage_events`: se a tabela tem policy `to rpg_api`, mesmo teste; se for só de sistema, assert negativo de privilégio (`not has_table_privilege('rpg_api', ...)`). A Etapa 0 lista as policies reais com `pg_policies` antes de escrever os asserts.
- **R13 — Integração com banco local** (`tests/test_rls_effective.py`, marker `infra_local`): com `strict=on` e sem principal, `pool.connection()` levanta `RlsScopeError`; com a marca de sistema, `current_user` é `rpg_runtime` do pool admin e enxerga os dois owners; com principal, `rpg_api` e só o próprio owner.

### Fora de escopo (com motivo)

- Revogar as 3 `SECURITY DEFINER` de `public` (`rpg_wallet_balance`, `rpg_wallet_history`, `rpg_current_session_active`): decisão do dono, registrada em D4.
- Mudar o modelo de roles (`rpg_api`/`rpg_runtime`/`rpg_admin`). `GRANT rpg_api TO rpg_runtime WITH INHERIT FALSE`: ganho só documental, fica em D3.
- Mover `pg_net` de `public`: ver D2 (recomendação: aceitar).
- Hardening de `app.current_owner_id()` com `execute` para `PUBLIC`: inofensivo sem `USAGE` em `app` para `anon`/`authenticated` (coberto pela invariante R11-iii); ver D5.
- Produção: a nuvem de produção não está certificada (SPEC-104 `on hold`); o alvo é o staging.
- Qualquer mudança em `evals/`, em contrato de API HTTP ou no perfil `legacy`.

## 3. Design técnico

### 3.1 Estado atual (evidência)

- `infrastructure/postgres.py:110-142` `_checkout`: só `if principal is not None: _apply_request_role(...)`; senão cai direto no `yield connection` com o login de sessão.
- `infrastructure/postgres.py:144-159`: `connection()` → `_checkout(request_scoped=True)`; `admin_connection()` → `(self.admin_pool or self)._checkout(request_scoped=False)`.
- `infrastructure/request_context.py:11-35`: `_principal` é um `ContextVar`; `principal_scope` o fixa. O boundary HTTP o define em `api.py:475-486`, só para `/game*`, `/account*`, `/telemetry*` e `/data/map?game_id=` (`api.py:388-396`). `/auth/*`, `/data/*`, `/health`, `/metrics`, webhook e cron não têm principal e (revisão independente) usam `admin_connection` ou não tocam o banco.
- `infrastructure/db_roles.py:28-57` `system_scope(connection)`: eleva uma transação JÁ aberta em `rpg_api`. **Nome já ocupado**: a marca nova NÃO pode chamar-se `system_scope`.

### 3.2 Marca de chamador de sistema (decisão de desenho)

Alternativas avaliadas para os (c): (1) parâmetro `as_admin` em cada método de store (`connection(as_admin=True)` já existe, `postgres.py:145`); (2) dois métodos por store; (3) marca no ponto de entrada. Escolhida **(3)**: são ~8 sites (c) em 3 stores usados por request e por cron, e (1)/(2) obrigam cada futuro chamador a lembrar a variante certa, que é exatamente o modo de falha. Com a marca, o default fica fechado e o sistema declara-se uma vez, no entrypoint.

Arquivo `infrastructure/request_context.py` (já é o dono do contextvar de principal; sem módulo novo):

```python
_system_caller: contextvars.ContextVar[str | None]  # default None


def system_caller(
    reason: str,
) -> ContextManager[
    None
]: ...  # fixa/restaura; reason = "cron:jobs", "worker", "script:admin_wallet_adjust"
def active_system_caller() -> str | None: ...
```

`_checkout(request_scoped=True)` passa a decidir assim (precedência: principal > marca de sistema > modo estrito):
1. principal presente → `_apply_request_role` (igual a hoje);
2. marca presente → conexão do pool admin (`self.admin_pool or self`), sem trocar de role, `label="admin"` (igual a `admin_connection`);
3. nenhum dos dois → por modo: `off` devolve como hoje; `shadow` loga/conta e devolve; `on` levanta `RlsScopeError`.

`RlsScopeError(RuntimeError)` fica em `infrastructure/contracts.py` ao lado de `Unauthorized`; não deve ser capturado como 401 (teste explícito de que o handler HTTP devolve 500 genérico com `error_code` sem vazar mensagem, no molde de `tests/test_http_error_leakage.py`). O modo entra em `PostgresPool.__init__` como parâmetro novo `strict_principal: str = "off"`; `build_runtime` o define lendo `RPG_RLS_STRICT_PRINCIPAL` só para perfil hosted com `request_rls`. Equivalência dos logins: `rpg_admin` e `rpg_runtime` têm o mesmo conjunto de grants e policies (`rls_effective_storage_test.sql:31-48` já prova), então rotear a marca para o pool admin não muda permissão.

### 3.3 Flag

`config/flags.yaml` (ordem alfabética, perto de `RPG_REQUEST_RLS`, `:807`): 

```yaml
RPG_RLS_STRICT_PRINCIPAL:
  kind: release
  default: "off"
  spec: SPEC-410
  expires: 2027-02-01
  note: "pool hosted sem principal nem marca de sistema: off=como antes, shadow=só loga/conta, on=levanta RlsScopeError; remover a flag e deixar 'on' fixo ao vencer"
```

O gate de flags roda na suíte default (`docs/guias/TESTES.md` § Flags). Em `scripts/staging/vercel_env.py` a flag segue o padrão de `RPG_PLOT_THREADS` (entra pelo `staging_flags.json`).

### 3.4 Inventário de threads e contexto (conferido)

Propagam o contextvar de principal (copy do contexto): `routes/turn.py:1696` (`contextualize`, `observability/telemetry.py:359-367`) e o principal explícito em `routes/turn.py:1637-1640`; `services/context_prefetch.py:110`; `services/context_sources.py:190,197`; `services/creature_gen.py:1460`; `services/encounter_preparation.py:508`; `agents/combat.py:1870`; `services/lease_heartbeat.py:92` (já testado: `tests/test_rls_runtime_config.py:265`); `llm_setup.py:1659`; `services/jev_rollout.py:515` (`contextualize`); `routes/billing.py:279` e `llm_setup.py:1228` (`run_in_threadpool`/`asyncio.to_thread` copiam o contexto). Sem propagação mas fora do hosted: `services/creature_gen_jobs.py:268` (thread daemon do perfil `legacy`; a Etapa 0 confirma que o único chamador é gated por perfil sem banco). `_drain_projection post_response` roda na thread da request (`routes/turn.py:1380`, handler em `1276-1279`). A Etapa 0 reexecuta `Grep` por `ThreadPoolExecutor|threading.Thread|to_thread|run_in_threadpool` em código de produto e anota qualquer ocorrência nova.

### 3.5 Migração

Arquivo novo `supabase/migrations/20261111120000_rls_hardening_rate_limit_wallet_delete.sql` (nome final com o timestamp do dia da execução, > `20261028120000`). Estrutura: 1) R6 (enable/force + `select app.grant_runtime_access();` + revoke); 2) R7; 3) R8 (dois `create trigger`); 4) R9 (`alter role ... set search_path`); 5) R10 (`comment on role`). Idempotente onde possível (`drop trigger if exists` antes de `create`). Termina com `select app.grant_runtime_access();` (contrato do repo, `20261015160000:11-12`). Pré-condição verificada na Etapa 0: o dono da migração tem `rolbypassrls` (`select rolbypassrls from pg_roles where rolname = current_user`), porque `FORCE RLS` sujeita o dono da tabela; é a mesma exigência já documentada em `20261019151000:24-27`. Ferramentas e testes que usam `postgres` para ler/limpar `rate_limit_buckets` (`tests/test_session_hardening_local.py:156-163`, `tests/test_account_lifecycle_local.py:346-353`, `scripts/staging/security_wave_smoke.py:195`) seguem funcionando se `postgres` tem BYPASSRLS; a Etapa 0 confirma no banco local e no staging, e se algum desses não for BYPASSRLS corrige o teste/script (login de sistema), não a policy.

### 3.6 Arquivos

- **Novos:** `supabase/migrations/2026…_rls_hardening_rate_limit_wallet_delete.sql`; `supabase/tests/rls_invariants_test.sql` (R11) e `supabase/tests/rls_behavior_test.sql` (R12); `docs/spec410/README.md` (ordem de deploy, rollback, evidência), `docs/spec410/inventario.md`, `docs/spec410/shadow-suite.md`.
- **Alterados:** `infrastructure/postgres.py` (modo, decisão do `_checkout`, `PostgresPool.__init__`), `infrastructure/request_context.py` (marca), `infrastructure/contracts.py` (`RlsScopeError`), `infrastructure/runtime.py` (ler a flag, passar `strict_principal`), `services/chronicle_repository.py:115` (`admin_connection`), `services/cron_internal.py:_run`, `workers/run_worker.py:main`, `workers/drain.py`, `scripts/admin_wallet_adjust.py`, `scripts/admin_wallet_reconcile.py`, `scripts/recover_account_deletions.py`, `scripts/seed_google_play_skus.py`, `observability/events.py` (evento novo), `config/flags.yaml`, `scripts/staging/vercel_env.py` (se a flag precisar de registro de modo), `tests/test_rls_runtime_config.py`, `tests/test_rls_effective.py`, `tests/test_spec343_security.py`, `supabase/tests/rls_effective_storage_test.sql` (mensagem do 3º assert).
- **Funções novas ≤ 60 linhas; `infrastructure/postgres.py` não passa de 1.000 linhas** (gate `tests/test_size_budget.py`): se a decisão do checkout crescer, extrair para `infrastructure/pool_scope.py`. Antes de criar helper: `Grep "def <nome>"`.

## 4. Plano passo a passo

Uma etapa por vez; testes primeiro; commit por etapa (inglês, Conventional Commits); `bash scripts/dev/pt.sh` com no máximo `-n 2`; suíte completa só do coordenador no pouso.

### Etapa 0 — Medição (sem código de produto)

1. Rodar o grep/AST do R1 e escrever `docs/spec410/inventario.md`; reconferir §3.4 (threads).
2. Escrever só a instrumentação descartável (patch local, não commitado) que conta checkout sem principal; rodar `tests/test_api*.py`, os testes de worker/cron e, se houver Supabase local (`bash scripts/dev/ram.sh` antes; `supabase status` sem órfãos), a suíte `infra_local` com `RPG_TEST_REQUEST_RLS=1`. Gravar a lista em `docs/spec410/shadow-suite.md`. Sem Supabase local, registrar "só estático + fakes" e delegar as `*_local` ao CI `audit-local.yml`.
3. Conferir no source: `rolbypassrls` do dono da migração, quem lê `rate_limit_buckets` (`scripts/staging/security_wave_smoke.py:195`), `extrelocatable` de `pg_net`, policies reais de `shared_pool`/`creature_portraits`/`account_deletions`/`usage_events` (`pg_policies`).
4. **Aceite:** inventário completo, nenhum chamador sem classe; todo (c) com tratamento escolhido; itens que contrariem a spec (ex.: R9) listados no hand-back.

### Etapa 1 — Testes que falham (TDD)

1. `tests/test_rls_runtime_config.py`: `test_checkout_sem_principal_modo_off_inalterado`, `test_checkout_sem_principal_shadow_loga_e_nao_levanta` (assert do evento `pool.checkout_without_principal` com `caller`), `test_checkout_sem_principal_on_levanta_rls_scope_error` (falha hoje: devolve conexão), `test_marca_de_sistema_usa_pool_admin_sem_role`, `test_principal_vence_marca_de_sistema`, `test_modo_estrito_so_vale_em_hosted_com_request_rls`, `test_request_rls_off_nunca_levanta`. Reutilizar `_pool()`/`_FakePooled` (`:105-122`).
2. `tests/test_rls_runtime_config.py`: `test_todo_chamador_de_connection_esta_classificado` (R1, AST na árvore de produto) — falha até a lista versionada existir.
3. `tests/test_rls_effective.py` (infra_local): `test_estrito_sem_principal_levanta`, `test_marca_de_sistema_ve_os_dois_owners`.
4. `supabase/tests/rls_invariants_test.sql` e `rls_behavior_test.sql` (R11/R12). A invariante (i) acusa `rate_limit_buckets` antes da migração: é o teste-que-falha de Parte B.
5. **Aceite:** falham pelos motivos esperados (colar saída resumida em `docs/spec410/README.md`).

### Etapa 2 — Marca de sistema e modo (revisor Opus)

1. Implementar `system_caller`, `RlsScopeError`, parâmetro `strict_principal` e a decisão do `_checkout` (R2, R4 §3.2), evento no registry, flag em `config/flags.yaml`, leitura em `build_runtime`.
2. **Aceite:** testes da Etapa 1 (parte Python) verdes; `bash scripts/dev/pt.sh tests/test_rls_runtime_config.py tests/test_db_logging.py tests/test_flag_registry.py tests/test_size_budget.py -q`; `ruff format --check` + `ruff check`; modo padrão `off` não muda nenhum teste existente fora os do R5.

### Etapa 3 — Migrar chamadores (revisor Opus)

1. Um teste por chamador migrado, com pool falso estrito `on` e sem principal: `test_chronicle_complete_funciona_sem_principal_em_modo_estrito` (usa admin), `test_cron_run_executa_sob_marca_de_sistema` (shared-pool, jobs, finops), `test_run_worker_main_executa_sob_marca_de_sistema`, `test_drain_jobs_sob_marca_de_sistema`, e um por script (`admin_wallet_adjust`, `admin_wallet_reconcile`, `recover_account_deletions`, `seed_google_play_skus`).
2. Implementar R3; atualizar a lista de classificação do R1.
3. **Aceite:** testes novos verdes; `bash scripts/dev/pt.sh tests/test_rls_runtime_config.py tests/test_chronicle*.py tests/test_spec192_cron_endpoints.py tests/test_cron_logging.py tests/test_run_worker*.py -q` (Glob define a lista final); ruff. **Nenhum modo `on` é ligado por padrão nesta etapa.**

### Etapa 4 — Migração e pgTAP

1. Escrever a migração (R6–R10) e o pgTAP; aplicar ao banco local (`supabase db reset` ou o fluxo do repo) e rodar `npx supabase test db`: invariantes e comportamento verdes; `tests/test_spec343_security.py::test_every_app_table_has_rls` com `RLS_EXCEPTIONS = set()`.
2. Reexecutar `tests/test_rls_effective.py`, `tests/test_session_hardening_local.py`, `tests/test_account_lifecycle_local.py`, `tests/test_postgres_jobs_local.py`, `tests/test_account_lifecycle_financial_local.py` (infra_local, `-n 2`), com e sem `RPG_TEST_REQUEST_RLS=1`.
3. **Aceite:** pgTAP todo verde; testes `infra_local` verdes; `docs/spec410/README.md` com rollback SQL (`alter table app.rate_limit_buckets no force row level security; ... disable row level security; drop trigger ...; alter role ... reset search_path` + restaurar o grant antigo) testado contra o banco local.

### Etapa 5 — Staging (§6) e revisão (revisor Opus)

1. Executar o smoke §6 até o passo 4 (`shadow`). `spec-reviewer` lê o diff completo (pool, marca, migração) e o `inventario.md`. Só então ligar `on` no staging (§6 passo 5).
2. **Aceite:** §6 completo; revisão APPROVED; coordenador faz `/spec-land` (suíte completa 1×).

## 5. Critérios de aceite

- [ ] `docs/spec410/inventario.md` classifica 100 % dos chamadores (a/b/c/d); teste de AST reprova chamador novo não classificado.
- [ ] Modo `on`: checkout request-scoped sem principal e sem marca levanta `RlsScopeError` (teste fake e `infra_local`); modo `off` idêntico a hoje; `legacy`/`local`/pools de script sem `request_rls` inalterados.
- [ ] Todo chamador (b) usa `admin_connection`; todo ponto de entrada de sistema (c) roda sob `system_caller`; nenhum chamador (c) editado método a método.
- [ ] Migração aplicada no banco local e no staging; invariantes pgTAP (i)–(v) verdes; `rate_limit_buckets` com `runtime_all`/`admin_all`, rate limit funcionando.
- [ ] pgTAP de comportamento para `image_quotes`, `operations`, `jobs`, `shared_pool` verde; negativos para as tabelas só de sistema.
- [ ] Trigger de delete da carteira ativo e a exclusão de conta (`tests/test_account_lifecycle*_local.py`) continua verde.
- [ ] `RLS_EXCEPTIONS` vazio em `tests/test_spec343_security.py`; mensagem do 3º assert de `rls_effective_storage_test.sql` corrigida; `comment on role rpg_api` presente.
- [ ] Flag `RPG_RLS_STRICT_PRINCIPAL` em `config/flags.yaml` com validade; gate de flags verde.
- [ ] Staging: `shadow` com 0 ocorrências de `pool.checkout_without_principal` (janela do §6), depois `on` verde nos mesmos gates.
- [ ] `uv run pytest` verde (suíte completa offline, 1× pelo coordenador) e `ruff format --check`/`ruff check` limpos; `tests/test_size_budget.py` verde.
- [ ] Revisão `spec-reviewer` APPROVED (independente; Etapas 2, 3 e 5).
- [ ] Saves antigos continuam carregando (nenhum formato de `GameState` muda).

## 6. Smoke test real (staging)

Sem LLM real obrigatório além de 1–2 turnos para exercitar a memória e a crônica (custo dentro do teto do staging). O que se prova é infra. **Ordem de deploy: migração antes do código; código em `shadow` antes de `on`.**

1. **Antes:** repetir no staging (somente leitura) as consultas da varredura de 11/11 e gravar em `docs/spec410/staging-antes.txt`: tabelas de `app` sem RLS/force, grants de `anon`/`authenticated`/`PUBLIC`, `search_path` e `rolinherit` de `rpg_runtime`/`rpg_admin`, `pg_net`.
2. **Migração no staging** (processo de migração do staging; o executor confirma qual) → rodar `npx supabase test db` contra o remoto ou as mesmas consultas de R11 → rate limit funcionando: `scripts/staging/security_wave_smoke.py` (conta/limite de login incrementa `rate_limit_buckets` pelo login de sistema), 1 login real. O código antigo é compatível com a migração (rate limiter e ciclo de conta usam `admin_connection`).
3. **Deploy do código com `RPG_RLS_STRICT_PRINCIPAL=shadow`** (via `staging_flags.json`, `/staging-deploy`). Gates existentes: `post_deploy`, `vercel_smoke`, `e2e_session`.
4. **Exercitar cada caminho de sistema** (evidência = logs do Vercel filtrados por `pool.checkout_without_principal`; o contador é por instância serverless e zera, então o log é a prova): `scripts/staging/verify_cron.py` (pg_cron → pg_net → Vercel, 200 em `jobs`, `operations`, `account-deletions`, `reconciliation`, `finops`, `shared-pool`; o cron de `finops` é horário: janela mínima de ~65 min); `scripts/staging/job_survival.py` (jobs + lease); um turno real que fecha capítulo (job `compress_chronicle` → `ChronicleRepository.complete`) e escreve memória (pgvector `stage`/`embed_memory`); `scripts/staging/account_deletion_recovery.py`; shared-pool se `pool_mode != off`. **Aceite do passo: 0 ocorrências na janela inteira.** Qualquer ocorrência vira chamador a classificar (Etapa 3) e reinicia a janela.
5. **Ligar `on`** no staging e repetir 3 e 4 (mesmos gates, 0 erros `RlsScopeError`).
6. **Rollback:** (código) `RPG_RLS_STRICT_PRINCIPAL=shadow` ou `off` no `staging_flags.json` + redeploy (variável de ambiente da Vercel só vale após novo deploy), ou revert do commit; (banco) o SQL de rollback testado na Etapa 4, nunca editando a migração aplicada. Como a migração é aditiva e compatível com o código antigo, reverter só o código não exige tocar no banco.

## 7. Riscos & compatibilidade

- **Derrubar worker/cron/script por chamador esquecido** (risco principal): mitigado por inventário AST versionado, `shadow` medido na suíte e no staging com janela, flag de três estados e padrão `off`; `on` só no staging nesta spec.
- **Marca de sistema virar atalho:** é um contextvar por entrypoint (não por método), nomeado com `reason`, perde para o principal presente e não cobre requests de usuário; o teste de AST reprova uso da marca fora dos entrypoints listados (lista no `inventario.md`).
- **Thread nova sem herdar o contexto:** passa a falhar alto em `on` (era silenciosamente privilegiada). O inventário do §3.4 cobre os pontos atuais.
- **`FORCE RLS` em `rate_limit_buckets` sujeita o dono da tabela:** coberto pela verificação de `rolbypassrls` (Etapa 0) e pelo `grant_runtime_access()`; se faltasse a policy, o rate limit nega tudo (falha segura, mas é indisponibilidade de login): por isso a ordem "migração + smoke de rate limit" antes do código.
- **Trigger de delete da carteira:** só bloqueia `DELETE` de linha; a exclusão de conta não toca essas tabelas (R8). O expurgo futuro de 5 anos fica anotado como dívida.
- **`search_path`:** só novas sessões; sem uso de objeto não qualificado de `public` (R9).
- Compatibilidade com saves antigos: nenhuma. MockLLM/FallbackLLM: sem mudança (nenhum structured output novo). Quota/latência: nenhuma no caminho quente (a decisão do checkout é um `if` extra); RLS `using (true)` em `rate_limit_buckets` custo desprezível.

## 8. Decisões do dono

- **D1 — Flag de rollout `off`/`shadow`/`on`?** Recomendo **sim**. Motivo: o modo de falha de um chamador esquecido é indisponibilidade de worker/cron em produção (jobs reprocessam, recuperação de carteira e exclusão de conta param), e há caminhos que a suíte não exercita de verdade (webhook Stripe/Google Play, reconciliação, recuperação de exclusão). Em `shadow` o staging prova contador zero antes de `on`; o rollback é trocar a flag. Validade da flag: 2027-02-01.
- **D2 — `pg_net` instalado em `public` (advisor `extension_in_public`).** Recomendo **aceitar e documentar**, não mover. Os crons chamam `net.http_post` qualificado (`scripts/staging/schedule_cron.py:39`), então o schema da extensão não afeta a chamada; mover exige recriar a extensão, o que perde `net._http_response` e o histórico que `scripts/staging/verify_cron.py` e o watchdog `app.cron_requests` usam, e a extensão é gerenciada pela plataforma (`scripts/staging/schema_diff.py:22` já a trata como tal). A Etapa 0 mede `extrelocatable`; se for `false`, a decisão fecha sozinha. Peço confirmação.
- **D3 — `GRANT rpg_api TO rpg_runtime WITH INHERIT FALSE`.** Recomendo **não fazer agora**. Os privilégios de `rpg_api` são subconjunto dos de `rpg_runtime`; as policies `to rpg_api` somam (OR) com `runtime_all`, então o ganho de segurança é nulo e o ganho é só documental (já tratado por R10). Exigiria PG ≥ 16 (a Etapa 0 confere a versão).
- **D4 — As 3 RPCs `SECURITY DEFINER` de `public`** (`rpg_wallet_balance`, `rpg_wallet_history`, `rpg_current_session_active`; `20261015120000:6,14`, `20261013173632:27`): ficam fora desta spec, por decisão registrada. Recomendo spec própria, com inventário de quem as chama (cliente PostgREST vs backend) antes de revogar.
- **D5 — `app.current_owner_id()` com `execute` para `PUBLIC`** (`20260819002358:13-24`). Recomendo **aceitar**: `anon`/`authenticated` não têm `USAGE` em `app`, então não resolvem o nome, e a função só devolve o claim do próprio request; a invariante R11-iii protege contra mudança futura. Revogar de `PUBLIC` arrisca views/policies que a avaliem com outro dono, sem ganho.
- **D6 — Quando promover `on` a padrão no código** (e remover a flag): recomendo ao vencer a flag, depois de ≥ 14 dias de `on` no staging sem ocorrência. Fica fora desta spec; vira follow-up.

## 9. Desvios e achados da execução (11/11)

- **Migração:** `20261111140000_rls_hardening_rate_limit_wallet_delete.sql` (o nome de §3.5 era indicativo). R9 mantido: nenhum SQL do produto resolve objeto de `public` sem qualificar. O `comment on role` fica num bloco que só avisa (`notice`) se faltar privilégio.
- **Achado da Etapa 0 (c):** `gamedata.py` lê o catálogo global (`runtime_catalog.list`) **no import**, sem principal. Em `on` isso levantaria e cairia no `except` (overlay de artefatos perdido em silêncio). Tratamento: marca `boot:gamedata` no ponto do import (entrypoint de boot; entra na lista `SYSTEM_CALLER_ENTRYPOINTS`). `scripts/pool_promote.py` também recebe a marca.
- **`strict_mode` mora em `infrastructure/pool_scope.py`** (módulo novo, mantém `postgres.py`/`runtime.py` dentro do gate de tamanho); `build_database_runtime` não cresceu (a chamada `boot_rls_mode` substituiu o log antigo de `request_rls_disabled`, que agora é emitido de lá).
- **Marca de sistema** só roteia ao pool admin quando `request_rls` está ligado; sem `request_rls` o pool é um só e nada muda.
- **Threads:** nenhuma sem propagação em caminho hosted (ver `docs/spec410/inventario.md`); `speech_to_text._run_to_completion` (SPEC-412) usa `ensure_future(to_thread)`, que copia o contexto, e há teste. `creature_gen_jobs.drenar_em_segundo_plano` não copia, mas só roda com `_database_profile()` falso.
- **Não executado nesta rodada** (sem Docker): pgTAP (`rls_invariants_test.sql`, `rls_behavior_test.sql`), `tests/test_rls_effective.py` (`infra_local`) e a medição `shadow` real. Escritos por comparação com os existentes.
- **pgTAP R12:** para `image_quotes`/`shared_pool` o comportamento é provado por insert negado (a policy `WITH CHECK` roda antes de constraints/FKs) e por privilégio, sem semear `pricing_versions`; `operations`/`jobs` usam DML real.
- **Fora de escopo** (saíram): D2 `pg_net`, D3 `INHERIT FALSE`, D4 RPCs `public` (SPEC-413), D5 `current_owner_id` (aceitos); ligar `shadow`/`on` no staging e promover `on` a padrão (D6) ficam com o coordenador/follow-up.
