# Revisão Sol independente — SPEC-239 / 240 / 241 / 245 (logging P0)

- **Revisor:** Sol (Claude Opus 5.5), independente — não escreveu as specs nem a implementação.
- **Data:** 2026-10-18. **Branch:** `logs-p0`, rebaseada em `main` `5695cb4` (fix Jev warm-up incluído).
- **Commits revisados:** `caa259c` (239), `d65c085` (240), `ae672f4` (241), `77454df` (245).
- **Correções do revisor:** `97e5a27`, `e5b3a4f`, `e448de4`, `358c628` (detalhe abaixo).
- **Veredito:** **APPROVED** (com as correções abaixo já aplicadas e testadas) + smoke staging verde.

## Escopo verificado

| Tema | Resultado |
|---|---|
| PII/segredos (e-mail, token, cookie, texto do jogador, nome do personagem, IP, ids crus) | Sentinela num turno completo POST + SSE + 404 (`tests/test_logging_review_239_245.py::test_full_turn_has_no_pii_sentinels`): nenhuma ocorrência. Teste AST SPEC-222 (`test_no_print_in_production`) verde. Staging: 0 e-mail, 0 IPv4, 0 UUID cru, 0 texto de ação nas linhas JSON. |
| Correlação entre threads | Thread SSE (`contextualize`) e pool/callback tardio do Jev carregam `request_id`/`action_ref` do request. Sem vazamento entre requisições: thread worker reutilizada do anyio (CapacityLimiter=1) não herda `bind_correlation` do request anterior; 8 threads concorrentes mantêm o próprio contexto. Staging: linhas `jev.primary` (pool) com o mesmo `action_ref` do `turn`. |
| Ordem de middleware | `_correlation_boundary` registrado por último = mais externo. `X-Request-ID` confirmado em 401 (boundary), 404, 413/429 (testes), 422, 500 (handler), SSE e respostas do CORS. |
| Handler global 500 | Responde `{"detail":"internal_error","code":"internal_error","request_id"}`; log com `error_type` + `stack` `módulo:linha` sem mensagem (teste com `RuntimeError("segredo-XYZ")`). |
| Forma HTTPException/422 vs. web | Corpo preserva `detail` e só acrescenta `request_id`; `web/src/http.ts`/`formatDetail` ignoram o campo extra. `npm test` 127/127; build Vite verde; Playwright Python `test_browser_local` (Chromium empacotado, API em :8210) 2/2. |
| Auth: motivos fechados / anti-enumeração | `session_rejected` (catálogo fechado), `csrf_rejected` (origem só se allowlist), `captcha_rejected`, `auth.upstream` com `upstream_code` fechado (`other`), `auth.rate_limited` com `key_ref` HMAC. Nenhum e-mail nem hash sem sal. Respostas públicas inalteradas. GoTrue timeout → 503 `auth_unavailable`. |
| Amostragem do rate-limit | 1 linha por `key_ref`/min; dicionário limpo acima de 2000 chaves (memória limitada). |
| Cardinalidade de métrica | **Defeito corrigido** (abaixo). `rpg_auth_rejections_total{reason}` agora só com prefixo fechado. |
| Volume | Staging (DeepSeek + Jev primary), após correções: **3–7 linhas JSON por turno SSE (média ≈4,2)** — `http.request`, `turn`, `turn_delivery`, `jev.primary`, eventual `npc.creating`/`storyteller.*`; zero linha não-JSON de `httpx`. Offline MockLLM: 3 (POST) / 4 (SSE). |
| Setup idempotente (Vercel warm) | Marcador no handler; `configure_logging` chamado em `vercel_app` + import de `api` não duplica (teste). Filtro de terceiros também idempotente (teste). |
| Worker/cron | `workers/run_worker.py` chama `configure_logging`; cron roda dentro da API (Vercel) — linhas `rpg.cron` JSON vistas no staging. |

## Defeitos encontrados e corrigidos (com testes)

