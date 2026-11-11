# SPEC-413 — rpcs-security-definer-publicas

> **Status:** `approved` (11/11: aprovada pelo coordenador por delegação do dono, "o resto é nois"; decisões do §8 = recomendações do autor; veto do dono segue possível) · antes `draft`
> **Criada:** 2026-11-11 · **Atualizada:** 2026-11-11
> **Depende de:** nenhuma (independente da SPEC-410; ordem de timestamps em §3)
> **Desbloqueia:** nada
> **Risco:** `alto` (migração + auth/carteira) → `spec-reviewer` obrigatório (AGENTS.md § Qualidade, revisão e evidência).
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `spec-reviewer` · **EVAL_AUTHORING_REQUIRED:** `false`.
> **Evidência:** pgTAP que falha antes (invariante "`public` sem função `SECURITY DEFINER` executável por `anon`/`authenticated`") e passa depois da migração; testes locais de carteira/ciclo de conta reescritos; critério §6: o advisor do Supabase para de acusar o lint `authenticated_security_definer_function_executable`.

---

## 1. Contexto & Objetivo

O advisor de segurança do Supabase no projeto do staging (11/11/2026) acusa, nível WARN, o lint `authenticated_security_definer_function_executable` em 3 funções do schema `public`, chamáveis por `authenticated` em `/rest/v1/rpc/…` com a chave publishable: `public.rpg_current_session_active()` (`supabase/migrations/20261013173632_account_lifecycle.sql:27–36`), `public.rpg_wallet_balance()` e `public.rpg_wallet_history(p_limit integer)` (`20261015120000_wallet_views_definer_functions.sql:6–30`, que substituiu duas views da carteira, SPEC-191). Todas têm `search_path=''`, filtram por `auth.uid()` e sessão viva, e o histórico limita `p_limit` a 200 (`:24`). Risco real baixo (cada usuário só vê o próprio saldo), mas é a **única superfície do app exposta pela Data API** (`supabase/config.toml:6`: `schemas = ["public", "graphql_public"]`; `public` não tem mais nada do app). Decisão do dono em 11/11: "vira spec própria" (era a D4 da SPEC-410, `specs/SPEC-410-rls-sem-falha-aberta.md:200`).

**Inventário de chamadores (feito em 11/11 por `Grep` no repositório, exceto histórico):**
- Código de produto: **nenhum**. O backend lê carteira por conexão psycopg própria (`infrastructure/wallet.py`, leitores de conta) e valida sessão com `app.runtime_session_active` (`infrastructure/supabase_identity.py:437`; definida em `20261015160000_runtime_login_role.sql:31`, schema `app`, sem grant a `authenticated`). Nem `web/src` nem o Android usam `supabase-js`/`.rpc(`/`/rest/v1` (grep em `web/src`, `web/e2e`; o executor repete incluindo qualquer pasta de app móvel).
- `rpg_current_session_active` era usada pelas policies de Storage `rpg_dynamic_*_own` (`20261013173632:47–66`), **removidas** por `20261017120000_rls_effective_storage_no_client_write.sql:88–91` (Storage sem escrita do cliente, SPEC-224). Hoje só as duas funções da carteira a chamam (`20261015120000:11,22`). O executor confirma isso consultando `pg_depend`/`pg_policies` no banco local e no remoto (R0).
- Scripts/testes: `scripts/staging/smoke_ab.py:296–347` (`check_wallet`, via REST), `tests/test_wallet_local.py:347–352,378–383`, `tests/test_account_lifecycle_local.py:271,298`, `tests/test_spec191_migrations.py:43–46` (lê o texto da migração antiga; segue verde porque ela não muda). `supabase/tests/*.sql`: nenhuma referência.
- Documentação: `docs/spec191/README.md:135–142,167` ("intencionais"); `specs/SPEC-224…:36` (R6, "continuam para `authenticated`", superado por esta spec); `docs/staging-wave-2026-10-17/evidence/advisors_security.json:7` e `docs/spec191/evidence/*` (históricos, não editar).

