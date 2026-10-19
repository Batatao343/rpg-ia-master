# Área 08 — Billing / wallet / jobs / workers (correção contábil e de reprocesso)

Data: 2026-10-15. Auditor: subagente Sonnet. Somente leitura + repros offline (nenhum provider/Postgres real).

**Cobertos (leitura integral):** `infrastructure/wallet.py`, `wallet_debt.py`, `reconciliation.py`, `stripe_payments.py`, `google_play_payments.py`,
`speech_finance.py`, `finops_reader.py`, `usage_events.py`, `kill_switch_store.py`, `pricing_catalog.py`; `services/usage_metering.py`, `shard_pricing.py`,
`purchase_reconciliation.py`, `image_quotes.py`, `speech_to_text.py`, `speech_pricing.py`, `daily_spend_cap.py`, `kill_switches.py`, `finops.py`, `finops_job.py`,
`finops_alerts.py`, `cron_internal.py`, `job_fence.py`, `operation_recovery.py`; `workers/*`; trechos de `dynamic_art.py` (complete/settle) e `postgres_jobs.py` (defer/fail);
SQL: constraints de `20261008170000_wallet_ledger.sql`.
**NÃO cobertos (tempo):** `services/stripe_checkout.py`, `services/google_play.py` (cliente HTTP), `image_pricing.py` (exceto require/price), demais migrations (triggers de
debt/hold em `20261015140000`), `infrastructure/postgres_jobs.lease` (área 04). Testes Postgres reais fazem skip: nada abaixo marcado "executado" depende de DB.

**Contagem:** crítica 0 · alta 2 · média 4 · baixa 3.

---

### BUG-08-01 — Tentativa de LLM que falha sem `usage` é gravada como US$ 1,00 e entra no teto diário, FinOps e custo do turno
- **Severidade:** alta
- **Categoria:** contabilidade
- **Local:** `services/usage_metering.py:166-171` (ramo "unknown": `_UNKNOWN_MIN_USD = 1.00`); consumidores: `infrastructure/finops_reader.py` (`usage_groups`/`owner_usage`), `services/daily_spend_cap.py:124`, `services/finops_alerts.py` (`unknown_pricing`/`cost_spike`), `api.py:729`.
- **Evidência:** `normalize_attempts` só descarta `network_attempted is False`/`build_error`/`circuit_open`. Uma tentativa real que falhou (429, 402, timeout, 5xx) tem `usage=None` → cai no `else` → `cost = max(1.00, ...)`, `billing_exact=False`, `pricing_version="unknown-conservative-v1"`. Esse valor é persistido em `app.usage_events.cost_usd` e somado como gasto real por `sum(cost_usd)`.
- **Reprodução (executado):**
  ```
  normalize_attempts([{deepseek, outcome:"error", network_attempted:True, usage:None},
                      {groq, outcome:"success", usage:{input_tokens:1000, output_tokens:300}}])
  deepseek error   1.000000000 estimated False      <- US$ 1,00 por uma chamada que falhou
  groq     success 0.000330000 token_priced True
  ```
  Efeitos em cascata: (a) cada fallback DeepSeek→Groq (cenário normal com DeepSeek 402/429) soma ~US$1; ~9 falhas/dia (R$ 50 ≈ US$ 8,3 a FX 6) disparam `evaluate_daily_cap` e desligam `image_generation` e `stt_fallback_expensive` com gasto real de centavos; (b) `unknown_pricing` (blocking) dispara para o par provider/modelo; (c) `cost_spike`: `usd >= 1.0` e provider sem histórico (`mean == 0`) gera alerta com 1 falha; (d) custo técnico mostrado ao jogador (`llm_cost_usd`) e `unit_costs` (custo por turno) inflados; (e) margem por SKU subestimada (custo variável alocado).
- **Impacto:** teto diário corta features pagas sem gasto real; alertas bloqueantes ruidosos mascaram os reais; relatório de margem enviesado.
- **Correção sugerida:** persistir eventos de falha sem usage com `cost_usd=0` e `billing_exact=False` (fora de somas de gasto), ou filtrar `usage_groups`/`owner_usage`/cap por `billing_exact or cost_basis<>'estimated'`; manter o piso de US$1 só dentro de quote/bloqueio da wallet.
- **Confiança:** confirmado por execução (normalização) + leitura (consumidores).
- **Testes existentes relacionados:** `tests/test_usage_metering.py` (cobre a estimativa, não o efeito no cap), `tests/test_spec197_daily_cap.py` (usa grupos sintéticos).

