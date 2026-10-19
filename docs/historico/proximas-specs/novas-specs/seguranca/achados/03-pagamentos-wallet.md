# Área 03 — Pagamentos e integridade financeira (auditoria 2026-10-15)

Somente leitura. Nenhum segredo lido. Resultado: **0 crítica, 0 alta, 1 média, 4 baixas, 1 info.** O núcleo financeiro (webhook Stripe, Google Play, wallet, reconciliação) resistiu à revisão; os achados são de custo/DoS e robustez operacional.

Arquivos inspecionados: api.py (l.235-262, 783-840, 1985-2270, 2420-2560), services/{stripe_checkout,google_play,google_play_fake,cron_internal,kill_switches,daily_spend_cap,image_quotes,purchase_reconciliation(parcial)}.py, infrastructure/{stripe_payments,google_play_payments,wallet,kill_switch_store,pricing_catalog}.py, scripts/admin_wallet_adjust.py, migrations 20261008170000, 20261012160000, 20261013120000, 20261015120000/130000/140000/150000.

## Achados

### PAG-01 — Teto diário de gasto é reativo (cron), opt-in e não cobre o LLM de texto; turnos não têm limite de custo por usuário
- **Severidade:** média
- **Categoria:** DoS/custo
- **Local:** `services/daily_spend_cap.py:1-15,107-147`; `services/finops_job.py`; `api.py:783-840` (`_rate_limit`, só por IP)
- **Evidência:** `cap_from_env()` retorna None sem `RPG_DAILY_SPEND_CAP_BRL` (feature OFF); `evaluate_daily_cap` só roda no cron e só desliga `image_generation`/`stt_fallback_expensive`. O docstring admite: "Text-LLM spend is bounded by the providers' prepaid balances, NOT by this cap". Turnos (`/game/action*`) não passam por wallet (ESTADO: reserve→execute→settle "pendente").
- **Cenário:** contas com e-mail confirmado (staging/produção) × N IPs/contas descartáveis, cada uma a 30 req/min/IP em `/game/action/stream` → gasto DeepSeek/Groq/Anthropic ilimitado até esgotar o saldo pré-pago do provider. O cap, se ligado, reage só no próximo tick do cron (janela de dezenas de minutos) e nunca age sobre texto. Perfis: hosted-supabase, android.
- **Impacto:** queima de crédito de provider / negação de serviço financeira; sem teto por owner/dia.
- **Correção sugerida:** (1) cota diária por owner (contador em Postgres, `INSERT .. ON CONFLICT DO UPDATE` com checagem) verificada ANTES de `app.invoke` em `/game/action*`; (2) cap diário obrigatório em hosted (fail-closed: sem env, usar default ou recusar subir); (3) checar o cap também no caminho de imagem/STT (leitura barata com cache de 30 s). Testes: `tests/test_spec197_daily_cap.py`.
- **Confiança:** confirmado por leitura (limitação documentada na spec)
- **Já coberto por spec?** Parcial: SPEC-196/197 declaram a limitação (R-11); nenhuma spec cria cota por owner para texto.
- **Status:** válido

### PAG-02 — Compras de teste do Google Play (`purchaseType=0`) são creditadas em produção
- **Severidade:** baixa
- **Categoria:** Pagamentos/Integridade financeira
- **Local:** `services/google_play.py:68,86-93` (campo lido, nunca usado); `infrastructure/google_play_payments.py:56-80`
- **Evidência:** `grep purchase_type` → só atribuição e `snapshot()`. `verify()` valida estado, quantidade, conta e consumo, mas não rejeita `purchase_type == 0` (license testing) nem `2` (rewarded).
- **Cenário:** conta listada como license tester compra SKU de graça e recebe Estilhas reais; em produção o custo de provedor (imagem/STT) é real.
- **Impacto:** crédito sem receita para qualquer licença de teste (lista controlada pelo operador, por isso baixa).
- **Correção sugerida:** em `verify()`, se `RPG_PLAY_ACCEPT_TEST_PURCHASES != "1"` e `facts.purchase_type in (0, 2)` → `GooglePlayError("google_play_test_purchase_rejected")`; permitir só em staging/fake. Teste em `tests/test_spec194_*`.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** válido

