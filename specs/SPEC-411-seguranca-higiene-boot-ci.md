# SPEC-411 — seguranca-higiene-boot-ci

> **Status:** `approved` (11/11: aprovada pelo coordenador por delegação do dono, "o resto é nois"; decisões do §8 = recomendações do autor; veto do dono segue possível) · antes `draft`
> **Criada:** 2026-11-11 · **Atualizada:** 2026-11-11
> **Depende de:** nenhuma (R4b/zizmor limpo depende do R2 da própria spec)
> **Desbloqueia:** nada (follow-up da varredura de segurança de 11/11; irmã de SPEC-409/410)
> **Risco:** `baixo` no geral; **R1 toca a política de boot (`infrastructure/runtime.py`)** → revisor Sonnet obrigatório para a Etapa R1; **R5 é caminho protegido de eval** → autoria de eval + aprovação do dono no environment `eval-governance`.
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet), uma etapa por vez · **REVIEW_MODEL:** Sonnet na R1; as demais por testes + lint + CI.
> **EVAL_AUTHORING_REQUIRED:** `true` **somente na Etapa R5** (`evals/protected-paths.txt` é protegido): commit separado por autor de eval, publicação via `/eval-publish`. R1–R4 e R6 são `false`.
> **Evidência:** teste que falha antes (R1 `hosted_security_problems` com flag sem marcador; R5 `protected_changes(["scripts/ci_eval_scope.py"])`; R6 `X-Forwarded-For`); comando nos itens de CI (R2 `uvx zizmor` sem `artipacked`; R3 YAML válido; R4 `ruff check --select …` limpo e job verde).

---

## 1. Contexto & Objetivo

A varredura de segurança de 11/11/2026 (gitleaks, pip-audit, osv-scanner, `npm audit`, actionlint = 0 achados; semgrep, zizmor e ruff-S triados = 0 verdadeiros positivos) mais a revisão independente deixaram seis itens de severidade **baixa**, todos endurecimento barato e independentes entre si: uma flag de compra de teste que o boot hospedado não recusa, 10 `actions/checkout` com credencial persistida, Dependabot sem `cooldown`, dois gates de segurança que faltam no CI, um buraco de governança de eval e um limite de `/metrics` que usa o IP errado atrás da Vercel.

Princípio: "menor mudança correta" (AGENTS.md § Qualidade) e fail-closed (SPEC-218). Nada muda comportamento de jogo. Cada fato abaixo foi conferido no source em 11/11; linhas são da `main` em `0514cafa` e o executor as reconfere na Etapa 0 (a `main` anda).

## 2. Requisitos

### R1 — `RPG_PLAY_ACCEPT_TEST_PURCHASES` recusada em hosted fora de staging

**Evidência do problema.**
- `infrastructure/runtime.py:468-477` `FORBIDDEN_IN_HOSTED` não contém a flag; só `scripts/release/checklist.py:56-65` (`FORBIDDEN_IN_PROD`, linha 62) a lista, e o checklist só olha os **nomes** de env do projeto Vercel de produção (`checklist.py:292-293`). O boot não protege.
- `specs/SPEC-225-supply-chain-ci-release-hygiene.md:35` (R8) manda a env entrar em `FORBIDDEN_IN_HOSTED` e ser "só permitida em `local`/staging": desvio de spec. `tests/test_boot_policy.py:248-253` documenta e tolera o desvio.
- A flag é lida em `infrastructure/google_play_payments.py:35-36` (`== "1"`) e o QA de compra de teste do staging precisa dela (`:30-31`). Logo **não** pode ir à lista fixa de proibidas.
- O runtime não distingue produção de staging. Não existe `VERCEL_ENV`, `RPG_ENV`, `RPG_DEPLOY_*` no repo (`Grep` zerado). `VERCEL_ENV` não serve: o staging é um projeto Vercel separado deployado com `--prod` (`scripts/staging/measure.py:53`, `job_survival.py:224`), então vale `production` nos dois. `scripts/staging/common.py:55-69` recusa ref protegida, mas isso é guarda de script, não do processo.
- Hoje o staging **não** define a flag (`scripts/staging/vercel_env.py` e `staging_flags.json` não a citam; o QA depende da SPEC-198, bloqueada no dono). Portanto a mudança não derruba o staging atual.

