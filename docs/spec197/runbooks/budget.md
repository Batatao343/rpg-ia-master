# Orcamento e limites de gasto (SPEC-197 R7)

Defesa em camadas: (1) teto no provedor (duro), (2) kill switches e alertas FinOps (nossos), (3) revisao diaria no
beta. Valores sao PROPOSTAS para o usuario confirmar em `external-inputs.md`.

| Camada | Onde | Limite sugerido (beta) | Quem |
|---|---|---|---|
| Supabase | Org > Billing: Spend Cap (Pro) | cap ligado; nenhum add-on sem aprovar | usuario |
| Vercel | Team > Billing > Spend Management (Pro) | alerta 50/75/100%, pausa no teto | usuario |
| DeepSeek | platform.deepseek.com, saldo prepago | recarga manual pequena; sem auto-recarga | usuario |
| Groq | console.groq.com, Billing/limits | free tier ou limite mensal | usuario |
| OpenAI (STT/imagem, se usado) | platform.openai.com > Settings > Limits | hard limit mensal + alerta | usuario |
| Jina (embeddings) | jina.ai dashboard | saldo prepago | usuario |
| Google (Gemini/Play) | Cloud Console > Budgets & alerts | alerta; sem chave Gemini se nao usada | usuario |
| Stripe | monitorar disputas/refunds | alertas por e-mail | usuario |

## Cap diario no app
- Custo por chamada e atribuido e comparado a margem em `services/finops.py`; `POST /internal/cron/finops` a cada
  15-30 min grava `app.finops_evaluations`. `FinopsCostSpike`, `FinopsMarginBelowTarget`, `FinopsExpensiveFallback`,
  `FinopsProviderFailure`, `FinopsEvaluationStale` pedem acao do operador.
- Resposta a custo anomalo: `off image_generation`, `off stt_fallback_expensive`, `off model:<p>/<m>` e, se preciso,
  `off new_purchases`. Playbook em `incident.md`.
- **Corte automatico diario (SPEC-197 R7, implementado):** defina `RPG_DAILY_SPEND_CAP_BRL` (ex. `30`). Sem a variavel
  (ou invalida/<=0) a funcao fica DESLIGADA. O cron `/internal/cron/finops` soma o gasto variavel do dia
  (`usage_events.cost_usd` x FX da pricing version mais nova, ou 6,0 se nao houver; dia = America/Sao_Paulo, UTC-3,
  ajustavel em `RPG_DAILY_SPEND_TZ_OFFSET_HOURS`). Acima do teto liga OFF `image_generation` e `stt_fallback_expensive`
  com ator `system:finops` e motivo na auditoria, uma unica vez (idempotente), e emite o alerta bloqueante
  `daily_spend_cap` (`FinopsDailySpendCap`). NUNCA religa sozinho: o humano faz
  `scripts/admin_kill_switch.py on <chave> --actor <voce> --reason "<motivo>" --apply`. Compras (`new_purchases`) e
  leitura de campanhas nao sao tocadas.
  **Cobertura honesta:** o cap corta SOMENTE imagem e STT caro. O gasto de LLM de texto NAO e limitado por ele: so
  pelo saldo prepago dos provedores (R-11). Opt-in `RPG_DAILY_SPEND_CAP_MODEL_SWITCHES=model:<provider>/<model>,...`
  desliga tambem esses fallbacks caros quando o teto estoura (mesma auditoria, mesmo nunca-religa).
  **Re-religar no mesmo dia:** se um humano religar uma chave depois do corte, o cron NAO a desliga de novo ate virar o
  dia (00:00 BRT); para voltar a ter protecao, suba `RPG_DAILY_SPEND_CAP_BRL` (religar sem subir o teto deixa o dia
  sem corte naquela chave) ou espere a virada. `RPG_DAILY_SPEND_TZ_OFFSET_HOURS` deve ser inteiro em -12..14.
  Erro na avaliacao do cap (config invalida, store fora) gera alerta bloqueante `daily_spend_cap_error` e o cron
  responde nao-2xx (`failed=1`), acionando o watchdog. Depende do cron estar agendado (R-12); cadencia 15-30 min.
- `data/finops_fixed_costs.json` deve refletir Supabase Pro + Vercel Pro reais antes da producao;
  `scripts/finops_margin_sim.py` reexecutado com precos live.

