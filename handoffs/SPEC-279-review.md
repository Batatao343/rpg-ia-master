# SPEC-279 — revisão independente (review)

> **Veredito:** `CHANGES_REQUIRED` (1 achado P1; o resto está correto)
> **Revisor:** Opus (revisor independente, não escreveu o código) · **Data:** 2026-10-19 · **Commit revisado:** `685faba` (branch `spec-279`)

## Escopo

`git diff main...spec-279`: migration `supabase/migrations/20261019150000_usage_events_survive_game_delete.sql`,
`infrastructure/finops_reader.py` (`ops_counts`), `infrastructure/account_read_model.py` (`usage`),
`scripts/staging/spec279_usage_survives_delete.py`, `tests/test_spec279_usage_retention{,_local}.py` e a spec.
Também conferidos os leitores e escritores de `app.usage_events` fora do diff: `infrastructure/usage_events.py`,
`infrastructure/postgres_turns.py` (claim), `infrastructure/wallet.py` (settle/reconcile),
`services/wallet_recovery.py`, `services/retention.py`, `infrastructure/account_lifecycle.py`
(`PRIVATE_TABLES`/export), `infrastructure/audit_source.py`, a cerca `account_write_fence` (SPEC-190), RLS/grants.
Fora do escopo: aplicação no staging (não foi feita) e a suíte completa.

## O que está correto

- **R1/R2:** no Postgres local, a FK `usage_events_operation_id_fkey` sumiu e `usage_events_game_id_fkey` virou
  `ON DELETE SET NULL` (conferido em `pg_constraint`). Depois do delete da campanha, `usage_groups`, `owner_usage`
  e `ops_counts.turns` do dia ficam iguais (teste local).
- **R3:** `operation_kind` vem só de `app.operations` (trigger `BEFORE INSERT`, `security definer`, valor do cliente
  sobrescrito; o teste local cobre esse caso). O backfill pula owners em `account_deletions`. Os leitores usam
  `left join` + `coalesce` e têm fallback por `has_column` quando o schema é anterior à migration (R6).
- **Cerca SPEC-190:** o `SET NULL` é um UPDATE e dispara `account_write_fence`. Na exclusão de conta não há conflito,
  porque `PRIVATE_TABLES` apaga `usage_events` antes de `operations`/`games` na mesma transação.
  `test_account_lifecycle_local` está verde.
- **R5:** RLS e grants não mudaram (`rpg_api` continua só com `select,insert`). Os grants de UPDATE para
  `rpg_runtime`/`rpg_admin` já existiam. A ação referencial roda como dono da tabela e não sofre RLS.
- **Idempotência:** só usa `if not exists`/`if exists`/`or replace`, o backfill só toca linhas `null` e o arquivo
  termina com `grant_runtime_access()`.
- **Privacidade:** o `operation_id` que fica retido é um UUID opaco gerado pelo cliente, e `game_id` vira nulo. A
  exclusão de conta continua apagando tudo (R4), e o TTL de 13 meses em `retention.py` não muda.
- **Wallet/recovery:** `reconcile_proven_no_charge` passa a encontrar o uso exato de uma operação apagada (antes o
  cascade apagava esse uso). `wallet_recovery` já tratava operação ausente como `UncertainEffect` antes deste diff.
- **Outros leitores:** `history_costs`/`operation_cost` e `audit_source` são escopados por jogo existente (`app.turns`
  / `game_id`), então não regridem. Nenhum leitor restante faz join obrigatório de `usage_events` com
  `operations`/`games`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `infrastructure/postgres_turns.py:112-136` (claim) + `infrastructure/usage_events.py:104-123` | **Um `operation_id` de campanha apagada pode ser reusado e o uso da nova operação escapa da medição.** O `operation_id` vem do cliente (`api.py:3968/4026/4076`, `uuid.UUID(req.action_id)`), e o `event_id` é `uuid5(operation_id:component:ordinal)`. Antes da 279, apagar a campanha apagava operação + usage, e a chave voltava a ficar livre de forma limpa. Agora a operação some, mas os eventos ficam. Um cliente que reenvie um `action_id` antigo numa campanha nova tem o claim aceito (a linha em `operations` não existe mais) e o LLM roda. Depois, `append_usage_events` colide em `(operation_id,component,attempt_ordinal)`. Com digest diferente → `Conflict("usage replay divergiu")`: o commit e o `fail(..., usage_events=...)` caem, e o gasto real do provider **não entra** no ledger nem no teto diário. Com digest igual → `do nothing` silencioso, e o uso da nova operação também não é gravado. Reproduzido no Postgres local (rollback): turno 1 no jogo A → delete do jogo A → mesmo `operation_id` no jogo B → `Conflict usage replay divergiu`. A spec (§2 R1, §7) afirma que a chave "continua correta". É um desvio do teto menor que o original (precisa de cliente hostil e é 1 para 1 com turnos já medidos), mas é justamente a classe de bug que a spec fecha. No wallet, `settle` também procuraria os `event_id` antigos (já liquidados). | No claim, quando a operação é **inserida** (`inserted` não nulo), recusar o id que já aparece em `app.usage_events` **antes** de qualquer efeito: `if inserted and connection.execute("select 1 from app.usage_events where operation_id=%s limit 1", (operation_id,)).fetchone(): raise Conflict("idempotency key indisponível")`. Usa o índice único que começa por `operation_id`. Alternativa no banco, mais robusta e que cobre também `dynamic_art`/jobs: trigger `BEFORE INSERT` em `app.operations` que recusa `id` presente em `usage_events` (`23505`/`42501`). Adicionar um teste `infra_local`: deletar a campanha → reusar o `operation_id` → claim recusado, sem chamar o LLM. Atualizar §7 da spec. |
| P3-1 | P3 | `scripts/staging/spec279_usage_survives_delete.py:120-122` | `day_spend_unchanged`/`day_turns_unchanged` comparam a soma **global** do dia no staging. Um turno real entre as duas medições derruba a prova (flake), apesar de `owner_spend_unchanged` já ser a prova exata. | Considerar só a soma do owner sintético, ou checar `a - b == 0` restrito às linhas sintéticas. Pode também deixar a checagem global só como informação. |
| P3-2 | P3 | `tests/test_spec279_usage_retention_local.py` | Não há teste que prove a cerca negando o `SET NULL` para um owner com `account_deletions` quando os jogos são apagados antes dos eventos. Hoje a ordem de `PRIVATE_TABLES` protege, mas uma limpeza futura (SPEC-280) que apague `games` direto quebraria com `account_deleted`. | Registrar em SPEC-280: apagar jogos de owner em exclusão exige apagar `usage_events` antes, ou pular esses owners. |

## Correções aplicadas

Nenhuma (revisor só edita este handoff).

## Pendências

- P1-1 precisa ser corrigido nesta branch antes do pouso e do `migrations push` no staging.
- P3-1/P3-2 são opcionais (P3-2 vai para a SPEC-280).

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -o addopts="" tests/test_spec279_usage_retention.py → 4 passed
RPG_TEST_DATABASE_URL=…:55322 … pytest tests/test_spec279_usage_retention_local.py tests/test_spec222_retention_local.py tests/test_account_lifecycle_local.py → 11 passed
script ad hoc (scratchpad, rollback): pg_constraint/pg_trigger/grants de app.usage_events → só game_id FK SET NULL; triggers attribution+fence; rpg_api select,insert
script ad hoc (scratchpad, rollback): reuso de operation_id após delete da campanha → Conflict "usage replay divergiu" (P1-1 reproduzido)
```
