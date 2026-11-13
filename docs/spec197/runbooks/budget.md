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

## Renovação de rate cards (SPEC-409)
Quatro cards versionados em `data/pricing/`; cada renovação é um **arquivo novo** `<tipo>_rate_card_<AAAA-MM-DD>.json`
(o antigo fica intacto como histórico; `tests/test_pricing_card_files.py` confere o sha256 dos antigos).

| Card | Arquivo atual | Quem lê | Janela |
|---|---|---|---|
| Imagem | `image_rate_card_*.json` | `services/image_pricing.py` | `RPG_RATE_CARD_MAX_AGE_DAYS` (30 d, 1..365) |
| STT | `speech_rate_card_*.json` | `services/speech_pricing.py` | idem |
| Embedding | `embedding_rate_card_*.json` | `services/embedding_pricing.py` | idem (entra em `installed_freshness()`) |
| LLM geral | `rate_card_*.json` | **dois** arquivos com o caminho fixo: `services/shard_pricing.py` (`_INSTALLED_CARD_PATH`, hash e data) **e** `services/usage_metering.py` (`RATE_CARD_VERSION`) | `RPG_FINOPS_LLM_CARD_MAX_AGE_DAYS` (30 d) |

**Quando avisa.** O teste `tests/test_rate_card_freshness.py::test_installed_rate_cards_not_near_expiry` usa o relógio
real e fica **vermelho a T-10 dias** do vencimento de qualquer card (CI em todo push, e o job `rate-cards` do
`validate.yml` na varredura semanal de segunda 06:23 UTC, que notifica por e-mail o dono do repositório). Vencido de
verdade: alerta `stale_rate_card` (bloqueante) e cotação de imagem/STT recebem `PricingUnavailable` (503).
`rate_card_expiring` (T-`RPG_RATE_CARD_WARN_DAYS`, 3 d) é só aviso e não falha o cron.

**Passo a passo (ordem importa).**
1. Ler a página pública de preço de cada provedor (OpenAI, Groq, DeepSeek, Jina) e gravar URL, data/hora e o trecho
   literal em `docs/spec409/` (modelo: `fontes.md` e `evidencia-*.md`). Sem evidência não se muda preço nem só a data.
2. Criar o JSON novo: `version` com a data do arquivo, `observed_at` = dia da leitura, `source(s)` com URL `https://`.
   No de **imagem** o `observed_at` leva offset (`"AAAA-MM-DDT00:00:00+00:00"`; o leitor subtrai de um datetime com
   fuso). Fonte secundária (ex.: Jina) deve ser dita no próprio `source`. `max_cost_usd` do STT é recalculado dos
   tetos (`tests/test_pricing_card_files.py`).
3. Apontar os leitores (tabela acima; no LLM, **os dois**). Rodar `tests/test_pricing_card_files.py`,
   `test_rate_card_freshness.py`, `test_image_pricing.py`, `test_speech_to_text.py`, `test_shard_pricing.py`.
4. Só no **LLM**: publicar no banco **antes do deploy**. `app.pricing_versions` é imutável e pina `rate_card_sha256` +
   `rate_card_observed_at`; sem linha nova a cotação e a compra falham com "conteúdo do rate card divergiu". Staging:
   `scripts/staging/publish_rate_card.py` (`--dry-run`, depois `--confirm-staging <ref>`) publica a versão, o SKU e os
   `image_price_profiles` novos (cópia dos anteriores; conferir `expires_at`, outro relógio) e `vercel_env.py` aponta
   `RPG_SPEECH_PRICING_VERSION` e `RPG_IMAGE_PRICE_PROFILE_*`. As linhas antigas ficam (histórico de compras).
   Imagem/STT/embedding **não** tocam `pricing_versions`.
5. **Pré-condição de deploy (imagem, STT e texto):** nenhuma reserva aberta e nenhum job de imagem em voo.
   `quote_usage` só aceita evento cuja versão do card é a atual (imagem/STT, mesmo com `authorized_snapshot`) e,
   no texto, a `rate_card_version` da linha da reserva; reserva `uncertain` com versão antiga trava a liquidação
   (ver "ATENCAO" abaixo). Conferir `select reference_type, status, count(*) from app.wallet_reservations where status in
   ('reserved','effect_started','uncertain') group by 1,2` e `art_generations` em `pending/generating`.
6. Deploy e smoke: cotação de imagem (`POST /game/{id}/art/quote`, sem gerar), uma requisição curta de STT e
   `POST /internal/cron/finops` com 200 e sem `stale_rate_card` em `app.finops_evaluations`. Cotação de imagem emitida
   antes do deploy pede nova (`image pricing changed`); é esperado.

**Alívio de emergência.** `RPG_RATE_CARD_MAX_AGE_DAYS` (até 365) destrava imagem/STT/`require_paid_effect`, mas esconde
o vencimento: só com prazo escrito e decisão do dono, e removido quando o card novo pousar. `RPG_FINOPS_BLOCK_STALE=0`
**não** basta (só afrouxa `require_paid_effect`, não `require_image_prices`/`require_speech_prices`).

**O que o alerta do cron faz e não faz.** `stale_rate_card` soma 1 em `failed` do `/internal/cron/finops` (HTTP 500,
chave `stale_rate_cards` com os nomes); só esse tipo (não `rate_card_expiring`, `wallet_mismatch` etc.). O mesmo
`kind` cobre a cotação `fx` e a linha `rate_card` mais nova de `app.pricing_versions`: FX vencida também deixa o cron
em 500 a cada hora (em produção, com janela de FX curta, decidir a tolerância no go da SPEC-197). Três respostas
não-2xx seguidas do mesmo job viram uma linha em `app.cron_health_alerts` (~3 h, cron horário) e um `RAISE WARNING` no
log do Postgres. **Ninguém é notificado ativamente** sem o envio de logs externo (Axiom, bloqueado no dono): o aviso que
chega a alguém é o CI vermelho/e-mail de T-10; a linha em `cron_health_alerts`/`finops_evaluations` entra na rotina
diária. Push de verdade é decisão futura (SPEC-409 D5).

`scripts/finops_margin_sim.py` (preços "live" do relatório de margem) **não** lê esses cards e não faz parte da renovação.

## Falhas de provider e retencoes (SPEC-236)
- Tentativa que falha SEM `usage` (402/429/timeout/5xx) e gravada com `cost_usd=0`,
  `cost_basis='failed_no_usage'`, `counts_as_spend=false`: fica auditavel, fora do teto diario, da margem e do custo do
  turno. O cron FinOps mostra a contagem em `provider_failures_no_usage[_by_provider]` (relatorio `finops-spend-v2`).
  A migration `20261017100000` tirou do gasto as falhas historicas gravadas como US$ 1,00 (linhas preservadas).
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
