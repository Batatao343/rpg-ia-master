# SPEC-220 — Sessão: revogação no logout, erros 401 consistentes, lockout por e-mail e OIDC

> **Status:** `draft`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** nenhuma · evolui SPEC-190/193 `done`; usa o `client_ip` da SPEC-219 se já existir, mas NÃO a exige (índice corrigido) (ordem final 2026-10-15)
> **Desbloqueia:** gate da SPEC-197; ativação futura de OIDC (ordem final 2026-10-15)
> **Origem:** auditoria de segurança 2026-10-15 — achados SESS-04, SESS-05/AUTHZ-08, SESS-07/AUTHZ-10(b), AUTHZ-09, INFRA-01, INFRA-07, INFRA-08
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — toca ciclo de vida de sessão (SPEC-190/193 tiveram review independente)
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Quatro pontos de sessão/autenticação ficaram abertos depois das SPEC-190/193:

1. **Logout não revoga quando o access expirou.** `auth_logout` só chama `identity_verifier.logout(access)` se o cookie de acesso existir; `logout()` faz `POST /auth/v1/logout?scope=global` com esse access e levanta `Unauthorized` se o GoTrue não devolver 2xx. Access vencido (vida ~1 h) ⇒ ou nada é revogado (cookie ausente) ou a rota devolve **500** (exceção não tratada) — em ambos os casos o **refresh** continua válido no servidor. No Android o refresh persiste 14 dias (SPEC-193), então um refresh roubado sobrevive ao "Sair".
2. **500 em vez de 401/403** quando o CSRF do logout falha: `_validate_auth_csrf` levanta `Unauthorized`/`ValueError` fora de qualquer `try`, e não existe `@app.exception_handler` para essas classes.
3. **Lockout direcionado**: `auth_limit` consome o bucket por e-mail (5/15 min) a cada tentativa, ANTES de validar a senha; 5 POSTs com o e-mail da vítima (de qualquer IP) bloqueiam o login/reset/verify dela por 15 min.
4. **Login em modo `app` sem checagem de Origin** (login CSRF, baixo); **OIDC** (perfis `hosted`/`portable`, não usados em produção) aceita qualquer token do mesmo IdP sem `aud`, sem `email_verified`, e assume `iss` quando ausente.

Fatos observados no HEAD:

- [F] `api.py:577-590` `auth_logout`: `_validate_auth_csrf(request)`; `access = request.cookies.get(ACCESS_COOKIE)`; `if access: get_runtime().identity_verifier.logout(access)`; depois `delete_cookie` ×5.
- [F] `infrastructure/supabase_identity.py:138-144` `logout()` → `httpx.post(.../auth/v1/logout?scope=global, headers=self._headers(access_token))`; `if status not in (200,204): raise Unauthorized`.
- [F] `grep -n exception_handler api.py` = 0. `_session_boundary` só cobre `/game|/account`; `/auth/*` fica fora do seu `try`.
- [F] `services/account_security.py:81-91` `auth_limit`: `for scope, value, limit in (("ip", remote, 20), ("email", email.casefold(), 5))` → `consume` incondicional; chamado em `api.py:297-300` antes de `identity_verifier.login`.
- [F] `api.py:282-306` `auth_login`: ramo `gotrue` chama `_auth_abuse` (Origin ∈ `_CORS_ORIGINS`); ramo `app` só `auth_limit`.
- [F] `infrastructure/oidc_identity.py:36-54`: `claimed_issuer = str(payload.get("iss") or self.issuer)`; validação = `GET userinfo` 200; sem `aud`/`azp`/`email_verified`/`alg`.
- [R] SPEC-190 cobre rotação do refresh no GoTrue e revogação global quando o access é válido; SPEC-193 definiu Max-Age de 14 dias do refresh no Android — esta spec não altera esses contratos, só fecha o caminho "access vencido".

