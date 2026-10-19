# SPEC-225 — Higiene de supply chain, CI e release: gitignore, permissões/pins de workflows, compras de teste do Play

> **Status:** `in-progress`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-19
> **Depende de:** nenhuma · complementa SPEC-173 `done` e SPEC-194/198 (ordem final 2026-10-15)
> **Desbloqueia:** gate de release SPEC-197/198 (ordem final 2026-10-15)
> **Origem:** auditoria de segurança 2026-10-15 — achados 07-01, 07-02, 07-03, 07-04, 07-05, 07-07, PAG-02 (todos baixos/info; nenhum segredo real encontrado no HEAD nem no histórico)
> **EXECUTOR_MODEL:** `Luna` (≡ Haiku) para os itens mecânicos (gitignore, permissions, pins); `Terra` (≡ Sonnet) para PAG-02 e o scanner
> **REVIEW_MODEL:** `Sol` (≡ Opus) · **REVIEW_REQUIRED:** `false` — mudanças de configuração com testes de contrato; a única regra de produto (PAG-02) é fail-closed
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

A varredura de segredos (nomes de arquivo rastreados, `git grep` por 15 padrões de chave, `git log --all --diff-filter=A` e `-G` no histórico) não encontrou **nenhum** segredo real: hits só em fixtures sintéticas de teste, DSNs do Supabase local e placeholders. O Android está correto (`allowBackup=false`, só `MainActivity` exportada, sem cleartext em release, keystore fora do repo com senha por env). As dependências Python estão acima dos limiares dos CVEs conhecidos. Restam itens preventivos e de higiene:

- [F] `.gitignore` raiz ignora `.env` e `.env.staging`, mas não `.env.*` (ex.: `.env.local`/`.env.production.local` gerados por `vercel env pull`), `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.keystore`, `google-services.json`, `*service-account*.json` (`git check-ignore -v` vazio para eles). `.vercelignore` já exclui `.env.*` do deploy.
- [F] `.github/workflows/validate.yml:1-9` e `audit-local.yml:1-15` sem `permissions:` (os outros três declaram `contents: read`); todas as actions por tag mutável (`actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/setup-node@v4`, `upload/download-artifact@v4`); `eval-protected.yml:24-76` executa código do ref escolhido no `workflow_dispatch` com secrets de Environment (`GOOGLE_API_KEY`, token do holdout) — a restrição de branch dos Environments não é visível no repo.
- [F] `web/package-lock.json`: `esbuild 0.21.5` (dev server, GHSA-67mh-4wv8-2f99) via `vite 5.4.21` (já pós CVE-2025-30208) — só `npm run dev`.
- [F] Seis scripts de ops aceitam `--dsn` com senha em argv (`scripts/export_game_data.py:21`, `migrate_file_saves.py:21`, `recover_operations.py:16`, `chaos_test.py:138`, `load_test.py:235`, `verify_restore.py:35`); os admin críticos já usam `--dsn-env`.
- [F] `services/google_play.py:68,86-93`: `purchase_type` é lido e nunca usado — compras de **license testers** (`purchaseType=0`) e `rewarded` (`2`) são creditadas como reais; o custo de provedor (imagem/STT) é real.

Objetivo: fechar a higiene preventiva com testes de contrato no CI e uma regra fail-closed para compras de teste.

## 2. Requisitos