**Requisitos.**
- **R1.1** Novo marcador de ambiente `RPG_DEPLOY_ENV`, valores aceitos `staging`; qualquer outro valor ou ausência = "não é staging" (falha fechada). Registrado em `config/flags.yaml` (`kind: config`, `spec: SPEC-411`), gate de flags da SPEC-340 verde.
- **R1.2** Nova `Requirement` em `HOSTED_SECURITY_REQUIREMENTS` (`runtime.py:597-613`): se `_truthy(env, "RPG_PLAY_ACCEPT_TEST_PURCHASES")` e `RPG_DEPLOY_ENV.strip().lower() != "staging"` → problema `"permitida só com RPG_DEPLOY_ENV=staging"`. Flag ausente/`0` → sem problema (o staging atual segue igual). `FORBIDDEN_IN_HOSTED` **não muda** (o teste `test_boot_policy.py:250-253` continua valendo).
- **R1.3** Efeito: produção (marcador ausente ou `production`) com a flag ligada falha o boot em hosted\* e em `portable` exposto (mesmo caminho que `RPG_COOKIE_SECURE`, `runtime.py:666-670`), e `is_hardened` vira `False`. `local`/`legacy` não são afetados.
- **R1.4** `scripts/staging/vercel_env.py` passa a enviar `RPG_DEPLOY_ENV=staging` nos literais do staging (junto de `RPG_RUNTIME_PROFILE`, ~`:40`). Preview não recebe a flag nem o marcador (`PREVIEW_LITERALS`, `:57`).
- **R1.5** Teste de paridade: o comentário/asserção de `test_boot_policy.py:248-253` passa a dizer que a flag é condicional (marcador de staging), não "só na lista de produção".

**Ordem de rollout (obrigatória, vai para o runbook em `docs/spec411/README.md`).** (1) pousar o código (flag ausente: nenhum efeito); (2) sincronizar o env do staging com `RPG_DEPLOY_ENV=staging` (`vercel_env.py`); (3) **só depois** ligar `RPG_PLAY_ACCEPT_TEST_PURCHASES=1` (SPEC-198). Inverter 2 e 3 faz o staging recusar o boot (`hosted_config_insecure`) ou aparecer `hardened=false`.

### R2 — `persist-credentials: false` nos checkouts restantes

**Evidência.** `.github/workflows/` tem 19 `uses: actions/checkout`; 9 já têm a flag (`coverage.yml:16`, `llm-playtest-weekly.yml:35`, `audit-local.yml:22`, `validate.yml:25,127,141`, `eval-protected.yml:28,58,70`). **Faltam 10** (batem com os 10 `artipacked` do zizmor):

| Workflow | Linhas do `uses:` | Qtde |
|---|---|---|
| `eval-gates.yml` | 20 (`scope`), 46 (`protected-evaluator-review`), 63 (`deterministic-evals`), 109 (`backend-selective`), 133 (`frontend-selective`) | 5 |
| `validate.yml` | 38 (`docs-only`), 53 (`test`), 100 (`api-fuzz`) | 3 |
| `audit-local.yml` | 35 (`infra-browser`) | 1 |
| `post-deploy-smoke.yml` | 24 (`smoke`) | 1 |

**Risco de quebra conferido:** `Grep "git push|gh (pr|api|release)"` nos workflows não acha nada; os jobs só fazem `git diff` local (`scripts/ci_eval_scope.py`, `ci_docs_only.py`), que usa objetos já baixados no checkout (`fetch-depth: 0` onde precisa). O único uso de token é `GITHUB_TOKEN` por `env:` do gitleaks (`validate.yml:130`), que não depende do checkout.

- **R2.1** Os 10 checkouts ganham `with: persist-credentials: false` (mesclando com `fetch-depth` onde já há bloco `with:`).
- **R2.2** O executor reconfere, nos scripts chamados por esses jobs (`scripts/dev_stack.py`, `audit_local_gate.py`, `post_deploy_smoke.py`, `ci_*`), que nenhum faz `git fetch/push` contra o remoto; se algum fizer, aquele job fica de fora e vira nota na spec.
- **R2.3** `uvx zizmor` (versão do R4a) não reporta `artipacked`.

