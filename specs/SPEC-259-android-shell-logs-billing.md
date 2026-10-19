# SPEC-259 — Android: códigos distintos de billing com debugMessage, console do WebView em debug e versão do app nas requisições

> **Status:** `done` — aprovada pelo dono em 2026-10-19; implementada em 2026-10-19; smoke no AVD `rpg34` em 2026-10-19: R1/R2/R3 ok, R4 falhou (§9), corrigido (§10) e verde no staging `65c0f23` (§11). Prioridade sugerida: **P3**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-19
> **Depende de:** SPEC-244, SPEC-261
> **Desbloqueia:** —
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `web/android` não tem `Log.*`, crash reporter nem captura de console: `MainActivity.java:27` substitui o chrome client sobrescrevendo só `onPermissionRequest`; debug do WebView só em `BuildConfig.DEBUG` (`~24`). `PlayBillingPlugin.java` rejeita com `billing_error` em 3 sites diferentes (`89`, `134`, `146`), sem `getDebugMessage()`, e engole `JSONException` (`76`). `version.properties` não chega ao servidor: um relato de bug do app não diz qual versão nem a qual `git_sha` do servidor falou.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — Códigos de rejeição distintos por etapa (`billing_query_failed`, `billing_launch_failed`, `billing_ack_failed`, `billing_bad_json`) com `responseCode` e `debugMessage` truncada (≤ 120 chars, sem tokens) no objeto de erro para o JS.
- **R2** — `Log.w("RPGBilling", ...)` em cada rejeição (código + responseCode); nenhum token de compra em logcat.
- **R3** — `onConsoleMessage` repassa `error`/`warning` do WebView ao logcat só em `BuildConfig.DEBUG`.
- **R4** — O shell injeta `X-RPG-App-Version: <versionName>+<versionCode>` (via header do bridge ou `window.__RPG_APP_VERSION__` lido pelo `http.ts`); o access log da SPEC-241 registra `app_version`.
- **R5** — Erros de plugin chegam ao beacon da SPEC-244 com `kind=native`.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Crashlytics/Sentry nativo (decisão de privacidade/Data Safety separada).

## 3. Design técnico

- **Alterados:** `web/android/app/src/main/java/.../MainActivity.java`, `PlayBillingPlugin.java`, `web/src/http.ts`, `api.py` (access log).

## 4. Plano passo a passo

### Etapa 1 — Testes

Teste unitário Java do mapeamento de códigos (se houver infra) ou teste TS do adapter do plugin; `tests/test_api_access_log.py` cobre `app_version`.

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`npm run build` + `./gradlew assembleDebug` + AVD `rpg34`.

## 5. Critérios de aceite

- [x] Cada falha de billing tem código distinto + `debugMessage` no JS; logcat de release só código + `responseCode` (R2), `debugMessage` saneada só em `BuildConfig.DEBUG`.
- [x] `app_version` aparece no access log (AVD `rpg34` contra o staging `65c0f23`: `app_version=1.0.0+1` com `client=android` — §11).
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline; na branch só falhou o Project Index desatualizado, regenerado no pouso `65c0f23`).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. AVD `rpg34` com Billing fake: cancelar compra ⇒ código `billing_user_canceled`/equivalente com responseCode; requisição carrega `X-RPG-App-Version`.

## 7. Riscos & compatibilidade

- Data Safety: logcat local só; nada sai do aparelho além do header de versão.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## 8. Notas de implementação (2026-10-19)

- **R1/R2** `BillingErrors.java` (Java puro, testado por `BillingErrorsTest` — 5 testes JUnit): códigos
  `billing_unavailable` (setup), `billing_query_failed` (`stage=products|pending`), `billing_launch_failed`,
  `billing_bad_json`; `call.reject(code, code, {responseCode, stage, debugMessage})`, `debugMessage` saneada (≤ 120 chars,
  sequências opacas ≥ 24 chars ⇒ `[redacted]`, sem controle). `Log.w("RPGBilling", "<code> responseCode=<n>")`
  (` debugMessage=<saneada>` só em `BuildConfig.DEBUG`, revisão P2/P3) — nunca token/produto/conta. `purchaseError` (listener) também leva `debugMessage` e loga
  `billing_purchase_update_failed`.
- **Desvio:** não existe `billing_ack_failed` — o plugin NUNCA confirma/consome (o servidor consome após creditar,
  SPEC-194); não há etapa de ack no shell para falhar.
- **R3** `MainActivity.onConsoleMessage`: `ERROR`/`WARNING` do console do WebView ⇒ logcat `RPGWebView`, só em
  `BuildConfig.DEBUG`.