### PAG-03 — Endpoints que disparam chamadas externas/linhas imutáveis sem rate limit (`/account/checkout`, `/account/purchases/google/verify`, `/game/{id}/art/quote`)
- **Severidade:** baixa
- **Categoria:** Rate limit / DoS
- **Local:** `api.py:790-800` (lista fechada de paths do `_rate_limit`), `api.py:2035-2050`, `2113-2135`, `2446-2490`; `infrastructure/stripe_payments.py:134-185`
- **Evidência:** a lista do middleware não inclui esses paths; `/account/transcriptions` tem limite próprio (5/min) mas os demais não. `checkout` aceita qualquer `request_id` UUID novo → nova linha `payment_orders` + `POST checkout/sessions` ao Stripe; `quote` insere linha em `image_quotes` (imutável por trigger, nunca expira do banco).
- **Cenário:** usuário autenticado em loop com `request_id` aleatório: milhares de ordens/sessões Stripe (429 do Stripe afeta todos os compradores) e crescimento ilimitado de tabelas imutáveis. `google/verify` com tokens inválidos bate na Play API (cota compartilhada).
- **Impacto:** esgotamento de cota Stripe/Play, inchaço do banco.
- **Correção sugerida:** `runtime.rate_limiter.consume(f"checkout:{user_id}", limit=5, window_seconds=60)` (idem `gplay-verify:` e `art-quote:`), além de limite de ordens `created` abertas por owner (ex.: ≤3) em `checkout()`.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** válido

### PAG-04 — Kill switches falham aberto por default quando o store é ilegível
- **Severidade:** baixa
- **Categoria:** Config/Infra
- **Local:** `services/kill_switches.py:100-140` (`snapshot`, `_fail_closed_keys`)
- **Evidência:** exceção em `store.load()` mantém cache anterior ou "tudo ligado"; `RPG_KILL_SWITCH_FAIL_CLOSED` é opt-in e vazio por padrão.
- **Cenário:** incidente com DB instável logo após o operador desligar `image_generation`/`new_purchases`: um cold start (Vercel) perde o cache e o switch volta a "on" enquanto o DB está ilegível.
- **Impacto:** efeito caro reabilitado silenciosamente durante falha de leitura.
- **Correção sugerida:** default `RPG_KILL_SWITCH_FAIL_CLOSED=image_generation,stt_fallback_expensive` em hosted (compras seguem abertas; revenue path). Teste: `tests/test_spec196_*`.
- **Confiança:** confirmado por leitura (decisão de design documentada)
- **Já coberto por spec?** SPEC-196 (decisão consciente); sem default em hosted.
- **Status:** válido (endurecimento)

### PAG-05 — Rate limit por `request.client.host` sem tratamento de proxy (Vercel)
- **Severidade:** baixa
- **Categoria:** Rate limit
- **Local:** `api.py:803-807`; `grep forwarded|proxy_headers` → nenhum resultado no código
- **Evidência:** chave `ip:{pseudonym(request.client.host)}`; não há leitura de `X-Forwarded-For`/`proxy_headers`.
- **Cenário:** atrás do proxy da Vercel `client.host` pode ser o IP do proxy ou ausente (`"?"`), colapsando todos os usuários num bucket de 30 req/min (auto-DoS) ou, ao "corrigir" lendo header cru, spoof. Depende do adaptador ASGI.
- **Impacto:** limite ineficaz ou indisponibilidade para todos.
- **Correção sugerida:** definir a fonte do IP (header confiável da plataforma, só quando `VERCEL` setado) e testar; somar limite por owner autenticado (PAG-01).
- **Confiança:** hipótese
- **Já coberto por spec?** não verificado (área infra/rate limit — outro auditor pode confirmar)
- **Status:** válido (a confirmar em staging)

### PAG-06 — Cap diário pode ser acionado por usuário pagante como alavanca de indisponibilidade
- **Severidade:** info
- **Categoria:** DoS/custo
- **Local:** `services/daily_spend_cap.py:107-147`
- **Evidência:** ao exceder o cap, desliga imagem e STT-fallback para TODOS até reativação manual.
- **Cenário:** usuário gasta o próprio saldo em imagens/STT para estourar o cap global e desabilitar o recurso para os demais (mitigado: gasto vem de saldo comprado; switch reversível).
- **Correção sugerida:** cap por owner além do global; alerta quando um owner concentra >X% do gasto.
- **Confiança:** provável
- **Já coberto por spec?** não
- **Status:** válido (informativo)