Objetivo: "Sair" sempre encerra a sessão server-side (refresh incluído); rotas `/auth/*` respondem 401/403 determinísticos; o bucket por e-mail conta só falhas e nunca bloqueia um login correto; OIDC validado por JWT antes de ser habilitado.

## 2. Requisitos

- **R1** — `POST /auth/logout`: se o access está ausente ou inválido e há cookie de refresh, o servidor faz `refresh(refresh_cookie)` e então `logout(novo_access, scope=global)`; se o refresh também for inválido, responde 204 mesmo assim (idempotente) e apaga cookies. Nunca 500. Teste: verificador falso registra `logout` chamado com um access derivado do refresh.
- **R2** — Alternativa quando o GoTrue expõe Admin API (service role já está no backend): `identity_verifier.revoke_all(user_id)` via `POST /auth/v1/admin/users/{id}/logout` (ou `DELETE sessions`); usada quando o access é válido OU quando a prova recente/`rpg_deletion` identifica o owner. R1 cobre o caso sem access; R2 é defesa extra — ponto D-A.
- **R3** — Handler global `@app.exception_handler(Unauthorized)` → 401 `{"detail": <código estável>}`; `ValueError` levantado por `validate_mutation_request`/`CsrfSigner` → 403 `{"detail":"csrf_invalid"}`; mensagens não incluem detalhes internos (lista fechada de códigos: `session_missing`, `session_invalid`, `csrf_invalid`, `origin_denied`, `captcha_required`, `captcha_invalid`, `recent_session_required`, `account_delete_not_requested`). `_session_boundary` passa a reutilizar o mesmo mapeamento (hoje devolve `str(exc)`).
- **R4** — `auth_limit` para `login`: o bucket por e-mail é consumido **após** falha de credencial (`Unauthorized` do verificador), com limite 10/15 min, e um sucesso de login zera o bucket do e-mail (`rate_limiter.reset(key)` novo). Para `signup`/`reset`/`verify` (sem "falha" distinguível) mantém-se consumo por tentativa, mas com chave composta `(email, ip)` e limite 5/15 min, mais um bucket só-e-mail folgado (20/h) contra e-mail bombing. O bucket por IP (20/15 min) permanece como está.
- **R5** — `auth_login` modo `app` passa pela mesma checagem de Origin de `_auth_abuse` (extraída para `_require_allowed_origin(request)`); `captcha` continua conforme `captcha_config()`.
- **R6** — `OidcIdentityVerifier.verify`: valida JWT localmente com JWKS (`RPG_OIDC_JWKS_URL`, cache 10 min, `alg` allowlist `RS256/ES256`, rejeita `none`/`HS*`), `iss == RPG_OIDC_ISSUER` (obrigatório), `aud`/`azp` contém `RPG_OIDC_AUDIENCE` (obrigatório), `exp`/`nbf`, `email_verified == true` quando a claim existe; `userinfo` só complementa. `RuntimeConfig.validate` para `auth_mode=oidc` exige as três envs. Enquanto não implementado, `validate()` recusa `auth_mode=oidc` com `oidc_not_hardened` (fail-closed) — ponto D-B.
- **R7** — Testes de transporte existentes (`tests/test_account_auth_transport.py`, `tests/test_account_lifecycle_security.py`) continuam verdes; novos casos nomeados no §4.
- **R8** — (INFRA-01) `_session_boundary` chama `await call_next(request)` **fora** do `try/except (Unauthorized, ValueError)`: o `try` cobre só verificação de identidade e CSRF. `ValueError` de handler volta a ser 500 genérico do Starlette (contado como 5xx em `rpg_http_requests_total`); `ValueError` do `CsrfSigner`/`proof()` por segredo curto vira 503 `{"detail":"server_misconfigured"}` (sem a mensagem interna). Teste: rota de teste em `/game/_raise_value_error` (só no app de teste) → 500, nunca 401; corpo não contém `str(exc)`.
- **R9** — (INFRA-07) `scripts/staging/auth_config.py` passa a declarar e diffar no Auth remoto: `password_min_length>=10`, `refresh_token_rotation_enabled=true`, `security_refresh_token_reuse_interval=10`, `jwt_exp=3600`, `security_update_password_require_reauthentication=true`, `disable_signup=false`; `supabase/config.toml` espelha (`minimum_password_length=10`, `[auth.password_requirements]`). `AuthRequest.password` passa a `min_length=10` (mensagem no front). O script valida que `uri_allow_list` não contém `*` nem `http://` fora de localhost.
- **R10** — (INFRA-08) Falhas de Origin/CSRF respondem **403** `csrf_invalid`/`origin_denied` (não 401), para que o cliente não dispare refresh/logout; `web/src/http.ts` trata 403 desses códigos como "recarregue a página" e não como sessão expirada.

