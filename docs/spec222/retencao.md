# Retenção de dados — gerado de `infrastructure/account_lifecycle.py` e `services/retention.py`

> Não editar à mão: `uv run python scripts/gen_retention_doc.py`. Teste:
> `tests/test_spec222_transparency.py`. É a fonte da seção 5 da política de privacidade.

## Apagado na exclusão de conta

`game_checkpoints`, `game_events`, `turns`, `art_generations`, `assets`, `chronicle_digests`, `memory_documents`, `runtime_catalog`, `usage_events`, `operations`, `jobs`, `games`, `image_quotes`.

## Retido após a exclusão (motivo legal e prazo)

| Tabela | Motivo e prazo |
|---|---|
| `wallet_accounts` | obrigação contábil/fiscal e defesa em disputa (extrato por identificador opaco, sem conteúdo de jogo) — 5 anos após a transação |
| `wallet_entries` | obrigação contábil/fiscal e defesa em disputa (extrato por identificador opaco, sem conteúdo de jogo) — 5 anos após a transação |
| `wallet_reservations` | obrigação contábil/fiscal e defesa em disputa (extrato por identificador opaco, sem conteúdo de jogo) — 5 anos após a transação |
| `wallet_attempt_tickets` | obrigação contábil/fiscal e defesa em disputa (extrato por identificador opaco, sem conteúdo de jogo) — 5 anos após a transação |
| `wallet_settled_usage` | obrigação contábil/fiscal e defesa em disputa (extrato por identificador opaco, sem conteúdo de jogo) — 5 anos após a transação |
| `payment_orders` | obrigação contábil/fiscal e defesa em disputa (extrato por identificador opaco, sem conteúdo de jogo) — 5 anos após a transação |
| `wallet_debt_entries` | obrigação contábil/fiscal e defesa em disputa (extrato por identificador opaco, sem conteúdo de jogo) — 5 anos após a transação |
| `purchase_reconciliation_state` | obrigação contábil/fiscal e defesa em disputa (extrato por identificador opaco, sem conteúdo de jogo) — 5 anos após a transação |
| `google_play_purchases` | obrigação fiscal e antifraude da compra Google Play; purchase_token anulado após consumo/exclusão, google_state minimizado — 5 anos |
| `account_deletions` | prova da exclusão (tombstone reduzido a owner_id e data após 30 dias) — 5 anos, prazo prescricional |

## TTL de metadados técnicos (cron `/internal/cron/operations`)

| Tabela | Prazo |
|---|---|
| `operations` | 90 dias após a conclusão (recibos de idempotência) |
| `jobs` | 30 dias após estado terminal |
| `usage_events` | 13 meses (prazo fiscal/contábil do consumo) |
| `finops_evaluations` | 180 dias |
| `account_deletions` | reduzida a owner_id e data após 30 dias; apagada após 5 anos |
