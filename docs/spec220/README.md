# SPEC-220: evidência (sessão, logout, lockout, OIDC)

Estado: **in-progress**. Implementação, gates locais e revisão Sol (APPROVED) concluídos.
Faltam o smoke de staging (§6) após o deploy e a aplicação da política de Auth no
projeto remoto pelo dono.

## O que mudou

| Req | Mudança |
|---|---|
| R1 | `POST /auth/refresh/logout` (alias de `/auth/logout`). O cookie de refresh tem path `/auth/refresh`, então só esse alias o recebe. Com o access ausente ou inválido, o servidor faz `refresh(refresh_cookie)` e chama `logout(novo_access)` (scope global). Refresh inválido ou upstream fora do ar resultam em 204 idempotente, com os cookies apagados. O front (`api.logout`) usa o alias. |
| R2 (D-A) | `SupabaseIdentityProvider.revoke_all(user_id)` chama `app.runtime_revoke_auth`, a mesma função privilegiada da exclusão de conta (SPEC-190). Roda sempre que o owner é conhecido. **Desvio:** o GoTrue não tem logout-por-id na Admin API, por isso a revogação usa o banco. |
| R3 | `AUTH_ERROR_CODES` + `public_auth_code()` em `infrastructure/contracts.py`. Handlers globais: `Unauthorized`→401, `CsrfError`→403, `SessionSecretError`→503. `_session_boundary` e as rotas `/auth/*` só devolvem códigos da lista fechada. |
| R4 (D-C) | Login: o bucket de falhas, com chave **(e-mail, IP)** desde a revisão Sol, é só inspecionado (`peek`) na tentativa, consumido só em falha de credencial (10/15 min) e zerado no sucesso (`reset`). Falhas de um IP atacante não trancam a vítima em outro IP. Signup/reset/verify: bucket `(e-mail, IP)` 5/15 min + só-e-mail 20/h. IP 20/15 min inalterado. A exclusão de conta apaga também os buckets `(e-mail, IP)` por prefixo. |
| R5 | `_require_allowed_origin` antes do login no modo `app`, devolvendo 403 `origin_denied` (antes `origin_invalid`). |
| R6 (D-B) | OIDC validado localmente via JWKS (RS256/ES256; `none`/`HS*` recusados; `iss` exato; `aud`/`azp`; `exp`/`nbf`; `email_verified`). Usa só `cryptography`, já dependência core. `auth_mode=oidc` exige `RPG_OIDC_ISSUER`, `RPG_OIDC_JWKS_URL` e `RPG_OIDC_AUDIENCE` (fail-closed). UserInfo passou a ser opcional e só complementa. **Desvio de D-B:** sem dependência nova, implementar R6 completo também é fail-closed e não quebra os perfis `portable`/`hosted`. |
| R7 | Testes de transporte e de ciclo de vida continuam verdes. |
| R8 | `call_next` fora do `try` no `_session_boundary`: `ValueError` de handler vira 500 genérico; segredo curto vira 503 `server_misconfigured`. |
| R9 | `scripts/staging/auth_config.py` declara e diffa `SESSION_POLICY` e recusa `uri_allow_list` com `*` ou `http://` fora de localhost. `supabase/config.toml`: senha mínima 10, rotação de refresh e reuse 10 s. Signup e reset exigem ≥10 caracteres. **Desvio:** o login aceita ≥8, para não trancar contas com senha legada. |
| R10 | Falha de Origin/CSRF devolve 403 `csrf_invalid`/`origin_denied`. `web/src/http.ts` mostra "recarregue a página", sem refresh e sem `rpg:auth-expired`. |

Também corrigido: `hmac.compare_digest` com str não-ASCII levantava `TypeError` (500) no CSRF. Agora compara bytes.

## Códigos de erro (lista fechada)

`session_missing`, `session_invalid`, `csrf_invalid`, `origin_denied`, `captcha_required`,
`captcha_invalid`, `recent_session_required`, `account_delete_not_requested`,
`credentials_invalid`, `link_invalid_or_expired`, `signup_failed`, `password_reset_failed`,
`account_deleted`, `server_misconfigured`.

## Testes

- Etapa 0: no HEAD `f98b12e`, `tests/test_session_hardening.py` deu 21/21 vermelho (logout 500, CSRF 500/401, bucket contando sucesso, ausência de Origin no login, senha 9 aceita, etc.).
- Novos: `tests/test_session_hardening.py` (23), `tests/test_oidc_identity.py` (reescrito, 17), `tests/test_session_hardening_local.py` (2, `infra_local`, GoTrue + Postgres locais), e um caso de prefixo em `test_account_lifecycle_local.py`.
- `infra_local` contra o Supabase local (127.0.0.1:55321/55322): logout com access vencido revoga o refresh antigo **e** a sessão de outro dispositivo; `PostgresRateLimiter.peek/reset`; lockout real. A única falha do conjunto `infra_local`, `test_spec197_daily_cap::test_postgres_store_audit_actor_and_idempotency`, falha igual no HEAD (pré-existente, não relacionada).
- Testes ajustados ao contrato R10 (401→403 em CSRF): `test_auth_sessions`, `test_latency_client_endpoint`, `test_speech_api`, `test_stripe_checkout_api`, `test_audit_export_local`.
- Front: `npm test` 86/86 (inclui o caso 403 CSRF); `npm run build` verde.

## Passos do dono (não cumpridos aqui)

1. Aplicar `SESSION_POLICY` no Auth de staging/produção: `python -m scripts.staging.auth_config plan|apply --confirm-staging <ref>`. Os campos são senha ≥10, rotação de refresh, reuse 10 s, `jwt_exp` 3600, reautenticação na troca de senha e signup habilitado. Os nomes dos campos vêm do contrato da Management API e ainda não foram validados contra o projeto remoto.
2. Smoke §6 em staging: logout com access apagado seguido de `/auth/refresh` com o refresh antigo deve dar 401; 11 senhas erradas devem dar 429; 21 resets de IPs distintos devem dar 429.
3. Revisão Sol independente (`REVIEW_REQUIRED: true`).
4. Clientes antigos que ainda chamam `/auth/logout` continuam funcionando, mas sem o refresh cookie. Para eles, a revogação só vale enquanto o access for válido (que já era o comportamento anterior).

## Revisão Sol (2026-10-16)

APPROVED com correções: lockout de login por (e-mail, IP); refetch forçado de JWKS limitado a 1/60 s; `exp`/`nbf` só NumericDate finito. Smoke local §6-equivalente (uvicorn perfil `local`, GoTrue/Postgres locais, 2 contas): **51/51** em [evidence/local_smoke.json](evidence/local_smoke.json) — login sem Origin 403, 5 logins corretos sem 429, CSRF não-ASCII 403, logout com access apagado 204 e `/auth/refresh` com o refresh antigo 401, 3 erros + acerto zera, 11ª errada 429, fuzz `/auth/*` sem 5xx. Suíte completa: 3120 passed, 175 skipped, exit 0; `infra_local` de conta/sessão 10/10; `npm test` 86/86; build verde; Playwright F01–F19 + account-lifecycle verdes (porta 4173). Parecer: `handoffs/SPEC-220-SOL-independent-review.md`.
