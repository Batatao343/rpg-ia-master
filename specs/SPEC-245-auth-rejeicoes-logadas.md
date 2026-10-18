# SPEC-245 — Auth: toda rejeição logada com motivo interno (GoTrue, sessão, CSRF/Origin, captcha, lockout)

> **Status:** `in-progress` — implementado em 2026-10-18 (branch `logs-p0`); falta a revisão Sol obrigatória e o smoke em staging.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-239, SPEC-240; branch `auth-debug` mergeada (mapeia `email_not_confirmed`/`captcha_failed` — esta spec só adiciona LOG, não muda mapeamento)
> **Desbloqueia:** SPEC-262 (runbook auth)
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true — superfície de segurança/anti-enumeração`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** O incidente de 2026-10-18 (`credentials_invalid` cru na tela de recuperação) foi difícil de rastrear porque nenhum caminho de auth loga. `infrastructure/supabase_identity.py`, `oidc_identity.py`, `services/account_security.py`, `services/auth_sessions.py` têm **zero** chamadas de log. Cada não-200 do GoTrue colapsa num `Unauthorized` fixo descartando `status_code`/`error_code` (login `:54-55`, signup `:69-70`, refresh `:113-114`, logout `:125-126`, verify `:89-90`, reset `:98-99`, delete `:152-153`, `_verify_remote` `:257-258`). `_unauthorized_handler` diz que “a mensagem interna fica só no servidor” (`api.py:95-98`), mas ela não é logada. `_session_boundary` devolve 401/403/503 calado (`api.py:182-192`); `CsrfError` (`auth_sessions.py:70-81`) e `_require_allowed_origin` (`api.py:510-513`) idem; `validate_captcha` colapsa erro do Turnstile, mismatch de hostname/action e **queda da Cloudflare** em `captcha_invalid` (`account_security.py:66-90`); `auth_limit`/`_too_many` (lockout por e-mail/IP, `account_security.py:100-143`) devolve 429 sem log. Timeouts `httpx` no proxy viram 500 sem log. Só `auth.email_delivery_failed` (`api.py:572-579`) existe, e só com `status_class`.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `SupabaseIdentityProvider`: toda chamada ao GoTrue emite `auth.upstream` com `op` (`login|signup|refresh|logout|verify|reset|recover|delete|verify_token`), `upstream_status` (int), `upstream_code` (GoTrue `error_code`, catálogo fechado, desconhecido ⇒ `other`), `duration_ms`, `public_code` (o código devolvido ao cliente). Nível `info` sucesso, `warning` 4xx, `error` 5xx/timeout. `httpx.TimeoutException`/`HTTPError` ⇒ `upstream_status=0`, `error_type`, e resposta 503 `auth_unavailable` (não 500).
- **R2** — `_session_boundary` e `_unauthorized_handler`: `auth.session_rejected` com `reason` interno fechado (`missing|expired|bad_signature|bad_aud_iss|revoked|tombstoned|session_invalid|server_misconfigured`), `route`, `request_id`. Mapear as mensagens internas atuais (`contracts.py:43-59`) para `reason`.
- **R3** — CSRF/Origin: `auth.csrf_rejected` com `reason` (`origin_denied|csrf_invalid|csrf_missing`), `origin_host` **apenas** se estiver na allowlist ou `other` (nunca a origem crua desconhecida acima de 64 chars).
- **R4** — Captcha: `auth.captcha_rejected` com `reason` (`missing|turnstile_error:<codes do Turnstile>|hostname_mismatch|action_mismatch|provider_unavailable`). Queda da Cloudflare (`httpx.HTTPError`) deixa de ser `captcha_invalid` para o log (o código público pode continuar fail-closed).
- **R5** — Lockout/limites de auth: `auth.rate_limited` com `action`, `bucket` (`email|ip`), `key_ref` (pseudônimo HMAC — **não** o SHA-256 sem sal usado como chave de armazenamento), `retry_after_s`; métrica `rpg_auth_rejections_total{reason}` cobrindo R2–R5.
- **R6** — OIDC (`oidc_identity.py:84-171`): motivo fechado de falha de JWT (`bad_signature|expired|bad_iss|bad_aud|unknown_kid|jwks_unavailable`) no log.
- **R7** — Anti-enumeração preservada: nenhuma linha contém e-mail (nem hash sem sal); `upstream_code` não altera a resposta pública além do que a `auth-debug` já faz.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Mudança de mapeamento público de códigos (feito na `auth-debug`); política de senha (SPEC-220).

## 3. Design técnico

- **Alterados:** `infrastructure/supabase_identity.py` (wrapper `_call(op, ...)` cronometrado), `infrastructure/oidc_identity.py`, `services/account_security.py`, `services/auth_sessions.py`, `api.py` (handlers e boundary), `infrastructure/contracts.py` (mapa interno→reason).

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_auth_logging.py` com GoTrue fake (`httpx.MockTransport`): `test_login_400_logs_upstream_code_not_email`, `test_timeout_returns_503_and_logs`, `test_session_expired_reason`, `test_csrf_reason`, `test_turnstile_outage_reason_provider_unavailable`, `test_lockout_logged_with_key_ref`, `test_no_email_in_any_auth_log` (sentinela).

