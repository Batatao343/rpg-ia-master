# SPEC-224 — RLS efetivo: role de menor privilégio, `SET ROLE` por request e policies de Storage sem escrita do cliente

> **Status:** `in-progress` (código/migration/testes locais prontos em 2026-10-17; faltam os critérios de staging §5; revisão Astra APPROVED 2026-10-17; depende do merge da SPEC-218)
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-17
> **Depende de:** SPEC-218 `done` (boot fail-closed) · SPEC-191 `done`. ATENÇÃO: o commit `8570d62` (SPEC-197 R-05) já criou o login `rpg_runtime` sem BYPASSRLS, porém com policies `runtime_all` por tabela, então o RLS por owner ainda NÃO é efetivo. Rebasear R1/R2 sobre esse estado: resta `SET LOCAL ROLE rpg_api` por request (R3–R5), pool admin separado (R2/R9) e Storage (R7) (ordem final 2026-10-15)
> **Desbloqueia:** promoção a produção da SPEC-197 (R-05 de mitigado para fechado) (ordem final 2026-10-15)
> **Origem:** auditoria de segurança 2026-10-15 — achados AUTHZ-02 (média, já rastreado como R-05 aberto), INFRA-02 (média)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Astra` (≡ Opus em contexto separado, adversarial) · **REVIEW_REQUIRED:** `true` — toca credencial de banco de produção e isolamento multi-tenant; erro = indisponibilidade total ou perda da segunda camada
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

As migrations declaram `ENABLE + FORCE ROW LEVEL SECURITY` em todas as tabelas `app.*` com dados de usuário e policies `TO rpg_api` baseadas em `app.current_owner_id()`/`auth.uid()` (SPEC-103). Mas o backend conecta com o usuário do `DATABASE_URL` (role `postgres` do pooler, que tem `BYPASSRLS`) e **nunca** executa `SET ROLE rpg_api` nem define `request.jwt.claim.sub` (grep em `infrastructure/`, `services/`, `api.py` = 0 ocorrências). Nenhuma policy é avaliada em produção: o isolamento depende 100% de `WHERE owner_id = %s` em Python (verificado consistente em todas as rotas — não há IDOR hoje), e qualquer bug futuro de query vira vazamento cross-tenant sem rede de segurança. Isso já consta como R-05 (P1, aberto) e como follow-up (i) da SPEC-191 — sem spec de implementação.

Em Storage, `supabase/migrations/20260820113242_dynamic_storage_bucket_rls.sql:18-52` cria 4 policies **ativas** `to authenticated` (select/insert/update/delete no prefixo `users/<auth.uid()>/`), com o comentário "defesa em profundidade caso uploads assinados sejam habilitados no futuro". O backend usa service role (`infrastructure/supabase_blob.py:30-35`); o cliente nunca recebe `SUPABASE_URL`/chave publishable (0 hits em `api.py`/`web/src`). Hoje, portanto, a pré-condição de abuso (ter a chave publishable) não está satisfeita — mas a chave publishable é **pública por design** da Supabase, e um usuário com ela + o próprio JWT (visível no DevTools como cookie `rpg_access`) poderia subir webp de 20 MiB em loop (sem teto de objetos/bytes por usuário), apagar ou sobrescrever a arte já paga. Policies de escrita para o cliente são desnecessárias e devem cair.

Fatos:

- [F] `infrastructure/postgres.py:25-60` `PostgresPool` abre conexões com o DSN; nenhum `SET ROLE`/`set_config` no runtime; `scripts/staging/smoke_ab.py` e pgTAP (`supabase/tests`) usam `SET ROLE rpg_api` + `request.jwt.claim.sub` — prova de que as policies funcionam quando a role é assumida.
- [F] `supabase/migrations/20260819002358_auth_rls.sql`: `create role rpg_api nologin`, policies `to rpg_api`, `app.current_owner_id()` lê `request.jwt.claim.sub` e nega tombstone.
- [F] Workers/cron (jobs, reconciliação, FinOps, exclusão de conta) precisam de visão cross-owner (admin) — exigem conexão/role separada.
- [F] `infrastructure/request_context.py` já expõe `current_principal()` por request (ContextVar) — o `SET LOCAL ROLE` pode ser derivado dele.

Objetivo: duas credenciais com privilégios distintos (`rpg_runtime` para requests de usuário, sem `BYPASSRLS`, membro de `rpg_api`; `rpg_admin`/`postgres` para workers/cron/admin), `SET LOCAL ROLE rpg_api` + `set_config('request.jwt.claim.sub', owner, true)` em toda transação de request de usuário, prova em teste de que `select * from app.games` sem `WHERE` devolve só o owner, e Storage sem policies de escrita para `authenticated`.

## 2. Requisitos

- **R1** — Migration cria `rpg_runtime` **login** (senha fora do repo; `NOBYPASSRLS`, `NOSUPERUSER`, `GRANT rpg_api TO rpg_runtime`, `GRANT USAGE ON SCHEMA app`, grants de tabela/sequence/function idênticos aos de `rpg_api` — gerados por `DO` block que itera `information_schema`), e documenta `rpg_admin` como a role de workers (pode ser o `postgres` do pooler em staging; produção cria `rpg_admin` com `BYPASSRLS` e só os grants necessários — D-A).
- **R2** — Runtime: `DATABASE_URL` (user requests) e `RPG_ADMIN_DATABASE_URL` (workers/cron/account lifecycle/wallet settlement/admin scripts). `RuntimeConfig.validate` em `hosted*`: os dois presentes, usuários distintos, e `DATABASE_URL` cujo usuário não seja `postgres` (fail-closed; override `RPG_ALLOW_SUPERUSER_DSN=1` só local).
- **R3** — `PostgresPool.connection(principal=None)`: quando chamado no contexto de um request (`current_principal()` presente), toda transação executa primeiro `SET LOCAL ROLE rpg_api; SELECT set_config('request.jwt.claim.sub', %s, true)` (e `request.jwt.claims` JSON mínimo `{"sub": …, "role": "authenticated"}` se alguma policy usar `auth.uid()`); sem principal (worker) usa o pool admin. Conexões do pool de usuário nunca executam DDL nem funções `security definer` de admin.
- **R4** — Prova de isolamento (teste Postgres local, `tests/test_rls_effective.py`): com o pool de usuário e principal A, `select count(*) from app.games` (sem filtro) == nº de jogos de A; `update app.games set …` em jogo de B afeta 0 linhas; `insert` com `owner_id` de B falha por policy; sem `SET ROLE` (pool admin) vê todos. O teste roda contra o Supabase local do CI (`audit-local.yml`).
- **R5** — Todos os stores de request (`PostgresGameStore`, `postgres_turns`, `pgvector_memory`, `chronicle_repository`, `account_read_model`, `image_quotes`, `usage_events` escrita por request) passam a usar o pool de usuário; inventário por grep de `pool.connection()` com classificação `user|admin` registrado no README; workers (`postgres_jobs`, `reconciliation`, `finops_*`, `account_lifecycle`, `cron_internal`, `wallet` settlement via job) no admin.
- **R6** — Funções `security definer` públicas (`rpg_wallet_balance/history`, `rpg_current_session_active`) continuam para `authenticated`; nada muda para o cliente.
- **R7** — Storage: migration remove `rpg_dynamic_insert_own`, `rpg_dynamic_update_own`, `rpg_dynamic_delete_own` (mantém `select` para futuros downloads assinados por sessão, D-B); pgTAP: `authenticated` não insere/atualiza/apaga em `rpg-dynamic`; `app.guard_storage_account_write` permanece.
- **R8** — Performance: `SET LOCAL` + `set_config` custam < 1 ms; medir p95 do turno antes/depois no staging (SPEC-200 fornece a baseline) — regressão > 5% exige ajuste (ex.: pool com `SET ROLE` por sessão em vez de por transação).
- **R9** — Rollback: `RPG_ADMIN_DATABASE_URL` ausente em `local`/`portable` → ambos os pools usam o mesmo DSN (compatibilidade), mas o `SET LOCAL ROLE` continua; em `hosted*` é obrigatório (R2).

### Fora de escopo

- Trocar o pooler/Supavisor ou o modo transacional (SPEC-181/191).
- Uploads assinados pelo cliente (não existem).

## 3. Design técnico

- **Arquivos novos:** `supabase/migrations/2026MMDD_runtime_role_and_storage_policies.sql`; `tests/test_rls_effective.py` (marker `infra_local`); `supabase/tests/storage_no_client_write_test.sql`.
- **Arquivos alterados:** `infrastructure/postgres.py` (`PostgresPool.connection()` com `_apply_request_role(conn)`), `infrastructure/runtime.py` (`admin_database_url`, `RuntimeConfig.validate`, `build_database_runtime` cria `pool` e `admin_pool`), todos os stores/jobs (R5), `scripts/staging/*` (rotação/criação da role, nunca imprimindo senha), `scripts/cloud_doctor.py` (checa usuário do DSN), `.env.example`, `docs/spec197/runbooks/production-promotion.md` (ordem: criar role → setar envs → deploy → smoke → remover grants antigos).
- **Assinaturas**
  ```python
  class PostgresPool:
      def connection(self, *, as_admin: bool = False) -> ContextManager[psycopg.Connection]: ...
  def _apply_request_role(conn: psycopg.Connection, owner_id: UUID) -> None: ...
  ```
- **SQL de request (R3):**
  ```sql
  set local role rpg_api;
  select set_config('request.jwt.claim.sub', %s, true),
         set_config('request.jwt.claims', %s, true);
  ```

## 4. Plano passo a passo

### Etapa 0 — Reprodução (vermelhos no HEAD)
1. `test_rls_not_enforced_today` (Postgres local: pool atual + principal A, `select count(*) from app.games` sem filtro retorna jogos de A e B); `test_storage_authenticated_can_insert_today` (pgTAP).

### Etapa 1 — Migration de role + Storage (R1, R7)
1. **Testes:** pgTAP (role existe, `NOBYPASSRLS`, membro de `rpg_api`, grants idênticos; Storage sem escrita de cliente).
2. **Implementação:** migration; aplicar no Supabase local do CI.

### Etapa 2 — Pools e `SET LOCAL ROLE` (R2, R3, R5, R9)
1. **Testes:** `test_rls_effective.py` (R4 completo); `test_runtime_requires_distinct_dsns_in_hosted`; `test_worker_uses_admin_pool`; inventário por grep em teste (`tests/test_pool_usage_inventory.py`: toda chamada `pool.connection()` em módulos de worker usa `as_admin=True`).
2. **Implementação:** §3. **Verificação:** `uv run pytest -m infra_local` + suíte completa (fakes de pool nos testes offline ganham `as_admin`).

### Etapa 3 — Staging: role real, rotação do DSN, medição (R8)
1. Criar `rpg_runtime` no staging (script em `scripts/staging/`, senha gerada e enviada à Vercel como env, nunca impressa); redeploy; `two_user_smoke` (SPEC-191) + medição p95 (SPEC-200).
2. Registrar no README; fechar R-05 no risk-register.

## 5. Critérios de aceite
- [x] Etapa 0 vermelha no HEAD, verde ao final; R1–R9; `uv run pytest` e `-m infra_local` verdes; pgTAP verde (rodado localmente no Postgres do Supabase local; o CI `audit-local` roda no push). Evidência: `docs/spec224/README.md`.
- [ ] Staging com `rpg_runtime`: smoke de dois usuários verde; `select current_user` via `/metrics`-like debug NÃO — provar por log estruturado do pool (`role=rpg_api`) em 1 request; p95 do turno dentro de +5%.
- [ ] Security Advisor do Supabase sem novo ERROR; [x] revisão Astra APPROVED com tentativa explícita de acessar jogo de B com principal A via SQL direto no pool de usuário (2026-10-17, `handoffs/SPEC-224-ASTRA-independent-review.md`; falta só o Security Advisor no staging).
- [ ] `docs/spec197/risk-register.md` R-05 → fechado.

## 6. Smoke test
Staging (sem LLM): login A e B; `GET /game/saves` de cada um; inspeção de 1 linha de log do pool com `role=rpg_api`; tentativa de upload direto no Storage com JWT de A (ferramenta de teste, chave publishable do staging) → 403.

## 7. Riscos & compatibilidade
- **Indisponibilidade por grants incompletos**: mitigado pelo `DO` block que copia grants de `rpg_api` e pelo inventário R5 + smoke staging antes de produção.
- **Supavisor transacional**: `SET LOCAL` é por transação — compatível com pool transacional (sem `SET` de sessão).
- **Funções `security definer` de admin** (`app.set_kill_switch`, `cron_health_check`) chamadas só pelo pool admin.
- **Testes offline** usam fakes — garantir que `as_admin` não quebre fixtures (default `False`).

## 8. Pontos de decisão do dono
- **D-A (role admin):** manter `postgres` do pooler para workers em staging e criar `rpg_admin` só em produção. **Default recomendado:** criar `rpg_admin` já no staging (paridade).
- **D-B (policy `select` do Storage):** remover também (cliente nunca lê direto; signed URLs usam service role) ou manter. **Default recomendado:** remover as 4 (RLS sem policy = deny), reintroduzir quando houver download assinado por sessão.
- **D-C (`SET ROLE` por transação vs. por conexão):** **Default recomendado:** por transação (`SET LOCAL`), compatível com pooler.

## 9. Evidência requerida
- Saídas de `uv run pytest`, `-m infra_local`, pgTAP; vermelhos da Etapa 0; inventário R5 no README; log do pool no staging (pseudonimizado); medição p95 antes/depois; parecer Astra; `risk-register` R-05 fechado; `ESTADO_ATUAL.md`/`ROADMAP.md`.

## 10. Execução (2026-10-17) — decisões e desvios
- **Defaults de decisão usados:** D-A criar `rpg_admin` já no staging/local (migration `20261017120000`); D-B remover as 4 policies de Storage (inclui `select`; teste `test_account_lifecycle_local` ajustado: o cliente não lê Storage direto); D-C `SET LOCAL` por transação.
- **`rpg_admin` sem BYPASSRLS:** `postgres` do Supabase não pode criar role com BYPASSRLS (PG16+ exige superuser); recebe policy permissiva `admin_all` + os mesmos grants do `rpg_runtime`, via `app.grant_runtime_access()` estendida. Produção pode trocar por BYPASSRLS fora da migration.
- **R5 desvio:** `image_quotes`, `usage_events` e `account_read_model` usam o pool de **sistema** (tocam `wallet_*`/`kill_switches`, que `rpg_api` não acessa por desenho); filtro por owner segue em Python. Inventário completo em `docs/spec224/README.md` e travado por teste AST.
- **API de pool:** além de `connection(as_admin=...)`, módulos de sistema usam `admin_connection(pool)` (`infrastructure/db_roles.py`), que degrada para `pool.connection()` em fakes de teste (sem alterar os ~25 fakes).
- **Rollback:** `RPG_REQUEST_RLS=off` (`vercel_env.py --use-admin-dsn` aplica DSN `postgres` + flag). Em `hosted*` sem `RPG_ADMIN_DATABASE_URL` o boot falha fechado (R2).
- **Revisão Astra (2026-10-17, APPROVED):** 4 correções — `db_roles.system_scope` para efeitos de wallet dentro da transação de request (confirm de quote no commit do turno e `restore_effects` quebravam com `InsufficientPrivilege` sob `rpg_api`; gatilhos diferidos da wallet checados ainda elevados), heartbeat de lease herdando o principal, boot recusando role de plataforma/`rpg_admin` no DSN de request, role+claims num único round trip (R8: +0,74–0,96 ms p50 local). Risco residual registrado: `rpg_runtime` mantém `runtime_all`, então conexão de request sem principal segue cross-tenant (follow-up: remover após medir no staging).
- **Pendente (dono, staging):** (a) aplicar a migration no staging; (b) `scripts/staging/runtime_role.py --role rpg_admin --apply` e re-rotacionar `rpg_runtime`; (c) `vercel_env.py` (envia `RPG_ADMIN_DATABASE_URL`) ANTES do deploy; (d) `two_user_smoke` + log estruturado do pool (`pool.request_role_applied role=rpg_api`) em 1 request; (e) p95 do turno dentro de +5% (SPEC-200); (f) Security Advisor sem novo ERROR; (g) ~~revisão Astra~~ feita; (h) fechar R-05 no `risk-register`.

