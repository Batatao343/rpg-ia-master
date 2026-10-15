# SPEC-193 — Fundação Android (Capacitor 8)

Status: `done` (15/10) — review independente CHANGES_REQUIRED corrigido (ver "Addendum 2026-10-15"); redeploy + smoke v2 em emulador no staging.

## Decisão de arquitetura
O WebView carrega o site hospedado (`server.url`, default `https://rpg-ia-master-staging.vercel.app`, override
`CAP_SERVER_URL` na hora do `npx cap sync`). Mesma origem => cookies first-party (HttpOnly, SameSite=Strict/Lax),
CSRF por Origin/`X-CSRF-Token` e `RPG_CORS_ORIGINS` inalterados; zero fork de UI.

Trade-offs: sem shell offline (fora de escopo da spec); o app depende de a rede estar no ar e do deploy web
(atualização do front = deploy, sem nova APK). Alternativa descartada: assets embutidos em `https://localhost`
exigiriam base URL da API + CORS + cookies `SameSite=None; Secure` (superfície CSRF maior).
`allowNavigation` = só o host configurado (Turnstile roda em iframe; links externos abrem fora do app).
Capacitor ainda copia `web/dist` para o APK (`assets/public`), mas não é usado com `server.url`.

## Layout / config
- `web/capacitor.config.ts` (appId DEV fixo `dev.rpgia.valoria.staging`; a identidade real do APK vive em `android/app/build.gradle` (`applicationId` + `namespace`) e no pacote Java `dev.rpgia.valoria.staging` — **SPEC-198 deve alterar os três juntos**; não há mais env `CAP_APP_ID`, que só mudava o `capacitor.config.json` gerado e enganava).
- `web/android/` (convenção Capacitor; builds ignorados pelo `.gitignore` gerado; `capacitor.config.json` gerado/ignorado).
- Versões exatas: `@capacitor/core|android|cli 8.5.3`, `@capacitor/app 8.1.2` (lockfile atualizado).
- Depuração do WebView: `MainActivity` força `WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)` — APK debug é depurável (CDP no smoke), release NUNCA, independente do `capacitor.config.json` gerado.
- `android.allowBackup=false`; `gradle.properties` com `android.overridePathCheck=true` (o repo vive em `Área de Trabalho`, path não-ASCII).

## Build
Capacitor 8 exige **JDK 21** (JDK 17 falha com `invalid source release: 21`). Usado Microsoft OpenJDK 21 em `%LOCALAPPDATA%\jdk21` (fora do repo).
```
cd web && npm ci && npm run build
npx cap sync android          # CAP_SERVER_URL=... CAP_DEBUG_WEBVIEW=1 opcionais
cd android && JAVA_HOME=<jdk21> gradlew.bat assembleDebug
```
APK: `web/android/app/build/outputs/apk/debug/app-debug.apk` (~21 MB).

## Código (frontend único)
- `src/native/platform.ts`: detecta Capacitor via `globalThis.Capacitor` (sem import; testável em node).
- `src/http.ts`: envia `X-RPG-Client: android` em todo request (inclui upload de áudio via XHR).
- `AccountScreen`: no Android não consulta/mostra checkout Stripe (política); `src/purchases/`: interface `PurchaseAdapter`,
  `WebStripeAdapter`, `AndroidPlayAdapter` (lança `not_available_until_spec_194_native`), seleção por plataforma.
- `src/native/lifecycle.ts` + `backPolicy.ts` + `App.tsx`: back = ignora se há ação em curso/pendente, volta em conta/simulador, senão minimiza (nunca fecha);
  resume = revalida sessão (`/auth/config`; expirada => tela de login) e reconcilia operação pendente por `operation_id` (nunca reenvia sozinho).
- Pendência de ação já persistia em `localStorage` (`pendingOperation.ts`, `action_id` reutilizado por `preparePending`): sobrevive reload/process death (verificado no emulador). Nada novo necessário.
- Testes: `web/tests/native.test.mjs` (plataforma, seleção de adapter, back policy) + header em `http.test.mjs` (22 verdes).

## Permissões (manifest)
`INTERNET`, `RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS` (o `BridgeWebChromeClient` pede as duas de áudio juntas; sem declarar a segunda o pedido inteiro é negado).
`MainActivity` troca o WebChromeClient: `onPermissionRequest` só aceita `AUDIO_CAPTURE` e só para o host de `server.url` (https, mesma porta); câmera/MIDI/DRM/outros origins são negados; o prompt de runtime de RECORD_AUDIO continua vindo do cliente padrão.

## Secret scan do APK
`evidence/apk_secret_scan.json`: todos os entries (dex, assets/public, resources) varridos por sb_secret, service_role, JWT `eyJ…`, sk_/rk_ live/test, whsec_, DATABASE_URL, postgres://, AIza…, private key, pk_ Stripe, sb_publishable_, Turnstile secret => **0 achados**.

