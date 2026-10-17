# SPEC-236 — evidência (FinOps/wallet/jobs)

Status: `in-progress` (2026-10-16). Código + testes offline e Postgres local (Supabase local) verdes.
Revisão independente `Sol` (+ Astra R1/R2/R5) APPROVED_WITH_FIXES em 2026-10-17 ([parecer](../../handoffs/SPEC-236-SOL-independent-review.md)). Pendentes: migration no staging e smoke real (§6).
Defaults do dono usados: D-A (piso US$ 1 só em `quote_attempt_ceiling`), D-B (30 d, alerta T−3 d), D-C (5xx = `unknown`).

## O que mudou

| Req | Mudança | Arquivos |
|---|---|---|
| R1 | Falha de rede sem `usage` → `cost_usd=0`, `cost_basis=failed_no_usage`, `billing_exact=false`, `counts_as_spend=false`. Resposta recebida sem usage (`invalid_structured`/`success`) segue conservadora. | `services/usage_metering.py` |
| R2 | Coluna `counts_as_spend` (+ backfill das falhas históricas de US$ 1,00, linhas preservadas); teto diário, FinOps (`owner_usage`, `usage_groups`, `cost_spike`, `unknown_pricing`, `expensive_fallback`, margem, custo unitário), custo do turno (`postgres_turns`, log da API) e o painel da conta somam só gasto. Falhas aparecem à parte: `provider_failures_no_usage[_by_provider]`, relatório `finops-spend-v2`. | migration `20261017100000_usage_counts_as_spend.sql`, `infrastructure/usage_events.py`, `infrastructure/finops_reader.py`, `services/finops_alerts.py`, `services/finops_job.py`, `services/daily_spend_cap.py`, `infrastructure/postgres_turns.py`, `infrastructure/account_read_model.py`, `api.py` |
| R3 | Override manual só vale para trip do sistema no MESMO dia-de-teto, anterior ao re-enable. | `services/daily_spend_cap.py` |
| R4 | `services/wallet_recovery.py` no cron `/internal/cron/operations`: libera reservas sem ticket de operações mortas, liquida `effect_started` com uso exato 1:1, o resto vira `uncertain`; imagem só quando o job está `dead`/`cancelled`. Alerta `wallet_uncertain_hold`. | `services/wallet_recovery.py`, `services/cron_internal.py`, `infrastructure/finops_reader.py` |
| R5 | STT: 4xx/429 recebido → evento exato de custo zero (`definitive_no_charge`), a reserva liquida e é liberada; timeout/cancel/5xx seguem `unknown` (retidos). `scripts/admin_wallet_reconcile.py` (dry-run padrão, `--apply --confirm-owner`, ator + evidência) liquida o uso exato e libera o resto. | `services/speech_pricing.py`, `services/speech_to_text.py`, `services/shard_pricing.py`, `infrastructure/wallet.py`, `scripts/admin_wallet_reconcile.py` |
| R6 | Refund PARCIAL antes do Checkout pago não marca o pedido `refunded`: outcome `pending_partial_refund`, crédito integral, clawback proporcional pelo reconciliador (SPEC-195). | `infrastructure/stripe_payments.py` |
| R7 | `RPG_RATE_CARD_MAX_AGE_DAYS` (default 30) para imagem/STT; alerta não bloqueante `rate_card_expiring` em T−3 d; runbook. | `services/shard_pricing.py`, `services/image_pricing.py`, `services/speech_pricing.py`, `services/finops_alerts.py`, `docs/spec197/runbooks/budget.md`, `observability/alerts/finops.yml` |
| R8 | Tick de heartbeat após o commit é benigno: `heartbeat()` aceita rowcount 0 com operação `completed`; `LeaseWatch.check()` confirma a conclusão antes de levantar `lease_lost`; `mark_committed()` para a renovação. | `infrastructure/postgres_turns.py`, `services/lease_heartbeat.py`, `services/turn_execution.py` |
| R9 | `lease` marca `dead` (`lease_expired_max_attempts`) os `running` expirados no teto; re-lease só abaixo do teto. Re-enqueue de `embed_memory`/`compress_chronicle` com documento `pending` reativa job `dead`/`cancelled` (espera `max(15 min, idade do job ao morrer)`, dobra a cada revive). | `infrastructure/postgres_jobs.py`, `infrastructure/pgvector_memory.py`, `services/chronicle_repository.py` |
| R10 | `settle_usage` acima do teto: limita ao teto, grava `financial_anomaly_milli` 1× e liquida (qualquer reserva). Job de imagem adiado > `RPG_IMAGE_DEFER_MAX_HOURS` (6 h) → `release_pre_effect` + geração `failed/deferred_timeout`. Com `RPG_DAILY_SPEND_CAP_BRL`, `image_generation`/`stt_fallback_expensive` falham fechados em cold start com store ilegível. | `infrastructure/wallet.py`, `services/image_quotes.py`, `workers/run_worker.py`, `services/kill_switches.py` |

