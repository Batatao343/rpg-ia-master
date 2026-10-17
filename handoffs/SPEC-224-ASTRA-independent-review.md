# SPEC-224 — Revisão Astra independente (adversarial)

- **Data:** 2026-10-17
- **Revisor:** Astra (≡ Opus, contexto separado; não escreveu a implementação)
- **Base:** branch `spec-224` empilhada sobre `spec-218` (`755fd74`), implementação ainda não commitada
- **Veredito:** **APPROVED** (com 4 correções aplicadas nesta revisão, 1 delas bloqueante). A spec segue
  `in-progress` só pelos critérios de staging (§5) e por depender do merge da SPEC-218.

## Escopo revisado

`infrastructure/{postgres,db_roles,request_context,runtime}.py`, todos os stores/jobs reclassificados
(`git diff` com 44 arquivos), migration `20261017120000_rls_effective_storage_no_client_write.sql`,
pgTAP `supabase/tests/*.sql`, `tests/{test_rls_effective,test_rls_runtime_config,conftest}.py`,
`scripts/{cloud_doctor,staging/runtime_role,staging/vercel_env,release/checklist}.py`, runbook e
`docs/spec224/README.md`. Ambiente: Supabase local `127.0.0.1:55322` (compartilhado com o worktree da
SPEC-219). Nenhuma ação remota.

## Ataques tentados

| Ataque | Resultado |
|---|---|
| **SQL direto** como `rpg_runtime` → `SET LOCAL ROLE rpg_api` + `request.jwt.claim.sub=A`, `select count(*)`/`update` sem `WHERE`/`delete` sem `WHERE` em **todas as 41 tabelas `app.*`** (rollback por tabela) | **Nenhum vazamento de dado por owner.** Tabelas por owner (games, checkpoints, events, operations 131 linhas, jobs 69, turns, memory_documents, chronicle_digests, assets, art_generations, runtime_catalog, image_quotes, usage_events 75, payment_*) → 0 linhas lidas/alteradas/apagadas. Wallet/kill switch/FinOps/reconciliação/Stripe/Google/rate limit/`owner_daily_counters`/cron → `InsufficientPrivilege`. Únicas leituras >0: catálogos globais sem owner (`pricing_versions`, `purchase_skus`, `embedding_profiles`) — por desenho. |
| `insert` com `owner_id` de B sob principal A | Bloqueado por policy (teste `test_user_pool_unfiltered_select_sees_only_the_principal_rows`). |
| Funções `SECURITY DEFINER` (`rpg_wallet_*`, `rpg_current_session_active`, `runtime_*`, `set_kill_switch`, `cron_health_check`, triggers) | `has_function_privilege('rpg_api', …)` = **false** em todas as 10; todas com `search_path` fixo (`''`/`pg_catalog`). `current_owner_id()` é invoker e nega tombstone. |
| Vazamento de role entre conexões do pool | `SET LOCAL`/`set_config(...,true)` morrem no fim da transação; nenhum `commit()`/`autocommit` no código (grep = 0); `connection.transaction()` dentro do checkout vira SAVEPOINT (role preservada). Teste de reuso da mesma conexão física com principal A → sem principal → B verde. |
| Pooler transacional / prepared statements | `prepare_threshold=None` no hosted; tudo por transação, sem `SET` de sessão. |
| **Efeito de sistema dentro do commit do turno** (confirm de quote de imagem diferido em `TurnEffects.flush`; `restore_effects` liberando reserva de quote abandonado na morte→checkpoint) | **BLOQUEANTE — corrigido.** Rodam na transação do request (`rpg_api`) e tocam `image_quotes … for update`/`wallet_*`, vetados a `rpg_api` → `InsufficientPrivilege`: arte paga impossível e restore quebrado com o RLS ligado. A suíte `RPG_TEST_REQUEST_RLS=1` não pegava porque os testes de quote usam pool fake com conexão `postgres`. Os gatilhos `DEFERRABLE INITIALLY DEFERRED` da wallet também disparariam no COMMIT como `rpg_api`. |
| Thread do heartbeat de lease | Rodava sem o `ContextVar` do principal → no login `rpg_runtime` (com `runtime_all`), fora do escopo por owner. **Corrigido** (contexto copiado). |
| Boot `hosted*`: DSNs trocados (`DATABASE_URL=rpg_admin`) ou role de plataforma (`authenticator`, `supabase_*_admin`) no DSN de request | Antes passavam (só `postgres/supabase_admin/service_role` eram barrados); `rpg_admin` como request faria **todo** request falhar no `SET ROLE` (não é membro de `rpg_api`). **Corrigido** + `cloud_doctor` usa a mesma regra. |
| Classificação admin × user nos handlers de request | Usos de sistema dentro de request, todos com filtro por owner em Python verificado: `api.py` (fronteira de exclusão de conta antes do principal; agregado de métricas; reformulação lendo wallet), `image_quotes` (issue/get/confirm: `owner_id=%s` em toda leitura), `account_read_model` (6 consultas, todas `owner_id=%s` + joins `o.owner_id=u.owner_id`), `usage_events.append` (operação travada e owner conferido antes; trigger definer revalida), `dynamic_art` (get/assets/set_quality por owner; `reserve` só é chamado após posse do jogo validada). Mesmo nível de proteção de antes da spec (era tudo `postgres`). |
| Storage sem as 4 policies `rpg_dynamic_*` | `web/src` não tem cliente Supabase nem `storage/v1` (grep = 0); downloads são signed URLs criadas pelo backend com service role (`supabase_blob.signed_url`), que não dependem de policy. pgTAP: `authenticated` não lê/insere/atualiza/apaga. |
| Migration idempotente | Aplicada 2× na mesma transação (rollback) sem erro; `grant_runtime_access()` só cria policy ausente. |
| Rollback `RPG_REQUEST_RLS=off` | Volta a `rpg_runtime`/DSN único sem trocar role (teste); `hosted*` sem admin DSN e RLS ligado falha no boot (fail-closed, R2). `vercel_env.py` recusa empurrar o DSN `rpg_runtime` sem `RPG_ADMIN_DATABASE_URL` (KeyError, não deploy silencioso) e o modo `--use-admin-dsn` envia `RPG_REQUEST_RLS=off`. |
| Performance (R8) | Local (loopback Docker, 1 600 transações × 2): `SET LOCAL ROLE` + `set_config` em 2 statements = **+1,3 ms p50**/transação (viola R8 < 1 ms). **Corrigido**: role e claims num único `select set_config(...)` → **+0,74–0,96 ms p50**. O p95 do turno no staging (≤ +5%) segue pendente. |