### Etapa 2 — Implementação

R1–R7.

### Etapa 3 — Verificação

`uv run pytest` verde; e2e de conta (`web/e2e/account-lifecycle.spec.ts`) verde.

## 5. Critérios de aceite

- [x] Cada rejeição de auth tem 1 linha com `reason`/`upstream_code` e `request_id`.
- [x] Nenhum e-mail/IP cru em log (teste).
- [x] Timeout do GoTrue ⇒ 503 `auth_unavailable`, não 500.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: login com senha errada, conta não confirmada, refresh com cookie expirado, POST sem CSRF — cada um aparece em `vercel logs` com `reason` distinto.

## 7. Riscos & compatibilidade

- Volume em ataque de força bruta: `auth.rate_limited` é amostrado (1 linha por `key_ref` por minuto) — contagem completa fica na métrica.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## 8. Notas de implementação

- Novo `observability/auth_log.py` (catalogo fechado de motivos, `reject`, `origin_host`, `rate_limited` amostrado 1 linha/key_ref/min) + metrica `rpg_auth_rejections_total{reason}`.
- `Unauthorized` ganhou `reason` opcional (so log); novo `AuthUnavailable` -> 503 `auth_unavailable` (codigo publico novo em `AUTH_ERROR_CODES`, `Retry-After: 5`).
- `SupabaseIdentityProvider._request`: toda chamada ao GoTrue emite `auth.upstream` (op, upstream_status, upstream_code do catalogo fechado ou `other`/`none`, duration_ms, public_code); timeout/erro de rede -> status 0 + `error_type` + 503. Sucesso em info (verify_token e reauth_logout em debug, para nao inundar). Mapeamento publico de codigos inalterado.
- `auth.session_rejected` no boundary e no handler de `Unauthorized` (reason: missing|expired|bad_signature|bad_aud_iss|revoked|session_invalid|upstream_rejected|server_misconfigured|unknown_kid|jwks_unavailable|bad_iss|bad_aud|upstream_unavailable); sem cookie de acesso o nivel e debug (bootstrap da SPA). `auth.csrf_rejected` (origin_denied|csrf_invalid|csrf_missing; `origin_host` so se na allowlist, senao `other`/`none`). `auth.captcha_rejected` (missing|turnstile_error:<codes sanitizados>|hostname_mismatch|action_mismatch|provider_unavailable|server_misconfigured). OIDC com reasons fechados.
- Desvio: o campo `action` do spec virou `op` nas linhas de captcha/rate_limited porque `action` e chave sensivel do `redact` (SPEC-222).
- Desvio: `key_ref` = HMAC (`pseudonym`) da chave de armazenamento do limiter (que ja contem digests sem sal); a chave crua nunca sai.
- Pendente: smoke em staging (senha errada, conta nao confirmada, refresh expirado, POST sem CSRF) e revisao Sol obrigatoria.