**Opções avaliadas.** (a) revogar e dropar as 3: superfície da Data API vai a zero; custo = reescrever 2 testes locais e 1 check de smoke. (b) mover para schema não exposto com execute só para o backend: o backend não as usa, então seria código morto com manutenção. (c) manter e documentar como exceção aceita: só faz sentido com cliente real, e não há. **Recomendação: (a).** O isolamento A×B da carteira continua provado pelo caminho real (psycopg, RLS `rpg_api`/`app.current_owner_id`), e o bloqueio por sessão revogada/conta apagada continua sendo `app.runtime_session_active` + `app.account_deletions` no backend.

## 2. Requisitos

- **R0 — confirmar antes de apagar.** Re-grep (`rpg_wallet_balance`, `rpg_wallet_history`, `rpg_current_session_active`, `wallet_balance_view`, `wallet_history_view`) em todo o repositório exceto `docs/historico/`, `CHANGELOG.md`, `specs/`, `handoffs/`; e no banco local e remoto: `pg_depend` (views, policies, outras funções) sem dependente das 3. Qualquer dependente vivo ⇒ parar e voltar ao dono (D1).
- **R1 — migração nova** (nunca editar as antigas): `drop function` das 3, nesta ordem (`rpg_wallet_balance()`, `rpg_wallet_history(integer)`, `rpg_current_session_active()`), com `if exists` e **sem** `cascade` (um dependente oculto deve falhar a migração, não sumir).
- **R2 — invariante pgTAP** em `supabase/tests/public_sem_funcoes_do_app_test.sql`: (i) nenhuma função `prosecdef` em `public` executável por `anon`, `authenticated` ou `PUBLIC`; (ii) mais forte: `public` não contém função que não pertença a uma extensão (`pg_depend.deptype='e'`). Se (ii) quebrar por função legítima de extensão em `public` no Supabase, ficar só com (i) e registrar. O teste falha no estado atual (as 3 funções existem).
- **R3 — default privileges.** Se a Etapa 0 confirmar que `pg_default_acl` concede `execute` em funções novas de `public` a `anon`/`authenticated` (padrão do Supabase), a migração acrescenta `alter default privileges in schema public revoke execute on functions from anon, authenticated, public` para o papel dono das migrações, de modo que uma função futura não reabra a superfície por esquecimento. Se o papel/ACL não permitir ou não se confirmar, o requisito sai e vai para o hand-back.
- **R4 — consumidores atualizados.**
  - `tests/test_wallet_local.py`: o bloco de `:340–383` troca "função existe e só `authenticated` executa" por "as funções **não existem** (`to_regprocedure` nulo) e `authenticated`/`anon`/`rpg_api` não têm `EXECUTE` em nada de `public` com `prosecdef`"; o saldo `311` do dono e o isolamento do outro dono passam a ser provados pelo caminho psycopg com principal (`PostgresWallet`/leitor de conta existentes), mesmo asserto numérico.
  - `tests/test_account_lifecycle_local.py:271,298`: a prova "conta apagada/sessão revogada não vê a carteira" passa a usar `app.runtime_session_active` (False para sessão revogada/tombstone) e a leitura da carteira pelo papel de runtime, não `public.rpg_wallet_balance()`. Mesmos casos, mesma intenção.
  - `scripts/staging/smoke_ab.py:285–347`: `check_wallet` vira "RPC não exposta": `POST /rest/v1/rpc/rpg_wallet_balance` com o JWT do usuário A e com a chave anon devolve 404/401/403 (nunca 200); o seed e a compra sintética (`PostgresWallet.credit_verified_purchase`) continuam, para manter a prova A×B no backend. O script antigo de resultado `pending_migration` (`:299–302`) deixa de existir.
  - `docs/spec191/README.md`: nota curta "removidas pela SPEC-413"; `specs/SPEC-224…` não é editada (spec `done`).
