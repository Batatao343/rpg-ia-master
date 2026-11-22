# SPEC-413 — RPCs SECURITY DEFINER públicas: dropadas

Migração: `supabase/migrations/20261111130000_drop_public_definer_rpcs.sql` (3x `drop function if exists`, sem `cascade`).
Rollback: `docs/spec413/rollback.sql` (recria as 3 com os mesmos grants). Invariante: `supabase/tests/public_sem_funcoes_do_app_test.sql`.

## Etapa 0 (R0) — inventário

- Banco remoto do staging (consulta do coordenador, 11/11): `public` sem tabela/view; as 3 funções com `search_path=""` e execute para `authenticated`; Postgres 17; `authenticated`/`anon` com USAGE e sem CREATE em `public`.
- Repo (grep em tudo exceto `docs/historico`): nenhum chamador de produto. `web/` sem `supabase-js`/`.rpc(`/`rest/v1`. Só testes (`test_wallet_local`, `test_account_lifecycle_local`, `test_spec191_migrations` que lê o texto da migração antiga), `scripts/staging/smoke_ab.py` e docs/evidências históricas.
- Dependências no SQL: `rpg_wallet_balance`/`rpg_wallet_history` chamam `rpg_current_session_active`. As 3 são `language sql` com corpo em string: não há `pg_depend` entre elas e a ordem do drop é indiferente para o Postgres (revisão Sol P3-3); no ROLLBACK a ordem importa (a de sessão é recriada antes). As policies de Storage `rpg_dynamic_*_own` que a usavam foram dropadas em `20261017120000` (linhas 88-91). Nenhuma view, trigger ou outra função as referencia.
- `pg_depend`/`pg_policies` no banco local: NÃO consultado (sem stack local nesta rodada). A ausência de `cascade` faz um dependente oculto falhar a migração em vez de sumir.

## D2 (default privileges): NÃO aplicado

`alter default privileges in schema public revoke execute ... from anon, authenticated, public` não resolve: ACL de default por schema é *somada* ao default global (PUBLIC tem EXECUTE implícito em função nova) e só consegue remover o que ela mesma concedeu. Remover de verdade exige `alter default privileges revoke execute on functions from public` global para o papel dono (afeta todos os schemas, p.ex. funções usadas por policies sob `rpg_api`), sem como validar aqui. Também quebraria `supabase/tests/rls_effective_storage_test.sql` (helper `public.spec224_rows` chamado como `authenticated`/`rpg_api`). Em dúvida, não fiz. A salvaguarda contra função futura exposta é o pgTAP novo (rodado à mão: nenhum workflow roda pgTAP hoje, follow-up F-2), que falha se surgir função própria em `public`.

## Runbook de aplicação no staging (coordenador)

1. Pousar na `main` o `smoke_ab.py` atualizado junto da migração (nada de produto chama as RPCs: código e migração são independentes).
2. Antes: `select oid::regprocedure from pg_proc where pronamespace='public'::regnamespace` deve listar só as 3; `pg_depend` sem dependentes (deptype 'n' de outros objetos).
3. Aplicar a migração (`supabase db push` ou MCP). Falha de dependência = parar; não usar `cascade`.
4. Verificar: `to_regprocedure` das 3 nulo; `npx supabase test db` (local) verde; `scripts/staging/smoke_ab.py`: `rpc/*` com JWT de A e anon = 404 com `PGRST202` (401/5xx não contam); fluxo de carteira do app segue 200; `get_advisors(security)` sem `authenticated_security_definer_function_executable`. Registrar abaixo (data, projeto, saída).
5. Rollback: aplicar `docs/spec413/rollback.sql` como MIGRAÇÃO NOVA (timestamp novo), nunca editando nem apagando a aplicada; um rollback manual fora de migração deixa `20261111130000` registrada como aplicada e exige `supabase migration repair` (revisão Sol P3-4).

## Evidência R6 (staging `uzeagzcyvxzrpjgrhaql`, 2026-11-22)

- **Aplicação:** `scripts.staging.migrations push --apply` aplicou `20261111130000` e `20261111140000`, nessa
  ordem; depois `status` = `in_sync`, 36 locais e 36 remotas (`docs/spec413/evidence/migrations_push.json`).
  Pré-checagens PC-1 e PC-2 de 13/11 em `docs/spec410/staging-antes.txt`; `audit-local` verde na `main`
  `84a3266a` (aplica as migrações num Postgres real).
- **PC-4, banco (MCP, só leitura):** `to_regprocedure` nulo para as 3 funções; nenhuma função própria em `public`.
- **PC-4, Data API:** `POST /rest/v1/rpc/{rpg_wallet_balance,rpg_wallet_history,rpg_current_session_active}`
  como `anon` = 3× `404 PGRST202`.
- **Advisor de segurança:** sem `authenticated_security_definer_function_executable`. Restam `pg_net` em `public`
  (aceito, D2 da 410) e proteção contra senha vazada desligada (ação do dono no painel).
- **Não rodou:** as 3 chamadas com JWT de usuário e o resto do `smoke_ab` (`rls`, `storage`, `pgvector`, `wallet`).
  O `setup_users` do script falha com 400 no `grant_type=password`: o staging usa Turnstile real desde `014a0c29`
  e o script não tem token de captcha (`docs/spec413/evidence/smoke_ab.json`). Nenhum usuário sintético ficou no
  Auth. pgTAP contra o staging também não rodou (sem `supabase test db` nesta máquina).

## Pré-checagens da revisão Sol (antes e depois de aplicar)

- PC-1 (antes): funções de `public` são só as 3; nenhuma função de outro schema cita os nomes no corpo (`prosrc`); `pg_policies`/`pg_views` sem menção.
- PC-2 (antes): logs da API do Supabase sem `POST /rest/v1/rpc/rpg_*` que não seja do `smoke_ab`.
- PC-3: aplicar com a versão `20261111130000`; sem `cascade`.
- PC-4 (depois): `to_regprocedure` nulo para as 3; pgTAP novo rodado contra o staging (é `begin … rollback`); smoke com 6× 404; carteira do app 200; advisor sem o lint.
- O pgTAP NÃO roda em CI hoje (nenhum workflow roda `supabase test db`): a guarda contra função nova exposta é manual até o follow-up F-2.
