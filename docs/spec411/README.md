# SPEC-411 — medições e runbook

## Etapa 0 (11/11, `main` em `3f89816a`)

- Checkouts: 19 `actions/checkout`; 9 já tinham `persist-credentials: false`; faltavam 10
  (eval-gates 5, validate 3, audit-local 1, post-deploy-smoke 1). `zizmor 1.32.0`: 10 `artipacked` antes, 0 depois.
  Nenhum script chamado por esses jobs faz `git fetch/push`; nenhum workflow usa `gh`/`git push`.
- Boot (R1): em `hosted*`, `RuntimeConfig.from_env` **levanta** `ValueError("hosted_config_insecure: ...")`
  quando `hosted_security_problems` não é vazio (exceto com `RPG_ALLOW_INSECURE_HOSTED=1`, que só deixa
  `hardened=false`). `portable` exposto levanta pelo mesmo caminho (`assert_boot_policy`). `legacy`/`local` não são afetados.
- R3: `cooldown` do Dependabot afeta só version updates, não security updates (documentação do GitHub).
- R4b: `S324` 3, `S105` 4 (3 `token_mode` + `TOKEN_URL`), `S602/S604/S605/S106/S107` 0 no produto.

## R1 — ordem de rollout (obrigatória)

1. Pousar o código (flag ausente: nenhum efeito).
2. Sincronizar o env do staging com `RPG_DEPLOY_ENV=staging` (`scripts/staging/vercel_env.py` já o envia; preview não recebe).
3. **Só depois** ligar `RPG_PLAY_ACCEPT_TEST_PURCHASES=1` (SPEC-198).

Inverter 2 e 3 faz o staging recusar o boot (`hosted_config_insecure: RPG_PLAY_ACCEPT_TEST_PURCHASES: ...`).
Produção: marcador ausente = produção; a flag ligada é recusada (nada a configurar).

## R4b — S608

Não ligado (29 falsos positivos). `tests/test_sql_identifier_allowlists.py` trava `_UPDATABLE` e as tabelas de
`account_lifecycle`. Os `noqa` adicionados: `S105` em `routes/turn.py` (3x `token_mode`) e `services/google_play.py` (`TOKEN_URL`).
