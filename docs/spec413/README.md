# SPEC-413 — RPCs SECURITY DEFINER públicas: dropadas

Migração: `supabase/migrations/20261111130000_drop_public_definer_rpcs.sql` (3x `drop function if exists`, sem `cascade`).
Rollback: `docs/spec413/rollback.sql` (recria as 3 com os mesmos grants). Invariante: `supabase/tests/public_sem_funcoes_do_app_test.sql`.

## Etapa 0 (R0) — inventário

- Banco remoto do staging (consulta do coordenador, 11/11): `public` sem tabela/view; as 3 funções com `search_path=""` e execute para `authenticated`; Postgres 17; `authenticated`/`anon` com USAGE e sem CREATE em `public`.
- Repo (grep em tudo exceto `docs/historico`): nenhum chamador de produto. `web/` sem `supabase-js`/`.rpc(`/`rest/v1`. Só testes (`test_wallet_local`, `test_account_lifecycle_local`, `test_spec191_migrations` que lê o texto da migração antiga), `scripts/staging/smoke_ab.py` e docs/evidências históricas.
- Dependências no SQL: `rpg_wallet_balance`/`rpg_wallet_history` chamam `rpg_current_session_active` (por isso a ordem do drop). As policies de Storage `rpg_dynamic_*_own` que a usavam foram dropadas em `20261017120000` (linhas 88-91). Nenhuma view, trigger ou outra função as referencia.
- `pg_depend`/`pg_policies` no banco local: NÃO consultado (sem stack local nesta rodada). A ausência de `cascade` faz um dependente oculto falhar a migração em vez de sumir.

## D2 (default privileges): NÃO aplicado

`alter default privileges in schema public revoke execute ... from anon, authenticated, public` não resolve: ACL de default por schema é *somada* ao default global (PUBLIC tem EXECUTE implícito em função nova) e só consegue remover o que ela mesma concedeu. Remover de verdade exige `alter default privileges revoke execute on functions from public` global para o papel dono (afeta todos os schemas, p.ex. funções usadas por policies sob `rpg_api`), sem como validar aqui. Também quebraria `supabase/tests/rls_effective_storage_test.sql` (helper `public.spec224_rows` chamado como `authenticated`/`rpg_api`). Em dúvida, não fiz. A salvaguarda contra função futura exposta é o pgTAP novo (CI), que falha se surgir função própria em `public`.

## Runbook de aplicação no staging (coordenador)

1. Pousar na `main` o `smoke_ab.py` atualizado junto da migração (nada de produto chama as RPCs: código e migração são independentes).
2. Antes: `select oid::regprocedure from pg_proc where pronamespace='public'::regnamespace` deve listar só as 3; `pg_depend` sem dependentes (deptype 'n' de outros objetos).
3. Aplicar a migração (`supabase db push` ou MCP). Falha de dependência = parar; não usar `cascade`.
4. Verificar: `to_regprocedure` das 3 nulo; `npx supabase test db` (local) verde; `scripts/staging/smoke_ab.py`: `rpc/*` com JWT de A e anon >= 400; fluxo de carteira do app segue 200; `get_advisors(security)` sem `authenticated_security_definer_function_executable`. Registrar abaixo (data, projeto, saída).
5. Rollback: aplicar `docs/spec413/rollback.sql` (não editar a migração aplicada).

## Evidência R6 (preencher no staging)

Pendente.