1. **Cardinalidade aberta na métrica** — `reason="turnstile_error:<codes>"` virava rótulo de `rpg_auth_rejections_total` (códigos vindos do provider). Agora o rótulo é só o prefixo fechado; os códigos ficam apenas no log. (`observability/auth_log.py`)
2. **Logs legados `%s` com id cru/IP** — ex.: `encounter.manifest_rebuilt game=<uuid>`. O formatter agora pseudonimiza UUIDs (`ref:<pseudônimo>`) e mascara IPv4 nas linhas legadas. (`observability/logging_setup.py`)
3. **Ruído de access log** — GET de navegação da SPA (`/`, rotas client-side) e `/auth/config` passam a `debug`.
4. **Linhas não-JSON de terceiros no Vercel** — o root logger da Vercel publicava `httpx`/`httpx2` (cliente do SDK openai) em INFO: ~4 linhas por turno com URL completa. Agora um filtro (não só nível — o SDK openai re-sobe o nível no import) as limita a WARNING fora de `RPG_LOG_LEVEL=debug`. Banner `Embeddings ativos` (2×/turno) rebaixado a debug.
5. **UX do 503 novo** — `auth_unavailable` caía na mensagem genérica; agora mostra "serviço de contas indisponível" (`web/src/lib/authErrors.ts` + teste Node).

## Smoke staging (Vercel `rpg-ia-master-staging` + Supabase `uzeagzcyvxzrpjgrhaql`)

- Deploy final `358c628` (`GIT_SHA` injetado; `/health` confere, `hardened=true`, perfil `hosted-supabase`). Env vars não alteradas (Jev `primary` mantido — 3/3 `jev.primary` decididos, p50 ≈ 280 ms).
- `e2e_session`: login, cookies, CSRF, novo jogo, **5 turnos SSE**, retry com mesmo `action_id`, estado, logout — todos verdes; limpeza do script (jogo + usuário) OK; varredura de usuários sintéticos: 0 restante.
  - `signup_captcha=false` **não é regressão desta branch**: `main` (`15cfd6a`, auth-debug) passou a responder 403 `captcha_invalid` ao token dummy; a expectativa 202 do script ficou desatualizada (follow-up: atualizar o check).
- Logs Vercel (`vercel logs --json`): toda linha JSON tem `event`/`level`/`logger`/`ts`/`request_id`; turnos com `action_ref` consistente.
  - 401 forçado (cookie inválido, `X-Request-ID: sol-review-401c`): `auth.session_rejected reason=bad_signature public_code=session_invalid source=boundary` + `http.request status=401 error_code=session_invalid`; header ecoado.
  - 404 forçado (`/data/nao-existe-review`): corpo `{"detail":"Not Found","request_id":"sol-review-404c"}`, header ecoado, `http.request status=404 level=warning`.
  - 401 sem cookie e 404 fora de rotas de API ficam em `debug` (anti-ruído, R1) — não aparecem em `info`.

## Follow-ups (não bloqueiam)

- Cliente web não envia `X-RPG-Client: web` → `client=unknown` no access log (só Android identifica).
- Linhas legadas `%s` restantes (`rpg.rag`, `rpg.encounter`, `rpg.npc_knowledge` info por turno) — migrar para `log_event`; `rag.py` ainda loga `str(exc)` em 2 pontos de warning (pré-existente).
- `scripts/staging/e2e_session.py`: atualizar a expectativa do probe de captcha para 403.
- Campos legados `owner_id_ref`/`game_id_ref` duplicam `owner_ref`/`game_ref` (1 release, como a spec prevê).

## Rollback

- Ruído/volume: `RPG_LOG_LEVEL=warning` (ou `RPG_LOG_LEVEL_<AREA>=warning`) + redeploy.
- Regressão funcional: `npx vercel@64.2.0 promote <deploy anterior>` — anterior a esta branch: `rpg-ia-master-staging-bi7io32h1-guilherme-medeiros-projects.vercel.app` (sha `9763ef6`).