- **R4** versão do app: `web/src/native/appVersion.ts` lê `versionName+versionCode` do shell (plugin nativo `App`
  do Capacitor, `App.getInfo()`), formato fechado; `http.ts` envia `X-RPG-App-Version` quando conhecida (requisições
  antes da leitura do boot saem sem ela). Access log `app_version` (formato fechado; senão `other`) — teste
  `tests/test_api_access_log.py::test_app_version_logged` (commit da SPEC-261, mesma função `_client_build_fields`).
- **R5** `androidPlay.ts`: rejeição de `getProducts`/`purchase`/`queryPendingPurchases` e o evento `purchaseError` ⇒
  beacon `kind=native`, `error_name=PlayBillingError`, `code=<codigo>:<responseCode>` (SPEC-244); o erro segue
  propagando como antes. Teste `web/tests/nativeLogs.test.mjs`.
- **Verificado offline (19/10):** `npm run build`, `tsc -b`, `node --test` (todos), `gradlew assembleDebug` +
  `:app:testDebugUnitTest` com JDK 21 (APK debug gerado; `BillingErrorsTest` 5/5).
- **Pendente (exige AVD `rpg34`, não executado — sem evidência inventada):** compra fake cancelada/erro no emulador
  mostrando `billing_*` com `responseCode` no JS e no `adb logcat -s RPGBilling RPGWebView`; requisição do WebView com
  `X-RPG-App-Version: 1.0.0+1` e `http.request app_version=1.0.0+1` no log do staging.

## 9. Smoke no AVD `rpg34` (2026-10-19)

Detalhe e evidência: [docs/spec259/README.md](../docs/spec259/README.md). APK debug com Billing real apontando para o staging
(`da6186b`), usuário sintético apagado ao fim, sem deploy.

- **R1/R2 ok:** `getProducts` rejeita com `billing_query_failed` + `{responseCode: -1, stage: "products", debugMessage}` no JS;
  logcat `RPGBilling: billing_query_failed responseCode=-1 debugMessage=...` (debug); sem token no logcat.
- **R3 ok:** console do WebView em `RPGWebView`.
- **Cancelamento fake não gera código:** por design o cancelamento resolve `{cancelled: true}` (fake e real); o caminho de erro
  foi provado com o BillingClient real (AVD `google_apis` sem Play: "Service connection is disconnected").
- **R4 FALHA:** nenhuma requisição leva `X-RPG-App-Version` e o access log do staging não tem `app_version` nas linhas
  `client=android`. Causa medida: `loadAppVersion()` roda na carga do módulo, quando `Capacitor.registerPlugin` ainda não
  existe (aparece ~200 ms depois); lança `app_plugin_unavailable` e o cache fica `null` para sempre. Correção sugerida no
  README (esperar `registerPlugin` ou reler de forma preguiçosa) + repetir o smoke. Quem age: executor da 259 (código web).

## 10. Correção do R4 (2026-10-19)

`loadAppVersion()` agora trata falha de leitura do plugin `App` como transitória: retenta até 15 × 200 ms (3 s) sem
bloquear o boot e sem cachear a falha; formato inválido continua descartado na hora (1 leitura). Requisições anteriores
à resolução saem sem o header (aceito: são as do bootstrap). Teste Node novo cobre plugin tardio, esgotamento e formato
inválido. Falta repetir o smoke R4 no AVD contra o staging redeployado da main com este fix.

## 11. Smoke R4 no AVD `rpg34` contra o staging `65c0f23` (2026-10-19)

Staging redeployado da main `65c0f23` (`/health` com o sha, `hardened=true`; post_deploy_smoke, vercel_smoke e
e2e_session verdes; Jev `primary`). Mesmo APK debug do §9 (Billing real, `server.url` = staging, não reinstalado: a
correção está no bundle web servido pelo staging). Usuário sintético por `generate_link`, apagado ao fim (200, `exists=false`).

- No WebView (CDP), as requisições do bootstrap (`/auth/config`, `/account/balance`, `/game/saves`) saem antes de o plugin
  resolver e vão sem o header, como aceito no §10. A partir de `/data/options` todas levam `X-RPG-App-Version: 1.0.0+1`.
- Access log (`vercel logs --json`): depois do clique em "Conta", as linhas `http.request` de `/account/balance`, `/account/series`,
  `/account/usage`, `/account/purchases` e `/account/purchases/google/profile` têm `client=android`,
  `client_build=65c0f23+202610191753` e `app_version=1.0.0+1`. `/data/*` não aparece no log de função (servido em cache).
- R1/R2 repetidos ok (`billing_query_failed` + `responseCode`, logcat sem token).
- Evidência: `docs/spec259/evidence/spec259_avd_smoke_r4fix.json`, `staging_access_log_r4fix.json`, `spec259_avd_staging_r4fix.jpg`.
