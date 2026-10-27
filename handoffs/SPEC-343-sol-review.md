# SPEC-343 — revisão sol (review)

> **Veredito:** `APPROVED`
> **Revisor:** Sol (Opus) · **Data:** 2026-10-27 · **Commit revisado:** `483e2d45`

## Escopo

`git diff main...HEAD`: api.py, services/account_security.py, infrastructure/oidc_identity.py, migration `20261027120000_embedding_profiles_rls.sql`, testes. Nada em `evals/`, nenhuma flag `RPG_*` nova.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | api.py (reauth) | Qualquer `Unauthorized` do `reauthenticate` (inclui token expirado, não só senha errada) consome o balde de falhas. Aceitável: o balde é por sessão e só ela é afetada. | Opcional: distinguir `reason`. |
| P2-2 | P2 | migration | Sem banco local, a RLS de `embedding_profiles` não foi provada em execução. Estaticamente correta. | Rodar `supabase/tests` no staging. |

## Verificações pedidas

1. `peek` ocorre em `_auth_abuse` antes do GoTrue; falha só consome no `except Unauthorized` de senha. CSRF, origem, 503 e cookie ausente (levanta antes) não consomem. OK.
2. Sucesso reseta só `auth:reauth:fail:<digest>` e, no login, as chaves (e-mail,IP) e e-mail do próprio endereço. Não toca baldes de outros usuários. OK.
3. Chave usa `_digest(access)`; token em claro nunca vira chave nem log. OK.
4. Balde só-por-e-mail do login é consumido apenas em `stage="failure"` e inspecionado (peek) no attempt; `auth_email_bucket_keys` (EMAIL_ACTIONS) não mudou. Testes existentes passam. OK.
5. OIDC: `aud` string e lista tratados; `azp` não substitui mais. OK.
6. Migration idempotente (`drop policy if exists`, enable/force repetíveis); mantém `grant select` a `rpg_api`; policy `using (true)` para `rpg_api`. `rpg_api` é NOLOGIN/NOBYPASSRLS e não dono (migrations de roles); FORCE RLS não o bloqueia. OK.
7. `app.rate_limit_buckets`: a exceção é aceitável. `rpg_api` perde o acesso por revoke (auth_rls:87) e o limiter usa o papel runtime; `anon/authenticated` já não têm grant. Sem risco real; endurecer com RLS fica como follow-up opcional.

## Correções aplicadas

Nenhuma necessária.

## Pendências

Provar a migration no staging/Supabase local quando houver banco (P2-2).

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec343_security.py tests/test_session_hardening.py tests/test_oidc_identity.py tests/test_auth_logging.py tests/test_flag_registry.py → 80 passed (72+8 pontos, sem falhas; linha de resumo suprimida pela config)
```