### R3 — `cooldown` no Dependabot

**Evidência.** `.github/dependabot.yml:5` (github-actions), `:14` (uv), `:23` (npm) sem `cooldown` (semgrep `dependabot-missing-cooldown` ×3).

- **R3.1** Cada um dos 3 ecossistemas ganha `cooldown: { default-days: 7 }` (proposta; D3). Efeito: versão recém-publicada (inclusive maliciosa) só vira PR após 7 dias.
- **R3.2** *A confirmar pelo executor na doc do Dependabot (Etapa 0):* que o `cooldown` **não** atrasa security updates (a doc diz que só afeta version updates) e que `default-days` vale para `github-actions`, `uv` e `npm`. Se algum ecossistema não suportar a chave, o YAML é rejeitado: validar com `actionlint`-like/`yaml.safe_load` e com a checagem de config do Dependabot na aba do GitHub após o push.
- **R3.3** O comentário do cabeçalho do arquivo cita a SPEC-411 R3.

### R4 — gates de segurança que faltam no CI

Já existem em `validate.yml` e **não são duplicados**: `pip-audit` (`:59-60`, `:103-106`), gitleaks no diff e semanal (`:120-131`), `npm audit` (`:149`).

- **R4a — zizmor.** Job novo `workflow-lint` em `validate.yml` (sem `needs`, roda também em PR só de docs/workflows): `uvx --from zizmor==<versão fixada> zizmor .github/workflows/` — o executor escolhe o modo mínimo que reproduz a triagem de 11/11 (`.github/workflows/`, falha em achado ≥ medium) e fixa a versão (padrão `pip-audit==2.10.1`, `:60`). Depende do R2 (sem ele o job nasce vermelho por `artipacked`). Se restarem achados triados como falso positivo, vão para `.github/zizmor.yml` com motivo por linha, nunca desligar a regra inteira. `permissions:` do job novo = `contents: read` (herda o topo); o checkout do job usa `persist-credentials: false`.
- **R4b — subconjunto ruff `S`.** Em `pyproject.toml:77` (`select`) acrescentar **somente**: `S324`, `S602`, `S604`, `S605`, `S105`, `S106`, `S107`. **Não ligar**: `S311` (54, RNG de jogo), `S101`, `S110`/`S112` (cobertos pelo gate de `except Exception`/BLE), `S603`, `S607`, `S108`, `S104`, nem a família `S` inteira. Escopo: só código de produto; `[tool.ruff.lint.extend-per-file-ignores]` ganha `"S"` para `tests/**`, `scripts/**`, `evals/**`, `playtest/**`, `.claude/**` (`docs`, `data` etc. já saem por `extend-exclude`, `:66`). Ignorar `S` em `evals/**` não altera hash de arquivo protegido (config fora de `evals/`), e `tests/test_ruff_protected_exempt.py` só cobra as famílias da SPEC-388, não `S`.
  - **Como entra:** `select` + zerar os hits no produto; `ruff-baseline.toml` (gerado por `scripts/dev/ruff_baseline.py`, congela dívida **por arquivo**) só é regenerado se sobrar hit. Meta: **nenhuma entrada nova** na baseline; rodar `bash scripts/dev/py.sh scripts/dev/ruff_baseline.py --check` e, se ficar stale por causa de outra mudança, regenerar sem inflar. O hook `.claude/hooks/ruff_after_edit.py` usa a mesma config (`ruff check --fix --force-exclude`), então as regras novas aparecem como "ruff ainda acusa" ao editar; nenhuma `S` tem autofix, não há risco de reescrita.
  - **S324 (3 hits):** `agents/combat.py:537,556` e `services/scene_cards.py:662` → `hashlib.sha1(..., usedforsecurity=False)`. É id derivado/determinismo do baralho, saída idêntica byte a byte (o parâmetro só sinaliza uso não criptográfico); não há troca de algoritmo. Prova: testes existentes de combate/scene_cards verdes, sem mudança de assert.
  - **S105/S106/S107 (4 falsos positivos):** `token_mode` em `routes/turn.py` (≈1727-1838; os números 1791/1808/1838 da triagem mudaram, o executor usa `ruff check --select S105,S106,S107` para achar) e `TOKEN_URL` em `services/google_play.py:25` → `# noqa: S105  # <motivo>` (nome de modo/URL pública, não segredo). `noqa` só de regra ativa no `select` (AGENTS.md).
  - **S602/S604/S605:** 0 hits; entram como barreira.
  - **S608 (29 hits, todos falsos positivos: o fragmento interpolado é constante ou vem de allowlist).** **Recomendação: NÃO ligar `S608`**; em vez de 29 `noqa`, travar as duas allowlists que realmente sustentam a segurança com um teste: `tests/test_sql_identifier_allowlists.py` asserta (i) `infrastructure.postgres_shared_pool._UPDATABLE` (`:29`, usado em `:119`) é exatamente o conjunto conhecido e cada nome casa `^[a-z_][a-z0-9_]*$`; (ii) `PRIVATE_TABLES` (`account_lifecycle.py:10`), `FINANCIAL_TABLES` e `EXPORT_TABLES` (`:350`) idem. Trade-off: o teste não pega um f-string SQL novo; os 29 `noqa` pegariam, ao custo de ruído permanente e de motivos que apodrecem. Decisão do dono em D4.
