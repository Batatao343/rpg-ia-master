# SPEC-237 — Rate card de embeddings (Jina): preço por token em vez do piso de US$ 1

> **Status:** `done` — aprovada pelo dono em 2026-10-17 ("Sim, spec + execução"); código, testes offline e revisão Sol entregues; staging 17/10: redeploy (`3250cdb`) com `RPG_DAILY_SPEND_CAP_TEXT=1`, 32 turnos DeepSeek sem 503, embeddings Jina `token_priced` com `embedding-2026-10-17-v1-8e04a9bb33e8be9b` (`docs/staging-wave-2026-10-17/evidence/spec237_text_cap_32_turns.json`).
> **Criada:** 2026-10-17 · **Atualizada:** 2026-10-17
> **Depende de:** SPEC-182 `done` (metering), SPEC-183/196 `done` (rate card pinado), SPEC-236 `in-progress` (cap diário, `counts_as_spend`)
> **Desbloqueia:** reativar `RPG_DAILY_SPEND_CAP_TEXT=1` no staging; gate de custos da SPEC-197
> **Origem:** staging wave 2026-10-17 (`docs/staging-wave-2026-10-17/README.md`, achado 3)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` — cobertura por testes unitários; sem dataset protegido

---

## 1. Contexto & Objetivo

- [F] `services/usage_metering.normalize_attempts` só precifica pelo rate card quando há `input_tokens` **e**
  `output_tokens` (`card and inputs is not None and outputs is not None`). Embedding reporta apenas tokens de
  entrada (`rag._emit_embedding_attempt` mapeia `total_tokens`/`prompt_tokens` → `input_tokens`), então cai no
  ramo `else`: `max(_UNKNOWN_MIN_USD=1.00, ...)`, `cost_basis="estimated"`, `pricing_version="unknown-conservative-v1"`.
- [F] `data/pricing/rate_card_2026-10-08.json` não tem nenhum modelo Jina (só groq/deepseek). Esse arquivo é
  pinado por sha em `services/shard_pricing.INSTALLED_RATE_CARD_SHA256` (e gravado em `app.pricing_versions`,
  imutável por trigger) — **não pode ser alterado no lugar**.
- [F] Efeito no staging: cada tentativa de embedding conta US$ 1 como gasto (`counts_as_spend=true`). Com
  `RPG_DAILY_SPEND_CAP_TEXT=1` (`services/daily_spend_cap.text_cap_exceeded`, chamado por
  `api._enforce_owner_budget`) todo turno passou a 503 `daily_spend_cap` após ~17 turnos; o cap de texto foi
  desligado no staging (`scripts/staging/vercel_env.py`).
- [F] Cadeia de embeddings (`rag.EMBEDDING_ROUTES`): jina (`jina-embeddings-v3`) → openai
  (`text-embedding-3-small`) → ollama → gemini. Chamadas medidas em `api.py` (`_embedding_telemetry_hook`,
  `category="embedding"`) e `workers/run_worker.py` (jobs `embed_memory`, `infrastructure/usage_events.py`).
- [F] Cliente Jina (`rag._JinaEmbeddingsHTTPX`) lê `payload["usage"]`; se a API omitir o bloco, o evento sai
  sem tokens -> piso de US$ 1.
- [F] Preço (revisão Sol, consulta web em 2026-10-17): desde o modelo de preços de **2025-05-06**
  (confirmado em https://jina.ai/api-dashboard/pricing/) a Jina vende pacotes de tokens: Standard
  **US$ 50 / 1B tokens = US$ 0,05/1M**, Premium US$ 500 / 11B = US$ 0,045/1M (valores em
  https://usagepricing.com/blueprint/jina-ai, observados em 2026-08-27; a página oficial não expõe os
  valores sem login). O US$ 0,02/1M do `.env.example`/`CHANGELOG.md` (pesquisa de 2026-07-16) é o
  preço antigo. O card usa **US$ 0,05/1M** (maior tarifa paga, conservador); os 10M tokens grátis
  não são modelados.

**Objetivo:** precificar embeddings Jina por token via um **novo rate card versionado e separado**, mantendo
o fail-safe de US$ 1 para qualquer modelo/provider sem preço, sem tocar o card pinado.

## 2. Requisitos

- **R1** — Existe `data/pricing/embedding_rate_card_2026-10-17.json` (versão `embedding-2026-10-17-v1`) com
  `jina:jina-embeddings-v3` a `0.05` USD/1M tokens de entrada. O card `rate_card_2026-10-08.json` permanece
  byte-idêntico (teste compara sha com `INSTALLED_RATE_CARD_SHA256` e proíbe "jina" nele).
- **R2** — Evento `category="embedding"` com `input_tokens` e sem `output_tokens` para modelo no card é
  precificado por `ceil(tokens × 0,05 / 1e6)` (9 casas), `cost_basis="token_priced"`, `billing_exact=true`,
  `pricing_version=EMBEDDING_PRICING_VERSION` (`<versão>-<sha256[:16]>`, ≤80 chars).
- **R3** — Quando a API Jina não devolve `usage`, o cliente estima `ceil(caracteres/2)` tokens (conservador:
  texto PT-BR ≈ 3–4 chars/token), marca `units_estimated=1`; o evento sai `cost_basis="estimated"`,
  `billing_exact=false`, ainda precificado pelo card (centavos, não US$ 1). Nenhum texto entra no evento.
- **R4** — Modelo/provider sem preço (ex.: `gemini`, `openai`, `ollama` de embedding) e qualquer categoria
  diferente de `embedding` mantêm o comportamento anterior: US$ 1 mínimo, `unknown-conservative-v1`.
- **R5** — Falha sem usage (`http_error`/`transport_error`) continua `failed_no_usage` (custo 0, fora do gasto).
- **R6** — 40 turnos offline simulados (3 embeddings × 3000 tokens) somam < US$ 0,05 (≈ US$ 0,018), bem abaixo de um cap de
  texto de R$ 5 (≈ US$ 0,9).
- **R7** — Sem mudança de schema SQL, de `SCHEMA_VERSION` ou de save.

### Fora de escopo

- [R] **Cascata de `usage_events` ao excluir campanha** (achado 5 da onda): NÃO incluído. `usage_events` também
  tem `operation_id ... on delete cascade` (e as operações caem junto com o jogo), e a exclusão de conta é
  apagamento de dados por desenho (SPEC-190/222). `on delete set null` em `game_id` não bastaria e exigiria
  rever apagamento/retenção e o trigger `validate_usage_attribution`. Spec própria, com decisão do dono sobre
  retenção do fato de gasto.
- Preços de OpenAI/Gemini/Ollama de embedding (não são o primário; seguem fail-safe).
- Freshness/expiração do card de embedding (`require_*_prices` como na STT) — [R] avaliar em spec de FinOps.
- Reativar o cap de texto no staging (passo operacional após revisão).

## 3. Design técnico

- **Novo** `data/pricing/embedding_rate_card_2026-10-17.json` — card de preço por token de entrada.
- **Novo** `services/embedding_pricing.py` — carrega o card, `EMBEDDING_PRICING_VERSION` (versão + sha16, como
  `speech_pricing`), `embedding_cost(provider, model, input_tokens) -> Decimal | None` (None = fora do card).
- **Alterado** `services/usage_metering.py` — `safe_provider_usage` passa a aceitar `units_estimated`; novo
  ramo em `normalize_attempts` (antes do ramo do card de texto): `category=="embedding"`, `inputs` presente,
  `outputs` ausente, modelo no card.
- **Alterado** `rag.py` — `_has_token_usage` + `_estimated_embedding_usage` em `_JinaEmbeddingsHTTPX._embed` quando falta `usage` (inclusive corpo inválido `invalid_response`, revisão Sol).
- **Alterado (revisão Sol)** `services/shard_pricing.quote_usage` — aceita `token_priced` de `category="embedding"` com `EMBEDDING_PRICING_VERSION` (antes rejeitaria como "rate card diverge"); a versão do card de embedding fora da categoria embedding continua recusada.
- **Alterado** `tests/test_usage_metering.py` — o caso de normalizador compartilhado assumia Jina "estimated";
  agora espera `token_priced` (mudança intencional).
- Sem migration: `cost_basis` (`token_priced`/`estimated`) e `pricing_version` já são aceitos pelas constraints
  de `app.usage_events`. Eventos antigos (US$ 1) permanecem; o cap diário é por dia, então se corrige em ≤24 h.
- Degradação: card ausente/corrompido falha no import (como os outros cards) — coberto pelos testes.

## 4. Plano passo a passo

1. **Testes** `tests/test_spec237_embedding_pricing.py` (falham antes): preço por token, fração de centavo,
   estimado, modelo desconhecido, outra categoria, falha sem usage, card pinado intacto, estimativa no cliente
   Jina, 40 turnos < teto.
2. **Implementação** conforme seção 3. 3. **Verificação:** focados + suíte completa + ruff.

## 5. Critérios de aceite

- [x] R1–R7 cobertos por testes verdes (`tests/test_spec237_embedding_pricing.py`, 10 testes)
- [x] Card de texto pinado intacto (teste de sha)
- [x] Modelo desconhecido continua fail-safe (US$ 1)
- [x] Suíte completa offline verde e ruff limpo (ver `docs/spec237/README.md`)
- [x] Revisão independente `Sol` (`handoffs/SPEC-237-SOL-independent-review.md`; 2 defeitos corrigidos)
- [x] Preço verificado online pela revisão Sol: US$ 0,05/1M (não 0,02) — card corrigido antes do commit
- [x] Staging: redeploy + reativar `RPG_DAILY_SPEND_CAP_TEXT=1` e rodar ≥30 turnos sem 503. **17/10:** deploy `6wy6q129o` (`git_sha 3250cdb`, `hardened=true`), `vercel_env.py` liga o cap de texto por padrão (`--no-text-cap` = rollback); 32/32 turnos 200, 0 × 503 `daily_spend_cap`; 56 embeddings Jina `token_priced` somando US$ 0,000098 (antes seriam 56 × US$ 1); 2 turnos extras confirmam `billing_exact=true`, `pricing_version=embedding-2026-10-17-v1-8e04a9bb33e8be9b`, 0 linhas `unknown-conservative` em 2 h. Dados sintéticos apagados.

## 6. Smoke

Offline: os testes acima. Staging (opt-in, após deploy): 30+ turnos com cap de texto ligado; conferir
`app.usage_events` de embedding com `pricing_version` `embedding-2026-10-17-v1-…` e custo ≈ 1e-5 USD.
Nenhuma chamada a provider real nesta execução.

## 7. Riscos & compatibilidade

- Preço errado → subestima/superestima gasto: mitigado por [H] sinalizada e fonte registrada no card.
- Estimativa 2 chars/token superestima ~1,5–2× (seguro para teto).
- Saves/schema: nenhum impacto. Linhas históricas a US$ 1 inflam o dia corrente até meia-noite do cap.
- Modelos de embedding adicionais exigem novo card versionado (nunca editar este no lugar).

## 8. Pontos de decisão do dono

- **D1** — Preço Jina. Resolvido na revisão Sol: US$ 0,05/1M (tarifa Standard vigente; ver seção 1 [F]).
- **D2** — Tratar a cascata de `usage_events` na exclusão de campanha em spec própria. Default: sim, fora desta.

## 9. Evidência requerida

Testes focados e suíte completa (exit 0), ruff, `docs/spec237/README.md`, parecer da revisão `Sol`, e a
evidência de ≥30 turnos no staging com o cap de texto ligado.
