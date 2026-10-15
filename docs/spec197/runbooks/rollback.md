# Rollback (SPEC-197)

## App (Vercel)
1. Decidir: o problema e do deploy (codigo) ou de dados/provider/custo? Provider/custo -> `incident.md` (kill switches primeiro).
2. `npx vercel@64.2.0 rollback` (volta ao deploy de producao anterior) ou
   `npx vercel@64.2.0 promote <url-de-deploy-READY-conhecido>` (`vercel ls --prod`). Troca de alias, instantanea,
   sem rebuild: env vars alteradas depois NAO sao reaplicadas ao deploy antigo.
3. `uv run python scripts/post_deploy_smoke.py --base-url https://<prod> --expected-sha <sha-anterior>`.
4. Anotar no incidente; corrigir em novo commit (nunca editar o deploy antigo).

Medido no drill do staging (`evidence/incident_drill.json`, Vercel CLI 64.2.0, Hobby):
- `npx vercel@64.2.0 rollback <url-do-deploy-anterior> --yes`: comando ~8 s; alias serve o deploy antigo ~17 s depois.
- `npx vercel@64.2.0 promote <url-do-deploy-atual> --yes`: comando ~9 s; alias de volta quase imediato. Ciclo completo ~34 s.
- Hobby so volta ao deploy IMEDIATAMENTE anterior (outro -> 402 "upgrade to pro"). `vercel rollback` sem URL so mostra status.
- URLs de deploy sao protegidas (401): verificar pelo alias `/health` (`git_sha`; deploy via CLI exige `-e GIT_SHA=<sha>`).
- Um reset de conexao transitorio durante a troca do alias e esperado; repetir o GET.

## Banco: forward-fix, sem down-migrations
- Politica expand/contract: toda migration deve ser compativel com o codigo N e N-1 (adicionar primeiro; remover
  so uma release depois). Por isso o rollback de app e seguro.
- Nunca SQL destrutivo manual em producao sem backup recente. Erro de migration -> nova migration corretiva via
  `migrations push`. Wallet/ledger sao append-only: correcao financeira so por entradas compensatorias
  (`scripts/admin_wallet_adjust.py`, dry-run por padrao).
- Divergencia de schema: `migrations status` e `schema_diff` antes de agir.

## Restore de backup portavel
Ferramenta: `scripts/staging/backup_restore.py` (`export`, `restore`, `verify`). Hoje exige `--confirm-staging <ref>` e
recusa refs em `RPG_PROTECTED_PROJECT_REFS`. Para producao (implementar na execucao da SPEC-197, com testes): modo
`--confirm-prod <ref>` que (a) exporta em modo leitura, (b) restaura somente em alvo DESCARTAVEL, nunca sobre producao.
1. `uv run python -m scripts.staging.backup_restore export --confirm-staging <ref> <dir>` (adaptado por ambiente).
2. `... restore <dir> --target-dsn <dsn-descartavel> --objects-dir <dir2> --confirm-disposable`.
3. `... verify` com os mesmos argumentos; comparar contagens e saldo de wallet.
4. Restaurar producao de verdade = decisao humana, em janela, com `new_purchases` e `image_generation` OFF antes.
Limites (R-03/R-04): owner de `storage.objects` nao e preservado no re-upload; plano Free sem PITR.
Frequencia minima no beta: export diario com retencao de 14 dias fora do Supabase; drill antes de abrir o beta.

## Evidencia exigida (R5)
Drill de rollback (deploy ruim simulado -> rollback -> smoke) e de restore (export -> restore descartavel -> verify),
ambos com JSON em `docs/spec197/evidence/`.
