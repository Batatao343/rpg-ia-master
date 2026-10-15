# SPEC-194 backend: Google Play Billing (consumiveis)

Status: backend + fake Google concluidos offline. Play Console/licence testing = SPEC-198; plugin nativo = SPEC-193.

## Contrato HTTP (autenticado, CSRF como demais rotas /account)
- `GET /account/purchases/google/profile` -> `{obfuscated_account_id}`; o app DEVE passar esse valor em `setObfuscatedAccountId` ao iniciar a compra (HMAC-SHA256(chave `RPG_PLAY_ACCOUNT_KEY`, "rpg-play-v1:"+owner_id), hex 64 chars; chave >=32 chars obrigatoria, sem ela `503 google_play_unconfigured`; sem migracao de valores antigos pois nao ha compras reais).
- `POST /account/purchases/google/verify` body `{product_id, purchase_token, order_id?}` (tudo nao confiavel).
  - 200 `{status:"fulfilled", state, product_id, sku_id, shard_milli, consumed}`; `{status:"pending"}` (sem credito; app tenta de novo).
  - 409 token_conflict/purchase_cancelled/already_consumed; 422 input/produto/ordem/conta/quantidade; 403 account_deleted; 503 unavailable/unconfigured.
  - Replay e idempotente; o app reenvia tokens de `queryPurchasesAsync` ao retomar (recupera consume falho e process death).
- Preco nunca vem do backend para este canal: so `shard_milli`. UI usa `ProductDetails` da Store.
- `X-RPG-Client: android` -> `/account/checkout*` (Stripe) responde 403 `stripe_unavailable_on_android` (politica R8, nao fronteira de seguranca).

## Env (somente backend)
`GOOGLE_PLAY_PACKAGE_NAME`, `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` (caminho ou JSON inline). JWT RS256 via `cryptography` -> `oauth2.googleapis.com/token`, scope androidpublisher.

## Catalogo
Linha em `app.purchase_skus` com `channel='google_play'`, `store_product_id=<product id Play>` (ex. `estilhas_pack_small`), pricing_version propria com fee `google_play` (R9: confirmar tier de taxa antes de producao). Publicar e migracao de operador.

## Maquina de estados (`app.google_play_purchases.state`)
get Google (purchaseState 0, productId, orderId, quantity=1, account hash, consumptionState 0) -> [tx: advisory lock + credito wallet `payment:google_play`/orderId + linha `fulfilled`] -> consume -> `consumed`; consume falha -> `fulfilled_unconsumed` -> retry (reenvio do app ou `GooglePlayPurchases.retry_unconsumed()`). `consumed` e terminal. token_sha256 e order_id unicos; trigger de imutabilidade; account_write_fence; RLS forcada, sem grants. Colunas `voided_at/void_reason` + `google_state` sanitizado reservadas para SPEC-195.

## Pendencias
- SPEC-198: teste real (Play Console, licence tester, package definitivo, track interno), `acknowledge` nao usado (consume ja reconhece).
- Ligar `retry_unconsumed` a worker/cron (nao ha job kind novo).
- Teste Postgres da `PostgresPurchaseStore` (migracao + concorrencia) requer lab local; so contratos offline foram executados.
- SPEC-195: refund/void consumindo `voided_at`.

## Cliente nativo (Capacitor 8 / Play Billing Library 9.1.0)
Versao fixada `com.android.billingclient:billing:9.1.0` (ultima estavel das release notes oficiais, 2026-06-18; Billing 8+ exigido por Google ate 31/08/2026). Sem SaaS de terceiros. O manifest merge da biblioteca adiciona `com.android.vending.BILLING` (verificado no manifest mesclado do APK).

- Plugin: `web/android/app/src/main/java/dev/rpgia/valoria/staging/PlayBillingPlugin.java` (registrado em `MainActivity` antes de `super.onCreate`). Metodos: `getProducts({productIds})` (preco SO do `ProductDetails`: formattedPrice/priceAmountMicros/currency/title), `purchase({productId, obfuscatedAccountId})` (`setObfuscatedAccountId`; `USER_CANCELED` -> `{cancelled:true}`; `ITEM_ALREADY_OWNED` -> re-emite compras possuidas), `queryPendingPurchases()` (`queryPurchasesAsync(INAPP)`). Eventos: `purchaseUpdated {purchaseToken, productId, orderId, purchaseState: PURCHASED|PENDING}`, `purchaseCancelled`, `purchaseError`. NUNCA consome nem reconhece (o servidor consome apos creditar). Conexao com `enableAutoServiceReconnection` e `PendingPurchasesParams.enableOneTimeProducts`.
- Web: `web/src/purchases/androidPlay.ts` (`AndroidPlayAdapter`). Fluxo: `GET /account/purchases/google/profile` (relido antes de CADA compra; `purchases_disabled:true` => nunca chama `launchBillingFlow`, UI neutra "Compras temporariamente indisponiveis") -> `GET /account/purchases/google/products` (novo: `product_id`, `sku_id`, `shard_milli`, sem preco) -> `plugin.getProducts` -> `purchase` -> evento PURCHASED -> `POST /verify` (so product_id/purchase_token/order_id) -> a UI so mostra "confirmada" com a resposta do servidor; PENDING nao chama verify nem credita; cancelamento nao chama verify. No `resume` (`App.tsx` `resumeSession`) chama `queryPendingPurchases` e reenvia cada token (dedupe por token em voo/ja cumprido; idempotente no servidor).
- Servidor: `GET /account/purchases/google/products` (api.py, lista a linha mais nova por `store_product_id` com `channel='google_play'`); `X-RPG-Client: android` recusa `/account/checkout` e `/account/checkout/skus` com 403 (teste); `cryptography` declarado em `pyproject.toml` (`>=50.0,<51`, lock = 50.0.0); `scripts/seed_google_play_skus.py` (dry-run por padrao, `--apply`; espelha SKUs `web` como `gp_<sku>`, product id = sku minusculo com `[^a-z0-9_.]`->`_`; so versoes de preco que ja tenham taxa `google_play` em `channel_fees`; `ON CONFLICT DO NOTHING`). `retry_unconsumed` JA e invocado por `POST /internal/cron/reconciliation` (`Reconciler.reconcile_batch`, SPEC-195) quando Google esta configurado.