Invariantes do ledger preservados: nenhum UPDATE/DELETE em `wallet_entries`; liquidação/liberação continuam
uma única entrada `settle`/`release` por reserva (constraints da SPEC-184); o backfill só altera
`usage_events.counts_as_spend` (o fato e o custo histórico ficam intactos); dívida/clawback continuam no
reconciliador da SPEC-195.

## Repros (antes → depois)

```
normalize_attempts([deepseek invoke_error usage=None, groq/gpt-oss-120b success 1000/300])
antes:  [1.000000000 estimated, 0.000330000 token_priced]      depois: [0 failed_no_usage, 0.000330000]
teto R$1, 9 falhas + 1 sucesso de US$0,01 (FX 6): antes exceeded/switch off; depois spent R$0,06, nada desligado
trip −20 h + re-enable −4 h + gasto > teto: antes manual_override=[image_generation]; depois switched_off inclui image
charge.refunded parcial (10/1050) antes do checkout: antes pedido refunded, 0 crédito; depois 311 creditados, clawback 2
job max_attempts=3 com lease expirando 3×: antes re-lease infinito (attempts 4,5,...); depois dead/lease_expired_max_attempts
STT 429 Groq + sucesso OpenAI: antes pending_reconciliation (reserva presa); depois settled 1 milli, reserved=0
```

Rodando os testes novos contra o HEAD (`git stash`), 27 casos falham (cada R1–R10); com a correção, todos passam.

## Testes

- Novos: `tests/test_bug_finops_wallet_jobs.py` (20, offline) e `tests/test_bug_finops_wallet_jobs_local.py`
  (12, `-m infra_local`, rollback total: migration 2×/backfill, custo zero persistido, cron libera órfã + idempotência,
  cron liquida exato/retém unknown, STT 429+fallback, STT timeout + CLI de reconciliação, refund parcial pré-checkout,
  poison lease, revive de job morto, settle acima do teto, TTL do adiamento de imagem, varredura de job de imagem morto).
- Ajustes justificados: `test_usage_metering` (falha sem usage = 0), `test_image_pricing` (janela 30 d),
  `test_spec192_cron_endpoints` (+ varredura da wallet e caso de falha da varredura).
- `uv run pytest --ignore=tests/test_project_index.py`: **2756 testes, 0 falhas, 180 skips**, exit 0.
- `RPG_TEST_DATABASE_URL=<supabase local> pytest -m infra_local`: **110 testes, 0 falhas, 11 skips**.
  `test_spec197_daily_cap::test_postgres_store_audit_actor_and_idempotency` falhava já no HEAD neste banco local
  compartilhado (trips de execuções anteriores contavam como override); passa com a regra do mesmo dia-de-teto.
- Migration aplicada 2× no Supabase local sem erro (e 2× dentro do teste, em transação revertida). Ruff verde.

## Limites

- Smoke real em staging (§6: falha DeepSeek forçada + fallback, trip de ontem, 429 do Groq) NÃO executado — exige
  staging/provedores reais, fora do escopo desta execução local.
- Retenção parcial de STT (só o teto das tentativas `unknown`) não implementada: o schema append-only não representa
  liquidação parcial de reserva aberta. Mitigação: CLI de reconciliação liquida o exato e libera o resto.
- Relatórios FinOps históricos mudam após o backfill (falhas antigas saem do gasto); o resumo traz
  `report_version=finops-spend-v2`.

## Revisão Sol (2026-10-17)

- **Ordem de deploy:** o código é seguro na `main` ANTES da migration: `infrastructure/usage_events.has_column`
  sonda o catálogo; sem `counts_as_spend` a falha sem usage é gravada como estimativa de custo 0 não exata e os
  leitores somam tudo (só falhas históricas de US$ 1 continuam no gasto até a migration). Sem
  `financial_anomaly_milli` o débito continua limitado ao teto e o excesso só é logado.
- Migration renomeada para `20261017100000` (depois de `20261016121500`, já na `main`).
- Novos testes: degradação sem migration, backoff do revive, mapeamento `stream_interrupted` e
  `tests/test_spec236_races_local.py` (3 corridas reais com conexões separadas).