- **R1** — `.gitignore` raiz: `.env.*` + `!.env.example` + `!.env.staging.example` (se existir), `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.keystore`, `*.jks`, `google-services.json`, `*service-account*.json`, `keystore.properties`, `signing.properties`. Teste `tests/test_gitignore_contract.py` roda `git check-ignore` para uma lista fixa de nomes e exige que todos sejam ignorados e que `.env.example` NÃO seja.
- **R2** — `validate.yml` e `audit-local.yml` ganham `permissions: { contents: read }` no topo; teste `tests/test_workflows_contract.py` (YAML) exige `permissions` em todo workflow e que nenhum job use `pull_request_target`.
- **R3** — Actions pinadas por SHA de commit com comentário da tag (`actions/checkout@<sha> # v4.x.y`) em TODOS os workflows; Dependabot (`.github/dependabot.yml`) para `github-actions`, `pip` (uv) e `npm` (web) com atualização semanal. O teste de R2 exige `uses:` com SHA de 40 hex.
- **R4** — `eval-protected.yml`: `persist-credentials: false` no primeiro checkout; `docs/` de governança (SPEC-165) registra como item de release "Environments `eval-provider`, `eval-holdout`, `eval-governance`, `post-deploy-smoke` com *deployment branches = main* e required reviewers" (configuração do GitHub, verificada manualmente e anotada no README com data).
- **R5** — Scanner de segredos no CI: job em `validate.yml` com `gitleaks` (action pinada) sobre o diff do PR e, semanalmente, histórico completo; allowlist versionada (`.gitleaks.toml`) para fixtures de `tests/` e DSNs `postgres:postgres@127.0.0.1`. Nunca imprime o valor (gitleaks redige por default `--redact`).
- **R6** — `pip-audit` e `npm audit --omit=dev --audit-level=high` no `validate.yml` (falha em HIGH/CRITICAL com allowlist por id e prazo); `npm audit` completo (incluindo dev) como job não bloqueante até migrar para Vite ≥ 6.4 (ponto D-A).
- **R7** — Scripts de ops: `--dsn` substituído por `--dsn-env NOME` (default `DATABASE_URL`) nos seis scripts; `--dsn` literal continua aceito só com `--allow-dsn-argv` (aviso). Teste unitário de parsing.
- **R8** — Google Play: `verify()` rejeita `purchase_type in (0, 2)` com `GooglePlayError("google_play_test_purchase_rejected")` (409, sem crédito e sem consume — o Play reembolsa automaticamente) a menos que `RPG_PLAY_ACCEPT_TEST_PURCHASES=1`; essa env entra em `FORBIDDEN_IN_HOSTED` (SPEC-218 R11) e só é permitida em `local`/staging (checklist `--env staging` a aceita). Teste em `tests/test_spec194_*`: `purchaseType=0` → rejeitado por default; aceito com a env.
- **R9** — `scripts/release/checklist.py`: novos itens "workflows com permissions/pins", "gitleaks verde no último CI da main", "Environments restritos (data da verificação manual)".

### Fora de escopo

- Migração de Vite 5 → 6/7 (D-A, spec própria se o `npm audit` bloquear).
- R8 (minify) e assinatura do APK (SPEC-198).

## 3. Design técnico

- **Arquivos alterados:** `.gitignore`; `.github/workflows/{validate,audit-local,eval-gates,eval-protected,post-deploy-smoke}.yml`; `scripts/{export_game_data,migrate_file_saves,recover_operations,chaos_test,load_test,verify_restore}.py`; `services/google_play.py` (R8); `scripts/release/checklist.py` (R9); `docs/spec194/README.md` (política de compras de teste).
- **Arquivos novos:** `.github/dependabot.yml`; `.gitleaks.toml`; `tests/test_gitignore_contract.py`; `tests/test_workflows_contract.py`; `tests/test_ops_scripts_dsn_env.py`.

## 4. Plano passo a passo

### Etapa 0 — Reprodução (vermelhos no HEAD)
1. `test_gitignore_contract` (`.env.local`, `x.keystore`, `google-services.json` não ignorados); `test_workflows_contract` (2 workflows sem `permissions`, 0 `uses` com SHA); `test_google_play_test_purchase_credited_today` (`purchaseType=0` creditado).

### Etapa 1 — gitignore, permissions, pins, Dependabot (R1–R4)
1. **Testes:** os dois contratos acima verdes. 2. **Implementação:** mecânica. 3. **Verificação:** CI `validate` verde no PR.

### Etapa 2 — Scanners (R5, R6) e scripts (R7)
1. **Testes:** `test_ops_scripts_dsn_env`; job de CI com `gitleaks` passando na árvore atual (allowlist mínima documentada).
2. **Implementação:** §3.

### Etapa 3 — Play test purchases (R8) + checklist (R9)
1. **Testes:** `tests/test_spec194_*` (rejeição default, aceite com env, sem consume); `tests/test_spec197_checklist.py` (novos itens).
2. **Implementação:** §3. **Verificação:** `uv run pytest -q`.

