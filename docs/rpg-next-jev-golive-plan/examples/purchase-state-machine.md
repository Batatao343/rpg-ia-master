# Purchase state machine — referência

Estados sugeridos (não copiar sem validar com adapters):

`created -> pending -> paid_verified -> credited -> reconciled`

Saídas: `cancelled`, `failed`, `refunded`, `revoked`, `disputed`, `needs_review`.

Regras:

- somente `paid_verified` pode criar entrada `purchase` no wallet ledger;
- `credited` é idempotente por provider purchase key;
- refund/revocation cria compensação/reversal, nunca apaga purchase;
- eventos tardios/out-of-order precisam convergir;
- client-side success não é estado financeiro.
