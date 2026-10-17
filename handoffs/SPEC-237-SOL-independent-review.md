# SPEC-237 — Revisão independente Sol (Opus, contexto separado)

**Veredito:** APPROVED_WITH_FIXES (2 defeitos + preço corrigidos nesta revisão). Status da spec segue
`in-progress`: falta o passo remoto (redeploy staging, `RPG_DAILY_SPEND_CAP_TEXT=1`, ≥30 turnos).

## Preço (tarefa 1)
- Consulta web 2026-10-17: a Jina adotou novo modelo de preços em 2025-05-06 (https://jina.ai/api-dashboard/pricing/);
  pacotes Standard US$ 50/1B (US$ 0,05/1M) e Premium US$ 500/11B (US$ 0,045/1M) segundo
  https://usagepricing.com/blueprint/jina-ai (observado 2026-08-27). `jina.ai/pricing` dá 404; a página oficial não
  mostra valores sem login. Agregadores divergem (0,018–0,05); 0,02 é o preço antigo.
- **Correção:** card passou de `0.02` para `0.05` (maior tarifa paga = conservador). Arquivo ainda não publicado,
  então a versão `embedding-2026-10-17-v1` foi mantida; o sha16 da `EMBEDDING_PRICING_VERSION` mudou junto.
  `.env.example` atualizado. Spec registra a fonte como [F].

## Ataque (tarefa 2)
- **Pinning/sha:** `EMBEDDING_PRICING_VERSION = versão + sha256[:16]` (mesmo padrão de speech/image), ≤80 chars
  (constraint `usage_events.pricing_version`). Card de texto `rate_card_2026-10-08.json` byte-idêntico
  (teste compara com `INSTALLED_RATE_CARD_SHA256`). OK.
- **DEFEITO 1 — `shard_pricing.quote_usage` (SPEC-183/184):** recusava todo `token_priced` cuja versão ≠
  `rate_card_version` do texto → um evento Jina exato numa liquidação de wallet levantaria
  `PricingUnavailable("rate card de usage diverge")`. Hoje turnos não liquidam wallet (SPEC-185 pendente), então
  era latente e fail-closed, mas contradiz "card honrado onde se soma custo". Corrigido: aceita `token_priced` só se
  `category=="embedding"` **e** versão == `EMBEDDING_PRICING_VERSION`; mesma versão em outra categoria segue recusada.
- **DEFEITO 2 — `rag._JinaEmbeddingsHTTPX`:** corpo não-JSON (`invalid_response`, provider respondeu e pode ter
  cobrado) saía sem usage → piso de US$ 1 → mesmo bug de cap do staging, em menor frequência. Corrigido com a
  mesma estimativa `ceil(chars/2)` marcada `units_estimated`.
- **Somatórios (196/236/185):** cap diário (`daily_spend_cap`), FinOps (`finops_reader`/`finops_job`,
  `COST_GROUPS["embedding"]`) e dashboard da conta (`account_read_model`) leem `cost_usd`/`counts_as_spend`
  persistidos — honram o novo custo sem mudança. `finops_alerts.unknown_pricing` só olha
  `unknown-conservative-v1` → Jina deixa de disparar o alerta bloqueante (desejado).
- **Frescor:** `installed_freshness`/`require_paid_effect` só conhecem llm/image/speech; o card de embedding não é
  avaliado (nem como ausente nem como velho). Não bloqueia nada. Follow-up [R]: incluir "embedding" no frescor
  numa spec de FinOps (fora de escopo declarado na spec).
- **Estimativa chars/2:** PT-BR ≈ 3–4 chars/token no tokenizer XLM-R da v3 → superestima ~1,5–2× (conservador).
  Para textos de 1–2 chars subestima tokens especiais, valor irrelevante (<1e-7 USD).
- **Dupla contagem:** um evento por POST HTTP; retry transitório emite `http_error` (sem usage →
  `failed_no_usage`, custo 0) e o sucesso emite um único `response`. `_ScopedMeteredEmbeddings` pula jina. OK.
- **Falhas zero:** `http_error`/`transport_error` sem usage → `failed_no_usage`, fora do gasto (teste existente).
- **Testes antigos alterados:** `test_usage_metering` ainda verifica `input_units` e `estimated` para os demais;
  `test_api_attempt_telemetry` recalculado (0,000345 LLM + 17×0,05e-6 = 0,000345850). Nenhuma regressão escondida.
- Outros providers de embedding (openai/ollama/gemini) seguem no piso US$ 1 por desenho (R4).

## Verificação
- `tests/test_spec237_embedding_pricing.py`: 13 (3 novos da revisão, vistos falhar antes da correção).
- Focados (spec237, shard_pricing, usage_metering, api_attempt_telemetry, wallet_spend_guard): verdes.
- Suíte completa `pytest -q -p no:warnings --ignore=tests/test_project_index.py`: exit 0. Ruff limpo.
- Nenhuma ação remota além da consulta web.