- **R4c** O job `workflow-lint` e o `ruff check .` (já em `validate.yml:61`) ficam verdes no branch; `ruff check --select S324,S602,S604,S605,S105,S106,S107 --force-exclude .` limpo.

### R5 — scripts de escopo de eval e o workflow em caminhos protegidos (EVAL_AUTHORING_REQUIRED)

**Evidência.** `.github/workflows/eval-gates.yml:20-33` decide `protected` rodando `scripts/ci_eval_scope.py` **do HEAD do PR**; `:55` roda `scripts/verify_protected_eval_change.py`, também do HEAD. Nem os dois scripts nem o workflow estão em `evals/protected-paths.txt` (30 linhas lidas; `evals/core/governance.py:28-43` define só o mínimo exigido, e `:89-100` une o arquivo ao mínimo). Um PR que altere esses arquivos não aciona o environment `eval-governance`.

- **R5.1** `evals/protected-paths.txt` ganha 3 linhas: `scripts/ci_eval_scope.py`, `scripts/verify_protected_eval_change.py`, `.github/workflows/eval-gates.yml`.
- **R5.2** Teste novo em `tests/test_ci_eval_gates.py` (ou `test_eval_governance.py`): `protected_changes([...cada um dos 3...], load_protected_paths(ROOT/"evals/protected-paths.txt"))` devolve o próprio caminho; **falha hoje** (devolve `[]`). E `classify(["scripts/ci_eval_scope.py"], protected)["protected"] is True`.
- **R5.3** `.py` protegidos novos exigem glob em `[tool.ruff.lint.extend-per-file-ignores]` com as famílias da SPEC-388 (`tests/test_ruff_protected_exempt.py:37-42`): acrescentar os dois scripts à lista em `pyproject.toml` (~`:91-101`), mesmo formato das linhas existentes. Está no commit de eval (a mudança é consequência direta da proteção).
- **R5.4** Nenhum dataset, evaluator, registry, expected, denominador ou baseline muda; `evals/baselines/deterministic.json` não fica stale (o executor confirma `evals compare` exit 0 no run do CI, conforme `/eval-publish`).
- **Limite honesto (para o dono, D5):** listar os caminhos só faz uma edição **honesta** nesses arquivos cair no gate. Como `scope` executa o `ci_eval_scope.py` e lê o `protected-paths.txt` **do HEAD**, um PR adversarial que reescreva o próprio script para emitir `protected=false` ainda passa. A correção forte é rodar o scope e ler a lista a partir do **base SHA**; é uma mudança de workflow maior e fica como follow-up (não-objetivo abaixo).
- **R5.5 Processo.** Commit **separado**, só com caminhos protegidos + o glob do `pyproject.toml` + o teste, por autor de eval; publicação por `/eval-publish` (`scripts/dev/eval_publish.py --base origin/main`), 1 aprovação do dono no environment `eval-governance` (`.claude/skills/eval-publish/SKILL.md`). Sem código de produto no mesmo commit.

