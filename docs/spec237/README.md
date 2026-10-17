# SPEC-237 — Evidência: rate card de embeddings (Jina)

Status: `in-progress` (código, testes offline e revisão Sol prontos; falta reativar o cap de texto no staging).

## O que mudou
- `data/pricing/embedding_rate_card_2026-10-17.json` + `services/embedding_pricing.py`: card novo e versionado
  (`embedding-2026-10-17-v1-<sha16>`), `jina:jina-embeddings-v3` a US$ 0,05/1M tokens de entrada [F, verificado online em 2026-10-17 pela revisão Sol; o
  0,02 do repo era o preço anterior a 2025-05-06].
- `services/usage_metering.py`: embedding com só `input_tokens` e modelo no card = `token_priced`; `units_estimated`
  vira `estimated` (ainda por card). Demais casos seguem no piso de US$ 1 (fail-safe).
- `rag.py`: sem bloco `usage` na resposta Jina, estima `ceil(chars/2)` tokens e marca `units_estimated=1`.
- Revisão Sol: `shard_pricing.quote_usage` aceita o card de embedding (antes recusaria evento exato de Jina);
  corpo Jina não-JSON (`invalid_response`) também é estimado em vez do piso de US$ 1.
- O card pinado `rate_card_2026-10-08.json` NÃO foi alterado (sha conferido por teste). Sem migration/SCHEMA_VERSION.

## Testes
`tests/test_spec237_embedding_pricing.py` (13) + ajustes em `tests/test_usage_metering.py` e `tests/test_api_attempt_telemetry.py` (Jina agora por token, não US$ 1).

## Fora de escopo
Cascata de `usage_events` na exclusão de campanha: [R] spec própria (cascata também via `operation_id`; apagamento
de conta é por desenho).

## Pendente
Redeploy staging e `RPG_DAILY_SPEND_CAP_TEXT=1` com ≥30 turnos.
Suite: exit 0; ruff limpo.
