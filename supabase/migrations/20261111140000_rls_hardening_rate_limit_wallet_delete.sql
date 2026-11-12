-- SPEC-410: higiene de banco da varredura de seguranca de 11/11 (defesa em profundidade).
--
--  R6  `app.rate_limit_buckets` era a unica tabela de `app` sem RLS: ENABLE + FORCE + as policies de
--      sistema (`runtime_all`/`admin_all`) que `app.grant_runtime_access()` cria para toda tabela com
--      RLS. Sem a chamada o FORCE RLS negaria tudo e o limite de login ficaria indisponivel.
--  R7  `revoke` explicito (public/anon/authenticated) nas 4 tabelas que so tinham o default.
--  R8  `delete` em `wallet_accounts` e `wallet_reservations` passa a ser barrado (ja era para
--      `wallet_entries`/`wallet_attempt_tickets`/`wallet_settled_usage`): a exclusao de conta nao as
--      apaga (retencao financeira de 5 anos, `infrastructure/account_lifecycle.py`).
--  R9  `search_path` dos logins: `extensions` antes de `public` (nenhum SQL do produto resolve objeto
--      de `public` sem qualificar; as funcoes SECURITY DEFINER fixam o proprio search_path).
--  R10 Comentario honesto de `rpg_api`: o isolamento por owner depende do `SET LOCAL ROLE` do app.
--
-- ORDEM DE DEPLOY: esta migracao ANTES do codigo (o codigo antigo e compativel: rate limiter e
-- ciclo de conta usam `admin_connection`). Aplicar como role BYPASSRLS (dono das tabelas), como em
-- `20261019151000`. Idempotente. ROLLBACK: docs/spec410/README.md (nunca editar esta migracao).

do $$
begin
  -- FORCE RLS sujeita tambem o dono da tabela: sem BYPASSRLS ele se trancaria fora.
  if not (select rolbypassrls from pg_catalog.pg_roles where rolname = current_user) then
    raise exception 'SPEC-410: apply as a BYPASSRLS role (table owner)';
  end if;
end $$;

-- R6 -------------------------------------------------------------------------------------------
alter table app.rate_limit_buckets enable row level security;
alter table app.rate_limit_buckets force row level security;
-- Cria `runtime_all` e `admin_all` (for all ... using (true) with check (true)) e os grants DML de
-- `rpg_runtime`/`rpg_admin`. O acesso e so de sistema: `rpg_api` perdeu o grant em 20260819002358.
select app.grant_runtime_access();
revoke all on app.rate_limit_buckets from public, anon, authenticated;

-- R7 -------------------------------------------------------------------------------------------
revoke all on app.assets, app.chronicle_digests, app.art_generations, app.memory_documents
  from public, anon, authenticated;

-- R8 -------------------------------------------------------------------------------------------
drop trigger if exists wallet_reservations_no_delete on app.wallet_reservations;
create trigger wallet_reservations_no_delete before delete on app.wallet_reservations
  for each row execute function app.reject_wallet_fact_mutation();
drop trigger if exists wallet_accounts_no_delete on app.wallet_accounts;
create trigger wallet_accounts_no_delete before delete on app.wallet_accounts
  for each row execute function app.reject_wallet_fact_mutation();

-- R9 -------------------------------------------------------------------------------------------
-- Vale so para sessoes novas (o pooler recicla). `app` segue primeiro; `public` por ultimo.
alter role rpg_runtime set search_path = app, extensions, public;
alter role rpg_admin set search_path = app, extensions, public;

-- R10 ------------------------------------------------------------------------------------------
do $$
begin
  comment on role rpg_api is
    'SPEC-410: tenant role. NOLOGIN/NOINHERIT, mas rpg_runtime e rpg_admin (inherit) sao membros e tem as '
    'policies runtime_all/admin_all (using true) em toda tabela com RLS. O isolamento por owner so vale '
    'se o app fizer SET LOCAL ROLE rpg_api + request.jwt.claim.sub (SPEC-224); sem isso a conexao e '
    'privilegiada. Por isso o pool falha fechado (RPG_RLS_STRICT_PRINCIPAL) e chamadores de sistema usam '
    'admin_connection/system_caller.';
exception when insufficient_privilege then
  raise notice 'SPEC-410: comment on role rpg_api skipped (insufficient privilege)';
end $$;

select app.grant_runtime_access();
