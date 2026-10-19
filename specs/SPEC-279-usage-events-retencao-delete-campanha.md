# SPEC-279 — usage-events-retencao-delete-campanha

> **Status:** `approved` — decisão do dono em 19/10/2026 ("gere uma spec e desenvolva") sobre o achado do staging.
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Depende de:** SPEC-182 (`usage_events`), SPEC-222 (retenção R7), SPEC-236 (`counts_as_spend`) — todas `done`
> **Desbloqueia:** SPEC-280 (limpeza de jogos órfãos não pode apagar gasto)

---

## 1. Contexto & Objetivo

`app.usage_events` (SPEC-182) nasceu com `operation_id ... references app.operations on delete cascade`
e `game_id ... references app.games on delete cascade`, e `app.operations.game_id` também cascateia de
`app.games`. Resultado medido no staging (19/10): **apagar uma campanha apaga o gasto dela**. O gasto some
do teto diário (`services/daily_spend_cap.py` soma `usage_events.cost_usd` do dia via
`PostgresFinopsReader.usage_groups`), do FinOps (`owner_usage`, `ops_counts`) e do histórico de consumo da
conta. Isso contraria a SPEC-222 R7 (usage_events retido **13 meses**, prazo fiscal/contábil, purge só no cron)
e abre um desvio do teto: jogar, apagar a campanha, e o gasto do dia "desaparece".

Objetivo: o fato de consumo sobrevive ao delete da campanha; só o TTL de 13 meses (R7) ou a exclusão da
**conta** (SPEC-190/222: `usage_events` está em `PRIVATE_TABLES`) o removem.

## 2. Requisitos

- **R1** — Apagar uma linha de `app.games` (delete de campanha, cascata de `operations`) **não** apaga
  `app.usage_events`: `game_id` vira `NULL` (`ON DELETE SET NULL`); `operation_id` deixa de ter FK e
  fica como id histórico opaco (como `wallet_settled_usage.usage_event_id` e
  `wallet_reservations.usage_operation_id`, que nunca tiveram FK) — assim a contagem de turnos e a chave
  `(operation_id, component, attempt_ordinal)` continuam corretas; `owner_id`, `created_at`, `cost_usd`,
  `counts_as_spend`, `category`, etc. ficam intactos. O trigger de insert continua provando que a operação
  existe e bate com owner/game no momento da escrita.
- **R2** — A soma do dia usada pelo teto diário (`usage_groups(dia)`) e por `owner_usage` é **idêntica**
  antes e depois do delete da campanha.
- **R3** — Snapshot do tipo de operação: nova coluna `usage_events.operation_kind` preenchida pelo trigger de
  atribuição no insert (fonte: `app.operations.kind`, nunca o cliente) e backfill das linhas existentes.
  `ops_counts` (turnos/imagens/voz do FinOps) e `AccountReadModel.usage` (histórico da conta) usam
  `LEFT JOIN` + `coalesce(u.operation_kind, o.kind)` e continuam contando/listando eventos de campanha apagada.
- **R4** — A exclusão de **conta** (SPEC-190) continua apagando `usage_events` do owner (sem mudança em
  `PRIVATE_TABLES`); o TTL de 13 meses (SPEC-222 R7) continua valendo.
- **R5** — RLS/grants inalterados (`select,insert` para `rpg_api`; policies por owner); o trigger de
  atribuição continua recusando owner/game divergentes. Migration idempotente, termina com
  `select app.grant_runtime_access();`.
- **R6** — Código compatível com schema anterior à migration (`has_column`), como o resto do repositório.

### Fora de escopo

- Reter gasto após exclusão de **conta** (política 222 manda apagar; risco residual em §7).
- `image_quotes`/`art_generations` órfãos; jogos sem dono em `auth.users` (SPEC-280).

## 3. Design técnico

