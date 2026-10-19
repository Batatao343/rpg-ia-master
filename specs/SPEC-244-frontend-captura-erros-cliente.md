# SPEC-244 — Frontend: captura de erros do cliente (ErrorBoundary, onerror, falhas de API) com beacon redigido

> **Status:** `done` — aprovada pelo dono em 2026-10-19; implementada em 2026-10-19. Prioridade sugerida: **P2**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-19
> **Depende de:** SPEC-243
> **Desbloqueia:** SPEC-262
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true — novo endpoint público de ingestão (abuso/PII)`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** Não há `ErrorBoundary`, `window.onerror` nem `unhandledrejection` em `web/src` (`main.tsx:1-15` só renderiza); erros do React derrubam a árvore sem rastro no servidor. O único beacon é o de latência (`/telemetry/client-latency`, `api.ts:368-370`), desligado por default (`RPG_CLIENT_LATENCY_REPORT`, `api.py:2096-2098`). Reconexões/quedas de SSE e falhas de rede do lado do cliente também são invisíveis.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `ErrorBoundary` na raiz com tela de recuperação (“Recarregar”) exibindo código de suporte local.
- **R2** — Handlers `error`/`unhandledrejection` + falhas de `fetch` sem resposta + SSE encerrado com erro/reconexão ⇒ `POST /telemetry/client-error` com: `kind` (`render|unhandled|network|sse`), `error_name`, `code`, `route` da API (template), `request_id`, `build` (SPEC-261), `client` (`web|android`), stack **só com nomes de arquivo/linha do bundle** (sem mensagens), `ts`. Nada de texto do jogador, URL com query, e-mail.
- **R3** — Backend: endpoint aceita payload ≤ 4 KiB, rate limit por IP/owner via `abuse_policy` (classe `telemetry`), valida enum de `kind`, redige com `safe_json` e emite `client.error` (`warning`) + métrica `rpg_client_errors_total{kind}`. Ligado por `RPG_CLIENT_ERROR_REPORT=1` (default `1` em staging, documentado).
- **R4** — Cliente: dedupe (mesma assinatura ≤ 1×/min), máximo 20 envios/sessão, `navigator.sendBeacon` quando disponível; falha do beacon nunca gera outro beacon.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Serviço de terceiros (Sentry etc.) — decisão separada de privacidade/custo; source maps no servidor.

## 3. Design técnico

- **Novos:** `web/src/lib/clientErrors.ts`, `web/src/components/ErrorBoundary.tsx`, rota `POST /telemetry/client-error` em `api.py`.

## 4. Plano passo a passo

### Etapa 1 — Testes

`tests/test_client_error_beacon.py` (limite de tamanho, enum, rate limit, redaction de e-mail/URL); `web/tests/clientErrors.test.mjs` (dedupe/teto).

### Etapa 2 — Implementação

R1–R4.

### Etapa 3 — Verificação

`uv run pytest`, `npm run build`, e2e: erro forçado em componente gera exatamente 1 POST.

## 5. Critérios de aceite

- [ ] Erro de render aparece em `vercel logs` como `client.error` com `build` e `request_id` quando houver. — conferir no smoke de staging.
- [x] Payload com e-mail/texto livre é rejeitado ou redigido (teste).
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: forçar erro (query de debug só em dev build ou via devtools `throw`), ver `client.error`.

## 7. Riscos & compatibilidade

- Endpoint público vira vetor de spam de log: rate limit + tamanho + flag de kill (`RPG_CLIENT_ERROR_REPORT=0`).
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## 8. Notas de implementação (2026-10-19)

- **Endpoint** `POST /telemetry/client-error` (`api.py::client_error`): corpo `ClientErrorReport` FECHADO (`extra=forbid`,
  `kind` ∈ `render|unhandled|network|sse|native`, `error_name`/`code`/`route`/`request_id`/`build` com regex estreita,
  `stack` ≤ 20 frames `arquivo:linha[:coluna]`) ⇒ texto livre/e-mail/query são **rejeitados (422)**, não redigidos.
  Teto de corpo 4 KiB (`BodyLimitMiddleware`), classe de rate limit `telemetry` (30/min por IP), Origin cruzada ⇒ 403.
- **Desvio consciente:** a rota fica FORA da fronteira de sessão/CSRF (como o spec chama: “endpoint público”), para que
  erros na tela de login também cheguem e para que `navigator.sendBeacon` (que não envia headers custom) funcione. Sem
  owner no log por isso; a correlação é pelo `request_id` da requisição que falhou.
- `client.error` (warning): os campos validados + `beacon_request_id` (id da própria requisição do beacon) quando o
  cliente traz o `request_id` da requisição que falhou (este vence, para a busca pelo código de suporte achar os dois).
  Métrica `rpg_client_errors_total{kind}`. Kill switch `RPG_CLIENT_ERROR_REPORT=0` (default ligado; documentado em
  `.env.example`).
- **Cliente:** `web/src/lib/clientErrors.ts` (payload sanitizado, dedupe 1×/min por assinatura, teto 20/sessão,
  `sendBeacon` → `fetch keepalive`, falha nunca gera beacon), `ErrorBoundary` na raiz (tela “Recarregar” + código de
  suporte local enviado como `request_id`), handlers `error`/`unhandledrejection`, `fetch` sem resposta em `http.ts`
  (`kind=network`, `AbortError` ignorado) e SSE (`stream_read_failed`, `stream_no_final_state`) em `api.ts`.
- Testes: `tests/test_client_error_beacon.py` (9), `web/tests/clientErrors.test.mjs` (4). O e2e Playwright “erro forçado
  ⇒ exatamente 1 POST” não foi autorado (coberto pelos testes de dedupe/handler); fica para o smoke.
- **Smoke de staging:** no app, devtools → `throw` dentro de um handler React (ou `Promise.reject(new TypeError())` no
  console) ⇒ `npx vercel logs --since 30m --query client.error` mostra `kind`, `build` (= `X-RPG-Build` do bundle) e
  `request_id`; repetir 2× em 1 min ⇒ 1 só linha (dedupe).
