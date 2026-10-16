# SPEC-236 — FinOps/wallet/jobs: custo fantasma de falhas, teto diário cross-day, reservas órfãs, STT incerto, refund parcial pré-crédito, lease e poison jobs

> **Status:** `in-progress` — código + testes offline/Postgres local entregues (2026-10-16); faltam o smoke
> real em staging (§6) e a revisão independente `Sol`/Astra (§9). Evidência: [docs/spec236/README.md](../docs/spec236/README.md).
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-16
> **Depende de:** nenhuma · SPEC-182/184/186/188/189/195/196 `done` e o teto diário da SPEC-197 são corrigidos (ordem final 2026-10-15)
> **Desbloqueia:** gate da SPEC-197/198 (custos e teto diário confiáveis); custo exato da SPEC-200 (ordem final 2026-10-15)
> **Origem:** auditoria de bugs 2026-10-15 — achados BUG-08-01..08-09, 04-02, 04-03, 04-08 (`achados/08-billing-jobs.md`, `04-persistencia-concorrencia.md`)
> **EXECUTOR_MODEL:** `Sol` (≡ Opus) — contabilidade financeira com efeito em dinheiro do jogador/operador
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` · **REVIEW_ASTRA:** recomendada para R1/R2/R5 (dinheiro)
> **EVAL_AUTHORING_REQUIRED:** `false` — cobertura por testes com fakes de `infrastructure/testing.py` + Postgres local (`-m infra_local`)

---

## 1. Contexto & Objetivo

Fatos no HEAD `d6af933` (área 08 executou `normalize_attempts` e o cap; orquestrador conferiu `usage_metering.py:
140-176`, `daily_spend_cap.py:75-84,118-130`):

- [F] **Falha sem `usage` custa US$ 1,00 "real"** — `services/usage_metering.normalize_attempts` só pula
  `network_attempted is False`/`build_error`/`circuit_open`; tentativa real que falhou (429/402/timeout/5xx) tem
  `usage=None` → ramo `else` → `cost = max(_UNKNOWN_MIN_USD=1.00, …)`, `billing_exact=False`,
  `pricing_version="unknown-conservative-v1"`, persistido em `app.usage_events.cost_usd`. `daily_spend_cap` soma
  `usage_groups(...).cost_usd` sem filtrar por exatidão; `finops_reader` (`sum(cost_usd)`), `finops_alerts`
  (`unknown_pricing` blocking, `cost_spike` com `usd >= 1.0` e provider sem histórico), `api.py:729` (custo do turno
  mostrado) e a margem por SKU herdam o valor. Cenário normal (DeepSeek 402/429 → Groq) soma ~US$ 1 por fallback;
  ~9 falhas/dia estouram R$ 50 e desligam `image_generation`/`stt_fallback_expensive` com gasto real de centavos.
- [F] **Override do teto diário vaza do dia anterior** — `daily_spend_cap._manually_reenabled`: exige só que a última
  linha seja re-enable humano de hoje E que exista QUALQUER trip do sistema anterior (`rows[1:]`, sem data). Trip ontem
  + re-enable hoje de manhã + gasto de hoje > teto → `image_generation` segue ligado (`manual_override`), só o STT é
  cortado. A docstring diz "trip do sistema **hoje**".
- [F] **Reservas de wallet órfãs sem varredura** — `PostgresWallet.recover` só é chamado em `speech_finance.py:82`
  (mesmo request); `operation_recovery.recover_expired` abandona `app.operations` mas não toca `app.wallet_reservations`;
  `docs/spec184/README.md:36` promete liberação automática.
- [F] **STT: qualquer tentativa não-exata deixa a reserva inteira `uncertain`** — `speech_finance.finish` exige
  `all(billing_exact)`; 429 definitivo do Groq + sucesso exato do fallback → `pending_reconciliation`, `reserved_milli
  > 0`, sem débito nem release; `reconcile_proven_no_charge` sem CLI/cron (teste `test_unknown_timeout_preserves_hold…`
  fixa o comportamento).
- [F] **Refund parcial antes do `checkout.session.completed`** — `stripe_payments._financial_event` ramo sem
  `purchase`: `status="refunded"` mesmo com `amount < gross`; `_checkout_event` só credita `if status not in TERMINAL`
  → compra paga com reembolso de 1% nunca credita; reconciliador deixa `orphaned`. (Leitura; exige Postgres.)
- [F] **Rate cards de imagem/STT expiram em 7 dias fixos** — `image_pricing.py:20-23`, `speech_pricing.require_speech_
  prices` (`timedelta(days=7)`) sobre cards `observed_at=2026-10-12` → `PricingUnavailable` para TODO quote/STT a partir
  de 2026-10-19 (janela em código, não config).
- [F] Lease/jobs (área 04): heartbeat pós-commit levanta `LeaseHeld` num turno já salvo (`lease_heartbeat.keep_lease_
  alive` + `turn_execution.operation_scope` → 500/SSE `error`, retry devolve recibo); `PostgresJobQueue.lease` re-leasa
  `running` expirado sem olhar `max_attempts` (poison loop com custo de provider); jobs `dead`/`cancelled` nunca
  reenfileirados por `on conflict (kind,dedupe_key) do nothing`.
- [F] Baixas: `settle_usage` LLM acima do teto lança e deixa `effect_started` sem anomalia; job de imagem adiado por
  kill switch segura reserva sem TTL; kill switches falham abertos em cold start com store ilegível.

Objetivo: gasto "real" = só custo exato ou estimado por rate card com tokens medidos; falhas sem usage custam
0 (auditáveis, fora das somas); teto diário com override apenas no mesmo dia; toda reserva tem caminho automático
de liberação/liquidação; refund parcial nunca bloqueia crédito; jobs com teto de tentativas e lease coerente.

## 2. Requisitos

- **R1** — [R] `normalize_attempts`: tentativa com `outcome != "success"` e sem `usage` → `cost_usd = 0`,
  `cost_basis="failed_no_usage"`, `billing_exact=False`, `counts_as_spend=False` (campo novo no evento, default
  `True` para legado exato/token_priced). O piso de US$ 1 fica restrito a `quote_attempt_ceiling` (reserva), nunca a
  `usage_events`. Teste de reprodução: deepseek `error` + groq `success` → `[0.000000000, 0.000330000]`.
- **R2** — [R] `daily_spend_cap`, `finops_reader.usage_groups/owner_usage`, `finops_alerts` (`cost_spike`),
  `api.py:729` e a margem por SKU somam apenas `counts_as_spend` (SQL: `where counts_as_spend`); eventos
  `failed_no_usage` aparecem em relatório separado ("falhas de provider", contagem). Migration idempotente: coluna
  `counts_as_spend boolean not null default true` + backfill `false` onde `pricing_version='unknown-conservative-v1'
  and outcome<>'success'`. Teste: 9 falhas + 1 sucesso de centavos → cap NÃO excedido.
- **R3** — [R] `_manually_reenabled` exige trip do sistema com `at >= since` (mesmo dia do teto) e o re-enable humano
  posterior a ele. Teste de reprodução: trip −20 h, re-enable −4 h, gasto > teto → `switched_off` inclui
  `image_generation`; trip −3 h, re-enable −1 h → override mantido.
- **R4** — [R] Cron `/internal/cron/operations` (ou novo `/internal/cron/wallet-recovery`, orçamento < 58 s) chama
  `wallet.recover` para reservas `reserved` cuja operação está `abandoned`/vencida (release pré-efeito) e
  `settle_usage` para `effect_started` cujos eventos exatos == tickets; incerteza real permanece `uncertain` com
  alerta FinOps `wallet_uncertain_hold` (count, idade). Teste Postgres local: reserva órfã → cron → `available_milli`
  restaurado, ledger com `release_pre_effect` 1×.
- **R5** — [R] STT `finish`: classifica cada tentativa como `exact` / `definitive_no_charge` (HTTP 4xx/429 recebido,
  decode local falhou antes da rede) / `unknown` (timeout/cancel/5xx sem corpo). Liquida as exatas, libera as
  `definitive_no_charge`, e só retém `uncertain` o teto da(s) `unknown`. Novo `scripts/admin_wallet_reconcile.py`
  (ator/motivo) para `reconcile_proven_no_charge`. Teste: 429 Groq + sucesso OpenAI → débito exato do OpenAI, resto
  liberado, `reserved_milli == 0`.
- **R6** — [R] Stripe pré-crédito: `_financial_event` sem `purchase` só marca `refunded` quando `amount >= gross_cents`;
  parcial grava `pending_partial_refund` no pedido e deixa `_checkout_event` creditar; o reconciliador aplica o clawback
  proporcional após o crédito (SPEC-195). Teste (Postgres local, fixtures Stripe): `charge.refunded` parcial antes de
  `checkout.session.completed` → crédito integral + clawback proporcional + ledger auditável.
- **R7** — [R] Janela de frescor dos rate cards configurável (`RPG_RATE_CARD_MAX_AGE_DAYS`, default 30) e alerta
  FinOps `rate_card_expiring` (warning em T−3 d, blocking só ao expirar); runbook de renovação em `docs/spec197/
  runbooks/budget.md`. Teste: card com 25 d → ok + warning; 31 d → `PricingUnavailable`.
- **R8** — [R] Lease: `keep_lease_alive` para o heartbeat (`stop.set()` + join) ao sinal de commit e `check()` ignora
  `lost` quando a operação já está `completed`; `heartbeat()` trata rowcount 0 + status `completed` como sucesso.
  Teste (coordinator fake de `lease.py`): tick pós-commit → sem exceção, operação `completed`.
- **R9** — [R] `PostgresJobQueue.lease`: antes de selecionar, marca `dead` (`last_error_code='lease_expired_max_
  attempts'`) os `running` expirados com `attempts >= max_attempts`; re-lease só se `attempts < max_attempts`.
  Enqueue de `embed_memory`/`compress_chronicle` reativa job `dead`/`cancelled` com mesmo `(kind, dedupe_key)` quando o
  documento segue `pending` (`status='queued', attempts=0`). Testes Postgres local: job que expira 3× → `dead`;
  re-enqueue após `dead` → `queued`.
