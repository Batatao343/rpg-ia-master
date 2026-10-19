# SPEC-259 — smoke no AVD `rpg34` contra o staging (2026-10-19)

APK debug gerado do `main` (`d2978d0`) com `server.url` = staging e **Billing real** (sem `-PplayBillingFake`),
instalado no AVD `rpg34` (android-34 `google_apis` x86_64, sem Play Store: `PlayStore.enabled = no`).
Staging no deploy `da6186b` (contém SPEC-259 e SPEC-261). Sessão aberta com usuário sintético
(`generate_link` + `POST /auth/verify` dentro do WebView, sem e-mail), apagado ao fim (`DELETE` 200, `exists=false`).
Nada foi deployado nem alterado no staging.

Evidência: [`evidence/spec259_avd_smoke.json`](evidence/spec259_avd_smoke.json),
[`evidence/staging_access_log.json`](evidence/staging_access_log.json),
[`evidence/boot_timing.json`](evidence/boot_timing.json), captura `evidence/spec259_avd_staging.jpg`.

| Item | Resultado |
|---|---|
| R1 código distinto + `responseCode` + `debugMessage` no JS | **ok**: `getProducts` → `billing_query_failed`, `{responseCode: -1, stage: "products", debugMessage: "Service connection is disconnected."}` |
| R2 logcat `RPGBilling` | **ok**: `W RPGBilling: billing_query_failed responseCode=-1 debugMessage=Service connection is disconnected.` (debugMessage só porque o build é debug); nenhum token/conta no logcat |
| R3 console do WebView no logcat (debug) | **ok**: linhas `RPGWebView` (warnings/errors do Turnstile e do bundle) |
| Cancelamento fake | **não gera código, por design**: no modo fake `purchase()` de produto `*cancel*` resolve `{cancelled: true}` (`PlayBillingPlugin.java:128`), e no modo real `USER_CANCELED` também resolve (`:147`, `:183`). Cancelar não é erro, então não há linha `RPGBilling`. O caminho de erro foi provado acima com o BillingClient real |
| R4 `X-RPG-App-Version` nas requisições | **FALHA**: nenhuma requisição do app levou o header, nem as pós-boot autenticadas (`/account/balance`, `/game/saves`, `/data/options`, `/data/onboarding`); `X-RPG-Client: android` e `X-RPG-Build` saem normalmente. `App.getInfo()` responde `{version: "1.0.0", build: "1"}` quando chamado depois |
| R4 `app_version` no access log do staging | **ausente**: as linhas `http.request` com `client=android` têm `client_build=da6186b+202610191331` e não têm o campo `app_version` (`vercel logs --json`) |

## Defeito encontrado (R4)

`web/src/main.tsx` chama `loadAppVersion()` uma única vez, na carga do módulo. No shell com `server.url` remoto, nesse
instante `window.Capacitor` já existe (`isNativePlatform() === true`), mas `Capacitor.registerPlugin` só aparece
~200 ms depois (medido: DOMContentLoaded 591 ms sem `registerPlugin`; disponível em 803 ms). `capacitorInfo()` lança
`app_plugin_unavailable`, o `catch` grava `cached = null` e nunca mais tenta. O teste unitário não pega porque injeta o
`read`.

Correção sugerida (pequena, spec 259 ou follow-up): em `loadAppVersion`, esperar `registerPlugin` (poll curto, ex.
até 3 s) antes de desistir, ou reler a versão de forma preguiçosa em `appVersion()` enquanto `cached` for `null` no
Android. Depois, repetir este smoke (`header_on_api_request` e `app_version=1.0.0+1` no access log).

## Reteste do R4 após o fix (2026-10-19, staging `65c0f23`)

**R4 verde.** O fix (retentativa da leitura do plugin `App` por até 3 s) foi deployado no staging `65c0f23`, e o mesmo APK foi
usado no AVD `rpg34`. As requisições depois do bootstrap levam `X-RPG-App-Version: 1.0.0+1`, e o access log tem
`app_version=1.0.0+1` com `client=android` em 5 rotas `/account/*`. As 3 primeiras requisições do boot saem sem o header (aceito).
`/account/purchases/google/profile` deu 503 porque o Play não está configurado no staging (SPEC-198), sem relação com o R4.
Evidência: [`evidence/spec259_avd_smoke_r4fix.json`](evidence/spec259_avd_smoke_r4fix.json),
[`evidence/staging_access_log_r4fix.json`](evidence/staging_access_log_r4fix.json), `evidence/spec259_avd_staging_r4fix.jpg`.

SPEC-281 no mesmo deploy: a primeira chamada Jev pós-deploy (`jev.primary`, `outcome=primary`) levou 285 ms, sem `timeout`.
As 3 chamadas Jev da e2e_session levaram 243–285 ms. Detalhe: [`evidence/jev_first_turns_65c0f23.json`](evidence/jev_first_turns_65c0f23.json).