## Rotina
Diaria no beta: saldo dos provedores, `finops_evaluations`, `cron_health_alerts`, refunds/disputas.
Semanal: rate cards (`stale_rate_card`); modelo novo em `ROUTES` so apos card publicado.

## Renovacao de rate cards (SPEC-236 R7)
- Janela de frescor dos cards de imagem/STT: `RPG_RATE_CARD_MAX_AGE_DAYS` (default 30 d, 1..365; valor invalido
  volta ao default, nunca amplia). O LLM segue `RPG_FINOPS_LLM_CARD_MAX_AGE_DAYS`.
- Alerta `rate_card_expiring` (NAO bloqueante) a partir de T-`RPG_RATE_CARD_WARN_DAYS` (default 3 d); ao expirar vira
  `stale_rate_card` (bloqueante) e quotes/STT novos recebem `PricingUnavailable` (503).
- Renovar: observar os precos publicados, gravar novo `data/pricing/<tipo>_rate_card_<data>.json` com `observed_at`
  atual, apontar `services/image_pricing.py`/`services/speech_pricing.py` para ele, rodar a suite e fazer deploy ANTES
  do T-0. Quotes de imagem ja emitidos com a versao antiga exigem novo quote (`image pricing changed`).

## Falhas de provider e retencoes (SPEC-236)
- Tentativa que falha SEM `usage` (402/429/timeout/5xx) e gravada com `cost_usd=0`,
  `cost_basis='failed_no_usage'`, `counts_as_spend=false`: fica auditavel, fora do teto diario, da margem e do custo do
  turno. O cron FinOps mostra a contagem em `provider_failures_no_usage[_by_provider]` (relatorio `finops-spend-v2`).
  A migration `20261016100000` tirou do gasto as falhas historicas gravadas como US$ 1,00 (linhas preservadas).
- Retencao `uncertain` (alerta `wallet_uncertain_hold`): so resolver com prova do provedor de que a tentativa
  desconhecida nao foi cobrada: `scripts/admin_wallet_reconcile.py --owner <id> --reservation <id> --actor <uuid>
  --evidence <ref>` (dry-run) e depois `--apply --confirm-owner <id>`. Uso exato ja persistido e debitado, nunca
  perdoado. O cron `/internal/cron/operations` libera reservas sem ticket de operacoes mortas e liquida as que tem uso
  exato 1:1 com os tickets (carencia `RPG_WALLET_RECOVERY_GRACE_SECONDS`, default 900 s).
- Stream cortado DEPOIS do primeiro chunk (outcome `stream_interrupted`: cliente fechou ou conexao caiu no meio) NAO
  e `failed_no_usage`: o provedor ja gerou (e cobrou) tokens, entao entra como estimativa conservadora que conta no
  teto diario/FinOps e nao e exata (reserva de wallet fica `uncertain`). So falha ANTES do primeiro chunk
  (`stream_error`) custa zero.
- ATENCAO (STT, rate card x reconciliacao): uma retencao ja autorizada liquida pelo snapshot (card VENCIDO nao a
  bloqueia), mas o uso exato de STT carrega a versao do card (`SPEECH_PRICING_VERSION` = versao + hash do arquivo).
  Ao RENOVAR o card, eventos gravados com a versao antiga deixam de ser faturaveis: `admin_wallet_reconcile.py
  --apply` (e o settle do cron) falham com `PricingUnavailable` e a retencao `uncertain` fica TRAVADA. Antes de
  deployar um card novo de STT, zerar `wallet_uncertain_hold` de STT (reconciliar tudo); nunca editar a reserva no banco.
- `wallet_spend_anomaly`: liquidacao acima do teto confirmado foi limitada ao teto; o excesso fica em
  `wallet_reservations.financial_anomaly_milli` (e em `art_generations` para imagem).
- Com `RPG_DAILY_SPEND_CAP_BRL` configurado, `image_generation`/`stt_fallback_expensive` falham FECHADOS em cold
  start com store ilegivel (opt-out `RPG_KILL_SWITCH_CAP_FAIL_OPEN=1`). Job de imagem pausado pelo switch libera a
  reserva apos `RPG_IMAGE_DEFER_MAX_HOURS` (default 6 h) e a geracao falha com `deferred_timeout`.