- **R10** — [R] `settle_usage` LLM com custo > teto: limita ao teto, grava `financial_anomaly_milli` 1× e liquida
  (mesmo contrato de `cap_confirmed_image`). Job de imagem adiado > `RPG_IMAGE_DEFER_MAX_HOURS` (default 6 h) →
  `release_pre_effect` + geração `failed` com motivo. Kill switches `image_generation`/`stt_fallback_expensive` fail-closed
  por default quando `RPG_DAILY_CAP_BRL` está configurado (cold start sem snapshot = desligado).

### Fora de escopo

- Preço/margem/SKUs (valores), FX, novos canais de pagamento.
- Segurança de webhooks/assinaturas (auditoria de segurança).
- Ligar `reserve→settle` às jogadas normais (SPEC-185 pendente) — esta spec deixa a base correta para isso.

## 3. Design técnico

### Arquivos alterados

- `services/usage_metering.py:140-176` — ramo `failed_no_usage` + `counts_as_spend` (R1); `infrastructure/usage_events.py`
  + migration `supabase/migrations/2026101600_usage_counts_as_spend.sql` (R2); `infrastructure/finops_reader.py:112-139`,
  `services/daily_spend_cap.py:124`, `services/finops_alerts.py`, `api.py:729`, `services/finops.py` (R2).