### BUG-08-02 — Override manual do teto diário "vaza" do dia anterior e impede o re-trip de hoje
- **Severidade:** alta
- **Categoria:** regra-divergente (docstring × código)
- **Local:** `services/daily_spend_cap.py:75-84` (`_manually_reenabled`)
- **Evidência:** a docstring diz "re-enable humano que seguiu um trip do sistema **hoje**", mas o código só exige `last` humano com `at >= since` e QUALQUER linha anterior `actor==system:finops, enabled=False` (`rows[1:]`), sem checar que essa linha seja de hoje.
- **Reprodução (executado):** trip do sistema ontem (-20h), re-enable humano hoje de manhã (-4h), gasto de hoje > teto:
  ```
  exceeded True  switched_off ['stt_fallback_expensive']  manual_override ['image_generation']
  ```
  `image_generation` continua ligado apesar do teto de HOJE estourado (o STT só foi cortado por não ter linha de auditoria).
- **Impacto:** o fluxo normal ("amanhã de manhã o operador religa") desarma o teto pelo resto do dia; gasto de imagem sem limite até virar o dia.
- **Correção sugerida:** exigir `any(a.actor_id==ACTOR and a.enabled is False and _ts(a.at) >= since for a in rows[1:])` (trip do sistema no mesmo dia-de-teto do re-enable).
- **Confiança:** confirmado por execução.
- **Testes existentes relacionados:** `tests/test_spec197_daily_cap.py::test_manual_reenable_same_day_not_retripped` (só mesmo dia; falta o caso cross-day).

### BUG-08-03 — Nada varre reservas de wallet órfãs: `PostgresWallet.recover` só é chamado dentro do `finish` do STT
- **Severidade:** média
- **Categoria:** contabilidade / divergência spec×código
- **Local:** `infrastructure/wallet.py:546` (`recover`), `services/operation_recovery.py:recover_expired`, `services/cron_internal.py` (`/operations`)
- **Evidência:** `grep "\.recover("` → único callsite em `speech_finance.py:82` (mesmo request). `recover_expired` só abandona `app.operations` com lease vencido; não toca `app.wallet_reservations`. `docs/spec184/README.md:36` promete "Queda sem ticket permite liberação automática".
- **Reprodução:** hipótese de caminho (sem DB): função serverless morta entre `wallet.reserve` e `finish` (ou crash entre `coordinator.complete` e `settle_usage` do STT): `reserved_milli` fica preso (`status='reserved'`, ou `'effect_started'` com usage exato já persistido). O cron `/operations` marca a operação `abandoned`, mas o saldo reservado segue indisponível.
- **Impacto:** Estilhas do jogador presas sem caminho automático (hoje restrito a STT/imagem sob flags; vira geral quando o turno usar a wallet).
- **Correção sugerida:** no cron `/operations` (ou novo `/wallet-recovery`) chamar `wallet.recover` para reservas `reserved` cuja operação foi abandonada/venceu, e `settle_usage` quando `effect_started` já tem eventos exatos == tickets.
- **Confiança:** provável (leitura de callsites; sem DB).
- **Testes existentes relacionados:** `tests/test_wallet_local.py` (cobre `recover` isolado, não o agendamento).

### BUG-08-04 — STT: qualquer tentativa falha (mesmo 429 definitivo) deixa a reserva inteira em `uncertain`, sem caminho operacional
- **Severidade:** média
- **Categoria:** contabilidade
- **Local:** `infrastructure/speech_finance.py:finish` (68-83), `services/speech_to_text.py:transcribe_audio`, `services/speech_pricing.py:speech_event`
- **Evidência:** tentativa com erro/timeout gera `speech_event(..., "unknown"/"error", {})` com `billing_exact=False`. `finish` exige `all(e.billing_exact)`; senão cai em `wallet.recover` → ticketed → `status='uncertain'` com a reserva de ambos os candidatos (até `RPG_SPEECH_MAX_RESERVE_MILLI`=100 milli). Vale mesmo quando o fallback teve sucesso exato e o jogador recebeu o texto: nenhum débito e nenhum release. `reconcile_proven_no_charge` não tem CLI/cron (`scripts/` só tem `admin_wallet_adjust.py` e `admin_kill_switch.py`).
- **Reprodução:** `tests/test_speech_finance_local.py::test_unknown_timeout_preserves_hold_and_retry_cannot_dispatch` fixa o comportamento (ReadTimeout seguido de sucesso ⇒ `pending_reconciliation`, `reserved_milli > 0`).
- **Impacto:** a cada fallback STT (caso comum com Groq 429) o saldo fica retido indefinidamente; operador sem ferramenta para resolver.
- **Correção sugerida:** distinguir falha definitiva (resposta HTTP 4xx/429 recebida ⇒ sem cobrança) de desconhecida (timeout/cancel); liquidar as tentativas exatas e liberar o restante quando as não-exatas forem definitivas; adicionar `scripts/admin_wallet_reconcile.py`.
- **Confiança:** confirmado por leitura (+ teste que fixa o comportamento).
- **Testes existentes relacionados:** `tests/test_speech_finance_local.py` (fixa o comportamento atual).