### R6 — `/metrics` usa o IP do cliente real

**Evidência.** `api.py:905` `ip = request.client.host if request.client else "?"` no limitador de `/metrics` (SPEC-221 R3, `_rate_limit_metrics`, `:897-916`); o resto usa `_client_ip` (`api.py:127` import, `:496`, `:531`, `:944`; definido em `api_core.py:246`, que delega a `services/abuse_policy.py:135 client_ip`). Esse helper: com `VERCEL` setado usa `x-vercel-forwarded-for` (a plataforma sobrescreve) e depois `x-real-ip`; com `RPG_TRUSTED_PROXY_HOPS=N>0` usa o N-ésimo valor da **direita** de `x-forwarded-for` (valores à esquerda são spoofáveis); senão `request.client.host`; nunca levanta. Atrás da Vercel todas as sondas sem token caem no mesmo balde (IP do proxy).

- **R6.1** `api.py:905` → `ip = _client_ip(request)`. Sem outras mudanças (o `record_block(..., ip=ip)` recebe o mesmo valor).
- **R6.2** Testes (no arquivo que já cobre o limite de `/metrics`; `Grep "_rate_limit_metrics|/metrics" tests/` define, provável `tests/test_surfaces_221.py`): (a) com `VERCEL=1` e `RPG_METRICS_TOKEN` ausente, 13 requisições com `x-vercel-forwarded-for` **distintos** → nenhuma 429; (b) 13 do **mesmo** `x-vercel-forwarded-for` → a 13ª é 429 com `Retry-After`; (c) com `RPG_TRUSTED_PROXY_HOPS=1` e `X-Forwarded-For: spoof, 203.0.113.9` o balde é `203.0.113.9` (o valor à esquerda é ignorado); (d) sem marcador de proxy e sem hops, `X-Forwarded-For` é **ignorado** (comportamento atual preservado, sem spoof). O teste (a) falha hoje.
- **R6.3** O scraper autenticado continua isento (`api.py:903-904` intocado).

### Fora de escopo (com motivo)

- `/health` devolver `profile`/`hardened`: decidido em SPEC-218 R9 e SPEC-221.
- Trocar SHA-1 por outro algoritmo "por segurança": não há seed secreta; o determinismo do baralho é decisão de produto. O R4b só sinaliza `usedforsecurity=False`.
- Os ~10 `except: pass` sem log: telemetria, pertencem à onda 383/384; o gate BLE já existe.
- `defusedxml` em `scripts/audit_local_gate.py`: parseia o JUnit do próprio CI; custaria uma dependência.
- Revogar as 3 RPCs `SECURITY DEFINER`: D4 da SPEC-410.
- Proteção de senha vazada no Auth: painel do dono.
- Stripe live: SPEC-197.
- Rodar `ci_eval_scope.py`/`protected-paths.txt` a partir do base SHA (fecha o limite do R5): follow-up em spec própria.
- Ligar `S311`, `S101`, `S110`/`S112`, `S603`, `S607`, `S108`, `S104`, `S608` no ruff (motivos no R4b).
- Exigir `RPG_DEPLOY_ENV` no `REQUIRED_ENV` do checklist de release (o checklist só vê nomes, não valores; o runtime já é a trava).
- Qualquer mudança de comportamento de jogo, evaluator, expected, dataset, baseline ou denominador.

## 3. Design técnico

