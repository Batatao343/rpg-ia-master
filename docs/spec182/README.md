# SPEC-182 — metering por tentativa

## Contrato entregue

- `LLMAttemptEvent` transporta somente contadores e custo informado pelo provider. Uma resposta estruturada mantém o `raw` apenas até a captura dos contadores; um stream emite um evento final por tentativa.
- `normalize_attempts` cria uma identidade UUID5 para `operation_id + component + ordinal`. Tentativas que não chegaram à rede ficam fora do ledger. Respostas inválidas, fallbacks e falhas após envio entram com usage conhecido ou estimativa conservadora marcada.
- `app.usage_events` é append-only para `rpg_api`: `SELECT` e `INSERT` com RLS por owner, sem `UPDATE`/`DELETE`. O writer compara o hash em replay e rejeita fatos divergentes. Exclusão de conta/jogo mantém cascata de privacidade.
- O commit do turno grava ledger, `app.turns.llm_cost_usd` e recibo na mesma transação. Arte dinâmica usa a operação `art` da geração e grava usage com a promoção do asset. `usage_json` da arte recebe somente contadores permitidos.
- `cost_basis` e `pricing_version` acompanham cada evento. `exact_billable_cost` retorna `None` se algum evento é estimado. `reserve_next_attempt` retorna limite pelo rate card, ou `None` para modelo desconhecido. Wallet e cobrança continuam fora desta spec.

## Fonte dos preços e semântica

O [rate card versionado](../../data/pricing/rate_card_2026-10-08.json) usa [Groq models](https://console.groq.com/docs/models) e [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/), consultados em 2026-10-08. Groq gpt-oss 20b/120b é `token_priced`; DeepSeek Flash usa o maior preço publicado, marcado `estimated`, pois a tarifa varia por horário. Um custo retornado pelo provider tem precedência e `cost_basis=provider_reported`.

Modelo/uso sem preço suficiente gera reserva `unknown-conservative-v1`, no mínimo US$ 1 por tentativa, `billing_exact=false`. É uma reserva para impedir cobrança subestimada; não é fatura do provider. O custo consolidado do turno inclui essa estimativa e o ledger permite distingui-la. O preço antigo de `playtest/pricing.py` permanece no playtest como estimativa, sem alimentar o turno durável.

## Comparação determinística, sem long-run

Fixture: primeira tentativa Groq 20b retorna structured inválido (1.000 input, 100 output, 200 cache); fallback Groq 120b responde (800 input, 200 output). A heurística anterior considera somente o sucesso e assume 1.200/400 tokens: **US$ 0,000420**. O normalizador registra **dois** eventos: US$ 0,000097400 + US$ 0,000240000 = **US$ 0,000337400**. Esta diferença é ilustrativa, pois os tokens da fixture são sintéticos.

## Abrangência e limites

- Jev continua `off` em produção pela SPEC-180. `decision_attempt` aceita a telemetria tipada caso seja promovido; não há escrita de decisão live nesta spec.
- Arte dinâmica escreve no ledger. O endpoint de imagem pode não fornecer uso/custo para o modelo atual; nesse caso o registro é estimado e nunca elegível a cobrança exata.
- Embeddings via LangChain hoje retornam vetor sem metadata de usage para os callsites de RAG. O normalizador aceita `category=embedding` e contadores quando o provider os disponibilizar; os callsites sem metadata não inventam tokens.
- STT é a SPEC-186; `category=speech_to_text` e `audio_units` já têm contrato e fixture, sem chamadas de áudio nesta spec.
- O rate card não é atualização automática nem garante preço futuro. Não houve chamadas live nesta implementação até definição de orçamento específico.

## Verificação

Corpus offline: `tests/test_usage_metering.py`, `tests/test_usage_capture.py`, `tests/test_api_attempt_telemetry.py` e regressões de streaming/roteamento. Integração Postgres local: `tests/test_postgres_jobs_local.py` e `tests/test_dynamic_art_local.py` com `RPG_TEST_DATABASE_URL`; inclui replay, atribuição, RLS e custo consolidado. A migration foi criada pela Supabase CLI, validada com rollback e aplicada somente ao Postgres local.

Gate pendente: 3–5 chamadas reais curtas para conferir metadata DeepSeek/Groq, somente após aprovação de teto de chamadas e custo. Nenhum long-run é necessário.