### BUG-08-05 — Stripe: reembolso PARCIAL entregue antes de `checkout.session.completed` marca o pedido `refunded` e nunca credita
- **Severidade:** média
- **Categoria:** regra-divergente / ordem de eventos
- **Local:** `infrastructure/stripe_payments.py` — `_financial_event` (ramo sem `purchase`) + `_checkout_event`
- **Evidência:** sem `wallet_entries.purchase` ainda, `outcome="blocked_before_credit"` e `status` permanece `"refunded"` (o `if kind == "refund" and amount < gross: status = row["status"]` está dentro do `elif purchase:`). `_checkout_event` aplica os financeiros pendentes ANTES de creditar e só credita `if row["status"] not in TERMINAL` ⇒ `refunded` bloqueia o crédito de uma compra paga com reembolso de, p.ex., 1%. O reconciliador (`_purchase` None ⇒ parked ⇒ orphaned após 8 tentativas) não corrige.
- **Reprodução:** hipótese (exige Postgres): `charge.refunded` com `amount_refunded < gross` entregue antes de `checkout.session.completed` (retomada de webhook após indisponibilidade). Esperado: crédito integral + clawback proporcional (SPEC-195); observado: pedido `refunded`, carteira sem crédito.
- **Impacto:** cliente paga e não recebe Estilhas (perda de dinheiro do jogador); raro, mas permanente.
- **Correção sugerida:** no ramo pré-crédito só marcar `refunded` quando `amount >= gross_cents`; parcial mantém o status e deixa o reconciliador aplicar o clawback proporcional após o crédito.
- **Confiança:** provável (leitura; sem DB).
- **Testes existentes relacionados:** nenhum para parcial pré-crédito (os testes SPEC-189/195 cobrem refund total fora de ordem).

### BUG-08-06 — Rate cards de imagem e STT expiram em 7 dias fixos a partir da data do arquivo: bloqueio total em 2026-10-19
- **Severidade:** média
- **Categoria:** regra-divergente (operacional)
- **Local:** `services/image_pricing.py:20-23`, `services/speech_pricing.py:require_speech_prices` (`timedelta(days=7)`), `services/finops_alerts.py:installed_freshness`; cartas `data/pricing/image_rate_card_2026-10-12.json` e `speech_rate_card_2026-10-12.json`
- **Evidência:** `observed_at` = 2026-10-12 e janela fixa de 7 dias ⇒ a partir de 2026-10-19 `require_image_prices` e `require_speech_prices` levantam `PricingUnavailable` para todo novo quote/STT; `require_paid_effect("image")` bloqueia o endpoint e o FinOps emite `stale_rate_card` blocking. A janela é código, não config (`RPG_FINOPS_BLOCK_STALE=0` só afeta `require_paid_effect`).
- **Impacto:** imagem e voz (quando ativadas) caem sozinhas em 4 dias sem deploy de novo card; jobs de imagem já confirmados falham em `dispatch` (liberam pré-dispatch).
- **Correção sugerida:** alerta de renovação (T-2d) + janela configurável por env + runbook.
- **Confiança:** confirmado por leitura (datas e constantes).
- **Testes existentes relacionados:** testes de stale injetam `at` (não detectam a data real).