## Verificado e OK
- **Webhook Stripe** (`api.py:2151`, `services/stripe_checkout.py:verify_event`): corpo lido em stream com teto de 256 KB e timeout de 15 s; HMAC-SHA256 sobre `t.` + raw body, `compare_digest`, tolerância ±300 s, `t` único, só então `json.loads`; `livemode is False` obrigatório; chaves `sk_test_`/`whsec_` obrigatórias (impede live por engano; adaptador também rejeita resposta live). Rota fora de cookie/CSRF por design.
- **Idempotência/concorrência** (`stripe_payments.accept_event`): `pg_advisory_xact_lock` por payment_intent/order/event, `stripe_events.event_id` PK + `body_sha256` (replay divergente → erro), triggers append-only.
- **Crédito só em evento pago** (`_checkout_event`): `payment_status=="paid"`, `mode=="payment"`, `amount_total==gross_cents`, `currency==order.currency`, `cs_test_`, intent único por ordem; crédito vem do SKU/ordem server-side; conferência de autoridade SKU×ordem antes de creditar; refund/dispute viram debt/hold via reconciliador; conta apagada → `reconciliation_required`.
- **Checkout**: success/cancel derivadas de `RPG_CHECKOUT_ORIGIN` (https, sem path) + `order_id` server-side — sem open redirect; `checkout_url` validada (`https://checkout.stripe.com`); `GET /account/checkout/{order_id}` filtra `owner_id`; cliente envia só `sku_id`+`request_id`; SKU precisa estar na allowlist E publicado.
- **Google Play** (`google_play.py`, `google_play_payments.py`): produto/pacote/token por regex; pacote vem do env; `facts.product_id`, quantidade=1, `purchaseState`, `consumptionState==0`, `orderId` consistente e `obfuscatedExternalAccountId` == HMAC(`RPG_PLAY_ACCOUNT_KEY`, owner) (chave ≥32, fail-closed); token e `order_id` UNIQUE + advisory lock; crédito e linha na mesma transação, consume só depois; consume envenenado com teto de tentativas. FAKE: só com `RPG_GOOGLE_PLAY_FAKE=1` + perfil `local` + sem `VERCEL`; flag em hosted → 503. `X-RPG-Client` é só política de UX (comentário e código honestos), não fronteira.
- **Wallet** (`infrastructure/wallet.py`, migration 20261008170000): CHECKs `available/reserved >= 0`, `settled+released <= ceiling`; triggers de imutabilidade em entries/tickets/settled_usage; constraint triggers de reconciliação conta×ledger; `FOR UPDATE` no account em toda mutação (sem TOCTOU em reserva); reserva idempotente com replay estrito; `admit_attempt` emite ticket antes da rede e limita soma ao teto; settle exige usage do owner/operation casando com tickets, teto da reserva, replays divergentes rejeitados; recover só libera pré-dispatch; sem overdraft em refund/ajuste. Dinheiro em `Decimal`/inteiros `shard_milli` (nenhum `float` em crédito/débito).
- **Dívida/hold**: `owner_debt` checado em `reserve` e trigger `guard_financial_hold` em reservations/tickets (cobre turno-com-reserva, STT e imagem); compra nova liquida dívida primeiro.
- **Quote de imagem** (`services/image_quotes.py`): quote filtrado por `owner_id`+`game_id`, imutável por trigger, expira em ≤5 min e amarra `timeline_epoch`; `confirmed` é `Literal[True]` com validador; `confirm` trava o quote `FOR UPDATE` e é idempotente; `dispatch` revalida hash do prompt, rate card e fence do job; excesso vira anomalia, débito limitado ao teto.
- **Leitura de conta**: `GET /account/balance|purchases|usage|series` via `PostgresAccountReader` com `current_principal()`; funções definer `rpg_wallet_balance/history` usam `auth.uid()` + sessão ativa, `search_path=''`, revoke de public/anon/rpg_api.
- **Cron interno** (`services/cron_internal.py`): `hmac.compare_digest`, segredo vazio/<32 chars → 503 (fail-closed), respostas só com contagens, orçamento limitado a `MAX_DURATION-5`, 500 em falha; tarefas idempotentes (SKIP LOCKED).
- **Kill switches/admin**: sem endpoint HTTP para alterar switch ou ajustar carteira (só scripts CLI); `app.set_kill_switch` é `security definer`, revogado para clientes, grava estado+auditoria imutável na mesma transação; `admin_wallet_adjust.py` exige `--actor` UUID, `--reason`, `--reference`, dry-run por padrão e `--confirm-owner`.
- **SKU/preço**: `quote_published_sku` lê preço/versão do SQL; cliente só informa `sku_id`; SKU de canal errado rejeitado em `credit_verified_purchase`.
- **Reconciliação**: eventos por `(provider, event_id)` únicos e append-only, transições imutáveis, reembolso parcial mantém compra paga, dispute won libera por lançamentos compensatórios, "created" tardio não reabre disputa vencida.
