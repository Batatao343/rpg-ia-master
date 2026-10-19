# SPEC-243 — Frontend: mapa central código→mensagem e “código de suporte” (request_id) em todo erro

> **Status:** `in-progress` — implementada em `logs-p1` (REVIEW_REQUIRED; smoke staging pendente)
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-241, SPEC-242; branch `auth-debug` mergeada (`web/src/lib/authErrors.ts`)
> **Desbloqueia:** SPEC-262 (runbook “usuário reportou erro”)
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `web/src/http.ts` monta `HttpError` com `message = detail` cru (`http.ts:39`, `65-86`); só há mapeamento pontual (429/503 `rateLimitNotice` `http.ts:9-21`, CSRF `62-63`, voz `146-150`, e agora `authErrors.ts` na branch `auth-debug`). `errMsg(err)` (`App.tsx:931`) exibe `err.message` em banners (`App.tsx:236,291,366,388,411`; `CreateScreen.tsx:86,125,150`; `CombatSimulatorScreen.tsx:40`) — foi assim que `credentials_invalid` apareceu cru. O cliente **nunca lê** `X-Request-ID` (grep só acha `Retry-After`, `http.ts:75`): um usuário não tem como informar ao suporte qual requisição falhou.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `HttpError` ganha `requestId` (header `X-Request-ID` ou `body.request_id`) e `code` (`body.code` ?? `detail` se for snake_case).
- **R2** — `web/src/lib/errorMessages.ts`: mapa único `code → mensagem pt-BR`, absorvendo `authErrors.ts`, `rateLimitNotice`, `STALE_PAGE_CODES` e o mapa de voz; código desconhecido ⇒ mensagem genérica (“Algo deu errado.”) — **nunca** o código cru. Teste Node garante que todo código do catálogo da SPEC-242 tem entrada (lista exportada pelo backend como JSON gerado).
- **R3** — Todo banner/toast de erro mostra “Código de suporte: `<8 primeiros chars do request_id>`” com botão copiar (o id completo vai para a área de transferência). Acessível (`aria-live`), sem quebrar 390px.
- **R4** — O cliente envia `X-Request-ID` próprio (uuid v4) em toda chamada, para que falhas de rede sem resposta também tenham id local exibível; o servidor já aceita (`telemetry.py:60-62`).
- **R5** — SSE: erro do stream exibe o mesmo código de suporte (`request_id` do evento de erro).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Captura automática de erros do cliente (SPEC-244); textos de UX finais (revisão de copy à parte).

## 3. Design técnico

- **Novo:** `web/src/lib/errorMessages.ts`, `web/src/components/SupportCode.tsx`. **Alterados:** `web/src/http.ts`, `web/src/api.ts`, `App.tsx` (`errMsg`), telas com banners.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`web/tests/errorMessages.test.mjs` (cobertura do catálogo, desconhecido ⇒ genérico); e2e `web/e2e/support-code.spec.ts` (login inválido mostra mensagem amigável + código de suporte, nunca `credentials_invalid`).

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`npm run build`, testes Node e e2e verdes; `uv run pytest` verde.

## 5. Critérios de aceite

- [x] Nenhum código snake_case cru visível na UI (e2e varre banners).
- [x] Todo erro mostra código de suporte copiável.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: senha errada, jogo inexistente, 429 — mensagens amigáveis + código; buscar o código em `vercel logs` acha a linha `http.request`.

## 7. Riscos & compatibilidade

- Coordenar com o merge da `auth-debug` (não duplicar o mapa de auth; absorver).
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## Execução (logs-p1, 2026-10-18)

Implementado: `web/src/lib/errorMessages.ts` (mapa único código→pt-BR, cobre todo o catálogo da 242 via `errorCodes.json`; absorve `authErrors.ts`, `rateLimitNotice`, `STALE_PAGE_*` e o mapa de voz), `HttpError.requestId`, `X-Request-ID` do cliente em toda chamada (inclui falha de rede e upload de voz), SSE com `request_id`/`error_code`, `components/SupportCode.tsx` (código de suporte copiável) em Banner e AuthScreen. Testes: `web/tests/errorMessages.test.mjs`, e2e `web/e2e/support-code.spec.ts` (Chromium empacotado). Desvio: prosa pt-BR vinda do servidor é preservada (só código cru/desconhecido vira mensagem do mapa/genérica). Falta o smoke de staging (§6) e a revisão Sol; jornada crítica não precisou de adaptação.
