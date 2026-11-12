# SPEC-410 — RLS sem falha aberta: operação

Estado: código, migração, rollback, testes e runbook entregues em 11/11. **Nada foi aplicado em banco
remoto** (migração, flag em `shadow`/`on` e smoke do staging são do coordenador).

## O que mudou

- `infrastructure/request_context.py`: `system_caller(reason)` / `active_system_caller()`.
- `infrastructure/pool_scope.py`: modo da flag (`strict_mode`), log/contador e erro (`on_missing_principal`).
- `infrastructure/postgres.py`: `PostgresPool(strict_principal=...)`; `connection()` decide
  principal > marca de sistema > modo. `RlsScopeError` em `infrastructure/contracts.py`.
- Flag `RPG_RLS_STRICT_PRINCIPAL` (`off` | `shadow` | `on`, padrão `off`, validade 2027-02-01):
  só vale em perfil `hosted`/`hosted-supabase` com `request_rls`.
- Evento `pool.checkout_without_principal` (`caller`, `mode`) e métrica
  `rpg_pool_checkout_without_principal_total{mode}`.
- Migração `supabase/migrations/20261111140000_rls_hardening_rate_limit_wallet_delete.sql`.
- Inventário: `inventario.md`; medição da suíte: `shadow-suite.md`.

## Ordem de deploy no staging (runbook)

1. **Antes (somente leitura):** repetir as consultas da varredura de 11/11 e gravar em
   `docs/spec410/staging-antes.txt` (tabelas de `app` sem RLS/force, grants de `anon`/`authenticated`/PUBLIC,
   `search_path`/`rolinherit` dos logins, `pg_net`). Conferir `select rolbypassrls from pg_roles where rolname = current_user`
   no role que aplica a migração (a migração aborta com `SPEC-410: apply as a BYPASSRLS role` se não tiver).
2. **Migração** `20261111140000` (antes do código; o código antigo é compatível). Depois:
   `npx supabase test db` (ou as consultas de `supabase/tests/rls_invariants_test.sql`) e
   `scripts/staging/security_wave_smoke.py` (o limite de login incrementa `rate_limit_buckets`) + 1 login real.
   **Se o rate limit negar tudo** (login indisponível): rollback do item R6 abaixo.
3. **Deploy do código com `RPG_RLS_STRICT_PRINCIPAL=shadow`** (via `staging_flags.json` + `/staging-deploy`;
   variável de ambiente da Vercel só vale após novo deploy). Gates: `post_deploy`, `vercel_smoke`, `e2e_session`.
4. **Exercitar os caminhos de sistema** e filtrar os logs da Vercel por `pool.checkout_without_principal`
   (o contador é por instância serverless e zera; o log é a prova):
   `scripts/staging/verify_cron.py` (jobs, operations, account-deletions, reconciliation, finops — janela de
   ~65 min — e shared-pool), `scripts/staging/job_survival.py`, um turno real que fecha capítulo
   (`compress_chronicle` -> `ChronicleRepository.complete`) e escreve memória (pgvector), `scripts/staging/account_deletion_recovery.py`,
   `/data/*`, `/health`, `/metrics` e webhooks.
   **Critério para `on`: 0 ocorrências na janela inteira.** Cada ocorrência traz `caller` (módulo.função):
   classifique-a no `inventario.md` (a, b ou c), trate (`admin_connection` ou marca no entrypoint) e reinicie a janela.
5. **`on`** no staging; repetir 3 e 4: 0 erros `RlsScopeError`, mesmos gates verdes.
6. **Não ligar `on` por padrão no código** nesta spec (D6: follow-up ao vencer a flag, ≥ 14 dias de `on` sem ocorrência).

## Rollback

- Código: `RPG_RLS_STRICT_PRINCIPAL=shadow` ou `off` no `staging_flags.json` + redeploy, ou revert do commit.
  A migração é aditiva e compatível com o código antigo: reverter só o código não exige tocar no banco.
- Banco (nunca editar a migração aplicada; rodar como a mesma role BYPASSRLS):

```sql
-- R6: rate limit volta a ficar sem RLS (os grants DML de rpg_runtime/rpg_admin permanecem)
alter table app.rate_limit_buckets no force row level security;
alter table app.rate_limit_buckets disable row level security;
drop policy if exists runtime_all on app.rate_limit_buckets;
drop policy if exists admin_all on app.rate_limit_buckets;
-- R8
drop trigger if exists wallet_reservations_no_delete on app.wallet_reservations;
drop trigger if exists wallet_accounts_no_delete on app.wallet_accounts;
-- R9 (volta a ordem antiga; vale para sessões novas)
alter role rpg_runtime set search_path = app, public, extensions;
alter role rpg_admin set search_path = app, public, extensions;
-- R10 (não havia comentário antes)
comment on role rpg_api is null;
-- R7 (revoke explícito) não é revertido: o banco já não tinha nenhum grant para esses roles.
```

NÃO testado contra banco local (sem stack nesta rodada): rodar uma vez no banco local antes de depender dele.

## Dívidas e notas

- Expurgo financeiro de 5 anos (futuro): terá de desabilitar `wallet_*_no_delete` explicitamente
  (`alter table ... disable trigger`). `TRUNCATE` não dispara trigger de linha; o produto não usa `truncate`.
- `scripts/staging/job_survival.py` pula `wallet_accounts`/`wallet_reservations` na limpeza sintética.
- D2: `pg_net` fica em `public` (aceito e documentado; os crons chamam `net.http_post` qualificado, mover
  recriaria a extensão e perderia `net._http_response`). D3: sem `GRANT rpg_api TO rpg_runtime WITH INHERIT FALSE`
  (só o comentário de `rpg_api` foi corrigido). D5: `app.current_owner_id()` mantém `execute` a PUBLIC,
  protegido pela invariante R11-iii (`anon`/`authenticated` sem `USAGE` em `app`).
- D4: as 3 RPCs `SECURITY DEFINER` de `public` saíram em SPEC-413 (`20261111130000`, ainda não aplicada no staging).

## Evidência (vermelho -> verde)

- Python: `tests/test_rls_runtime_config.py` — com o código de antes da spec, os testes novos falham
  (`ImportError: cannot import name 'system_caller'`, evento `pool.checkout_without_principal` ausente); com a
  implementação, os 67 testes do arquivo passam.
- pgTAP (`supabase/tests/rls_invariants_test.sql`, `rls_behavior_test.sql`) e `tests/test_rls_effective.py`
  (`infra_local`): escritos, **não executados** (sem Docker/`RPG_TEST_DATABASE_URL`). A invariante (i) acusa
  `rate_limit_buckets` antes da migração e passa depois.