- **Arquivos novos:** `docs/spec411/README.md` (medições da Etapa 0, runbook de rollout do R1, saída do `zizmor`, resultado do R4b); `tests/test_sql_identifier_allowlists.py` (R4b); `.github/zizmor.yml` só se sobrar falso positivo.
- **Arquivos alterados:**
  - R1: `infrastructure/runtime.py` (1 `Requirement` + 1 função `_test_purchases_problem(env)`, ≤ 10 linhas, ao lado de `_forbidden_problem`, `:577`), `config/flags.yaml`, `scripts/staging/vercel_env.py` (literal), `tests/test_boot_policy.py`, `.env.example` (documentar o marcador).
  - R2: `.github/workflows/{eval-gates,validate,audit-local,post-deploy-smoke}.yml`.
  - R3: `.github/dependabot.yml`.
  - R4: `.github/workflows/validate.yml` (job `workflow-lint`), `pyproject.toml` (`select` + per-file-ignores `S`), `agents/combat.py`, `services/scene_cards.py`, `routes/turn.py`, `services/google_play.py`, `ruff-baseline.toml` só se necessário.
  - R5: `evals/protected-paths.txt`, `pyproject.toml` (globs dos 2 scripts), `tests/test_ci_eval_gates.py`.
  - R6: `api.py` (1 linha), teste do limite de `/metrics`.
- **Assinaturas:** nenhuma pública nova. `Requirement("RPG_PLAY_ACCEPT_TEST_PURCHASES", _test_purchases_problem)` com `_test_purchases_problem(env: Mapping[str, str]) -> str | None`.
- **Formato (R1):** `RPG_DEPLOY_ENV=staging` (string, case-insensitive, sem espaços); qualquer outro = produção.
- **Schemas/saves:** nenhum. Nenhum `GameState` muda.

## 4. Plano passo a passo

Uma etapa por item, independentes (exceto R4a depois de R2). Um commit por etapa, inglês, Conventional Commits. Subagente roda só testes do escopo (`bash scripts/dev/pt.sh`, `-n 2`), `ruff format`+`ruff check`, e não edita `ESTADO_ATUAL.md`/`ROADMAP.md`/`specs/index.yaml`.

### Etapa 0 — Linha de base (sem código de produto)
1. Criar `docs/spec411/README.md`. Reconferir cada linha citada (`Grep`); contar checkouts sem a flag (esperado: 10 de 19).
2. R1: confirmar onde `hosted_security_problems` derruba o boot em `hosted*` (`RuntimeConfig.from_env` vs só `/health`/`is_hardened`) e registrar; confirmar no `.env.staging`/Vercel (só nomes) que a flag **não** está definida no staging.
3. R3: confirmar na doc do Dependabot o suporte e a semântica do `cooldown` (R3.2).
4. R4b: `uv run ruff check --select S324,S602,S604,S605,S105,S106,S107,S608 --force-exclude . --statistics` e colar contagens (esperado 3/0/0/0/4 e S608=29); versão atual do `zizmor` para fixar.

### Etapa R6 — `/metrics` (menor risco, primeiro)
1. **Testes primeiro:** R6.2 (a)–(d); (a) falha antes.
2. Trocar `api.py:905` por `_client_ip(request)`.
3. Verificação: o arquivo de teste do limite de `/metrics` + `tests/test_abuse_policy.py -q`.

### Etapa R2 — `persist-credentials: false`
1. Sem teste Python; prova por comando: `uvx --from zizmor==<v> zizmor .github/workflows/` mostra 10 `artipacked` antes, 0 depois.
2. Editar os 10 checkouts (R2.1); conferir R2.2.
3. Verificação: `check_workflow_hygiene` do release (`scripts/release/checklist.py:306`) e `tests/test_spec225*` verdes; `actionlint` se disponível; CI do branch verde (ci-watcher).

### Etapa R3 — `cooldown`
1. Prova: `yaml.safe_load(.github/dependabot.yml)` mostra `cooldown.default-days == 7` nos 3 blocos; semgrep `dependabot-missing-cooldown` = 0.
2. Editar (R3.1/R3.3).
3. Verificação: após o push, a aba "Dependabot" do GitHub não mostra erro de config (coordenador confere).

