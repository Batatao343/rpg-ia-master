# SPEC-189 — evidência do Checkout Stripe web

Status: `done`; executor Sol High e revisão Sol High independente **APPROVED**
(`SPEC-189-SOL-20261013-INDEPENDENT-01`, sem achados abertos) sobre `b724736`
(rebase byte-idêntico do commit revisado `b171698`). SPEC-188 está `done`;
base `29c1881` já contém a correção de CI do índice. Nenhuma chamada Stripe, pagamento
real, recarga de IA ou ativação comercial nesta execução.

## Contratos e ownership

| Requisito | Source e prova |
| --- | --- |
| R1 autoridade de SKU | `quote_published_sku` valida quote/frescor, allowlist backend e pedido com snapshot protegido; corpo HTTP estrito só aceita SKU e request UUID |
| R2 sessão | Adapter test-only com chave `checkout:<order UUID>`, BRL/cents server-side e return URLs de origin fixo; pedido durável antes de rede; cutoff de retry 23h |
| R3 assinatura/store | HMAC raw body + timestamp antes de JSON, 256KiB/15s, hash e fatos sanitizados append-only por `evt_` |
| R4 fulfillment | `paid` + mode/session/order/intent/amount/currency exatos; evento, vínculo e ledger na mesma transação; success/cancel GET só observa |
| R5 economics | Fee reconciliada de balance transaction, fato append-only e margem real = bruto − fee − budget alocado; grant imutável |
| R6 refund/dispute | Fatos financeiros append-only; refund/reversal total uma vez; saldo gasto/inquiry/partial/FX/closed ficam em hold auditável |
| R7 secrets | Config somente backend; sem dependência Stripe/browser public key; scanner do bundle registrado nos gates |
| R8 test mode | `sk_test_*` obrigatório, `livemode=true` rejeitado, default desativado e catálogo vazio; smoke Stripe remoto não executado |

Canonical owner de saldo/ledger segue `infrastructure/wallet.py` e tabelas
SPEC-184. O mapa curado de ownership foi consultado seletivamente antes de
criar o writer; não contém entrada da wallet. Source/migrations confirmam
owner account UUID, ledger append-only e conservation no commit. Novo store
`infrastructure/stripe_payments.py` coordena fatos/pedidos e usa conexão
compartilhada com wallet para round-trip e replay. Não usa GameState como saldo.
Novas tabelas ficam em `app`, RLS enabled/forced; clients sem grants, role
`rpg_api` somente leitura por owner de pedidos e fatos financeiros. Eventos
Stripe não são expostos. Nenhuma view nova em `public`.

## Testes e comandos

Todos os comandos Python usaram `uv run --no-sync python` com `.venv` Python
3.13 do workspace principal, `UV_PROJECT_ENVIRONMENT`/`UV_CACHE_DIR` process
scoped e basetemp gravável dentro do clone. Não usam Python global 3.14.

- Red inicial: teste de assinatura falhou na coleta antes do módulo; testes
  Postgres falharam na coleta antes do store; 4 contratos HTTP falharam antes
  de implementar endpoints. Os gates abaixo passaram depois da implementação.
- Focado: `python -m pytest tests/test_stripe_checkout.py
  tests/test_stripe_checkout_api.py tests/test_stripe_checkout_local.py
  tests/test_stripe_checkout_concurrency_local.py -o addopts= -q`:
  **39 passed, 1 warning**, exit 0, 7,71s no rerun após prefixo `du_`.
  XML em `.tmp/spec189-focused.xml`.
  Inclui 9 signature/adapter/config, 4 HTTP auth/CSRF/return/body e
  **23 Postgres rollback**; migrations/dados revertidos em cada fixture.
- **3 races reais multi-connection** usam schema UUID exclusivamente em
  Postgres loopback, instanciando as migrations canônicas nele. Setup precisa
  commit para duas conexões verem o mesmo pedido; teardown remove o schema.
  Nenhuma escrita em `app` ou catálogo comercial. Provas: paid duplicado
  simultâneo, paid com IDs/eventos distintos e refund órfão versus primeiro
  paid. Um crédito no máximo; saldo final zero no refund.
- Afetados: wallet spend guard, account API, auth sessions e shard pricing:
  **24 passed, 5 warnings**, exit 0. Ruff em todos os módulos afetados: verde.
- Frontend focado: **7 Chromium** (390/1440, Axe, catálogo indisponível,
  success pendente → paid, cancel, replay terminal null URL e corrida com
  snapshot de saldo antigo), build TypeScript/Vite verde.
- Suíte Python completa, browser completo e bundle scan: gates finais abaixo.

## Limites e operação

`RPG_STRIPE_ENABLED=0` é default. Para teste conectado exige chave `sk_test_*`,
endpoint secret `whsec_*`, `RPG_CHECKOUT_ORIGIN` HTTPS sem path/query e
`RPG_STRIPE_ALLOWED_SKUS` JSON com IDs de SKUs web já publicados pelo operador.
Nenhum preço é semeado. Body estrito rejeita owner, preço e créditos do client.
Customer/PII do Stripe não é persistido; somente referências opacas, números
financeiros selecionados e SHA-256 do body autenticado.

