# SPEC-280 — revisão independente (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (revisão técnica independente; não escreveu o código) · **Data:** 2026-10-19 · **Commit revisado:** `0a20fb9`

## Escopo

Branch `spec-280` (empilhada sobre `spec-279`), diff `git diff spec-279...spec-280`: migration
`supabase/migrations/20261019151000_auth_user_delete_erases_games.sql`, `scripts/admin_orphan_games.py`,
`tests/test_spec280_orphan_games.py`, `tests/test_spec280_orphan_games_local.py` e a spec. Conferido contra
SPEC-190 (`infrastructure/account_lifecycle.py`, `20261013173632_account_lifecycle.sql`), SPEC-222 e SPEC-279.
Fora: aplicação no staging (Etapa 4), suíte completa.

Verificado e correto:
- Fecho de cascata de `app.games` no Postgres local: checkpoints, events, turns, operations, jobs, memory,
  assets, art_generations, chronicle_digests, runtime_catalog. `usage_events.game_id` = SET NULL (SPEC-279). Nenhuma
  tabela financeira nem `image_quotes` está no fecho, então nenhum trigger append-only/imutável é atingido.
- Função `security definer`, dona `postgres` (`rolbypassrls = t`), então a FORCE RLS de `app.games` não se aplica.
  Executado como `supabase_auth_admin` (papel do GoTrue) sem tombstone: jogo apagado, uso fica com `game_id` NULL.
- Fluxo SPEC-190: `finish` apaga `usage_events`/`art_generations` antes de `games` e só depois chama
  `identity.delete_user`, então o trigger é no-op ali.
- Script: dry-run é só leitura (rollback). `apply` usa `for update of g`, confere a contagem e o snapshot
  financeiro na mesma transação, e `conn.transaction()` faz rollback em qualquer exceção. A saída tem só
  contagens; o DSN é lido pelo nome e nunca impresso. As 9 tabelas de `FINANCIAL_TABLES` têm `owner_id`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `supabase/migrations/20261019151000_auth_user_delete_erases_games.sql:8-14` | **Viola R2.** Se o owner tem tombstone em `app.account_deletions` (qualquer status) e ainda tem jogos, o `delete from app.games` do trigger cascateia `UPDATE usage_events SET game_id=NULL` (e `art_generations.asset_id` SET NULL). Isso dispara `account_write_fence` (BEFORE INSERT OR UPDATE), que dá `raise 'account_deleted'`. Resultado: o Admin API/GoTrue falha ao apagar o usuário ("Database error deleting user"). Reproduzido localmente como `supabase_auth_admin` em transação com rollback: `ERROR: account_deleted … UPDATE ONLY "app"."usage_events" SET "game_id" = NULL … PL/pgSQL function app.erase_games_of_deleted_auth_user() line 3`. Acontece, por exemplo, quando o operador apaga pelo painel um usuário cuja exclusão SPEC-190 está em `deleting` (worker atrasado ou caído entre `begin` e o delete privado). | Na função: `if exists (select 1 from app.account_deletions where owner_id = old.id) then return old; end if;` antes do delete. O worker SPEC-190 é dono desse owner e apaga os jogos. Assim fica consistente com o script, que já pula esses owners. Adicionar um teste `infra_local`: tombstone + jogo + `usage_events` → `delete from auth.users` não falha e o jogo fica para o worker. |
| P2-1 | P2 | `tests/test_spec280_orphan_games.py:23` | `assert "raise" not in sql` é usado como prova de R2, mas não cobre `raise` vindo das cascatas (ver P1-1). Dá falsa garantia. | Manter, mas a prova de R2 tem de ser o teste `infra_local` do P1-1. |
| P2-2 | P2 | `scripts/admin_orphan_games.py:26-29` (e `:74-76`) | O script exclui só `status='deleting'`. Owner com tombstone `deleted` e jogos remanescentes faria o `delete` bater no fence. Falha segura (psycopg levanta e a transação inteira volta), mas o script aborta em vez de pular. | Excluir qualquer linha em `account_deletions` (`not exists (… where d.owner_id = g.owner_id)`). Na contagem `skipped`, também sem filtro de status. |
| P2-3 | P2 | `supabase/migrations/20261019151000_auth_user_delete_erases_games.sql:8-14` | A correção depende de o dono da função ter BYPASSRLS. Se a migration for aplicada por um papel sem bypass, a FORCE RLS de `app.games` faz o delete afetar 0 linhas em silêncio (no-op invisível). No local e no `supabase db push` o dono é `postgres` (bypass), então hoje está ok. | Opcional: no bloco `do $$`, `raise` se `(select rolbypassrls from pg_roles where rolname = current_user)` for falso. Também pode ficar como verificação no smoke de staging (Etapa 4: trigger provado via Admin API). |
| P2-4 | P2 | `scripts/admin_orphan_games.py:41-49` | O guard OIDC só detecta `auth.users` vazio. Num banco misto (perfil `hosted`/OIDC já usado e algum usuário Supabase criado), jogos de owners OIDC aparecem como órfãos. O `--expect` do dry-run é a única barreira. | Documentar no docstring/runbook que o script só vale para bancos do perfil `hosted-supabase`. Opcional: exigir `--profile hosted-supabase` explícito. |
| P2-5 | P2 | `scripts/admin_orphan_games.py:134` | O comentário diz "after apply: must be 0", mas nada verifica isso. | Opcional: `if a.apply and result["plan"]["orphan_games"]: return 1`. |
| INFO | — | migration `:15` + `:26` | O `revoke` é seguido de `grant_runtime_access()`, que regrava EXECUTE para `rpg_runtime`/`rpg_admin` (padrão do projeto). Função de trigger não pode ser chamada diretamente, então não há impacto. | Nenhuma. |
| INFO | — | `tests/test_account_lifecycle_worker_local.py:20-21` | `test_leased_image_worker_cannot_upload_after_account_erasure` falha com `DuplicateTable: payment_orders` porque reaplica migrations num banco já migrado. Pré-existente e não tocado pela 280; não é regressão. | Fora do escopo (o teste supõe um banco sem as migrations de 13/10). |

## Correções aplicadas

Nenhuma até agora (cabe ao executor).

## Pendências

- Corrigir P1-1 (+ teste) e P2-2 antes do push para o staging. P2-3/P2-4/P2-5 ficam a critério do executor.
- Etapa 4 (staging) continua pendente, assim como a evidência `spec280_*.json`.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -o addopts="" tests/test_spec280_orphan_games.py → 4 passed
RPG_TEST_DATABASE_URL=… pytest tests/test_spec280_orphan_games_local.py tests/test_account_lifecycle_local.py tests/test_account_lifecycle_worker_local.py → 10 passed, 1 failed (pré-existente, DuplicateTable)
psql (local): fecho de FKs de app.games + triggers + dono/bypassrls da função → confirmado acima
psql (local, supabase_admin, BEGIN…ROLLBACK): tombstone + jogo + usage_events, delete auth.users como supabase_auth_admin → ERROR account_deleted (P1-1); sem tombstone → jogo apagado, usage game_id NULL
```