### Etapa R1 — marcador de staging e flag de compra de teste (revisor Sonnet)
1. **Testes primeiro** (`tests/test_boot_policy.py`): `test_play_test_purchases_recusada_sem_marcador_de_staging` (env hosted seguro + flag `1` → `hosted_security_problems` contém `RPG_PLAY_ACCEPT_TEST_PURCHASES`; falha antes); `..._recusada_com_marcador_production`; `..._aceita_com_marcador_staging` (sem problema); `..._flag_ausente_nao_exige_marcador` (staging atual); `..._assert_boot_policy_levanta_em_hosted_supabase` (flag + sem marcador); `..._legacy_e_local_nao_afetados`; asserção de paridade `FORBIDDEN_IN_HOSTED` inalterado. `tests/test_staging_vercel_env*` (o que existir por `Grep vercel_env tests/`): `RPG_DEPLOY_ENV=staging` nos literais e **fora** de `PREVIEW_LITERALS`.
2. Implementar R1.1–R1.5; `config/flags.yaml`; runbook em `docs/spec411/README.md` com a ordem de rollout.
3. Verificação: `tests/test_boot_policy.py tests/test_flag_registry*.py tests/test_spec194_google_play.py tests/test_spec197_checklist.py -q` (Glob define a lista), `ruff`. Revisor Sonnet lê o diff de `runtime.py` e confirma fail-closed (marcador ausente = recusa) e que nada novo é exigido de quem não liga a flag.

### Etapa R4 — gates de segurança
1. **Testes primeiro:** `tests/test_sql_identifier_allowlists.py` (R4b); `ruff check --select …` com 3+4 hits antes.
2. R4b: `select`, per-file-ignores `S`, `usedforsecurity=False` (3), `noqa` com motivo (4); rodar `ruff_baseline.py --check`. R4a: job `workflow-lint` com versão fixada.
3. Verificação: `ruff check .`, `ruff format --check .`, `tests/test_size_budget.py`, testes de combate e `scene_cards` do escopo, `uvx zizmor` limpo; job novo verde no CI.

### Etapa R5 — governança de eval (FINAL e isolável; EVAL_AUTHORING_REQUIRED)
1. **Teste primeiro** (R5.2): falha hoje com `[]`.
2. Autor de eval: 3 linhas em `evals/protected-paths.txt`, globs em `pyproject.toml`, teste. Commit separado, sem código de produto.
3. Verificação local: `tests/test_ci_eval_gates.py tests/test_eval_governance.py tests/test_ruff_protected_exempt.py -q`; `python -m evals.core.governance check --root .`.
4. `/eval-publish`; o dono aprova `eval-governance`. **A spec pode fechar `in-progress`** aguardando esse clique sem travar R1–R4 e R6; vira `done` quando o run do `eval-gates` com aprovação passar e `compare` sair 0.

### Fechamento
`ruff format --check`, `ruff check`, `dup_helpers.py --diff main...HEAD` (nenhum helper novo esperado), `tests/test_size_budget.py`; coordenador: suíte completa 1× no `/spec-land`.

## 5. Critérios de aceite

- [ ] R1: com `RPG_RUNTIME_PROFILE=hosted-supabase`, config segura e `RPG_PLAY_ACCEPT_TEST_PURCHASES=1`, `hosted_security_problems` acusa a flag sem `RPG_DEPLOY_ENV=staging` e fica limpo com ele; `RPG_DEPLOY_ENV` registrada em `config/flags.yaml`; `vercel_env.py` envia o marcador só ao staging; runbook com a ordem 1-2-3 no `docs/spec411/README.md`.
- [ ] R2: `Grep persist-credentials` = 19/19 checkouts; `zizmor` sem `artipacked`; nenhum job do CI quebrou (CI verde).
- [ ] R3: `cooldown.default-days: 7` nos 3 ecossistemas; item de doc do R3.2 confirmado e registrado.
- [ ] R4a: job `workflow-lint` com `zizmor` de versão fixada, verde. R4b: regras `S324,S602,S604,S605,S105,S106,S107` no `select`, `S` ignorada em `tests/scripts/evals/playtest/.claude`, 0 hit no produto, `ruff-baseline.toml` sem entrada nova, `S608` conforme D4 (teste de allowlist se aceita a recomendação).
- [ ] R5: as 3 linhas em `evals/protected-paths.txt`, teste verde, `test_ruff_protected_exempt.py` verde, publicado com aprovação do dono no `eval-governance` e `compare` exit 0. (Único item que pode manter a spec `in-progress`.)
- [ ] R6: limite de `/metrics` por `_client_ip`; testes (a)–(d) verdes; scraper autenticado continua isento.
- [ ] `uv run pytest` verde (suíte completa offline, 1× pelo coordenador no pouso)
- [ ] Guard de FallbackLLM: não se aplica (nenhum `with_structured_output` novo)
- [ ] Saves antigos continuam carregando (nenhum formato muda)

