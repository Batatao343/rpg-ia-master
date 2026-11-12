# SPEC-410 — medição `shadow` na suíte

Rodada de 11/11 sem stack local (sem Docker, sem `RPG_TEST_DATABASE_URL`): **só estático + fakes**.

- Estático: `docs/spec410/inventario.md` (AST sobre a árvore de produto).
- Fakes: a instrumentação (`PostgresPool.connection` -> `pool_scope.on_missing_principal`) é exercitada por
  `tests/test_rls_runtime_config.py` com pools falsos nos três modos. As suítes de API/worker/cron usam o perfil
  `legacy` ou pools falsos, que nunca constroem `PostgresPool` com `request_rls`; logo não geram ocorrência
  e **não** servem de medição real do hosted.
- NÃO executado: suíte `infra_local` com `RPG_TEST_REQUEST_RLS=1` (delegada ao CI `audit-local.yml` ou ao
  coordenador com stack local) e o smoke do staging (§6 da spec). A lista real de chamadores a migrar sai do
  log `pool.checkout_without_principal` do staging em `shadow`.
