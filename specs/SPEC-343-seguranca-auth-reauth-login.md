# SPEC-343 — Segurança: trava de falhas no reauth, balde por e-mail no login, `aud` estrito no OIDC e RLS em `embedding_profiles`

> **Status:** `approved` (Aprovação: dono, 27/10, inspeção de segurança geral — "faz uma inspeção de segurança geral criando e executando specs do que encontrar")
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Depende de:** SPEC-220 (`done`, limites de auth), SPEC-337 (`done`, bateria HTTP).
> **Desbloqueia:** —

---

## 1. Contexto & Objetivo

A inspeção de segurança de 27/10 (auditoria somente leitura de auth/sessão, pagamentos e migrations) não achou nada crítico ou alto: CSRF e provas HMAC usam `compare_digest`, o webhook Stripe e o Google Play são idempotentes e revalidados no servidor, a carteira tem lock + unicidade, e as funções `SECURITY DEFINER` têm `search_path` fixo e `revoke` para `anon`/`authenticated`. Sobraram quatro achados médios/baixos que cabem em código e teste offline:

- **A1 (médio) — reauth sem trava por conta.** `POST /auth/reauth` (`api.py:1036-1057`) só passa pelo balde de IP (`IP_ATTEMPTS = (20, 900)`) e pelo `authfail` do boundary. Uma falha de senha **não** chama `auth_limit(..., stage="failure")`. Quem rouba um cookie `rpg_access` pode adivinhar a senha a 20 tentativas por IP a cada 15 min, por quantos IPs tiver, para obter `rpg_recent` — e com ele export e `account/delete`.
- **A2 (médio) — login sem contador global por e-mail.** O balde de falhas do login é por `(e-mail, IP)` (`account_security.py:135`, decisão da revisão Sol para não trancar a vítima). No modo captcha `app`, login não exige captcha (`api.py:915-917`). Um botnet com muitos IPs faz credential stuffing contra um e-mail sem nenhuma trava por conta. Signup/reset já têm um balde "folgado" só por e-mail (`EMAIL_ONLY_ATTEMPTS`); login não.
- **A3 (baixo) — OIDC aceita `azp` no lugar de `aud`.** `oidc_identity.py:161`: `if self.audience not in audiences and claims.get("azp") != self.audience` — um token emitido para outro serviço passa se o `azp` bater. O perfil OIDC não está em produção.
- **A4 (baixo) — `app.embedding_profiles` sem RLS.** `20260819002401_pgvector_memory.sql:3,59`: única tabela de `app` sem `enable row level security` (só `grant select to rpg_api`). Dado de configuração, sem PII; mesmo assim quebra a invariante "toda tabela de `app` tem RLS".

**Objetivo:** fechar os quatro com teste vermelho antes, sem flag nova, sem mudar formato de cookie nem de token.

## 2. Requisitos

### Reauth (A1)
- **R1 — balde de falhas do reauth por sessão.** Nova constante `REAUTH_FAILURES = (5, 900)` em `services/account_security.py`. Chave `auth:reauth:fail:{sha256(access_token)}` (digest do cookie `rpg_access`; não o user_id, para não precisar de chamada extra ao GoTrue antes do limite). `auth_limit(runtime, request, action="reauth", stage="failure", access=<cookie>)` consome o balde. A tentativa (`stage="attempt"`, chamado em `_auth_abuse`) faz `peek` e devolve 429 `auth_rate_limit` + `Retry-After` quando o balde está cheio, **antes** de chamar o GoTrue.
- **R2 — só falha de senha conta.** O handler `/auth/reauth` chama a falha apenas quando `identity_verifier.reauthenticate` levanta `Unauthorized`. CSRF inválido (403), origem negada, captcha e 503 não consomem. Sem cookie `rpg_access` → 401 como hoje, sem consumir.
- **R3 — sucesso zera.** `auth_success(runtime, action="reauth", email="", access=<cookie>)` faz `reset` da chave. Sexta falha → 429; sucesso → próxima tentativa passa.