### BUG-08-07 — `settle_usage` (não-imagem) com custo > teto lança `SpendCeilingExceeded` e deixa a reserva em `effect_started` sem registrar anomalia
- **Severidade:** baixa
- **Categoria:** contabilidade
- **Local:** `infrastructure/wallet.py:532-533`
- **Evidência:** só o ramo `cap_confirmed_image` limita ao teto e grava `financial_anomaly_milli`. Para LLM, `provider_reported` não é limitado ao bound do rate card (`normalize_attempts` aceita qualquer `provider_cost_usd`), então custo reportado > teto faz todo `settle` falhar do mesmo jeito; a reserva não vira `uncertain`, o excesso não é registrado e o retry repete o erro.
- **Impacto:** fundos retidos sem trilha do excesso (hoje só alcançável quando o turno usar a wallet).
- **Correção sugerida:** limitar ao teto, registrar o excesso 1× e liquidar; ou marcar `uncertain`.
- **Confiança:** hipótese (caminho de código).
- **Testes existentes relacionados:** nenhum para LLM acima do teto.

### BUG-08-08 — Job de imagem adiado (kill switch) segura a reserva indefinidamente
- **Severidade:** baixa
- **Categoria:** estado-inconsistente
- **Local:** `workers/run_worker.py` (`generate`, JobDeferred 60 s), `infrastructure/postgres_jobs.py:defer`
- **Evidência:** `defer` devolve a `attempts` e re-agenda para sempre enquanto `image_generation` estiver off; a reserva fica `reserved` (pré-dispatch, liberável com segurança) sem TTL, e a quote já expirou para a UX.
- **Impacto:** Estilhas presas enquanto o switch (ou o teto diário) estiver desligado; combinado com BUG-08-01/02 pode durar dias.
- **Correção sugerida:** após N horas adiado, liberar via `release_pre_effect` (status `reserved`) e marcar a geração `failed`.
- **Confiança:** provável.
- **Testes existentes relacionados:** `tests/test_spec196*` cobre o defer, não um teto de duração.

### BUG-08-09 — Kill switches falham ABERTO em cold start com store ilegível (inclui o corte do teto diário)
- **Severidade:** baixa
- **Categoria:** guard-fallback
- **Local:** `services/kill_switches.py:122-145`
- **Evidência:** sem snapshot bom (`_ever_loaded=False`) e `RPG_KILL_SWITCH_FAIL_CLOSED` vazio ⇒ tudo habilitado. Em serverless cada cold start parte sem snapshot; oscilação do DB reabre `image_generation` mesmo após o teto diário tê-lo desligado.
- **Impacto:** gasto pago pode escapar do corte durante incidente de DB. Decisão documentada na docstring, por isso baixa.
- **Correção sugerida:** default fail-closed para `image_generation`/`stt_fallback_expensive` quando o teto diário estiver configurado.
- **Confiança:** confirmado por leitura.
- **Testes existentes relacionados:** testes de fail-safe cobrem o comportamento documentado.

---

## Descartados / falsos positivos
- **Settle 2x / release 2x no wallet:** `_terminal_transfer` roda sob `for update` da reserva + unique `(owner_id,entry_type,reference_type,reference_id)`; replay de `settle_usage` compara `usage_event_ids` e devolve o mesmo registro. Sem duplicação.
- **Arredondamento de Estilhas:** `quote_purchase` usa floor para o grant e ceil para fee/margem; `quote_usage`/`quote_attempt_ceiling` usam ceil exato (`as_integer_ratio`), sem `float`. `float(` só aparece em resumo/métrica do cap (`daily_spend_cap.py:109-146`), sem impacto contábil.
- **Reconciliador (refund/dispute/void fora de ordem, duplicado):** `fold` independe de ordem/duplicata (máximos cumulativos, rank de disputa); plano idempotente recomputado sob lock do owner + advisory lock; tabelas de transição fechadas. Sem dupla aplicação nem refund > bruto (`min(gross, ...)`).
- **Stripe/Google fulfillment não re-cotam preço:** correto (webhook não depende de FX fresco).
- **Kill switch `new_purchases` x crédito legítimo:** `require_purchases` só é chamado ao criar pedido novo (`checkout`) e em `verify` de token novo; webhook/`prior` seguem creditando.
- **Cron 58 s:** `drain_jobs` exige 15 s de janela antes de iniciar job; imagem >40 s poderia ser cortada pela plataforma, mas cai no caminho `uncertain` por desenho (SPEC-188).
- **`events[-1:]` em `_append_job_attempt`:** correto, pois o capture roda a cada tentativa com a lista cumulativa; replay idempotente por digest.
- **Heartbeat/lease/poison de `PostgresJobQueue`:** já reportado pela área 04.