### Fora de escopo

- Max-Age do refresh Android (SPEC-193, risco aceito).
- Vincular o token CSRF à sessão (SESS-10, descartado).
- Rate limit por owner/IP real (SPEC-219).

## 3. Design técnico

- **Arquivos alterados**
  - `api.py`: `auth_logout` (R1/R2), `exception_handler`s (R3), `_session_boundary` usa `error_code(exc)`, `auth_login` (R5), `auth_limit` chamadas reordenadas (R4).
  - `infrastructure/contracts.py`: `Unauthorized(code: str, detail: str = "")` com `code` da lista fechada; `CsrfError(ValueError)`.
  - `services/auth_sessions.py`: `validate_mutation_request` levanta `CsrfError("csrf_invalid"|"origin_denied")`.
  - `infrastructure/supabase_identity.py`: `logout_via_refresh(refresh_token)`, `revoke_all(user_id)` (Admin API, service role), ambos tolerantes a 401/404 (sem exceção).
  - `infrastructure/postgres_turns.py`: `PostgresRateLimiter.reset(key)`; `local_adapters` idem.
  - `services/account_security.py`: `auth_limit(..., stage="attempt"|"failure")`, `auth_success(runtime, email)`.
  - `infrastructure/oidc_identity.py` + `infrastructure/runtime.py` (R6).
- **Assinaturas**
  ```python
  def auth_limit(runtime, request, *, action: str, email: str = "", stage: str = "attempt") -> None
  def auth_success(runtime, *, action: str, email: str) -> None
  class SupabaseIdentityVerifier:
      def logout_via_refresh(self, refresh_token: str) -> bool
      def revoke_all(self, user_id: UUID) -> bool
  ```
- **Códigos de erro** (R3): tabela fechada em `infrastructure/contracts.py:AUTH_ERROR_CODES`; teste de que toda `Unauthorized(...)` levantada no código usa um código da tabela (grep via AST em `tests/test_auth_error_codes.py`).

## 4. Plano passo a passo

### Etapa 0 — Reprodução (vermelhos no HEAD)

1. **Testes** (`tests/test_session_hardening.py`): `test_logout_with_expired_access_leaves_refresh_valid` (verificador falso: `logout` levanta `Unauthorized`; afirmar que a rota devolve 5xx hoje e que `refresh(...)` continua aceito); `test_logout_bad_csrf_returns_500_today`; `test_login_email_bucket_counts_successful_attempts` (5 logins corretos → 6º 429); `test_oidc_accepts_token_without_aud` (se o perfil for instanciável em teste). Registrar vermelho.

### Etapa 1 — Erros 401/403 consistentes (R3)

1. **Testes:** `test_auth_error_codes_closed_set`, `test_logout_bad_csrf_403`, `test_session_boundary_401_code_only` (resposta não contém `str(exc)` interno).
2. **Implementação:** handlers + códigos.

### Etapa 2 — Logout revoga via refresh / Admin API (R1, R2)

1. **Testes:** `test_logout_expired_access_uses_refresh_then_global_logout`, `test_logout_without_any_cookie_is_204`, `test_logout_revoke_all_when_available` (Admin API mock), `tests/test_account_auth_gotrue_local.py` ganha caso real contra GoTrue local: login → expirar access (relógio/JWT curto) → logout → `refresh` devolve 401.
2. **Implementação:** §3.