## 6. Smoke test com LLM real

Não se aplica: nenhuma etapa muda `with_structured_output`, prompt, roteamento ou modelo. Verificação equivalente de infra, obrigatória antes de `done`:
1. R1: `bash scripts/dev/py.sh -c` com env hosted seguro + flag, com e sem `RPG_DEPLOY_ENV=staging`, mostrando recusa e aceite (nomes, nunca valores); depois do sync do staging com o marcador, `scripts/staging/vercel_smoke.py` verde (coordenador, só se o staging for sincronizado nesta spec).
2. R2/R4a: run do `validate`/`eval-gates` no branch verde, incluindo o job `workflow-lint`.
3. R6: `bash scripts/smoke_api.sh` offline sem regressão; no staging, 13 `GET /metrics` sem token de IPs distintos não dão 429 (opcional, coordenador).

## 7. Riscos & compatibilidade

- **R1: staging não subir por falta de marcador.** Só ocorre se a flag for ligada antes de `RPG_DEPLOY_ENV=staging`. Hoje a flag está ausente, então nada muda até a SPEC-198. Mitigação: ordem 1-2-3 no runbook e teste "flag ausente não exige marcador". Reverter = `git revert` do commit da etapa.
- **R1: produção.** Ausência de marcador = produção = flag recusada: é o comportamento desejado (falha fechada); não exige configurar nada em produção.
- **R2: job que dependa do token persistido.** Conferido: nenhum `git push`/`gh` nos workflows; R2.2 reconfere os scripts. Se algum job quebrar, a flag volta só nele, com comentário.
- **R3:** atrasa PRs de versão em 7 dias; security updates não (a confirmar, R3.2). Se `cooldown` for rejeitado por ecossistema, o Dependabot para de abrir PRs daquele bloco: validar a config pós-push.
- **R4a:** zizmor pode reportar achados novos além dos 10 `artipacked`; triar, não desligar regra. **R4b:** `S` em `scripts/**` ignorada é lacuna consciente (ferramentas de dev); `S608` fora do ruff é lacuna consciente (D4).
- **R5:** o commit de eval exige o clique do dono; até lá o gate fraco continua como hoje. A mudança do workflow protegido passa a exigir aprovação em PRs futuros que a toquem (inclusive esta). Limite do base-SHA no R5.
- **R6:** atrás de proxy sem `RPG_TRUSTED_PROXY_HOPS` nem `VERCEL`, o comportamento é idêntico ao atual (`client.host`); com `VERCEL`, passa a limitar por cliente real (mais baldes, menos 429 colaterais).
- MockLLM/FallbackLLM, quota e latência: sem impacto.

## 8. Decisões do dono

- **D1 — Marcador.** Recomendado: `RPG_DEPLOY_ENV=staging` (novo, registrado), com falha fechada (ausente = produção). Alternativa descartada: `VERCEL_ENV` (vale `production` nos dois projetos).
- **D2 — Desvio da SPEC-225 R8.** Recomendado: aceitar a flag como **condicional** (proibida salvo marcador de staging) em vez de entrar em `FORBIDDEN_IN_HOSTED`, porque o staging a exige; o objetivo da R8 (produção recusa) é cumprido.
- **D3 — Cooldown.** Recomendado: `default-days: 7` nos 3 ecossistemas.
- **D4 — `S608`.** Recomendado: não ligar no ruff; teste que trava `_UPDATABLE` e as tabelas de `account_lifecycle`. Alternativa: ligar com 29 `# noqa: S608  # <motivo>`.
- **D5 — Hardening do R5.** Recomendado: fazer só as 3 linhas agora (publicação com 1 clique) e abrir spec própria para executar o scope a partir do base SHA.
- **D6 — Aprovação do `eval-governance`** para a Etapa R5 (clique do dono; spec pode ficar `in-progress` até lá).
