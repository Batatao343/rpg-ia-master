# SPEC-259 — Android: códigos distintos de billing com debugMessage, console do WebView em debug e versão do app nas requisições

> **Status:** `draft` — aguardando aprovação do dono. Prioridade sugerida: **P3**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
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

- [ ] Cada falha de billing tem código distinto + `debugMessage` no JS e no logcat.
- [ ] `app_version` aparece no access log.
- [ ] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [ ] Saves antigos continuam carregando.

## 6. Smoke test

1. AVD `rpg34` com Billing fake: cancelar compra ⇒ código `billing_user_canceled`/equivalente com responseCode; requisição carrega `X-RPG-App-Version`.

## 7. Riscos & compatibilidade

- Data Safety: logcat local só; nada sai do aparelho além do header de versão.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.
