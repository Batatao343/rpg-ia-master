# SPEC-413 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (spec-reviewer, papel Sol) · **Data:** 2026-11-11 · **Commit revisado:** `ea65f0c1`

**Seguro aplicar no staging: sim**, desde que as pré-checagens da § Pendências (PC-1 a PC-4) rodem antes. Nenhum achado P0 ou P1.

## Escopo

`git diff main...HEAD` (base `55f09de1`, commit único `ea65f0c1`): migração `20261111130000_drop_public_definer_rpcs.sql`, `docs/spec413/{README.md,rollback.sql}`, pgTAP `supabase/tests/public_sem_funcoes_do_app_test.sql`, `tests/test_wallet_local.py`, `tests/test_account_lifecycle_local.py`, `scripts/staging/smoke_ab.py::check_wallet`, `docs/spec191/README.md` e o cabeçalho e § 9 da spec.
Fora do escopo: nenhum SQL foi executado (sem Postgres local, por decisão do coordenador). A leitura é estática e foi cruzada com os fatos do remoto que o coordenador informou.

### Verificações que passaram

- **Assinaturas da migração** batem com a criação. `rpg_wallet_balance()` e `rpg_wallet_history(p_limit int default 50)` vêm de `20261015120000:6,14`; `rpg_current_session_active()` vem de `20261013173632:27`. `int` = `integer` e o default não entra na assinatura. Nenhuma migração posterior faz `create or replace`, `alter function` ou `grant/revoke` nelas (grep em `supabase/migrations/`). As views legadas e as policies `rpg_dynamic_*_own` que usavam a função de sessão foram removidas em `20261015120000:3-4` e em `20261017120000:88-91`.
- **Ordem dos drops.** As 3 são `language sql` com corpo em string (`as $$…$$`), não `BEGIN ATOMIC`, então não há `pg_depend` entre elas e a ordem é indiferente para o Postgres. A ordem usada (carteira antes da sessão) ainda é a correta: nunca deixa uma função "quebrada" no meio. Sem `cascade`. O `if exists` deixa a migração idempotente e o timestamp `20261111130000` é maior que o último aplicado (`20261028120000`), sem colisão.
- **Typo mascarado por `if exists`:** não há. As 3 assinaturas estão corretas. A prova pós-aplicação é o `to_regprocedure` do runbook e do pgTAP.
- **Rollback.** Os corpos, `language sql`, `stable`, `security definer`, `set search_path=''` e os `revoke all … from public, anon, rpg_api` + `grant execute … to authenticated` são idênticos, linha a linha, aos das migrações de origem. A ordem (sessão primeiro) é necessária porque `check_function_bodies` valida a referência de `public.rpg_current_session_active()` no corpo das funções da carteira. O owner fica igual se rodar como `postgres` (SQL editor ou psql), como na migração original. O `service_role` recebe EXECUTE pelo default ACL de `public` nos dois casos, então nada fica mais amplo que o original.
- **pgTAP** segue o molde dos existentes (`begin; create extension if not exists pgtap with schema extensions; plan; …; finish(); rollback;`).
  - O `deptype='e'` com `classid='pg_proc'::regclass` e `objid=p.oid` é a forma correta de checar se a função pertence a uma extensão.
  - `has_function_privilege('anon'|'authenticated', oid, 'EXECUTE')` já inclui o que vem de PUBLIC por herança.
  - Com os fatos do remoto, as 3 asserções falham antes da migração (as 3 funções existem e `authenticated` tem EXECUTE) e passam depois.
  - Ordem dos arquivos: `public.spec224_rows` é criado dentro da transação de `rls_effective_storage_test.sql`, que faz `rollback` (linha 138). Não vaza para este teste em nenhuma ordem.
  - Nenhuma migração do repo cria função em `public` além das 3. `vector` está em `extensions`.