### Login (A2)
- **R4 — balde de falhas só por e-mail.** Nova constante `LOGIN_EMAIL_ONLY_FAILURES = (50, 3600)` e chave `auth:login:email:{sha256(e-mail normalizado)}`. Consumida junto com a `(e-mail, IP)` em `stage="failure"`; `peek` na tentativa. 50 falhas do mesmo e-mail vindas de 50 IPs distintos → 429 na 51ª, de qualquer IP. 49 falhas → passa. Sucesso (`auth_success`) zera as duas chaves. O limite é deliberadamente folgado (DoS da vítima custa 50 senhas erradas por hora e dura 1 h); ajustar = mudar a constante.
- **R5 — chaves apagáveis no delete.** `auth_email_bucket_keys`/`auth_email_bucket_prefixes` (usadas na exclusão de conta) continuam cobrindo a nova chave: `tests/test_session_hardening.py::test_bucket_keys_cover_new_address_derived_buckets` segue verde e um teste novo confirma que `auth:login:email:<digest>` está em `auth_email_bucket_keys(email)`.
- **R6 — log fechado.** `observability.auth_log.rate_limited(action, bucket, key, retry)` recebe `bucket="email"` (login) e `bucket="session"` (reauth); o log **não** contém o e-mail nem o token em claro (só o que já faz hoje para as outras chaves).

### OIDC (A3)
- **R7 — `aud` obrigatório.** `OidcIdentityProvider.verify` recusa (`Unauthorized`, `reason="bad_aud"`) todo token cujo `aud` (string ou lista) não contenha `self.audience`. `azp` deixa de substituir `aud`. `tests/test_oidc_identity.py::test_azp_can_carry_audience` vira `test_azp_does_not_replace_audience` (espera `Unauthorized`); teste novo: `aud` lista contendo a audiência + `azp` qualquer → aceito.

### Migration (A4)
- **R8 — RLS em `embedding_profiles`.** Migration nova `supabase/migrations/20261027120000_embedding_profiles_rls.sql`: `enable` + `force row level security`; `revoke all on app.embedding_profiles from public, anon, authenticated`; policy `embedding_profiles_read for select to rpg_api using (true)` (tabela de configuração; leitura de qualquer linha é o comportamento atual); nenhuma policy de escrita (só o dono do schema escreve, como hoje). Idempotente (`drop policy if exists` antes).
- **R9 — prova estática.** `tests/test_spec343_security.py` lê a migration e asserta as cláusulas de R8; e varre `supabase/migrations/*.sql` provando que **toda** `create table app.<t>` tem um `alter table app.<t> enable row level security` em alguma migration (direto ou via o loop `execute format('alter table app.%I enable row level security', t)` com `t` na lista — basta aceitar que o nome aparece numa lista de `foreach` de uma migration que contém esse `format`). Lista de exceções vazia. Esse é o teste que fica vermelho antes do R8.

### Fora de escopo
- Captcha adaptativo no login (`captcha_mode="app"`); mudar `LOGIN_EMAIL_FAILURES`; vincular o token CSRF à sessão (double-submit + Origin allowlist + `SameSite` já mitigam; mudar o formato invalidaria sessões vivas no staging) — registrados em §7.
- Oráculo `email_not_confirmed` no login (`supabase_identity.py:148`) e resposta de signup com `RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED=0`: dependem de config do staging; vão ao relatório como bloqueio/aceito.
- Rodar a migration no Supabase cloud ou local (não há Docker nesta máquina; o job `audit-local` aplica as migrations no CI).

## 3. Design técnico

**Arquivos alterados**
- `services/account_security.py` — constantes `REAUTH_FAILURES`, `LOGIN_EMAIL_ONLY_FAILURES`; `_reauth_failure_key(access)`; `_login_email_key(address)`; `auth_limit(..., access: str = "")` ganha os ramos `action == "reauth"` (peek/consume por sessão) e, no login, o segundo balde só por e-mail; `auth_success(..., access="")` zera as chaves novas; `auth_email_bucket_keys`/`_prefixes` incluem `auth:login:email:`.
- `api.py` — `auth_reauthenticate`: lê o cookie antes, passa `access=` para `_auth_abuse` (que ganha parâmetro `access: str = ""` repassado a `auth_limit`); no `except Unauthorized` chama `auth_limit(runtime, request, action="reauth", stage="failure", access=access)` **antes** de levantar o 401; no sucesso chama `auth_success(runtime, action="reauth", email="", access=access)`. Login: `auth_success` já é chamado; o `stage="failure"` passa a consumir as duas chaves.
- `infrastructure/oidc_identity.py:155-162` — remove a alternativa `azp`.
- `supabase/migrations/20261027120000_embedding_profiles_rls.sql` — novo.
- `tests/test_oidc_identity.py` — renomeia/inverte o teste do `azp`.