- `services/daily_spend_cap.py:75-84` (R3).
- `services/cron_internal.py`, `services/operation_recovery.py`, `infrastructure/wallet.py:546` (R4).
- `infrastructure/speech_finance.py:68-83`, `services/speech_to_text.py`, `services/speech_pricing.py`, novo
  `scripts/admin_wallet_reconcile.py` (R5).
- `infrastructure/stripe_payments.py` (`_financial_event`, `_checkout_event`), `services/purchase_reconciliation.py` (R6).
- `services/image_pricing.py:20-23`, `services/speech_pricing.py`, `services/finops_alerts.py` (R7).
- `services/lease_heartbeat.py`, `services/turn_execution.py` (R8); `infrastructure/postgres_jobs.py` (`lease`, `enqueue`),
  `infrastructure/pgvector_memory.py:107`, `services/chronicle_repository.py:66` (R9).
- `infrastructure/wallet.py:532-533`, `workers/run_worker.py`, `services/kill_switches.py:122-145` (R10).

### Schema (usage_events)

```sql
alter table app.usage_events add column counts_as_spend boolean not null default true;
update app.usage_events set counts_as_spend=false
 where pricing_version='unknown-conservative-v1' and outcome<>'success';
```

## 4. Plano passo a passo

### Etapa 0 — Testes de reprodução (vermelhos no HEAD)
`tests/test_bug_finops_wallet_jobs.py` (fakes) + `tests/test_bug_finops_wallet_jobs_local.py` (`-m infra_local`):
`test_failed_attempt_costs_zero` (R1), `test_daily_cap_ignores_failed_attempts` (R2), `test_manual_override_only_same_day`
(R3), `test_cron_recovers_orphan_reservation` (R4), `test_stt_definitive_failure_releases` (R5),
`test_partial_refund_before_checkout_still_credits` (R6), `test_rate_card_window_configurable` (R7),
`test_heartbeat_after_commit_is_benign` (R8), `test_expired_lease_respects_max_attempts` e `test_dead_job_reenqueued` (R9).
### Etapa 1 — R1, R2, R3 (metering/cap) — revisão `Sol` + Astra recomendada
### Etapa 2 — R4, R5, R10 (wallet/STT/anomalias)
### Etapa 3 — R6, R7 (Stripe/rate cards)
### Etapa 4 — R8, R9 (lease/jobs) · regressão `uv run pytest` + `uv run pytest -m infra_local` (Supabase local)