- **Testes `*_local`** lidos como se fossem rodar:
  - As fixtures `wallet_case` e `deletion_case` existem.
  - `app.runtime_session_active(uuid, uuid)` é chamado na ordem (sessão, usuário), como em `20261015160000:31` e em `infrastructure/supabase_identity.py:437`.
  - `PostgresWallet(c.pool).balance` já é usado na mesma fixture (`:319`) e é só leitura (`infrastructure/wallet.py:187`).
  - A query `exposed` usa `values(...)` com tipo text, que tem cast implícito para `name` em `has_function_privilege`.
  - Coleta e import passam (pulados sem `RPG_TEST_DATABASE_URL`).
- **Consumidores.** Fiz meu próprio grep, que confirma o do executor. `rpg_wallet_balance|rpg_wallet_history|rpg_current_session_active`, `rest/v1/rpc`, `.rpc(`, `@supabase/` e `createClient(` só aparecem em `scripts/staging/smoke_ab.py`, nos testes, nas specs/handoffs e em docs de evidência. `web/package.json` não tem `supabase`; `web/src`, `web/android`, `workers/`, `infrastructure/`, `scripts/` e `.github/` não têm nenhum chamador. O Android (Capacitor) não fala com a Data API. O drop não quebra o produto.
- **D2 não aplicado: a justificativa procede.** Pela documentação do Postgres, o `ALTER DEFAULT PRIVILEGES … IN SCHEMA` só soma ao default global e não revoga o EXECUTE que PUBLIC recebe por padrão. Revogar por schema tiraria só os grants do Supabase a `anon`/`authenticated`/`service_role`, mas `anon`/`authenticated` seguiriam executando via PUBLIC. O efeito real exige `alter default privileges for role postgres revoke execute on functions from public` global, que vale para `app.*` e quebraria o helper `public.spec224_rows` (criado por `postgres`, chamado como `authenticated`/`rpg_api`). Não aplicar foi a decisão certa.
- **Regras.** O diff não toca `docs/guias/*`, `AGENTS.md`, `evals/` nem `specs/index.yaml`. O ruff, o size budget e o `dup_helpers` passaram. `check_wallet` tem 46 linhas.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `scripts/staging/smoke_ab.py:326` | `all(status >= 400 …)` aceita qualquer erro: um 401 de JWT de A expirado ou inválido (PGRST301), um 5xx do gateway ou um 503 de cache de schema contam como "RPC não exposta". Depois do drop, o PostgREST devolve **404 `PGRST202`** ("Could not find the function … in the schema cache") para o JWT de A e para anon. Um smoke mal configurado passaria em silêncio. | Exigir `status == 404` (ou 404 com `code == "PGRST202"` no corpo) nas 6 chamadas e gravar o `code` no `res`. Antes do drop, aceitar 401/403 só para anon não é necessário: a spec já pede rodar depois. |
| P2-2 | P2 | `docs/spec413/README.md:15` | O texto diz que a salvaguarda contra função futura exposta é "o pgTAP novo (CI)". Nenhum workflow em `.github/` roda `supabase test db` ou pgTAP (grep vazio). Hoje a salvaguarda é manual e local, ou seja, D2 fica sem rede automática. | Corrigir o texto ("pgTAP local/manual; não roda em CI") e abrir follow-up (ver Pendências F-1/F-2). |
| P3-1 | P3 | `tests/test_account_lifecycle_local.py:263` | `balance(c.a)==0` é vacuamente verdadeiro: A nunca teve `wallet_accounts`, e `balance` lê por `owner_id` sem gate de sessão. A prova real de "sessão revogada não chega à carteira" é o `runtime_session_active=False` (`:257-262`) mais o `Unauthorized` do `verify` (`:254`). A asserção antiga provava o gate pelo caminho do cliente, que deixou de existir. Não há perda de cobertura do produto, mas a linha engana. | Remover a linha ou comentar que o gate do backend é o `verify`. |
| P3-2 | P3 | `tests/test_wallet_local.py:363` | Repete `balance(other)==0` da `:321`. O isolamento A×B pelo backend é um `where owner_id=%s` trivial. Aceitável, porque não há mais superfície de cliente. | Opcional: remover a duplicata. |
| P3-3 | P3 | `docs/spec413/README.md:10` | "(por isso a ordem do drop)": com corpo em string não há dependência que o Postgres imponha. A ordem é boa prática, não requisito. | Ajustar a frase (cosmético). |
| P3-4 | P3 | `docs/spec413/README.md:23` | O rollback manual deixa `20261111130000` registrado como aplicado em `supabase_migrations.schema_migrations`. Um `db reset`/`push` futuro dropa de novo. | No passo 5, acrescentar: depois do rollback, criar uma migração nova de recriação (ou `supabase migration repair --status reverted 20261111130000`) e reverter o arquivo na `main`. |