**Arquivos novos**
- `tests/test_spec343_security.py` — R1–R6 com a fixture `hardened` de `tests/test_session_hardening.py` (importar/duplicar o mínimo: perfil DB offline, `MemoryRateLimiter`, identidade fake cujo `reauthenticate` levanta `Unauthorized` para senha errada e devolve o owner para a certa), R9 estático.

**Assinaturas**
```python
REAUTH_FAILURES = (5, 900)
LOGIN_EMAIL_ONLY_FAILURES = (50, 3600)
def auth_limit(runtime, request, *, action: str, email: str = "", stage: str = "attempt", access: str = "") -> None
def auth_success(runtime, *, action: str, email: str, request=None, access: str = "") -> None
```

## 4. Plano passo a passo

1. **Testes vermelhos (R1–R3):** `test_reauth_sixth_failure_is_429`, `test_reauth_success_resets_bucket`, `test_reauth_csrf_failure_does_not_consume`, `test_reauth_without_access_cookie_is_401_and_does_not_consume`. Depois código em `account_security.py` + `api.py`.
2. **Testes vermelhos (R4–R5):** `test_login_fifty_failures_from_distinct_ips_lock_email`, `test_login_success_resets_email_only_bucket`, `test_email_bucket_keys_include_login_email_only`. Depois código.
3. **R7:** inverter o teste do `azp`, adicionar o positivo, remover a alternativa em `oidc_identity.py`.
4. **R9 vermelho** (varredura de `create table app.*` sem RLS acusa `embedding_profiles`) → **R8** migration → verde.
5. Testes do escopo: `tests/test_spec343_security.py tests/test_session_hardening.py tests/test_oidc_identity.py tests/test_auth_logging.py tests/test_flag_registry.py` (no máximo `-n 2`). `ruff check`/`ruff format` nos `.py` tocados.

## 5. Critérios de aceite

- [ ] R1–R3: reauth bloqueia na 6ª falha de senha por sessão, zera no sucesso, não consome em 403/401-sem-cookie.
- [ ] R4–R5: 51ª falha do mesmo e-mail em IPs distintos → 429; sucesso zera; chave nova listada em `auth_email_bucket_keys`.
- [ ] R6: log de `rate_limited` sem e-mail/token em claro.
- [ ] R7: `azp` não substitui `aud`.
- [ ] R8–R9: migration nova; varredura estática prova RLS em toda tabela `app.*`.
- [ ] Nenhuma flag `RPG_*` nova; `tests/test_flag_registry.py` verde.
- [ ] Suíte completa verde no pouso; revisão independente APPROVED.

## 6. Smoke test real

Offline (perfil DB offline com `MemoryRateLimiter`): os testes de R1 e R4 **são** o smoke — não há GoTrue nesta máquina. A migration é aplicada pelo job `audit-local` no CI (não roda localmente).

## 7. Riscos & compatibilidade

- **DoS da vítima pelo balde só por e-mail (R4):** 50 falhas/h é folgado de propósito; o cliente web já exibe `auth_rate_limit` com `Retry-After`. Se incomodar, subir a constante.
- **Reauth keyed pelo access token:** quem tem o cookie e troca de sessão (novo login) zera o balde — mas o novo login passa pelo balde do login. Aceito.
- **Token CSRF sem vínculo com a sessão (não corrigido):** mitigado por Origin allowlist + `SameSite=Strict` + ausência de subdomínios; mudar o formato quebra sessões vivas.
- **OIDC:** nenhum deploy usa o perfil; a mudança é segura.
- **Migration:** `force row level security` com policy `using (true)` para `rpg_api` preserva o comportamento de leitura; nenhum caminho de escrita existe no código (`Grep embedding_profiles` só em leitura).

## 8. Decisões do dono

- Aprovação em bloco em 27/10 ("faz uma inspeção de segurança geral criando e executando specs do que encontrar"). Limiares (5/15 min reauth; 50/h e-mail) escolhidos pelo coordenador; reversíveis por constante.

## Histórico de mudanças

- 2026-10-27 — criada (`approved`) a partir da inspeção de segurança geral.