## Smoke em emulador (`evidence/emulator_smoke.json`, AVD `rpg34`, android-34 google_apis x86_64, headless)
Usuário sintético via Admin API (removido ao fim), WebView dirigido por CDP. Resultados: staging carregado remotamente (platform=android);
login pela UI (Turnstile de teste OK); cookies de sessão invisíveis ao JS (só `rpg_csrf`), nenhum token em web storage; jogo criado e 1 ação;
HOME -> relançar: sessão mantida e reenvio do mesmo `action_id` não duplica turno (op `completed`); force-stop: localStorage persiste, reenvio do mesmo id após novo login não duplica.
Telas: `evidence/0*.png`.

### Achados
1. **Process death exige novo login**: access/refresh/CSRF são cookies de sessão (SPEC-190, sem Max-Age) e o WebView os descarta ao reiniciar o processo. Background/resume (processo vivo) preserva. Resolvido no addendum abaixo (cookies persistentes + refresh único no boot).
2. **Microfone bloqueado pelo header** `Permissions-Policy: microphone=()` (api.py) — afetava também o voice input web. Corrigido para `microphone=(self)` (1 linha em api.py); **requer redeploy do staging e reexecução do check `mic_getUserMedia`** (hoje `NotAllowedError`).
3. O bundle de staging do primeiro smoke não continha as mudanças web desta spec; coberto no smoke v2 (redeploy).

## Ainda para SPEC-194 native / SPEC-198
- Plugin nativo Play Billing (`ProductDetails`, `setObfuscatedAccountId` via `/account/purchases/google/profile`, `queryPurchasesAsync` -> `/verify`) atrás do `AndroidPlayAdapter`.
- applicationId de produção, assinatura/keystore, AAB, Play Console; deep links só se auth/pagamento exigirem (hoje não).
- Redeploy + reteste de mic e do header; review Sol do boundary WebView/sessão.

## Decisoes do orquestrador (aplicadas)
1. **Sessao sobrevive a process death (achado 1):** com header `X-RPG-Client: android`, `_set_session_cookies` (api.py; login/signup/verify/refresh) define `Max-Age` no cookie de **refresh** e no **CSRF** (`rpg_csrf`) (env `RPG_ANDROID_REFRESH_MAX_AGE_SECONDS`, default 1209600 = 14 dias, clamp 3600..2592000). O cookie de access continua de sessao/curto; web inalterado. No boot nativo (Capacitor), se `/auth/config` diz nao autenticado, o app faz UM `POST /auth/refresh` (CSRF do cookie, mesma origem) e re-checa a config; nunca em loop. Logout/exclusao limpam o refresh (`Max-Age=0`). Risco aceito (spoofing do header): qualquer cliente pode enviar `X-RPG-Client: android` e ganhar cookies persistentes. Um site de outra origem nao consegue definir header customizado sem preflight CORS (que a API nao concede), e um atacante com XSS ja teria capacidade maior; os cookies sao `HttpOnly` (exceto CSRF por design)/`Secure`/`SameSite=Strict`, com path restrito, refresh rotacionado e revogado em logout/exclusao (SPEC-190). O header so altera a duracao do cookie, nunca autorizacao. Testes: `tests/test_account_lifecycle_security.py`.
2. **`.vercelignore`** exclui `web/android` e dirs de build (projeto nativo fora do upload; `test_spec192_vercel_packaging.py` verde).
3. **Microfone (achado 2):** `Permissions-Policy: camera=(), microphone=(self), geolocation=()` com teste. `getUserMedia` e governado por Permissions-Policy, nao por CSP (CSP nao tem diretiva de microfone). Ainda requer redeploy + reexecucao do check `mic_getUserMedia` no staging.

## Addendum 2026-10-15 (execução Claude)
Equivalência de modelo: Claude Opus 5.5 executou as correções do review independente (Sol: CHANGES_REQUIRED, opção (a)).
Correções: (1) `rpg_csrf` ganha o mesmo Max-Age do refresh para `X-RPG-Client: android`; logout/exclusão limpam os três cookies; boot nativo faz um único `POST /auth/refresh` antes de mostrar login (testes pytest + node). (2) `MainActivity` força `setWebContentsDebuggingEnabled(BuildConfig.DEBUG)` (`buildConfig` ligado no gradle). (3) `CAP_APP_ID` removido (ver Layout). (4) `file_paths.xml` sem `external-path` (só cache). (5) Topbar a 360px: ações ocupam linha própria e rótulos truncam com reticências. (6) Claims e risco de spoofing do header corrigidos acima.
O pacote de produto fica só com o contrato do SPEC-193; Stripe segue oculto no Android (`isAndroidClient`) — a política de servidor `_refuse_android_stripe` pertence ao SPEC-194.
Evidência do redeploy e do smoke v2: `evidence/emulator_smoke_v2.json`, `evidence/vercel_smoke_v2.txt`.
