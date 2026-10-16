# SPEC-220: parecer da revisão independente Sol

- **Data:** 2026-10-16
- **Base:** worktree `rpg-spec-220` (mudanças não commitadas sobre `f98b12e`)
- **Veredito:** **APPROVED**, com três correções aplicadas pelo revisor. O status da spec continua `in-progress` por causa de gates remotos.

## Compatibilidade

- Não precisa de migration nova. `app.runtime_revoke_auth` e `app.runtime_auth_email` vêm de `20261015160000_runtime_login_role.sql` (SPEC-197 R-05), que está na main e já foi aplicada no staging (`docs/spec197/evidence/runtime_role.json`). `app.rate_limit_buckets` é anterior à SPEC-197.
- Main avançou com a SPEC-213. Os arquivos `api.py`, `infrastructure/postgres_turns.py` e `specs/index.yaml` também foram alterados lá, mas o `git merge-tree` contra a main fica limpo, sem conflitos.
- Android (SPEC-193): `X-RPG-Client`, o refresh e o `rpg_csrf` persistentes e o `POST /auth/refresh` do boot continuam iguais. O cookie de refresh (path `/auth/refresh`) chega a `/auth/refresh/logout`. O login exige Origin, e a WebView manda Origin em POST same-origin.
- Exclusão (SPEC-190): os buckets `(e-mail, IP)` são apagados por prefixo. O caminho `rpg_deletion` do `_session_boundary` foi extraído sem mudar de comportamento. A jornada account-lifecycle segue verde.

## Correções do revisor

1. **DoS de lockout.** Antes, o bucket de falhas do login era só por e-mail: 10 senhas erradas, vindas de qualquer IP, trancavam o login correto da vítima. Agora a chave é `(e-mail, IP)`, 10/15 min, zerada no sucesso daquele IP. O bucket por IP (20/15 min) continua valendo. Teste: `test_login_failure_lockout_is_per_email_and_ip_so_victim_is_not_dosed`.
2. **Amplificação de requests no OIDC.** Cada `kid` desconhecido forçava um novo fetch de JWKS. Agora o refetch forçado acontece no máximo 1 vez a cada 60 s.
3. **Claims de tempo no OIDC.** `exp`/`nbf` agora precisam ser NumericDate finitos. Strings, bool, NaN e inf são recusados.

## Ataques verificados sem achado

- `alg` none/HS256 e confusão RS/EC são recusados.
- `iss` ausente ou errado, `aud`/`azp`, `exp`/`nbf` e `email_verified=false` são verificados.
- Logout sem access válido revoga via refresh, e o 401 subsequente foi confirmado no GoTrue local.
- Origin fora da allowlist recebe 403.
- `compare_digest` com valores não-ASCII responde 403, nunca 500.
- Login com erro sempre devolve o código genérico `credentials_invalid`.

## Riscos residuais

- Vítima e atacante atrás do mesmo NAT ainda dividem o bucket de falhas.
- O peek seguido de consume não é atômico: uma rajada concorrente pode passar um pouco de 10.
- Rotação do `RPG_SESSION_SECRET`: um cliente com CSRF antigo recebe 403 e a mensagem "recarregue", mas recarregar não reemite o CSRF. A recuperação só acontece quando o access expira (≤1 h → 401 → `rpg:auth-expired`). Follow-up sugerido: na falha de CSRF, oferecer novo login.
- O F07 falhou uma vez numa execução com porta temporária e passou no rerun. Dois testes da account-lifecycle fixam a porta 4173 no `toHaveURL`.

## Evidência

- Suíte completa: 3120 passed, 175 skipped, exit 0.
- `infra_local` de conta e sessão: 10/10.
- `npm test`: 86/86. Build verde.
- Playwright: F01–F19 e account-lifecycle verdes.
- Smoke local §6-equivalente: 51/51, em `docs/spec220/evidence/local_smoke.json`.

## O que falta para `done`

- Smoke de staging (§5/§6) depois do deploy.
- O dono aplicar `SESSION_POLICY` no Auth remoto com `scripts/staging/auth_config.py` (R9). Os nomes dos campos da Management API ainda não foram validados contra o projeto.