- **Migration nova** `supabase/migrations/20261019150000_usage_events_survive_game_delete.sql`:
  1. `add column if not exists operation_kind text`;
  2. backfill `operation_kind` a partir de `app.operations` (pulando owners em `account_deletions`, cuja
     cerca de escrita recusaria o update — mesmo padrão da 236);
  3. `create or replace function app.validate_usage_attribution()` passa a gravar `new.operation_kind`;
  4. `drop constraint if exists usage_events_operation_id_fkey` (sem recriar);
  5. `drop constraint if exists usage_events_game_id_fkey` + `add ... on delete set null`;
  6. `select app.grant_runtime_access();`.
  *Desvio do primeiro desenho* (SET NULL também em `operation_id`): descartado durante a implementação porque
  vários eventos do mesmo turno virariam N "turnos" no `ops_counts` e a chave de idempotência perderia sentido.
  A cascata `SET NULL` é um UPDATE: dispara `account_write_fence` (cerca da SPEC-190). Na exclusão de conta
  `usage_events` é apagado antes de `operations`/`games` (`PRIVATE_TABLES`), então não há linha a atualizar.
- **`infrastructure/finops_reader.py`** — `ops_counts`: `left join` + kind por `coalesce` quando a coluna existe.
- **`infrastructure/account_read_model.py`** — `usage`: idem.
- `services/retention.py` não muda (já não apaga operação referenciada; com `SET NULL` isso só fica mais seguro).

## 4. Plano passo a passo

### Etapa 1 — Testes primeiro
1. `tests/test_spec279_usage_retention.py` (offline): a migration declara `on delete set null` para
   `game_id`, remove a FK de `operation_id` sem recriá-la, grava `operation_kind` no trigger, é idempotente
   (`if exists`/`if not exists`/`or replace`) e termina com `grant_runtime_access()`; `ops_counts` e
   `AccountReadModel.usage` usam `left join`.
2. `tests/test_spec279_usage_retention_local.py` (`infra_local`, rollback): campanha com 2 eventos
   (um gasto, um `failed_no_usage`) → `delete from app.games` → eventos existem com `game_id` nulo,
   `operation_id` preservado e `operation_kind='turn'`; `usage_groups`/`owner_usage` do dia iguais; `ops_counts.turns` igual;
   histórico da conta ainda lista o evento; exclusão de conta (delete por `PRIVATE_TABLES`) remove.

### Etapa 2 — Migration + código

### Etapa 3 — `infra_local` completo + suíte completa

### Etapa 4 — Staging
`migrations push --apply`; prova com campanha sintética (soma do dia antes/depois do delete).

## 5. Critérios de aceite

- [ ] R1–R3 cobertos por teste `infra_local` verde em Supabase local.
- [ ] R4: `test_account_lifecycle_local` e `test_spec222_retention_local` verdes.
- [ ] Migration idempotente aplicada no staging; evidência sem PII em
      `docs/staging-wave-2026-10-17/evidence/spec279_*.json` (soma do dia inalterada após o delete).
- [ ] Revisão independente (`handoffs/SPEC-279-review.md`) aprovada.
- [ ] Suíte completa verde.

## 6. Smoke

Sem LLM (mudança de schema/SQL). Smoke = staging: criar usuário/campanha sintéticos, inserir consumo
atribuído, medir `sum(cost_usd) where counts_as_spend` do dia, apagar a campanha, medir de novo (igual),
limpar (usuário e eventos sintéticos removidos; staging volta ao estado de antes).

## 7. Riscos & compatibilidade

- Saves/jogos: nenhum impacto (só metadado de consumo).
- Exclusão de conta continua apagando o gasto do owner (política 222). Um abuso "cria conta → gasta → apaga
  conta" ainda tira o gasto do teto do dia; mitigação existente: CAPTCHA + confirmação de e-mail + cota diária
  por owner; se virar problema, spec própria (ex.: agregado diário anônimo).
- `operation_id` pendurado (operação apagada) é só um UUID opaco; nenhum leitor faz `join` obrigatório
  com `operations` depois desta spec (`ops_counts`/histórico usam `left join`).
