# SPEC-195: reconciliacao cross-channel, refunds, disputas e revogacoes

Status: implementado; correcoes da revisao adversarial (H1/H2/M1-M3/L1-L6) aplicadas e cobertas
por testes Postgres (`tests/test_spec195_postgres_local.py`) e MemoryStore (paridade).
Politica e vetores dourados: [refund-debt-policy.md](refund-debt-policy.md).

## Arquitetura
- `services/purchase_reconciliation.py` (puro): eventos normalizados, `fold`, `target_milli`,
  `plan_adjustment`, tabelas de transicao fechadas, normalizadores Stripe/Google.
- `infrastructure/reconciliation.py`: `Reconciler.reconcile_batch(max_items)`, `MemoryStore`
  (referencia de testes) e `PostgresStore` (mesmo plano puro sob lock advisory + lock da conta).
- `infrastructure/wallet_debt.py`: divida (hold) append-only, `settle_owner_debt`, `forgive_debt`.
- `infrastructure/wallet.py`: `reserve` levanta `FinancialHold` com divida > 0; credito de compra
  quita divida primeiro.
- Migracao `20261015140000_purchase_reconciliation.sql`: novos tipos de entrada
  (`clawback`, `claw_release`, `debt_settlement`), `purchase_reconciliation_events`
  (unique provider+event id), `purchase_reconciliation_state`, `wallet_debt_entries`,
  `purchase_fee_records`, triggers de hold em reservations/tickets. RLS forcada, sem grants.

## Maquinas de estado
```
Stripe:  created -> paid -> refunded_partial -> refunded_full (terminal)
                      \-> disputed -> dispute_won | dispute_lost | refunded_*
                      (dispute_won/lost podem voltar a disputed por nova disputa)
Google:  pending -> purchased -> fulfilled -> consumed
                         \_________\___________\-> voided | revoked (terminais)
```
O estado e DERIVADO do conjunto de eventos (maximo cumulativo de refund; status terminal de
disputa vence "open"), entao ordem/duplicatas nao mudam o resultado; transicao fora da tabela
falha o item (conta como `failed`, nunca grava).

## Mapa de eventos
| Origem | Evento | Normalizado |
|---|---|---|
| Stripe | `charge.refunded` (amount_refunded cumulativo) | `refund` |
| Stripe | `charge.dispute.created` (inquiry `warning_*` ignorada) | `dispute_open` |
| Stripe | `charge.dispute.closed` won/warning_closed / lost | `dispute_won` / `dispute_lost` |
| Stripe | `fee_reconciled` (payment_financial_events) | `fee_reconciled` -> `purchase_fee_records` |
| Google | Voided Purchases API `voidedpurchases.list` (`orderId`, `voidedTimeMillis`, `voidedReason`) | `voided`; `voidedReason` 5 Fraud / 6 Friendly_fraud / 7 Chargeback -> `revoked`; 8 Unacknowledged_purchase e demais -> `voided` |

Google: `GET .../purchases/voidedpurchases`, `startTime` ate 30 dias no passado, `type=0`,
paginacao `maxResults`/`token` (nomes de wire; a referencia REST os lista como `pageSelection.*`). O poll roda no cron; id do evento = `void:{order}:{voidedTime}`.
`StripePayments.accept_event` apenas registra o fato e dispara um passe imediato best-effort; o
efeito na carteira so ocorre no reconciliador (nunca ha dois caminhos).

## Cron
`POST /internal/cron/reconciliation` (Bearer `RPG_CRON_SECRET`): poll Google + ingest do backlog
Stripe + `reconcile_batch` (tambem chama `GooglePlayPurchases.retry_unconsumed`). Agendar
a cada 5-15 min junto aos demais crons (vercel.json/pg_cron: fora deste escopo).
Resposta: `ingested, applied, parked, orphaned, failed, unconsumed_retried, parked_total,
orphaned_total, google_voided_new`. Gauge `rpg_reconciliation_events{status=parked|orphaned}`.

## Runbook
- Eventos `parked` = compra ainda nao creditada; retentativa com backoff (5 min dobrando ate 6 h) e
  passam a `orphaned` apos 8 tentativas/14 dias (nao entram mais no lote; contados em
  `orphaned_total` e no gauge). Inspecionar: `select * from app.purchase_reconciliation_events
  where status='orphaned'`. Um `orphaned` indica refund de PaymentIntent estrangeiro **ou** compra creditada so depois de esgotadas as
  tentativas: se a compra aparecer depois, o proximo lote a reconcilia (`open_refs` inclui `orphaned` cuja
  compra ja existe) e o fulfill do Google dispara um passe imediato best-effort. Alerta `ReconciliationOrphaned`
  (`orphaned_total > 0` por 1 h) pede triagem manual do que continuar orfao.
- Historico de estados por compra: `app.purchase_reconciliation_transitions` (append-only).
- Conta com divida (hold): `select sum(debt_delta) from app.wallet_debt_entries where owner_id=...`.
  Resolve sozinha ao comprar de novo; ou perdoar pela CLI.
- Ajuste admin (dry-run por padrao):
  `uv run python scripts/admin_wallet_adjust.py forgive-debt --owner U --amount-milli N --actor A --reason R --reference INC-1`
  e repetir com `--apply --confirm-owner U`. `--reference` nao aceita `% _ * \`. Replays com
  razao/valor diferente voltam `replay_divergent: true`. `credit` + quitacao rodam em UMA transacao.
- Disputa ganha apos divida paga por compra nova: o credito e devolvido (V8). Divida perdoada
  depois liberada por disputa ganha NAO vira credito (V14).
- O hold do banco (trigger, SQLSTATE 42501) e mapeado para `FinancialHold` (409-class), nunca 500.

## Limitacoes conhecidas
- L1: `charge.refund.updated` (refund `failed`/`canceled`, que reduziria o `amount_refunded`) NAO e
  consumido: o reconciliador usa o maximo cumulativo (monotonico), entao um refund revertido pelo
  banco mantem a claim ate intervencao manual (`credit` admin com `--reference` do incidente).
- Orfaos so se recuperam quando a compra passa a existir (ver Runbook); void de order realmente nunca creditada
  permanece `orphaned` ate triagem manual.
- Poll de voids Google: `maxResults=1000` e watermark persistido (`purchase_reconciliation_cursors`, avanca para
  inicio do poll - 1 h de sobreposicao; poll truncado por `max_pages` NAO avanca), entao >500 voids/30 dias nao se perdem.

## Pendencias
- Cron schedule em infraestrutura.
