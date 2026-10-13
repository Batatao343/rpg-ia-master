# SPEC-189 — revisão independente Sol High

- `decision`: **APPROVED**
- `review_model`: Sol (`gpt-6.1-sol`)
- `review_effort`: High
- `review_run_id`: `SPEC-189-SOL-20261013-INDEPENDENT-01`
- Contexto independente: `/root/spec189_reviewer_sol`
- Commit revisado: `b1716983be7e929285356fe429acdb53b91e3b4b`
- Base: `85d2bccb243c52d5eb4212684953d3a9f9bfa156`
- Achados abertos: **nenhum**

## Escopo e independência

Conferi ESTADO_ATUAL, índice de specs, dependência SPEC-188 `done`, spec
aprovada, política/contrato de modelos, diff congelado, source relevante,
migrations, fixtures, testes e handoff do executor. A skill Supabase orientou
a conferência de grants, RLS e funções. O working tree estava limpo antes
de gravar este parecer; HEAD correspondia ao commit revisado.

O reviewer não implementou correções e não modificou source, testes,
evaluators, expected, datasets, baseline ou exclusões. Achados foram enviados
ao executor/coordenador e suas correções foram conferidas no source final.
O diff em `evals` é vazio; as mudanças em `tests` são arquivos novos desta spec.
Nenhuma chamada ao Stripe ou a provider de IA foi executada pelo reviewer.

## Contratos verificados

