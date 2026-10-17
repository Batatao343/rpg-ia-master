# SPEC-225 — evidência: supply chain, CI e release hygiene

**Status:** `in-progress` (ver "Pendências"). **Data de execução:** 2026-10-16.

## O que mudou

- **R1 `.gitignore`:** `.env.*` com `!.env.example` e `!.env.staging.example`; `*.pem/*.key/*.p12/*.pfx/*.keystore/*.jks`,
  `google-services.json`, `*service-account*.json`, `keystore.properties`, `signing.properties`.
- **R2/R3 workflows:** `permissions: contents: read` em `validate.yml` e `audit-local.yml`; todas as actions de terceiros
  pinadas por SHA com comentário da versão (checkout v4.2.2, setup-uv v5.4.1, setup-node v4.4.0, upload-artifact v4.6.2,
  download-artifact v4.3.0, gitleaks-action v2.3.9). Os SHAs vieram de `gh api` (tags anotadas desreferenciadas).
  `.github/dependabot.yml` (github-actions, pip em `/`, npm em `/web`, semanal).
- **R4 `eval-protected.yml`:** `persist-credentials: false` no primeiro checkout de cada job. Lógica dos jobs intocada.
- **R5 scanner:** job `secret-scan` em `validate.yml` (gitleaks-action, `fetch-depth: 0`, allowlist `.gitleaks.toml`),
  com `schedule` semanal (segunda 06:23 UTC) para o histórico. O job `test` roda só fora do `schedule`.
- **R6 audits:** `npm audit --omit=dev --audit-level=high` bloqueante; `npm audit` completo em job `npm-audit-full`
  não bloqueante (`continue-on-error`); `pip-audit==2.10.1` em `requirements.txt` com allowlist (ver abaixo).
- **R7 ops:** `services/dsn_cli.py` (`add_dsn_arguments`/`resolve_dsn`). Os seis scripts da spec mais
  `scripts/export_game_audit.py` (mesmo padrão, achado durante a execução) usam `--dsn-env` (padrão `DATABASE_URL`).
  `--dsn` literal exige `--allow-dsn-argv` e emite aviso.
- **R8 Google Play:** `infrastructure/google_play_payments.py` rejeita `purchaseType` 0 e 2 com
  `google_play_test_purchase_rejected` (409 na API) antes de qualquer crédito ou consume, salvo
  `RPG_PLAY_ACCEPT_TEST_PURCHASES=1`. O fake local passou a emitir compra normal (`purchase_type=None`).
- **R9 checklist:** `workflows_permissions_pins`, `gitleaks_main_green` e `environments_restricted` em
  `scripts/release/checklist.py`; `RPG_PLAY_ACCEPT_TEST_PURCHASES` entra em `FORBIDDEN_IN_PROD`.

## Testes

- Novos: `tests/test_gitignore_contract.py`, `tests/test_workflows_contract.py`, `tests/test_ops_scripts_dsn_env.py`.
- Ampliados: `tests/test_spec194_google_play.py` (rejeição por default, aceite com env, sem consume),
  `tests/test_spec197_checklist.py` (novos itens de R9).
- Reprodução (vermelha antes da correção): gitignore 13 falhas, workflows 7+ falhas, Play `purchaseType` 0/2 creditado.

## Verificações locais

- **gitleaks v8.24.2** (imagem Docker pinada por tag) sobre a árvore de trabalho com `.gitleaks.toml`: `no leaks found`.
  Sem allowlist havia 8 achados, todos falso-positivos (texto de documentação, hashes de compromisso em
  `ground-truth.commitment.json`, nomes de teste de redaction). O histórico completo NÃO foi varrido localmente.
- **pip-audit 2.10.1** sobre `requirements.txt` sem allowlist: **5 vulnerabilidades em 3 pacotes**
  (`multidict` 6.7.1 PYSEC-2026-4244; `urllib3` 2.7.0 PYSEC-2026-4177/4176/4175; `langgraph-sdk` 0.4.3 PYSEC-2026-4240).
  Com a allowlist do `validate.yml`: `No known vulnerabilities found, 5 ignored`.
  A auditoria de 2026-10-15 que dizia "acima dos limiares" estava desatualizada: esses advisories são posteriores.