- **R5 — ordem de deploy e rollback** em `docs/spec413/README.md`: como nada de produto chama as funções, migração e código/scripts podem ir juntos; mesmo assim a migração vai ao staging **depois** do `smoke_ab.py` atualizado estar na `main` (senão o smoke antigo reprova). Rollback: arquivo SQL em `docs/spec413/rollback.sql` que recria as 3 funções (corpo copiado das migrações antigas), **testado** no banco local; nunca editar migração aplicada.
- **R6 — aceite no remoto.** Depois da migração no staging, `get_advisors(type=security)` (coordenador) não lista mais `authenticated_security_definer_function_executable`; o resultado entra em `docs/spec413/README.md` (data, projeto, saída resumida).

### Fora de escopo

- Outras funções `SECURITY DEFINER` em `app`, `storage` ou `extensions` (já sem grant a `authenticated`; `handoffs/SPEC-224-ASTRA-independent-review.md:24`).
- RLS/falha aberta (SPEC-410), views, Storage, `config.toml` (`schemas`); desligar a Data API inteira (`schemas = []`) é decisão separada (D3).
- Recriar leitura de carteira via REST para algum cliente futuro (nova spec, nova função, com revisão).
- Editar migrações antigas, `docs/historico/`, evidências históricas.

## 3. Design técnico

- **Arquivos novos:** `supabase/migrations/20261111130000_drop_public_definer_rpcs.sql` (R1, R3); `supabase/tests/public_sem_funcoes_do_app_test.sql` (R2, `plan(N)`, molde de `supabase/tests/rls_effective_storage_test.sql`: `begin; create extension if not exists pgtap with schema extensions; …; rollback`); `docs/spec413/README.md` (R0 com saídas, R5, R6); `docs/spec413/rollback.sql`.
- **Arquivos alterados:** `tests/test_wallet_local.py`, `tests/test_account_lifecycle_local.py`, `scripts/staging/smoke_ab.py`, `docs/spec191/README.md` (R4). `tests/test_spec191_migrations.py` não muda.
- **Timestamps (conflito com a SPEC-410):** a 410 cria `2026…_rls_hardening_rate_limit_wallet_delete.sql` e `supabase/tests/rls_invariants_test.sql`; os objetos não se sobrepõem (a 410 não toca nas 3 funções). O timestamp acima é maior que o da última migração da `main` (`20261028120000`); quem pousar depois confere `ls supabase/migrations` e renumera se houver empate ou se a outra tiver pousado com timestamp maior que precise ficar antes. Se a 410 pousar primeiro, a invariante R2 pode ser movida para dentro do arquivo dela; por padrão fica em arquivo próprio para evitar conflito de merge.
- **SQL esperado (forma, sem código de produto):** três `drop function if exists public.<nome>(<args>)`; opcionalmente o `alter default privileges … in schema public revoke execute on functions from …`.

## 4. Plano passo a passo

### Etapa 0 — Inventário (R0, sem código)
1. Greps do R0 e, no banco local (`supabase db reset` ou fluxo do repo) e no remoto (consulta somente leitura via MCP/CLI): `pg_depend` das 3 funções; `pg_policies` citando `rpg_current_session_active`; `pg_default_acl` do schema `public`; extensões com objetos em `public`. Salvar saídas em `docs/spec413/README.md`. Qualquer dependente vivo ⇒ hand-back e D1.

### Etapa 1 — Testes primeiro
1. `supabase/tests/public_sem_funcoes_do_app_test.sql` (R2). Rodar `npx supabase test db`: **falha** antes da migração (prova de que o teste pega o estado atual).
2. Reescrever os trechos de `tests/test_wallet_local.py` e `tests/test_account_lifecycle_local.py` (R4) para o contrato novo: `test_rpcs_publicas_da_carteira_nao_existem` (`to_regprocedure(...) is null`), `test_carteira_do_dono_pelo_runtime_311_e_outro_dono_vazio`, `test_sessao_revogada_nao_passa_em_runtime_session_active`. Os dois últimos passam no código atual; o primeiro falha. Rodar com o Postgres local (`bash scripts/dev/pt.sh tests/test_wallet_local.py tests/test_account_lifecycle_local.py tests/test_spec191_migrations.py`).

