# SPEC-280 — games-fk-owner-orfaos

> **Status:** `approved` — decisão do dono em 19/10/2026 ("gere uma spec e desenvolva") sobre o achado do staging.
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Depende de:** SPEC-279 (apagar jogo não apaga mais gasto — a limpeza aqui apaga jogos), SPEC-190, SPEC-222
> **Desbloqueia:** smokes de staging que apagam usuário pelo Admin API sem limpar jogos antes

---

## 1. Contexto & Objetivo

`app.games.owner_id` não referencia `auth.users`. Quando um usuário é apagado pelo Admin API do Supabase
Auth (scripts de staging, painel, operação manual) — fora do fluxo de exclusão de conta da SPEC-190 — os
jogos dele ficam órfãos: conteúdo privado de campanha sem titular, fora do alcance de qualquer purge.
No staging (19/10) havia **13 jogos órfãos de 13 owners** e 58 `usage_events` de owners inexistentes.

O fluxo da SPEC-190 (tombstone → apaga `PRIVATE_TABLES` → apaga o usuário no Auth) não gera órfãos; o
buraco é o caminho "apagar direto no Auth". Objetivo: apagar o usuário no Auth apaga os jogos dele (e tudo
que cascateia de `games`), **sem** apagar dado financeiro nem o gasto (`usage_events`, retido pela SPEC-279),
e limpar com segurança os órfãos que já existem.

**Por que não uma FK `games.owner_id → auth.users`** (o desenho óbvio): medido em 19/10 com a FK `NOT VALID`
no Supabase local, ~50 testes `infra_local` quebram (criam jogos com owners sintéticos, sem usuário no Auth);
e os perfis `hosted`/`portable` (SPEC-181, OIDC) têm owners que **não existem** em `auth.users` — a FK
recusaria todo jogo nesses perfis. O tratamento equivalente para o perfil Supabase é um trigger
`AFTER DELETE ON auth.users` com a mesma semântica de `ON DELETE CASCADE`, sem restringir inserts.

## 2. Requisitos

- **R1** — `delete from auth.users where id = X` (o que o Admin API faz) apaga `app.games` de X e, por cascata,
  checkpoints/eventos/turnos/operações/memória/assets do jogo. `usage_events` sobrevivem (SPEC-279:
  `game_id` vira NULL); nenhuma tabela financeira (`wallet_*`, `payment_*`, `google_play_purchases`,
  `purchase_reconciliation_state`) é tocada.
- **R2** — O trigger nunca impede a exclusão no Auth: função `security definer`, `search_path=''`; owner com
  tombstone da SPEC-190 (`account_deletions`, qualquer status) é pulado — a cascata (`usage_events` SET NULL
  é UPDATE) bateria na cerca `account_write_fence` e o GoTrue falharia; esses jogos são do worker da 190.
  A migration recusa aplicar sem `BYPASSRLS` no dono da função (com `FORCE RLS` em `app.games` o delete
  seria no-op silencioso).
- **R3** — Migration idempotente e portátil: só cria o trigger se `auth.users` existir (`to_regclass`);
  `create or replace function` + `drop trigger if exists`; `revoke` da função para `public/anon/authenticated/
  rpg_api`; termina com `select app.grant_runtime_access();`.
- **R4** — Limpeza dos órfãos existentes por `scripts/admin_orphan_games.py --dsn-env VAR [--env-file F]`:
  - **dry-run por padrão**: conta jogos órfãos (owner sem linha em `auth.users`), owners distintos e
    `usage_events` ligados a eles (quantidade e soma que conta como gasto); saída só com contagens (sem ids);
  - exclui owners com qualquer tombstone em `account_deletions` (a SPEC-190 cuida);
  - só para bancos do perfil `hosted-supabase` (banco misto OIDC+Auth: o `--expect` do dry-run é a barreira);
  - depois do `--apply` o dry-run é refeito e o script sai com código 1 se ainda houver órfãos;
  - **recusa** se `auth.users` não existe ou está vazio (perfil OIDC: tudo pareceria órfão);
  - **recusa** se `usage_events.game_id` ainda cascateia (SPEC-279 não aplicada — apagaria gasto);
  - `--apply --expect N` só apaga se o número de órfãos medido na mesma transação for exatamente N (o
    número visto no dry-run); confere dentro da transação que a soma de gasto e as contagens das tabelas
    financeiras desses owners são idênticas antes/depois, senão `rollback`.