`stripe_webhook` limita o body e verifica HMAC dos bytes originais e timestamp
antes do JSON e antes de chamar o store. `verify_event` usa comparação constante,
aceita assinaturas `v1`, aplica tolerância de 300s e rejeita eventos live.
O timestamp da assinatura permite delivery atrasado com assinatura nova;
`created` do evento não é usado como dedupe. O contrato foi confrontado com
[webhooks Stripe](https://docs.stripe.com/webhooks).

Checkout exige autenticação/CSRF e um body estrito com SKU e UUID de request.
Owner vem do principal; preço, crédito, canal e versão vêm do catálogo
imutável server-side. O pedido preserva esses fatos por trigger, e o grant
confere o snapshot contra o SKU antes de usar o writer canônico da wallet.
Metadata contém somente referência opaca e não autoriza preço/créditos.
Pedido é durável antes da rede; retries usam a mesma chave Stripe e são
limitados a 23h, abaixo da [retenção mínima de 24h](https://docs.stripe.com/api/idempotent_requests).

Fulfillment exige evento aplicável, `paid`, mode payment, session/intent,
valor e moeda compatíveis. Dedupe, vínculo do pedido, ledger e saldo usam a
mesma conexão/transação. Advisory lock por PaymentIntent precede o order lock
e serializa refund/dispute inicialmente órfão contra o primeiro vínculo pago.
Replay do mesmo evento, eventos pagos distintos e entrega reordenada não
duplicam grant; financial facts anteriores impedem ressurreição de crédito.
Savepoints internos da wallet permanecem dentro da transação externa.

Success/cancel e consulta de status são leituras owner-scoped. O frontend
consulta a wallet/ledger do servidor, preserva UUID no retry e não cria saldo
pela URL. Gerações de leitura descartam snapshots antigos tanto na tela da
conta quanto no cabeçalho. A abordagem respeita fulfillment por webhook
[documentado pelo Stripe](https://docs.stripe.com/checkout/fulfillment?payment-ui=stripe-hosted).

Refund/dispute são append-only; reversão total mantém purchase original e
ocorre no máximo uma vez. Saldo gasto, partial, inquiry, FX/valor divergente e
closed ficam em reconciliação explícita, sem overdraft ou recrédito silencioso.
Fee real é obtida por balance transaction e registrada como fato imutável;
margem reconciliada não altera o grant. RLS é enabled/forced, clients não têm
grants nas tabelas e `rpg_api` só lê pedidos/fatos do owner. Não há nova view
pública ou função SECURITY DEFINER.

## Achados resolvidos

1. **Disputas rejeitadas pelo prefixo de fixture.** O hardening exigia `dp_`;
   IDs reais usam `du_`. Source e fixtures agora seguem a
   [referência oficial do Dispute](https://docs.stripe.com/api/disputes/object).
2. **Inquiry tratada como chargeback e status perdido.** Os oito statuses
   documentados são preservados; `warning_*` e `prevented` não geram débito
   automático. O outcome permanece auditável e exige operador.
3. **Disputa maior que o pagamento rejeitada.** Amount/currency divergentes
   agora produzem financial fact e reconciliation_required; refund inválido
   continua rejeitado. A distinção segue
   [inquiry e valores disputados](https://docs.stripe.com/disputes/how-disputes-work).
4. **Saldo pago sobrescrito por leitura antiga.** Fence de geração protege
   conta e cabeçalho; replay terminal pago refaz leituras no servidor. E2E
   retém snapshots antigos, libera-os após o pagamento e verifica ambos.
5. **Default desativado importava dependência opcional.** O helper retorna
   503 antes de importar o store Postgres quando checkout está desativado;
   a regressão verifica explicitamente essa fronteira.

## Gates e evidência

- Python pré-commit: **2.134 passed, 113 skipped, 15 deselected**, **exit 0**,
  285,21s. Li diretamente `.tmp/spec189-full-final.xml`: `tests=2247`,
  `failures=0`, `errors=0`, `skipped=113`, `time=285.183`.
- Focados: **39 passed**, incluindo **23 PostgreSQL com rollback** e
  **3 corridas com conexões independentes** em schema local descartável.
  Conferi os testes de dedupe, crash/rollback, orphan refund, RLS, economics,
  inquiry e valor/moeda divergentes. Afetados: **24 passed**.
- Durante implementação, reexecutei independentemente o subset inicial de
  assinatura/API: **7 passed**, exit 0, Python 3.13 via `uv run --no-sync`.
- Checkout Chromium: **7 passed**; browser completo: **45 passed, 1 skipped**,
  exit 0. Build TypeScript/Vite, Ruff e freshness do índice: verdes.
- Scan independente do bundle não encontrou `STRIPE_SECRET_KEY`,
  `STRIPE_WEBHOOK_SECRET`, `sk_live_`, `sk_test_` ou `whsec_` em `web/dist`.

Resultados focados/Postgres/browser/build/Ruff/índice foram fornecidos pelo
executor/coordenador e conferidos com source, handoff e relatório. O primeiro
full teve problemas de temp path Windows/Unicode e freshness durante edição;
o full final ASCII passou sem mudar RAG, testes existentes ou oráculos.
Não solicitei repetição por docs/formatação após o gate pré-commit.

## Limites da aprovação

A aprovação cobre implementação e evidência local da SPEC-189. Integração
segue desativada por default, aceita apenas test mode e não publica SKU
comercial. Smoke Stripe conectado permanece `not_run_not_connected` e é
gate de release SPEC-197. Live mode não está autorizado.

Fee tardia depende de replay pago ou execução de `reconcile_fee`; scheduler
operacional permanece no gate de release. Disputas/partial/closed/saldo gasto
exigem reconciliação de operador e eventual ajuste auditado. Não houve
provisionamento, advisors ou migração cloud. Esses limites estão explícitos
na spec e em `docs/spec189/README.md` e não impedem o fechamento local.

## Atestação após alinhamento da base — 2026-10-13

A decisão **APPROVED** também se aplica à implementação rebased
`b724736bcb188bd7113fe1480d2a47ce933391f6`, sobre a base
`29c1881fee6dd745117aeece5e685f9884a3ebfe`. Confirmei independentemente:

- `b171698` e `b724736` têm o mesmo tree Git:
  `f220a79c5bff7984ac9105319dadb5e27c2027ca`.
- Closure anterior `69736a4a82b9eb8f460f10794e08081985e9da97`
  (`backup/spec189-before-base-align`) e closure nova
  `2c345f69eb9fd914142d3d22887132496c1b36f6` têm o mesmo tree:
  `2171c75abc6997dd56903d58249c1cd26e26128a`.
- Bases `85d2bcc` e `29c1881` também têm trees idênticos; os dois
  `git diff --exit-code` passaram e `git range-diff` marcou ambos os commits `=`.

O alinhamento mudou somente o histórico/hashes. Source e conteúdo versionado
equivalentes preservam o parecer e seus gates; não revisei código novamente
nem executei testes adicionais. Atualizações posteriores de referências,
documentação e índice ficam fora desta atestação de igualdade dos trees.