## 5. Critérios de aceite

- [x] Testes de reprodução vermelhos → verdes; `tests/test_usage_metering.py`, `test_spec197_daily_cap.py`,
      `test_speech_finance_local.py` (caso `unknown_timeout` reclassificado conforme R5), `test_wallet_local.py`,
      `test_spec189*`/`test_spec195*`, `test_postgres_jobs_local.py` verdes ou diff justificado.
      (Diffs justificados: `test_usage_metering` — falha sem usage agora custa 0; `test_image_pricing` — janela 30 d;
      `test_spec192_cron_endpoints` — o cron `/operations` também varre a wallet. O caso `unknown_timeout` segue
      `uncertain` sem mudar: timeout continua `unknown`.)
- [x] `uv run pytest` verde; `-m infra_local` verde em Supabase local; migration idempotente aplicada 2× sem erro.
- [x] FinOps dashboard/alertas: falhas de provider em painel próprio; `cost_spike` sem disparo por falha.
      (Resumo do cron `provider_failures_no_usage[_by_provider]`, relatório `finops-spend-v2`; regras Prometheus
      `FinopsRateCardExpiring`/`FinopsWalletUncertainHold`/`FinopsWalletSpendAnomaly`.)
- [x] Guard de FallbackLLM: não se aplica.

## 6. Smoke test com LLM real (staging, custo mínimo)

1. Forçar 1 falha DeepSeek (chave inválida temporária) + fallback Groq em 1 turno → `usage_events`: falha com
   `cost_usd=0, counts_as_spend=false`; custo do turno = só Groq.
2. Teto diário: trip simulado ontem (fixture) + re-enable hoje → novo gasto acima do teto desliga imagem.
3. STT: provocar 429 no Groq (limite) → transcrição pelo fallback, `reserved_milli == 0` ao final.

## 7. Riscos & compatibilidade

- R2 muda relatórios históricos de FinOps (backfill zera falhas): documentar no README e versionar o relatório.
- R5 reclassifica um teste que fixava o comportamento atual (`unknown_timeout`): timeout continua `unknown`
  (retido); só 4xx/429 recebidos viram definitivos.
- R10 fail-closed em cold start pode negar imagem por alguns segundos durante incidente de DB — aceito (dinheiro).

## 8. Pontos de decisão do dono