Eventos desconhecidos são recebidos/dedupados sem grant. Refund/dispute órfão
fica armazenado e é aplicado quando o Checkout vincula intent; refund/dispute
anterior bloqueia crédito atrasado. Reservas de consumo já abertas não são
canceladas por refund; saldo consumido vira reconciliação sem overdraft.
Inquiry `warning_*` e `prevented` não têm debit automático. Valor parcial,
moeda/valor de chargeback divergentes e closed won/lost requerem operador;
restauração é ajuste auditado, jamais delete ou recrédito silencioso.

Fee ausente/falha de lookup não impede fulfillment confirmado. Delivery pago
repetido tenta reconciliation até haver fee; depois evita lookup repetido.
Um agendador/rotina operacional de `reconcile_fee` e Stripe test-mode smoke
com conta aprovada permanecem no release gate SPEC-197. Sem conta/conexão
previamente aprovada disponível, smoke remoto é `not_run_not_connected`.
Release/live mode não é autorizado por esta spec.

CLI Supabase ausente do PATH e da busca local; migração SQL criada conforme
fallback operacional autorizado, sem registrar migration history local.
O SQL foi realmente aplicado/testado via psycopg e revertido nas fixtures.
Checklist Supabase: secrets backend; ownership/RLS por role/predicate;
nenhuma security definer/view pública nova; grants clients revogados;
advisors remotos não invocados porque nenhuma conexão cloud foi aprovada.

## Revisão e fontes primárias

Revisão preliminar Sol detectou inquiry/statuses ausentes, chargeback com
valor/FX distinto e prefixo de disputa (`du_`, conforme Stripe). Corrigidos
com fixtures de IDs reais e sete regressões Postgres: warning
statuses/prevented preservam outcome sem debit; valores >gross/moedas
divergentes ficam auditados em hold. O parecer formal aprovou o commit congelado.

Fontes consultadas em 2026-10-13:

- [Stripe assinatura e raw body](https://docs.stripe.com/webhooks).
- [Checkout Session e payment_status](https://docs.stripe.com/api/checkout/sessions/object).
- [Checkout fulfillment por webhook](https://docs.stripe.com/payments/checkout/fulfill-orders).
- [Stripe idempotency keys, retenção mínima 24h](https://docs.stripe.com/api/idempotent_requests).
- [Dispute object/statuses](https://docs.stripe.com/api/disputes/object) e
  [inquiry/valor de disputa](https://docs.stripe.com/disputes/how-disputes-work).
- [Supabase RLS e grants](https://supabase.com/docs/guides/database/postgres/row-level-security).
  Changelog markdown não pôde ser lido pelo fetch (content-type); docs oficiais
  de RLS confirmaram o contrato aplicado. Sem mudança de SDK/API Supabase.

## Gates finais

- **Suíte Python pré-commit:** `uv run --no-sync pytest
  --basetemp=C:/tmp/rpg_spec189_gate --junitxml=.tmp/spec189-full-final.xml`:
  **2.134 passed, 113 skipped, 15 deselected**, exit 0, **285,21s**.
  Markers padrão excluem provider/playtest pagos; Postgres condicionado ao DSN
  é skipped aqui e já foi provado no gate focado acima. Seis warnings: depreciações
  existentes e cache pytest sem permissão, sem efeito no gate.
- **Browser completo:** **45 passed, 1 skipped**, exit 0, 46 cenários, 3m.
  O primeiro run pegou HMR durante edição do App; F05 isolado e repetição
  completa em source estável passaram, sem mudar o oracle.
- **Build TypeScript/Vite:** verde. **Ruff:** verde. **Bundle scan:** PASS;
  `web/dist` não contém `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
  `sk_test_` ou `whsec_`. Skill React best practices aplicada ao checklist
  de componentes, hooks, stale writes, acessibilidade e TypeScript.
- **Project Index:** regenerado/check fresh, **6.352 nodes / 16.424 edges**,
  source tree hash `00628ceed21cc0c66568c37e55af07d80072f936ebfe4d9c79269288ef0bb582`.
  LF canônico nos arquivos de source conforme `.gitattributes`; os quatro
  arquivos de baseline com CRLF só no working tree foram normalizados para
  os bytes LF do HEAD. Nenhuma alteração semântica neles.
- **Integridade:** evaluator, expected, datasets de regressão, baseline,
  denominador e exclusões protegidos intactos. Sem campanhas longas/IA paga.

O primeiro full usou basetemp dentro do clone Unicode/longo: oito failures
de FAISS/Windows path e dois de freshness após ajuste do helper offline
durante o run. Source final do helper retorna 503 antes de importar dependência
Postgres opcional; seu teste focado passou. Índice foi atualizado e o único
full final válido usou path curto ASCII com source semanticamente estável.
A repetição resolve esses failures sem alterar produto RAG, testes existentes
ou oráculos. Nenhum full adicional é necessário para atualizar estas docs.

Commit de implementação `b724736` preserva byte a byte a árvore de `b171698`,
aprovado pelo revisor independente;
[parecer completo](../../handoffs/SPEC-189-SOL-independent-review.md).
Branch enviada ao GitHub na [PR #25](https://github.com/Batatao343/rpg-ia-master/pull/25).
O fechamento local não ativa Checkout comercial; Stripe test-mode conectado
continua condicionado à conta e é obrigatório no release gate SPEC-197.