- **R5** — Evidência do staging sem PII em `docs/staging-wave-2026-10-17/evidence/spec280_*.json`.

### Fora de escopo

- Outras linhas por owner que não pendem de `games` (operações sem jogo, jobs sem jogo, `runtime_catalog`
  de escopo `user`, `owner_daily_counters`, blobs no Storage) quando o usuário é apagado direto no Auth:
  o caminho suportado de exclusão de conta continua sendo a SPEC-190. Os blobs de jogos apagados pelo
  trigger não entram na fila de purge (o caminho do app `commit_delete` enfileira; o do Auth não).
- Jogo criado *depois* da exclusão no Auth (JWT ainda válido por até 1 h) — corrida residual; o script de
  limpeza é reexecutável.

## 3. Design técnico

- **Migration** `supabase/migrations/20261019151000_auth_user_delete_erases_games.sql`:
  `app.erase_games_of_deleted_auth_user()` (`returns trigger`, `security definer`, `search_path=''`,
  `delete from app.games where owner_id = old.id; return old;`) + trigger `rpg_erase_games_on_auth_delete`
  `after delete on auth.users for each row`, dentro de `do $$ ... if to_regclass('auth.users') ...`.
  O dono da função é `postgres` (`bypassrls`), então a `force row level security` de `app.games` não bloqueia.
- **Script** `scripts/admin_orphan_games.py`: `plan(conn) -> dict` e `apply(conn, expect) -> dict` operam
  na transação do chamador (testáveis com rollback); `main` abre a conexão pelo `--dsn-env`, roda `plan`
  e, com `--apply`, `apply` + commit. Evidência JSON por `--out`.

## 4. Plano passo a passo

### Etapa 1 — Testes primeiro
1. `tests/test_spec280_orphan_games.py` (offline): texto da migration (trigger `after delete on auth.users`,
   `security definer`, `search_path=''`, `to_regclass`, idempotência, `revoke`, `grant_runtime_access`);
   CLI do script: sem `--apply` não chama `apply`; `--apply` sem `--expect` recusa.
2. `tests/test_spec280_orphan_games_local.py` (`infra_local`, rollback): usuário no Auth com jogo +
   `usage_events` + linha de carteira → `delete from auth.users` → jogo some, uso fica (`game_id` NULL),
   carteira intacta; jogo de outro owner intacto; `plan` acha órfão sintético e ignora owner em
   `account_deletions` `deleting`; `apply` com `expect` errado recusa; com o certo apaga, gasto igual;
   recusa com `usage_events` em cascata (simulado com FK recriada dentro da transação).
### Etapa 2 — Migration + script. ### Etapa 3 — `infra_local` + suíte completa.
### Etapa 4 — Staging: `migrations push --apply`; dry-run; `--apply --expect 13`; dry-run de novo (0);
prova do trigger com usuário sintético (cria usuário + jogo, apaga no Admin API, jogo some).

## 5. Critérios de aceite

- [ ] R1–R4 cobertos por testes verdes (offline + `infra_local`).
- [ ] Migration aplicada no staging; órfãos 13 → 0 sem mudar gasto nem tabelas financeiras; trigger provado
      com usuário sintético via Admin API; evidência em `docs/staging-wave-2026-10-17/evidence/spec280_*.json`.
- [ ] Revisão independente (`handoffs/SPEC-280-review.md`) aprovada.
- [ ] Suíte completa verde.

## 6. Smoke

Sem LLM. Smoke = §4 Etapa 4 no staging.

## 7. Riscos & compatibilidade

- Apagar no Auth agora apaga campanhas — é o comportamento desejado (dado privado sem titular); a
  exclusão pelo app (SPEC-190) não muda.
- Perfil OIDC: o trigger não dispara (não há delete em `auth.users`); o script recusa rodar sem usuários no Auth.
- Ordem de deploy: SPEC-279 antes (o script verifica).
