# SPEC-352 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (rodada 2; rodada 1 = `CHANGES_REQUIRED`)
> **Revisor:** Opus 5.5 / Sol (spec-reviewer) · **Data:** 2026-10-28 · **Commit revisado:** `71f06511` (r1) → `af9e2715` (r2)

## Escopo

`git diff spec-347...spec-352` (5 commits, 37 arquivos): `services/creature_portraits.py`,
`services/image_quotes.py` (`_confirm`, `peek_ceiling`, `_portrait_failed`), `services/dynamic_art.py`,
`workers/dynamic_art_jobs.py`, `workers/run_worker.py`, `workers/blob_purge_jobs.py`,
`infrastructure/{account_lifecycle,postgres,postgres_turns,runtime,supabase_blob}.py`,
`api.py` (quote/confirm/view/quality), a migration `20261028120000_creature_portraits.sql`,
`scripts/retire_creature_portrait.py`, o front (`App.tsx`, `CombateTab.tsx`, `portraitOrder.ts`) e os testes.
Fora: e2e Playwright (não rodado aqui), smoke de staging §6 (pendente, documentado na spec).

Conferido e OK: chave recalculada no servidor (`extra="forbid"`, `enemy_id` só com `monster`), curada
corta a oferta (409 `creature_portrait_curated`), flag off/legacy deixa `gerar` nulo e não lê o registro,
claim antes de `wallet.reserve` na mesma transação, pré-ticket libera / pós-ticket `uncertain` +
`mark_failed`, R3 (pending de geração morta é reclamável), `ready` imutável por trigger, CHECKs
`ready ⇒ thumb+store` e "sem dono só ready/retired", `rpg_api` só `select` com RLS forçada, fence de
conta excluída, bucket `rpg-shared-art` privado com URL assinada e chaves `shared/creatures/{hash12}/…`,
cópia idempotente (`already_shared`/conteúdo igual), exportação sem object keys, `delete_game` só linhas
`game`, quality 422 para `monster`, sem import de provider. Nenhuma mudança em `evals/`. Sem
`with_structured_output` novo (guard de FallbackLLM não se aplica).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P0-1 | P0 | `services/creature_portraits.py:181-201` (`claim`) | **Cobrança dupla sob concorrência real.** No `ON CONFLICT ... DO UPDATE ... WHERE`, o subselect `not exists (select 1 from app.art_generations ... status = any(LIVE))` roda com o **snapshot do início do comando** (READ COMMITTED). Na confirmação real a geração do vencedor é inserida na MESMA transação do claim (`_confirm` → `repository.reserve`, `services/image_quotes.py:258`); o segundo confirmador fica bloqueado no índice do PK, acorda depois do commit do primeiro, vê a linha `pending` (versão travada mais recente) mas **não vê** a `art_generations` recém-commitada → `not exists` = true → sobrescreve a linha com a geração dele e segue para `wallet.reserve` + job. Reproduzido no Postgres local (55322): tx1 = claim + insert da geração, aberta; tx2 = claim (bloqueia); commit tx1 → resultado `['won','won']`, linha final com a geração de tx2 e `version=2`. O teste `test_concurrent_claim_two_connections` (`tests/test_spec352_creature_portraits_db.py:514`) não pega porque pré-commita as duas `art_generations` antes da corrida. Viola R6/R7/D-352-4. | Tirar a checagem de geração do `WHERE` do upsert e fazer em comandos separados (cada um com snapshot novo): (1) `insert ... on conflict (portrait_key) do nothing returning *` → se voltou linha, venceu; (2) senão `select ... from app.creature_portraits where portrait_key=%s for update` (bloqueia até o outro commitar); (3) **novo comando** lendo `art_generations.status` da `generation_id` travada; (4) se `failed`/`retired` ou geração morta/ausente → `update ... set status='pending', ...`; caso contrário `CreaturePortraitTaken`. Corrigir o teste de corrida para reproduzir o fluxo real: tx1 faz claim + insert da geração e só commita depois que tx2 já está bloqueada (ou rodar dois `repo.confirm` reais em duas conexões) e assertar 1 reserva, 1 job, 1 `won`. |
| P1-1 | P1 | `workers/run_worker.py:109-132` | O job `copy_creature_portrait` é enfileirado **depois** do commit de `repository.complete`, fora da transação e best-effort (`log_fallback` engole a falha). Se o enqueue falhar ou o worker morrer entre os dois passos, a linha fica `ready`/`store='private'` para sempre: a arte compartilhada é servida a outros jogadores a partir de `users/{owner}/…` do pagador e some (linha apagada por `erase_owner`) quando ele excluir a conta — contrário a R8 ("o job promove depois") e D-352-9. | Enfileirar o job na mesma transação de `complete` (passar `queue`/`connection`, como `_confirm` faz com `generate_dynamic_art`), ou acrescentar um varredor idempotente que reenfileire `ready` + `store='private'` antigos. Teste: falha no enqueue não deixa linha privada órfã. |
| P2-1 | P2 | `api.py:2846` (`_portrait_sign`) | Linha `ready`/`private` visível a outro jogo é assinada pelo `blob_store` privado: o outro jogador recebe URL assinada de um objeto em `users/{owner}/…` (expõe o UUID do dono na URL). Janela curta enquanto a cópia não ocorre, mas permanente se P1-1 acontecer. | Só assinar `private` para o `origin_game_id`; para outros jogos tratar como `pending` (sem `src`) até a promoção. |
| P2-2 | P2 | `services/creature_portraits.py:262-282` (`erase_owner`) | Linhas `visibility='pool'` `ready` cuja entrada do pool **não** está `promoted` ficam desvinculadas (`origin_game_id=null`): ninguém mais as vê (R4 exige promoção ou jogo de origem), mas o `claim` continua bloqueado por `status='ready'` — a chave `tipo:bst:{entry}` fica travada e o objeto fica no bucket. R14 só manda desvincular as **promovidas**. | Em `erase_owner`, apagar também `visibility='pool'` cujo `shared_pool.status <> 'promoted'` (devolvendo as keys compartilhadas), ou marcá-las `retired`. Teste `_db` para o caso. |
| P2-3 | P2 | `infrastructure/runtime.py:803` | No perfil `s3`, `shared_blob_store = blob_store`: a cópia vai para o mesmo bucket privado com prefixo `shared/` e o mesmo `signed_url`; ok funcionalmente, mas a purga de conta por prefixo `users/` não toca `shared/` e não há teste do caminho s3. | Registrar como follow-up (s3 não é o perfil de staging) ou adicionar teste mínimo de put/sign com chave `shared/creatures/…`. |