### Modo fake (somente smoke/dev)
- Android: `BuildConfig.PLAY_BILLING_FAKE` = `-PplayBillingFake=true` E `BuildConfig.DEBUG`; em release e sempre `false` (buildConfigField fixo). Produtos fake com preco "R$ 9,99"; id contendo `cancel` -> cancelado; contendo `pending` -> PENDING; demais -> PURCHASED com token `fake-<obfuscatedAccountId>-<n>`.
- Backend: `services/google_play_fake.py::FakeGooglePlayClient`, selecionado em `api._google_play()` SO se `RPG_GOOGLE_PLAY_FAKE=1` E `RPG_RUNTIME_PROFILE=local` (hosted/portable/legacy nunca). Atesta a conta pelo proprio token.
- Smoke de emulador (`scripts/android_billing_smoke.mjs`, AVD `rpg34`): o WebView carrega `http://10.0.2.2:8765` (build debug com `CAP_SERVER_URL`; `cleartext` so para esse host via `src/debug` network security config; release inalterado) servindo `web/dist` + API MOCK que registra chamadas. Prova: plugin registrado, listagem com preco da Store, evento -> `/verify` unico (corpo = product_id/token fake/order id), cancel sem verify, pending sem verify/credito, kill switch sem launch. Evidencia em `evidence/emulator_smoke.json` + 5 JPG; `evidence/apk_secret_scan.json` (596 entradas, 0 achados). NAO prova billing real.

## Pendente para SPEC-198
Produtos no Play Console (ids do script de seed; consumiveis), license testers, trilha de teste interno, applicationId/assinatura definitivos, service account real (`GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`) e `GOOGLE_PLAY_PACKAGE_NAME` no backend, confirmar tier de taxa (R9) em `channel_fees`, teste real com compra de licenca (staging hoje devolve 503 `google_play_unconfigured` em `/verify`, esperado), politica de Play Billing para a descricao da loja. Staging: rodar o seed e republicar o web (o WebView remoto so enxerga o novo cliente apos deploy).

## Follow-ups da revisao (APPROVED_WITH_FOLLOWUPS)
- **Restore**: `restorePending()` e single-flight e roda na partida fria (apos auth conhecida), no resume e ao montar a AccountScreen; o mesmo token nunca e reenviado em paralelo (dedupe por token no adapter).
- **Cleartext**: `res/xml/network_security_config.xml` (cleartext proibido) + `usesCleartextTraffic=false` (com `tools:replace`, pois o plugin cordova gerado declara `true`) no manifest main; o source set `debug` troca para `debug_network_security.xml` (so 10.0.2.2). `capacitor.config.ts` recusa `http://` salvo `CAP_BUILD=debug` + host `10.0.2.2`. Gradle `checkReleaseCleartext` (dependencia de `assembleRelease`/`bundleRelease`) falha se `capacitor.config.json` sincronizado tem `server.url` http:// ou o manifest release mesclado tem `usesCleartextTraffic=true`.
- **Consume envenenado**: 400/404/410 no consume -> re-GET; `consumptionState==1` => `consumed`; senao `consume_attempts++` e, na 8a, estado terminal `consume_failed` (fora do lote de retry; log de erro so com a classe; `consume_failed` no resumo do cron de reconciliacao). Erros transitorios (5xx/rede) nunca contam. Coluna editada in-place na migration 20261015130000 (ainda nao aplicada no staging).
- **Fake guard**: modo fake recusado (503) com `VERCEL` setado ou perfil `hosted*`; `RPG_GOOGLE_PLAY_FAKE` em `FORBIDDEN_IN_PROD` do checklist de release.
- `GooglePlayClient` por processo (`shared_client()`, bearer reutilizado ate expiry-60s, thread-safe); `WalletConflict` no verify => `409 google_play_wallet_conflict`.

## Item 8 (para a SPEC-198): compras sem obfuscated id
Compras fora do app (codigos promocionais, resgate na Play Store, compras iniciadas sem o `setObfuscatedAccountId`) chegam sem `obfuscatedExternalAccountId` e hoje sao RECUSADAS (`google_play_account_mismatch`) — nada e creditado e, sem consume, o Google reembolsa/estorna automaticamente em ~3 dias. A SPEC-198 deve decidir a politica (manter recusa e documentar no suporte, ou fluxo de resgate com vinculo explicito ao owner). Tambem: o preco do SKU semeado por `scripts/seed_google_play_skus.py` e so o espelho do SKU web; o preco real cobrado vem do cadastro do produto no Play Console e DEVE ser igualado manualmente (o app exibe apenas o `formattedPrice` da Store).