## 5. Critérios de aceite
- [x] Etapa 0 vermelha, verde ao final; R1–R9 implementados; `uv run pytest` verde (ver evidência).
- [x] CI `validate` com gitleaks/pip-audit/npm audit verdes (push da main `c64a717`, 2026-10-19: validate 39277806887, audit-local 39277806546, eval-gates 39277806563 `success`; ver `docs/spec225/README.md`).
- [x] `git check-ignore` confirma a lista.
- [x] Dependabot abriu PRs (#28–#42); Environments verificados e anotados (os 4 com *deployment branches = main* e reviewer Batatao343; `ENVIRONMENTS_VERIFIED: 2026-10-19`).
- [x] Sem a env (teste unitário) → 409 e sem consume.
- [ ] Staging Android (`RPG_PLAY_ACCEPT_TEST_PURCHASES=1`): compra de license tester continua creditando (**bloqueado por SPEC-198**: exige app na trilha interna do Play Console com license tester e aparelho com Play Store; o AVD `rpg34` é `google_apis` sem Play. Quem age: dono (Play Console) + frente de staging (env).

## 6. Smoke test
Sem LLM/pagamento real: CI do PR + `scripts/release/checklist.py --env staging` verde.

## 7. Riscos & compatibilidade
- Pins por SHA exigem manutenção — Dependabot cobre. `gitleaks` pode acusar fixtures — allowlist versionada e revisada.
- R8 muda comportamento do staging com testers: ligar a env no staging ANTES do deploy (runbook).

## 8. Pontos de decisão do dono
- **D-A (Vite 6/7 agora):** o advisory é só dev server. **Default recomendado:** adiar; `npm audit` dev não bloqueante.
- **D-B (gitleaks histórico semanal):** custo de CI pequeno. **Default recomendado:** sim.
- **D-C (compras de teste em produção):** rejeitar (default) vs aceitar para QA de produção. **Default recomendado:** rejeitar; QA usa staging.

## 9. Evidência requerida
- Saída de `uv run pytest`; links dos runs de CI (validate/gitleaks/audits) verdes; captura/anotação da configuração dos Environments; `docs/secXX/README.md`; `ESTADO_ATUAL.md`/`ROADMAP.md`.

## 10. Registro de execução (2026-10-16)

- Implementado R1–R9 e evidência em [docs/spec225/README.md](../docs/spec225/README.md).
- Desvios: `export_game_audit.py` recebeu `--dsn-env` (além dos seis listados em R7); `FORBIDDEN_IN_HOSTED` não existe no
  repo, então a env de teste entra em `FORBIDDEN_IN_PROD`; `.github/dependabot.yml` usa ecossistema `pip` em `requirements.txt`.
- Defaults D-A/D-B/D-C aplicados como recomendados.
- Achado resolvido em 2026-10-17: os 5 advisories do pip-audit foram corrigidos no lock (allowlist removida). Segue bloqueando o fechamento:
  os Environments de GitHub não estão configurados como R4 pede.

## 11. Registro de fechamento (2026-10-19)

- CI verde na main (`c64a717`) com `secret-scan`, `pip-audit`, `npm audit` e `npm-audit-full`; Dependabot ativo.
- Environments reconferidos via `gh api`; `post-deploy-smoke` ganhou reviewer (R4 pede reviewers nos quatro).
  Faltam só secrets do dono para rodar `eval-protected` (`GOOGLE_API_KEY` em `eval-provider`; `HOLDOUT_REPOSITORY` +
  `HOLDOUT_REPOSITORY_TOKEN` em `eval-holdout`), fora dos critérios.
- O primeiro `schedule` semanal do gitleaks (histórico) falhou com 3 falso-positivos em caminhos renomeados; corrigido
  com `.gitleaksignore` (verificado localmente: 568 commits, `no leaks found`).
- Smoke Android: AVD `rpg34` sobe e o Billing real reporta `billing_query_failed responseCode=-1`, mas a compra de license
  tester não é exercível sem SPEC-198. **A spec segue `in-progress` só por esse critério**; recomendação: movê-lo para a
  SPEC-198 e marcar esta `done`.