- **npm audit --omit=dev --audit-level=high:** `found 0 vulnerabilities`. **npm audit (completo):** 10 (5 high),
  todos na árvore de dev (vite 5/esbuild), não bloqueante conforme D-A.
- YAML de todos os workflows e do dependabot parseado com `yaml.safe_load`. `actionlint` não está instalado; revisão manual.
- Ruff nos arquivos tocados: verde.

## pip-audit: allowlist removida (2026-10-17)

Os cinco advisories tinham correção compatível; o `uv.lock` foi atualizado com `uv lock --upgrade-package` (demais pins intactos) e `requirements*.txt` reexportados (pillow fica fora, como antes). O step de `validate.yml` roda `pip-audit` sem `--ignore-vuln`.

| Advisory | Pacote | Ação |
|---|---|---|
| PYSEC-2026-4244 | multidict 6.7.1 | atualizado para 6.9.1 |
| PYSEC-2026-4177/4176/4175 | urllib3 2.7.0 | atualizado para 2.8.0 |
| PYSEC-2026-4240 | langgraph-sdk 0.4.3 | atualizado para 0.4.8 |

Resultado: `pip-audit -r requirements.txt` = `No known vulnerabilities found`; `npm audit --omit=dev --audit-level=high` = 0 vulnerabilidades (sem mudança em `web/`, sem migração major do Vite). Sem advisories pendentes, não há prazo de revisão de allowlist.

## Environments do GitHub (R4, verificação manual)

Consulta `gh api repos/Batatao343/rpg-ia-master/environments` em 2026-10-16:

| Environment | Existe | Required reviewers | Deployment branches |
|---|---|---|---|
| `eval-governance` | sim | 1 | **sem restrição** (`deployment_branch_policy: null`) |
| `eval-provider` | **não listado** | — | — |
| `eval-holdout` | **não listado** | — | — |
| `post-deploy-smoke` | **não listado** | — | — |

**Achado (bloqueia o critério):** os jobs `eval-provider`/`eval-holdout`/`post-deploy-smoke` referenciam environments
que não aparecem na API, e `eval-governance` não restringe branches. Sem restrição de branch, um `workflow_dispatch`
de qualquer ref pode usar secrets de Environment. A correção é configuração do GitHub (criar os três environments com
*deployment branches = main* e required reviewers, e restringir o `eval-governance`), não de código. Não foi alterada
nesta execução. Depois de aplicar e reconferir com `gh api`, adicionar a linha `ENVIRONMENTS_VERIFIED: AAAA-MM-DD`
neste arquivo; o checklist de release só passa com essa linha.

### Verificação de 2026-10-17

Aplicado pelo coordenador com autorização do dono (`gh api`, conta Batatao343):

| Environment | Required reviewers | Deployment branches |
|---|---|---|
| `eval-governance` | Batatao343 | só `main` |
| `eval-provider` | Batatao343 | só `main` |
| `eval-holdout` | Batatao343 | só `main` |
| `post-deploy-smoke` | — | só `main` |

ENVIRONMENTS_VERIFIED: 2026-10-17

## Pendências (por que a spec segue `in-progress`)

1. ~~Environments~~ — aplicados e verificados em 2026-10-17.
2. CI verde no PR com `secret-scan`, `npm-audit-full` e pip-audit: exige push/PR (não feito).
3. ~~Dependabot~~ — abriu PRs após o push de 2026-10-17.
4. Varredura do histórico completo com gitleaks: roda no `schedule` semanal; primeiro resultado ainda não observado.
5. Staging com `RPG_PLAY_ACCEPT_TEST_PURCHASES=1` antes do deploy (runbook de R8; compra de license tester em staging
   não foi executada).

## Defaults de decisão usados (seção 8 da spec)

- **D-A:** Vite não migrado; `npm audit` completo não bloqueante.
- **D-B:** gitleaks semanal no histórico: sim.
- **D-C:** compras de teste rejeitadas em produção por default; QA usa staging com a env.

## Limites

- Nenhuma alteração de lógica de jobs de eval; nenhum secret tocado; nenhum recurso remoto criado.
- `FORBIDDEN_IN_HOSTED` (citada em R8) não existe no repositório; a regra foi aplicada à lista de produção
  `FORBIDDEN_IN_PROD` do checklist, que é a lista equivalente em uso.