## Correções aplicadas nesta revisão

1. **Efeitos financeiros dentro da transação de request** (bloqueante): `infrastructure/db_roles.system_scope(connection)`
   — se a transação está em `rpg_api`, faz `SET LOCAL ROLE NONE` só durante o bloco, checa os gatilhos
   diferidos da wallet ainda elevado (`SET CONSTRAINTS ALL IMMEDIATE` → `DEFERRED`; os únicos deferrable
   de `app` são os da wallet) e volta a `rpg_api`. Aplicado em `ImageQuoteRepository.confirm`, no bloco de
   wallet de `restore_effects` e nas 7 entradas `connection=` de `PostgresWallet`/`DynamicArtRepository`.
   No-op para pool admin, fakes e `RPG_REQUEST_RLS=off`. Testes: `test_image_quote_confirm_inside_the_request_commit_reaches_the_wallet`,
   `test_restore_effects_release_wallet_hold_under_request_role` (vermelhos antes: `InsufficientPrivilege`).
2. **Heartbeat de lease** herda o contexto do request (`copy_context().run`) → UPDATE do lease sob `rpg_api`.
   Teste `test_lease_heartbeat_thread_inherits_the_request_principal` (vermelho antes).
3. **Validação de credenciais**: `privileged_request_db_user()` barra `postgres`, `supabase_*`, `authenticator`,
   `service_role`, `pgbouncer*` e `rpg_admin` no DSN de request; admin não pode ser `rpg_runtime`. 4 casos novos.
4. **Um round trip** para role + claims (R8).

## Riscos residuais (aceitos, registrados)

- **`rpg_runtime` mantém `runtime_all` (permissivo):** uma conexão do pool de request aberta **sem principal**
  (código futuro em thread sem contexto, rota fora de `_session_scoped_path`) roda cross-tenant, como antes da spec.
  Hoje isso é o que sustenta o rollback `RPG_REQUEST_RLS=off`, o perfil de DSN único (R9) e o `system_scope`.
  Follow-up recomendado após o smoke de staging: medir conexões de request sem principal e, se zero, remover
  `runtime_all` de `rpg_runtime` (request DSN passa a ser fail-closed).
- `rpg_admin` não tem `BYPASSRLS` (o `postgres` do Supabase não pode concedê-lo): usa `admin_all`. Equivalente.
- SQL injection dentro de uma transação `rpg_api` ainda pode `RESET ROLE` (o session user é `rpg_runtime`);
  o RLS por request é rede contra bug de filtro, não contra injeção.
- `system_scope` usa `SET CONSTRAINTS ALL`: se um dia surgir constraint deferrable fora da wallet, ela será
  checada no fim do bloco (comentado no código).
- O teste de inventário de tabelas por owner falha localmente só por `owner_daily_counters`, criada pela
  SPEC-219 no banco compartilhado (não existe nesta branch). Dois testes de `test_image_quotes_local.py`
  dependem de estado do banco compartilhado (ver evidência).

## Evidência

Ver seção "Revisão Astra" de `docs/spec224/README.md` (contagens de suíte, infra_local nos dois modos, pgTAP, ruff).
