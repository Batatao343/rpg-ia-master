# SPEC-236 — Revisão independente Sol (+ Astra para R1/R2/R5)

- **Run:** `SPEC-236-SOL-20261017-INDEPENDENT-01` · revisor ≡ Opus em contexto separado (não escreveu a spec)
- **Base:** branch `spec-236`, commit do executor rebaseado sobre `main` (sem conflitos)
- **Veredito:** **APPROVED_WITH_FIXES** — 4 defeitos corrigidos nesta revisão (testes vermelho → verde).
  A spec segue `in-progress` só pela migration em staging + smoke §6.

## Escopo revisado

Correção financeira de R1–R10: falha sem usage custa 0 e não é gasto; teto confirmado vs liquidação;
teto diário cross-day; liberação de reservas órfãs (lease/fence, idempotência, nunca liberar viva nem
duas vezes); refund parcial pré-crédito; teto de tentativas e coerência de lease; ledger append-only; RLS/grants.

## Achados e correções

| # | Sev | Achado | Correção | Teste |
|---|---|---|---|---|
| F1 | **Alta** | O código quebrava TODO turno em perfil DB se publicado antes da migration: `append_usage_events` inseria `counts_as_spend` e `failed_no_usage` (CHECK legado rejeita), `postgres_turns`/`finops_reader`/`account_read_model`/`settle_usage` liam colunas novas (`UndefinedColumn`, reproduzido). | Probe de catálogo `has_column`/`spend_schema_ready` (presença cacheada; ausência re-sondada). Sem a migration: falha sem usage é gravada como estimativa de custo **0** não exata (nunca US$ 1, nunca liquidável); leitores somam tudo; `postgres_turns`/conta/voz usam predicado por `cost_basis` (agnóstico); anomalia acima do teto continua limitando o débito e só loga. Digest do evento inalterado → replay atravessa a migration. | `test_code_degrades_safely_without_the_migration` (schema legado simulado em transação revertida) |
| F2 | Média | Migration `20261016100000` ficava ANTES de `20261016121500` (já na `main`): ordem fora de sequência no histórico Supabase. | Renomeada para `20261017100000_usage_counts_as_spend.sql` (+ referências em teste/README/runbook). | migration 2× nos testes locais |
| F3 | Média (custo) | Revive de job `dead` com cooldown fixo de 15 min: a varredura de crônica roda a cada turno, então um `compress_chronicle` com falha persistente compraria `max_attempts` chamadas SMART a cada 15 min, indefinidamente. | Espera = `max(15 min, idade do job ao morrer)` → dobra a cada revive (15 min, 30 min, 1 h, 2 h…), sem coluna nova. | `test_dead_job_revival_backs_off_exponentially` |
| F4 | Baixa | Outcome novo `stream_interrupted` caía em `llm_other_error` no export de auditoria (SPEC-207). | Mapeado para `llm_stream_error`. | `test_stream_interrupted_keeps_its_audit_error_code` |

## Verificado sem defeito

- **R1/R2 (Astra):** só falhas de rede/transporte sem leitura de usage viram `failed_no_usage`; resposta recebida sem usage
  (`success`/`invalid_*`/`stream_interrupted`) segue estimada. `failed_no_usage` é `billing_exact=false` → nunca liquida
  automático (timeout segue retido). CHECK `no_spend ⇒ cost 0 ∧ counts_as_spend=false`. Backfill só toca
  `usage_events.counts_as_spend` (fato/custo preservados; `rpg_api` não tem UPDATE; migration roda como owner).
- **Teto vs liquidação (R10):** débito nunca excede `ceiling_milli`; excesso registrado 1× (liquidação é terminal);
  replay devolve a mesma reserva sem nova entrada.
- **Teto diário (R3):** trip precisa estar em `[since, re-enable]` do mesmo dia-de-teto (UTC−3 fixo); audit limitado a 200
  linhas falha fechado (override perdido ⇒ re-trip).
- **Varredura (R4):** `reserved` só libera via `recover` com lock da operação e lease vencido; `effect_started` só liquida
  com eventos exatos 1:1 aos tickets sob lock (recontagem em `settle_usage`); qualquer divergência ⇒ `uncertain`
  (nunca reembolso automático); imagem só com job `dead`/`cancelled`; carência 900 s.
- **STT (R5, Astra):** só 4xx/429 recebidos são zero exato; 5xx/timeout/cancel ⇒ reserva inteira `uncertain`; CLI exige
  ator, evidência, `--apply --confirm-owner`, liquida o exato e libera o resto.
- **Stripe (R6):** parcial pré-crédito mantém status, crédito integral, clawback proporcional (2 milli em 311) auditável.
- **Jobs (R9):** `running` expirado no teto ⇒ `dead` com `for update skip locked`; nunca re-leased.
- **Lease (R8):** tick pós-commit é benigno; lease realmente perdido antes do commit ainda levanta.
- **Append-only/RLS:** nenhum UPDATE/DELETE em `wallet_entries`/`tickets`/`settled_usage`; triggers de conservação
  (`wallet_account_reconciles`, `wallet_reservations_reconcile`) verdes em todos os testes; `usage_events` segue sem
  UPDATE para `rpg_api`.

## Corridas reais (Postgres local, conexões separadas, 5 execuções seguidas verdes)

`tests/test_spec236_races_local.py`: 3 varreduras simultâneas na mesma órfã ⇒ 1 `release`; 2 varreduras + liquidação
do dono simultâneas ⇒ 1 desfecho terminal, 1 `settle`; 4 workers no mesmo job envenenado ⇒ nenhum lease, `dead` 1×.

## Evidência de execução

- `pytest -m infra_local` (arquivos afetados: wallet, speech_finance, postgres_jobs, image_quotes, stripe*, spec194_196,
  account_read_model, process_crash, spec197, worker_fence, account_lifecycle_financial, SPEC-236): exit 0.
- Suíte completa offline (`pytest --ignore=tests/test_project_index.py`, sem pipe): exit 0, ~3.357 passed, ~206 skipped, 0 falhas. Ruff nos arquivos tocados: exit 0.

## Seguro para a `main` antes da migration?

**Sim** após F1: sem a migration o jogo não quebra; perde-se só a separação de gasto das falhas HISTÓRICAS (as novas já
custam 0) e o registro da anomalia acima do teto (o teto continua valendo). Aplicar `20261017100000` no staging
antes do smoke §6.

## Pendências (fora desta revisão)

- Aplicar a migration `20261017100000_usage_counts_as_spend.sql` no staging.
- Smoke real §6 (falha DeepSeek forçada + fallback; trip de ontem + re-enable hoje; 429 do Groq no STT).
- Follow-up opcional: painel da conta mostra turno com falha sem usage como "exato" (só exibição).