## Correções aplicadas

Nenhuma até aqui. O revisor não edita código.

## Pendências

**Pré-checagens obrigatórias antes de aplicar no staging (coordenador):**

- **PC-1.** Imediatamente antes de aplicar, repetir no remoto: (a) `select oid::regprocedure, prosecdef from pg_proc where pronamespace='public'::regnamespace` deve listar só as 3; (b) `select oid::regprocedure from pg_proc where prosrc ilike any(array['%rpg_wallet_balance%','%rpg_wallet_history%','%rpg_current_session_active%']) and pronamespace <> 'public'::regnamespace` deve vir vazio, porque chamador com corpo em string não aparece em `pg_depend`; (c) `pg_policies`/`pg_views` sem os nomes.
- **PC-2.** Olhar os logs da API do Supabase (PostgREST) dos últimos 7 a 14 dias por `POST /rest/v1/rpc/rpg_` vindos de fora do `smoke_ab`. É a evidência barata de que não há cliente externo desconhecido, que o grep do repo não pode dar.
- **PC-3.** Aplicar com a mesma versão `20261111130000` (`supabase db push` ou MCP `apply_migration` com esse nome), para o histórico remoto bater com o arquivo. Sem `cascade` em nenhuma hipótese. Erro de dependência: parar.
- **PC-4.** Depois de aplicar: `to_regprocedure` das 3 nulo; rodar o próprio `supabase/tests/public_sem_funcoes_do_app_test.sql` via psql contra o staging. Ele é `begin … rollback`, então o `create extension pgtap` também é revertido. Assim o pgTAP roda uma vez de verdade, já que não rodou local. Depois, smoke (com P2-1 corrigido ou lendo os 6 status, que devem ser 404), fluxo de carteira do app 200 e `get_advisors(security)` sem `authenticated_security_definer_function_executable`.

**Follow-ups (para o coordenador virar spec ou nota):**

- **F-1 (barato, recomendado):** D3, tirar `public` de `[api].schemas` no projeto (Data API sem schema exposto). Remove a classe de risco inteira, já que o app só usa Auth, conexão direta e service role. Já está registrado como fora da 413.
- **F-2:** levar o pgTAP de `supabase/tests/` para o CI (job com `supabase start` + `supabase test db`), ou um teste `infra_local` equivalente. Sem isso, o invariante R2 não protege contra regressão.
- **F-3 (alternativa a D2):** um event trigger `ddl_command_end` que dê `revoke execute … from public, anon, authenticated` em função nova de `public`. Só se F-1 não for adotado, porque exige validar suporte via `supautils` no Supabase hosted.

## Comandos rodados

```text
git diff main...HEAD --stat → 9 arquivos, +173/-81
bash scripts/dev/pt.sh tests/test_spec191_migrations.py tests/test_spec191_staging_tools.py tests/test_spec192_staging_scripts.py tests/test_wallet_local.py tests/test_account_lifecycle_local.py → rc=0, 39 passed, 21 skipped (os *_local coletados e pulados sem RPG_TEST_DATABASE_URL)
ruff check . → All checks passed (rc=0)
ruff format --check . → 1980 files already formatted (rc=0)
scripts/dev/size_budget.py → rc=0
scripts/dev/dup_helpers.py --diff main...HEAD → nenhuma função nova com nome já usado
Grep consumidores (rpg_wallet_*/rpg_current_session_active, rest/v1/rpc, .rpc(, @supabase/, createClient() em todo o repo exceto docs/historico → só smoke_ab, testes, specs/handoffs e docs de evidência
Grep .github/ por supabase/pgtap → vazio (pgTAP fora do CI)
```