## Correções aplicadas

| Achado | Commit | Verificação (rodada 2) |
|---|---|---|
| P0-1 | `053dc4cc` | `claim` virou comandos separados: `insert … on conflict do nothing` → `select … for update` → `select` da geração (snapshot novo) → `update`/`CreaturePortraitTaken`. `race352.py` (tx1 = claim + geração sem commit prévio; tx2 bloqueada; commit tx1) agora dá `['won','taken']`, linha com a geração de tx1, `version=1`. Teste novo `test_concurrent_claim_two_connections_real_confirm_flow` reproduz exatamente esse fluxo. Como o claim precede `wallet.reserve` na mesma transação, o perdedor reverte sem reserva (coberto por `test_second_confirm_same_key_is_taken_without_reservation_or_debit`). Fechado. |
| P1-1 | `a7b774e6`, `af9e2715` | `enqueue_copy_job` roda dentro de `_mark_portrait_ready`, na transação de `complete` (dedupe `copy-portrait:{generation_id}`, `on conflict do nothing`). Varredor `sweep_private_portraits` no cron de jobs reenfileira `ready`+`private` com > 30 min; idempotente por hora (dedupe `…:sweep:{YYYYMMDDHH}`), e o job de cópia é idempotente (`already_shared`/`skipped`). Testes `_db` novos verdes. Fechado. |
| P2-1 | `465fef04` | `_registry_src`: linha `private` de outro jogo → sem `src`, `pending=True`. Fechado. |
| P2-2 | `af9e2715` | `erase_owner` apaga `pool` não promovida (devolve keys compartilhadas); teste `_db`. Fechado. |
| P2-3 | `af9e2715` | teste do caminho s3 do store compartilhado. Fechado. |

## Pendências

- **P2-4 (novo, follow-up):** `services/creature_portraits.py` `delete_game` só apaga `visibility='game'`. Uma linha `shared`/`pool` `ready`+`private` de um jogo apagado perde a geração e o job (FK `on delete cascade` em `art_generations`/`jobs`), o varredor não a vê (join com `art_generations`) e a P2-1 a esconde de todos: a chave fica travada para sempre. Correção sugerida: `delete_game` apagar também `store='private'` do jogo. Raro (cópia falhou + jogo apagado antes do varredor).
- **P2-5 (follow-up):** o teste de corrida prova o claim com duas conexões; não há teste com dois `repo.confirm` completos concorrentes (1 reserva/1 job). A garantia vem da ordem claim→reserve na mesma transação; aceitável.
- Smoke real §6 no staging e prints 390/1440 (declarados na spec).
- Ownership de `app.creature_portraits` em `project_index/state_ownership.yaml` (coordenador, no pouso).
## Comandos rodados

```text
git diff spec-347...spec-352 --stat → 37 arquivos, +2956/-76
RPG_TEST_DATABASE_URL=…55322… bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec352_creature_portraits.py tests/test_spec352_creature_quote_api.py tests/test_spec347_creature_art.py tests/test_spec352_creature_portraits_db.py tests/test_image_quotes_local.py → 121 passed, 0 skipped
bash scripts/dev/py.sh <scratchpad>/race352.py (claim + insert de geração em tx1 aberta; tx2 bloqueada; commit tx1) → results ['won','won'], linha final com a geração de tx2 (P0-1 reproduzido; dados limpos)
# rodada 2 (af9e2715)
bash scripts/dev/py.sh <scratchpad>/race352.py → results ['won','taken'], linha com a geração de tx1, version=1
RPG_TEST_DATABASE_URL=…55322… bash scripts/dev/py.sh -m pytest -p no:cacheprovider -rs (mesmos 5 arquivos) → 126 passed, 0 skipped
```