### Etapa 3 — Lockout (R4) + Origin no login `app` (R5)

1. **Testes:** `test_login_success_does_not_consume_email_bucket`, `test_login_failures_lock_after_10`, `test_login_success_resets_email_bucket`, `test_signup_bucket_is_email_ip_composite`, `test_login_app_mode_requires_origin`.
2. **Implementação:** §3. **Verificação:** `uv run pytest tests/test_session_hardening.py tests/test_account_* -q`.

### Etapa 4 — OIDC (R6)

1. **Testes** (`tests/test_oidc_identity.py`): JWKS falso (chave RSA de teste gerada no teste), `aud` errado → 401, `alg=none` → 401, `iss` ausente → 401, `email_verified=false` → 401, feliz → `Principal`; `RuntimeConfig` recusa `oidc` sem envs.
2. **Implementação:** §3 (`python-jose`/`PyJWT` já disponíveis? Verificar `uv.lock`; preferir `PyJWT[crypto]` se nenhum existir — dependência nova exige aprovação, D-B).
3. **Verificação:** `uv run pytest -q` completo.

## 5. Critérios de aceite

- [ ] Etapa 0 vermelha no HEAD, verde ao final; R1–R7 cobertos; `uv run pytest` verde; GoTrue local (`-m infra_local`) verde no caso de logout.
- [ ] Nenhuma rota `/auth/*` devolve 5xx para entrada do cliente (teste fuzz leve: cookies/headers vazios, inválidos, CSRF errado).
- [ ] Smoke staging: login → esperar/forçar expiração do access (ou apagar o cookie `rpg_access` no DevTools) → "Sair" → `POST /auth/refresh` manual com o refresh antigo = 401.
- [ ] 5 logins corretos seguidos do mesmo e-mail não geram 429; 11 senhas erradas geram 429; login correto depois de 3 erros zera o contador.
- [ ] Revisão Sol independente APPROVED.

## 6. Smoke test

Staging, sem LLM: fluxo de logout acima (2 contas); lockout com senha errada ×11 → 429; e-mail bombing: 21 `reset/request` para o mesmo e-mail em 1 h de IPs distintos → 429 a partir do 21º (bucket folgado) sem bloquear login da vítima.

## 7. Riscos & compatibilidade

- **Android**: o app faz UM `POST /auth/refresh` no boot (SPEC-193); R1 não muda isso. Logout agora pode demorar 1 round-trip extra (refresh+logout).
- **GoTrue Admin API** exige service role (já no backend); se indisponível, R1 basta.
- **Bucket só-falhas** permite enumeração mais lenta? Não: mensagens continuam genéricas e o bucket por IP (20) permanece.
- **Dependência nova** para JWT (R6) só se necessário — D-B.

## 8. Pontos de decisão do dono

- **D-A (Admin API no logout):** usar `revoke_all` sempre que o owner for conhecido. **Default recomendado:** sim (defesa extra barata).
- **D-B (OIDC agora ou fail-closed):** implementar R6 completo ou apenas bloquear `auth_mode=oidc` até haver uso. **Default recomendado:** bloquear agora (fail-closed, 1 linha + teste) e implementar R6 quando um perfil OIDC entrar no roadmap.
- **D-C (limites):** 10 falhas/15 min por e-mail; 20/h só-e-mail para signup/reset. **Default recomendado:** adotar.

## 9. Evidência requerida

- Saída de `uv run pytest` completa + `-m infra_local` (GoTrue local) com o caso de logout; vermelhos da Etapa 0.
- Transcrição do smoke §6 (status codes), `docs/secXX/README.md` com tabela de códigos de erro e decisões D-A..D-C; parecer Sol em `handoffs/`; atualização de `ESTADO_ATUAL.md`/`ROADMAP.md`.