> **Decisões aplicadas (2026-10-16, defaults autorizados pelo dono para esta onda):** D-A = manter o piso em
> `quote_attempt_ceiling` (só reserva; nunca em `usage_events`); D-B = 30 d (`RPG_RATE_CARD_MAX_AGE_DAYS`) com
> alerta T−3 d (`RPG_RATE_CARD_WARN_DAYS`); D-C = 5xx continua `unknown` (só 4xx/429 recebidos são definitivos).

- **D-A (piso de US$ 1 em reserva):** manter em `quote_attempt_ceiling` (default) ou reduzir ao máximo do rate card.
- **D-B (janela de rate card):** 30 d (default) ou 14 d com alerta T−3.
- **D-C (STT `definitive_no_charge` em 5xx):** tratar 5xx com corpo como definitivo (default não — `unknown`).

## 8.1 Desvios registrados na implementação (2026-10-16)

- **R1:** `failed_no_usage` vale para falhas de rede/transporte (`invoke_error`, `stream_error`, `http_error`,
  `transport_error`, `unknown`, ...). Respostas RECEBIDAS sem bloco de usage (`invalid_structured`,
  `invalid_response`, `success`/`response`) seguem na estimativa conservadora: o provedor respondeu e pode ter
  cobrado. Backfill da migration espelha a regra (e exige ausência de unidades medidas).
- **R2:** coluna `counts_as_spend` NÃO entra no digest do evento (o digest legado continua idêntico em replays);
  ela deriva do `cost_basis`. CHECK novo: base sem gasto ⇒ `cost_usd=0` e `counts_as_spend=false`.
- **R3:** o trip que justifica o override precisa estar no MESMO dia-de-teto (`since ≤ trip ≤ re-enable` e
  `trip < since+1d`).
- **R4:** a varredura roda no cron `/internal/cron/operations` com carência `RPG_WALLET_RECOVERY_GRACE_SECONDS`
  (default 900 s, mínimo 60) para nunca disputar um request ainda terminando. Reservas de imagem pertencem ao job:
  só job `dead`/`cancelled` (ex.: lease expirado no teto, R9) entrega a reserva à varredura (release se pré-dispatch,
  `uncertain` se ticket emitido; geração `failed`).
- **R5:** retenção PARCIAL (só o teto das `unknown`) não é representável sem mudar o schema append-only
  (`wallet_reservations` exige `settled=released=0` enquanto aberta e uma única entrada settle/release por reserva).
  Implementado: 4xx/429 recebidos viram evento EXATO de custo zero (`definitive_no_charge`) e a reserva liquida e
  libera tudo; havendo `unknown`, a reserva inteira fica `uncertain` (≤ `RPG_SPEECH_MAX_RESERVE_MILLI`) até o
  operador usar `scripts/admin_wallet_reconcile.py`, que agora LIQUIDA o uso exato já persistido e libera o resto
  (antes recusava "no-charge contraditório"). O CLI só aceita reserva `uncertain`.
- **R7:** o exemplo "25 d → warning" da Etapa 0 é incompatível com T−3 d sobre 30 d; teste usa 28 d → warning,
  25 d → sem alerta, 31 d → `PricingUnavailable`.
- **R10:** o excesso fica em `wallet_reservations.financial_anomaly_milli` (coluna nova) para qualquer reserva, além
  de `art_generations` para imagem. A variável do teto é `RPG_DAILY_SPEND_CAP_BRL` (a spec citava `RPG_DAILY_CAP_BRL`);
  opt-out do fail-closed: `RPG_KILL_SWITCH_CAP_FAIL_OPEN=1`. O TTL do adiamento usa o relógio do banco
  (`art_generations.created_at`); falha ao checar o TTL mantém o adiamento (nunca quebra a pausa).
- **R9:** reativação de job `dead`/`cancelled` tem cooldown de 15 min (`DEAD_JOB_REVIVE_COOLDOWN`) para que o
  re-enqueue automático a cada turno não recrie um loop pago.

## 9. Evidência requerida

- `uv run pytest` completo e `-m infra_local`; testes antes/depois; saída da migration 2×.
- `docs/<spec>/README.md` com repros (`m.py`, `cap_repro.py`, `lease.py`) transcritas, relatório FinOps antes/depois e
  revisão `Sol` (+ Astra para R1/R2/R5).
