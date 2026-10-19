# SPEC-261 — Build id ponta a ponta: sha automático no `/health`, build do bundle web e header `X-RPG-Build`

> **Status:** `done` — aprovada pelo dono em 2026-10-19; implementada em 2026-10-19. Prioridade sugerida: **P2**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-19
> **Depende de:** SPEC-249
> **Desbloqueia:** SPEC-243 (código de suporte com build), SPEC-244, SPEC-259
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `/health` (`api.py:2085-2092`) lê `GIT_SHA` ou `VERCEL_GIT_COMMIT_SHA`, mas deploys por CLI exigem `-e GIT_SHA=…` manual (`docs/spec192/README.md:14`) — esquecido, vira `""`. O bundle web não tem build id (nada em `web/vite.config.ts`/`web/src` injeta versão). Um relato de bug não diz qual frontend falou com qual backend; erros pós-deploy (cliente velho em cache × API nova) são indistinguíveis.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `vite.config.ts` define `__RPG_BUILD__` = sha curto (`VERCEL_GIT_COMMIT_SHA` ou `git rev-parse --short HEAD` no build) + timestamp; exposto em `web/src/build.ts`.
- **R2** — O cliente envia `X-RPG-Build` em toda requisição; o access log (SPEC-241) registra `client_build` e, quando diferente do `git_sha` do servidor, `build_skew=true`.
- **R3** — Script de deploy de staging (`scripts/staging/*`) passa `GIT_SHA` automaticamente; `/health` com `git_sha` vazio em perfil hosted gera `runtime.config_warning` (SPEC-249).
- **R4** — Tela de conta/rodapé mostra `build` (curto) para o usuário copiar em relatos.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Forçar reload em skew (feature de produto separada).

## 3. Design técnico

- **Alterados:** `web/vite.config.ts`, `web/src/http.ts`, `web/src/build.ts` (novo), `api.py` (access log), `scripts/staging/vercel_deploy*.py` (ou equivalente).

## 4. Plano passo a passo

### Etapa 1 — Testes

`web/tests/build.test.mjs` (define presente); `tests/test_api_access_log.py::test_build_skew_flag`.

### Etapa 2 — Implementação

R1–R4.

### Etapa 3 — Verificação

`npm run build`; `uv run pytest`.

## 5. Critérios de aceite

- [x] Toda requisição do web carrega `X-RPG-Build` (teste `web/tests/build.test.mjs`). [ ] `/health` nunca vazio em staging — conferir no próximo deploy (smoke).
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: `curl /health` mostra sha do deploy; abrir o app e ver `client_build` no `http.request`.

## 7. Riscos & compatibilidade

- Nenhum.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## 8. Notas de implementação (2026-10-19)

- `web/scripts/buildId.mjs::computeBuildId` → `<sha7>+<AAAAMMDDhhmm UTC>` (`VERCEL_GIT_COMMIT_SHA` > `GIT_SHA` > `git
  rev-parse` > `dev`; valor fora de hex vira `dev`). `vite.config.ts` injeta em `__RPG_BUILD__`; `web/src/build.ts` expõe
  `BUILD_ID`/`buildShort()`.
- `http.ts` envia `X-RPG-Build` em toda requisição (inclusive upload de voz). CORS aceita `x-rpg-build` e
  `x-rpg-app-version`.
- Access log `http.request`: `client_build` (formato fechado; fora do formato ⇒ `other`) e `build_skew=true` só quando o
  sha do bundle não é prefixo do `GIT_SHA`/`VERCEL_GIT_COMMIT_SHA` do servidor.
- R3: `scripts/staging/s192.vercel` acrescenta `-e GIT_SHA=<HEAD> --build-env GIT_SHA=<HEAD>` a todo `deploy` que não o
  traga (`deploy_args`, testado). O aviso `runtime.config_warning code=git_sha_missing` já existia (SPEC-249) e vale para
  qualquer perfil.
- R4: tela de Conta mostra "Versão do app: `<sha7>`".
- Smoke de staging: `curl https://<staging>/health` ⇒ `git_sha` igual ao commit do deploy; abrir o app e conferir
  `http.request` com `client_build=<sha7>+…` e sem `build_skew`.