### Etapa 2 — Migração
1. Escrever a migração (R1, R3), aplicar no banco local, rodar `npx supabase test db` (verde) e os testes da Etapa 1 (verdes). Testar `docs/spec413/rollback.sql` (aplica e reverte; invariante volta a falhar com ele aplicado, o que prova que o teste enxerga).

### Etapa 3 — Smoke script e docs
1. Atualizar `smoke_ab.py::check_wallet` (R4); teste offline do script, se houver (`tests/test_spec192_staging_scripts.py`, `tests/test_spec191_staging_tools.py`). `ruff format --check` e `ruff check`.

### Etapa 4 — Remoto (coordenador, §6)
Aplicar no staging, rodar `smoke_ab.py` atualizado e `get_advisors` (R6). Revisão `spec-reviewer` do diff (foco: R0 completo, sem `cascade`, rollback testado).

## 5. Critérios de aceite

- [ ] R0 registrado: nenhum chamador de produto, nenhum dependente em `pg_depend`/`pg_policies`.
- [ ] `npx supabase test db`: o pgTAP novo falha antes e passa depois; os pgTAP existentes continuam verdes.
- [ ] Migração nova aplicada sem editar nenhuma antiga; `to_regprocedure` das 3 nulo no local e no staging.
- [ ] Testes locais reescritos verdes; `test_spec191_migrations.py` verde sem mudança.
- [ ] `smoke_ab.py` atualizado: RPC antiga responde ≥ 400 para A e anon; A×B da carteira provado pelo backend.
- [ ] `get_advisors(security)` no staging sem `authenticated_security_definer_function_executable` (evidência em `docs/spec413/README.md`).
- [ ] `docs/spec413/rollback.sql` testado no local.
- [ ] `uv run pytest` verde (suíte completa, 1× no pouso); revisão `spec-reviewer` APPROVED.

## 6. Smoke test com LLM real

Sem LLM. Smoke de infra no staging (coordenador): (1) aplicar a migração; (2) `scripts/staging/smoke_ab.py` atualizado: `rpc/rpg_wallet_balance` com JWT de A e com anon não devolve 200; (3) fluxo real de carteira pelo app (login, `GET /account/…` de saldo/uso) segue 200 com o mesmo saldo (prova que o backend não dependia das RPCs); (4) `get_advisors` security: lint ausente. Sem estes 4, a spec não vira `done`.

## 7. Riscos & compatibilidade

- Dependente oculto das funções (view, policy, função) ⇒ `drop` sem `cascade` falha a migração em vez de apagar o dependente; R0 antecipa.
- Cliente externo desconhecido chamando a RPC ⇒ passa a receber 404; mitigado pelo inventário (nenhum no repo) e pelo fato de o front não usar `supabase-js`. Registrado como D1.
- Saves, MockLLM, quota: não afetados. Dados de carteira: nenhuma tabela mexe (só funções).
- Rollback por `rollback.sql` (recria as funções com os mesmos grants); migração aditiva ao contrário não se aplica, é só remoção.

## 8. Decisões do dono

- **D1 — Opção (a): revogar e dropar as 3 RPCs.** Recomendo sim (nenhum cliente as usa; superfície da Data API vai a zero). Alternativa (c), manter como exceção aceita, só se existir cliente que o repo não mostra.
- **D2 — Default privileges (R3):** travar `public` para que funções futuras não nasçam executáveis por `anon`/`authenticated`? Recomendo sim, se a Etapa 0 confirmar o padrão do Supabase.
- **D3 — Desligar a Data API no projeto (`schemas = []`/remover `public`):** fora desta spec; recomendo avaliar depois, junto com o dono do Supabase, já que o app só usa Auth, conexão direta e service role. Não afeta GoTrue.
