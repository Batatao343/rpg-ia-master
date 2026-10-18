# Debug de auth no staging — 2026-10-18

Escopo: staging `rpg-ia-master-staging.vercel.app` + Supabase `uzeagzcyvxzrpjgrhaql`. Só leitura
no banco/Auth. Nenhum usuário de teste criado. Turnstile real mantido. Nenhum env var alterado,
nenhum redeploy (ver "Deploy").

## Sintoma

Dono criou conta, foi em "Recuperar acesso", digitou o e-mail, Turnstile "Sucesso!", e a tela
mostrou o texto cru `credentials_invalid`.

## Evidência (logs do GoTrue + `auth.users`, horários UTC)

| hora | evento GoTrue | resposta da nossa API |
|---|---|---|
| 14:03:43 | `/signup` 200, `user_confirmation_requested` (e-mail de confirmação saiu) | 202 genérico |
| 14:03:51 | `/signup` de novo → 429 `over_email_send_rate_limit` | 202 genérico |
| 14:04:00 | `/token` (login) → 400 `email_not_confirmed` | **401 `credentials_invalid`** |
| 17:39:53, 17:40:00 | `/signup` → **500 SMTP `535 "Authentication credentials invalid"`** | 202 genérico |
| 17:40:27 | `/token` → 400 `email_not_confirmed` | **401 `credentials_invalid`** (cru na tela) |
| 17:40:34 | `/recover` → **500 SMTP `535`** (`user_recovery_requested`) | 202 genérico + log `auth.email_delivery_failed` |

`auth.users` do dono: criado 14:03:43, `email_confirmed_at = null`, `recovery_sent_at = null`,
`last_sign_in_at = null`. Nenhum bucket de lockout de falha (`app.rate_limit_buckets` só tem os
contadores de tentativa normais) — o lockout não participou.

Config Auth (Management API, sem segredos): `smtp.resend.com:465`, user `resend`,
sender `onboarding@resend.dev`, `rate_limit_email_sent=10`, captcha turnstile ligado.
A chave `RESEND_API_KEY` (= `RPG_STAGING_SMTP_PASS`) do `.env.staging` **é recusada pela Resend**
(`GET /domains` → 400 "API key is invalid"), e o hash do `smtp_pass` gravado no Supabase também
não bate com ela.

## Causa raiz

1. **SMTP quebrado (infra, bloqueante).** Desde a troca da chave Resend, todo e-mail do Auth
   (confirmação e recuperação) falha com `535` no SMTP. Por isso nada chega e a conta segue não
   confirmada. A API esconde isso de propósito (anti-enumeração, SPEC-190) e só registra
   `auth.email_delivery_failed`/`rpg_auth_email_delivery_failures_total`.
2. **`credentials_invalid` cru na tela (frontend).** A tentativa de *login* (conta não confirmada)
   devolveu 401 `credentials_invalid`; `App.handleLogin` mostrava `error.message` (= o código) e a
   `AuthScreen` continuava exibindo esse erro do pai depois de trocar para "Recuperar acesso". A
   recuperação em si respondeu 202 — o texto na tela era o erro velho do login.
3. **Mapeamento GoTrue pobre (backend).** Toda falha do `/token` virava `credentials_invalid`:
   "e-mail não confirmado" parecia senha errada, e captcha recusado pelo GoTrue também — e ainda
   contava no bucket de falha de credencial (lockout por e-mail+IP). No cadastro, captcha recusado
   virava o 202 "enviaremos instruções" mesmo sem conta criada.

## Correção (branch `auth-debug`)

- `infrastructure/supabase_identity.py`: lê `error_code` do GoTrue. Login: `email_not_confirmed`
  → `email_not_confirmed` (GoTrue só diz isso com a senha correta — não enumera);
  `captcha_failed` → `captcha_invalid`; resto segue `credentials_invalid`. Cadastro e
  recover/resend: `captcha_failed` → `captcha_invalid` (não depende da conta). Falha SMTP segue
  `AuthEmailDeliveryError` (202 genérico + métrica).
- `api.py`: login conta no bucket de lockout **só** `credentials_invalid`; captcha → 403
  `captcha_invalid` em login/cadastro/recover/resend. `email_not_confirmed` entra em
  `AUTH_ERROR_CODES`.
- `web/src/lib/authErrors.ts` (novo) + `App.tsx`/`AuthScreen.tsx`: nenhum código cru na tela;
  mensagens pt-BR ("E-mail ou senha incorretos.", "Confirme seu e-mail… Reenviar confirmação",
  "verificação anti-robô expirou", 429 com minutos); erro/aviso do pai é limpo ao trocar de tela e
  ao enviar.

Depois de corrigir o SMTP, entrar com a conta não confirmada mostra "Confirme seu e-mail…" em vez
de `credentials_invalid`.

## Verificação

- `tests/test_auth_gotrue_error_mapping.py` (11 casos, vermelhos antes / verdes depois), suítes de
  auth relacionadas verdes; suíte completa `uv run pytest` verde (contagem no commit).
- `web/tests/authErrors.test.mjs`; `npm test` 126/126; `npm run build` verde.
- Playwright local `e2e/account-lifecycle.spec.ts` 9/9, incluindo o fluxo do dono (login não
  confirmado → senha errada → "Esqueci minha senha" sem alerta herdado → aviso genérico, nenhum
  `snake_case` na página).
- Staging antes do deploy: `/auth/config` gotrue+captcha required, `git_sha c3bab62`.

## Deploy

Depois que o outro agente terminou (Jev `primary` no ar, commits na `main` `4d60cf7`), `auth-debug`
foi rebaseado na `main` e publicado com `vercel deploy --prod -e GIT_SHA=9763ef6` (deploy
`rpg-ia-master-staging-lkq7km6zl`). Nenhum env var tocado (`RPG_JEV_ROUTER_MODE`,
`RPG_JEV_ROUTER_PRIMARY_APPROVED`, `TYPESAFE_API_KEY` seguem os da Vercel). Rollback:
`npx vercel@64.2.0 promote https://rpg-ia-master-staging-gnlwq6evi-guilherme-medeiros-projects.vercel.app`.

Verificação no staging: `/health` `git_sha 9763ef6`; Playwright abre "Recuperar acesso" sem alerta
herdado e o bundle servido contém as mensagens novas; POST direto `/auth/reset/request` e
`/auth/login` sem token → 403 `captcha_required` (Turnstile continua obrigatório). Os caminhos
`email_not_confirmed`/`captcha_invalid` vindos do GoTrue não foram exercitados no staging (exigem
Turnstile real) — cobertos pelos testes locais e pelo clique do dono abaixo.

## O que o dono precisa fazer

1. Na Resend, criar/copiar uma API key **válida** (sending access serve) e colá-la em Supabase →
   Authentication → Emails → SMTP Settings → Password (host `smtp.resend.com`, porta 465, user
   `resend`). Atualizar também `RESEND_API_KEY`/`RPG_STAGING_SMTP_PASS` no `.env.staging` (a atual
   é recusada pela Resend). Alternativa: `scripts/staging/auth_config.py apply` após atualizar o
   `.env.staging`.
2. No staging: "Reenviar confirmação de e-mail" para o seu endereço → abrir o link → entrar.
   (O link de 14:03 já expirou.) Se ainda não chegar, os logs do Auth mostram `535` de novo.
3. Teste de recuperação depois de confirmado: "Esqueci minha senha" → o e-mail deve chegar
   (`recovery_sent_at` passa a ser preenchido).
