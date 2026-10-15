# SPEC-195 - Politica de refund/dispute/revocation e divida (policy gate)

Status: `approved` (2026-10-15, autorizacao em bloco do usuario para SPEC-191..198; registrada no
contexto de `docs/planos/equivalencia-modelos-claude.md`). Escrita ANTES do codigo; os vetores
abaixo sao reproduzidos 1:1 em `tests/test_spec195_reconciliation.py`.

## Regras

1. `available` nunca fica negativo (CHECK ja existente em `wallet_accounts`).
2. Refund/dispute/revocation de uma compra de `S` milli-estilhas gera uma *claim* alvo
   `target = floor(S * reversed_cents / gross_cents)` (voided/revoked Google: `S`).
   `reversed_cents = min(gross, refunded_cents_max + sum(disputas abertas ou perdidas))`.
   O alvo e funcao do CONJUNTO de eventos (maximo cumulativo, status terminal vence), nunca da
   ordem de chegada -> reordenar/duplicar eventos produz o mesmo estado final.
3. Aplicar a diferenca `delta = target - applied`:
   - `delta > 0`: `clawback = min(available, delta)` (entrada `clawback`, `available -= clawback`);
     o resto `delta - clawback` vira **divida** (`wallet_debt_entries` kind `open`).
   - `delta < 0` (disputa ganha / estorno do estorno): libera-se `-delta`: primeiro quita a divida
     em aberto DESTA compra (`release`); o restante volta como credito (`claw_release`) mas SO ate
     o que foi realmente retirado da carteira (clawback + divida quitada via `debt_settlement`);
     a parte que o admin perdoou apenas fecha o perdao (`forgive_close`, `debt_delta = 0`).
4. Divida > 0 = *financial hold*: nenhuma NOVA reserva/ticket pago (`FinancialHold`; trigger no
   banco). Leitura gratis de campanhas continua. Reservas ja abertas seguem reconciliaveis
   (settle/release).
5. Compra nova (ou qualquer credito) quita divida primeiro: apos o credito, `debt_settlement`
   debita `min(divida, available)` e grava `settle` FIFO (compra mais antiga primeiro, desempate
   por chave) na divida. A quitacao NAO depende de liberar reservas: ela paga so de `available`
   (reservas abertas nao sao tocadas). Quando uma reserva e encerrada e devolve credito
   (`release`), a quitacao tambem roda nesse momento, para o hold nao sobreviver a saldo livre.
6. Historico nunca e reescrito: tudo e entrada compensatoria append-only.
7. Ajuste admin (perdoar divida / credito / debito) so via `scripts/admin_wallet_adjust.py`
   (CLI, dry-run por padrao, `--apply` explicito), com `actor_id`, `reason` e `reference`
   obrigatorios, auditado em `wallet_entries`/`wallet_debt_entries`. Nao existe endpoint publico.
8. Eventos de provider sao deduplicados por `(provider, provider_event_id)`; evento cuja compra
   ainda nao foi creditada fica `parked`, com retentativa exponencial (5 min ate 6 h) e estado
   terminal `orphaned` apos 8 tentativas ou 14 dias; so linhas devidas entram no lote. Eventos
   Stripe sem efeito financeiro recebem marcador em `purchase_reconciliation_skips`.
9. Taxa real (`fee_reconciled`) vai para `purchase_fee_records` (registro separado); a compra
   original e o ledger nao sao reescritos.

## Vetores dourados (S=5000 milli, gross=500 cents, salvo indicacao)

| # | Cenario | Resultado esperado |
|---|---|---|
| V1 | compra; sem gasto; refund total (500c) | clawback 5000; available 0; divida 0 |
| V2 | compra; gasta 3000; refund total | clawback 2000; divida 3000; available 0; reserva bloqueada |
| V3 | V2 + nova compra 5000 | credito 5000, debt_settlement 3000; available 2000; divida 0 |
| V4 | compra; refund parcial 200c; depois total 500c | claw 2000 (avail 3000); depois claw +3000 (avail 0) |
| V5 | compra; gasta 4500; refund parcial 200c | claw 500; divida 1500; available 0 |
| V6 | compra; gasta 3000; disputa aberta 500c; disputa ganha | abre: claw 2000 + divida 3000; ganha: release 3000 divida + claw_release 2000; avail 2000; divida 0 |
| V7 | compra; gasta 3000; disputa aberta; disputa perdida | claw 2000 + divida 3000 permanecem |
| V8 | V6 intermedio (divida 3000) + compra 5000 (quita 3000) + disputa ganha | release 0 de divida (ja quitada), claw_release 5000; available 7000; divida 0 |
| V9 | mesmo event_id duas vezes | segunda e no-op; estado identico |
| V10 | refund chega antes da compra ser creditada | evento `parked`; apos credito, reconcile aplica V1 |
| V11 | Google: compra consumida, gasta 5000, voided | divida 5000; available 0; reserva bloqueada |
| V12 | refund 500c depois refund 200c (fora de ordem, cumulativo) | max = 500c -> claim 5000 uma vez |
| V13 | fee_reconciled 30c duas vezes mesmo event | 1 registro de taxa; ledger intacto |
| V14 | V6 intermedio (claw 2000 + divida 3000), admin perdoa 3000, depois disputa ganha | release 0 de divida; `claw_release` so 2000 (o que foi realmente retirado); os 3000 perdoados so FECHAM o perdao (`forgive_close`, sem dinheiro); available 2000; divida 0 |
| V15 | compra 5000, gasta 3000; refund 200c + disputa 300c aberta (claw 2000 + divida 3000); admin perdoa 3000; disputa ganha (alvo 5000 -> 2000) | volta o dinheiro realmente retirado (`claw_release` 2000) ANTES de fechar o perdao (`forgive_close` 1000); available 2000; divida 0. Em reversao parcial o dinheiro pago real e devolvido primeiro: decisao que favorece o usuario |

Invariantes: `available >= 0`; `divida >= 0`;
`available = compras + claw_release - clawback - debt_settlement - gasto`;
`divida = open - settle - release`; por compra `applied = target` apos reconciliar.
