# SPEC-189 — handoff para Sol High independente

Executor: Sol High (`gpt-6.1-sol`), contrato obrigatório cumprido.
Reviewer: Sol High em contexto independente; decisão ainda pendente.
Branch: `spec-189-stripe-web-checkout-webhooks`, base SPEC-188 `done` + fix CI
`85d2bcc`. Commit congelado será informado pelo executor após os gates.

Leia `specs/SPEC-189-stripe-web-checkout-webhooks.md` e
`docs/spec189/README.md`. Source relevante: `api.py` routes checkout/webhook;
`services/stripe_checkout.py`; `infrastructure/stripe_payments.py`;
`infrastructure/wallet.py` shared connection; migration `20261013120000`;
AccountScreen/App/api web e novo checkout E2E. Comparar com base `85d2bcc`.

Foco obrigatório: raw bytes/assinatura antes de parse; server-side SKU/version/
credits; owner/CSRF; retry/Stripe janela 24h; session/order/intent/mode/paid/
amount/currency; concorrência orphan financial versus primeiro bind; replay
event e paid distintos; atomicidade dedupe + pedido + ledger; refund/inquiry/
dispute/FX/closed e saldo gasto; fee real auditada; secrets bundle; test-only.

Evidência: 39 focados (23 PG rollback + 3 races multi-connection local), 24
afetados, Ruff verde; build e 7 Checkout Chromium verdes. Gate Python pré-commit
**2134 passed,113 skipped,15 deselected**, exit 0,285,21s; browser completo
**45 passed,1 skipped**, exit 0; bundle secret scan PASS e índice fresh.
Hash congelado será fornecido diretamente pelo root após o commit.

Três achados da análise preliminar já corrigidos: warning/prevented inquiry
sem debit; disputes com amount/FX diferente auditados; IDs reais `du_`.
O primeiro full teve falhas de temp path Unicode/longo e índice durante edição;
full final ASCII passou. Nenhum evaluator/expected/dataset foi alterado.

Limites: nenhum Stripe remoto, live mode ou SKU comercial; integração desativada
por default. Partial/inquiry/dispute divergente/closed/funds spent precisam
ajuste de operador e ficam em reconciliation_required, sem apagar histórico.
Fee atrasada depende de replay/reconcile_fee; scheduler é operação de release
SPEC-197. Não autoaprovar revisão; status permanece review-pending até parecer.
