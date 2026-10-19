# 04 — Testes e CI

Foco: tempo da suíte, seleção de testes, estabilidade do Playwright, Project
Index no CI, aprovação de governança de evals, custo do CI. Números do worktree
`b05932e`, dos logs em scratchpad e de `gh run list` (40 runs mais recentes).

## 1. Estado atual

### Suíte Python

| Métrica | Valor |
|---|---|
| Testes coletados | **4.145** (4.130 no conjunto default; `llm_contract` 11 + `llm_playtest` 4 desselecionados) |
| Arquivos de teste | 342; os 15 maiores têm 36–106 testes cada (`test_mecanica_orfa` 106, `test_boot_policy` 66…) |
| Markers que viram `skip` sem stack local | `infra_local` 158 · `security_local` 14 · `browser_local` 11 · `chaos_local` 1 |
| Plugins | **nenhum** (sem `xdist`, `timeout`, `randomly`); sem `--durations` em lugar nenhum |
| Só coleta | ~12 s |
| Duração local completa (logs) | 120 s · 119 s · 192 s (10-16, ~3 K testes) · 361–393 s (sessão 10-15/16) · **667 s** (10-18, 3.854 passed, 223 skipped) |
| Duração nos subagentes da onda | 64 execuções parseáveis: **mediana 10,7 min**, 72 min somados; as mais longas 667/525/502 s — máquina disputada por vários agentes rodando a suíte ao mesmo tempo |
| Execuções completas na onda | **268 comandos por 80 agentes** (de 1.154 `pytest`), 112 estouraram os 120 s e viraram background |
| No CI (Linux) | `validate` 2,7–3,1 min no total (lint + audit + **suíte completa** + npm test + build) |
| `tests/test_project_index.py` | 7 testes, **34 s**, e falha sempre que há arquivo fonte alterado/novo no worktree (58 falhas em 31 agentes; brief já manda `--ignore`) |
| Isolamento | `tests/conftest.py` já força MockLLM, `tmp_path` para saves/memória/cache de runtime, embeddings nulos — **pré-condição para paralelizar já existe** |
| Flaky conhecidos | `WinError 5` no `os.replace` do save sob OneDrive (retry no código); nenhum rerun no CI nos 40 runs |

### Playwright (`web/e2e`)

| Métrica | Valor |
|---|---|
| Specs / testes | 26 arquivos, ~169 testes; projetos chromium, mobile-320, mobile-390, chromium-motion |
| Config | `baseURL 127.0.0.1:4173` **fixo**, `fullyParallel:false`, `retries:0`, timeout 30 s, `reuseExistingServer: !CI`, webServer = `vite dev` (ou `preview` com `RPG_E2E_SERVER`) |
| Dor observada | porta 4173 compartilhada entre worktrees (dica manual no brief); `test-failed-1.png` lido **18×**; `ENOENT test-results` 2×; `node_modules` ausente em worktree novo 3× (`ERR_MODULE_NOT_FOUND`) |
| No CI | `frontend-selective` (eval-gates, 25 min cap) e `audit-local` (Playwright Python, ~3,5 min) |

### CI (`.github/workflows`)

| Workflow | Gatilho | Duração típica | Observações |
|---|---|---|---|
| `validate.yml` | push main, PR, cron semanal | 2,7–3,1 min | sem `timeout-minutes`, **sem cache do uv** (`setup-uv` sem `enable-cache`), suíte completa sempre — inclusive nos **46 % de commits docs-only** |
| `audit-local.yml` | push main, PR, dispatch | 3,3–3,5 min | Supabase local + Playwright Python |
| `eval-gates.yml` | push main, PR, dispatch | 0,9–1,0 min; **12,2 min** quando espera aprovação | `scope` → `protected-evaluator-review` (environment **eval-governance**) → `deterministic-evals` (inclui `project_index check` ~29 s) → `backend-selective` / `frontend-selective` |
| `eval-protected.yml` / `post-deploy-smoke.yml` | manual | — | ok |
| Dependabot | semanal | — | burst de 18/10: **`validate` falhou em 7/7 PRs** (0,5–3,2 min, falha antes da suíte) — ruído vermelho permanente |

### Project Index no CI

- `python -m project_index check` regenera o grafo em memória e compara byte a
  byte com `manifest.json` + `repo_graph.json` (`project_index/generator.py:801-812`).
- O hash de origem inclui **`git ls-files --cached --others --exclude-standard`**
  (`generator.py:98-115`): qualquer arquivo `.py/.ts/...` **não rastreado** ou
  editado torna o índice "stale" → por isso o rebuild precisa de worktree limpo
  (`reindex.sh`, memória `project-index-clean-build`), e um `.zip`/pasta solta
  deixou o CI vermelho 3× em 15/10.
- Artefato commitado: `repo_graph.json` **12,7 MB, 391.232 linhas**; 117 commits
  tocam `project_index/` (40 % desde 28/09); 65 commits são só "chore: rebuild
  project index"; 482 K linhas de diff desde 12/10.
- O próprio `AGENTS.md:14-16` diz que o índice "não entra no contexto ou fluxo
  padrão" e o benchmark v6 (`docs/project-index-benchmark/`) deu 0/8 vitórias de
  custo — ou seja, o artefato mais caro de manter é o menos usado.

### Governança de evals (o "dance" de aprovação)

- Caminhos protegidos (`evals/protected-paths.txt`): `evals/core`, `evaluators`,
  `datasets/regression`, `manifest.lock.json`, `metrics-registry.yaml`, schemas,
  `web/e2e/contracts`. Tocar neles → job `protected-evaluator-review` com
  `environment: eval-governance` (reviewer obrigatório) **e**
  `scripts/verify_protected_eval_change.py` exige variável
  `EVALUATOR_CHANGE_APPROVED=true` (fail-closed).
- Na prática (transcrito do coordenador): `gh variable set EVALUATOR_CHANGE_APPROVED`
  em loop `for t in 1 2 3` → push → `gh run watch` (11×) → unset → **10 ciclos**,
  15–60 min cada; 10 handoffs `EVAL_AUTHORING_REQUIRED` esperando autoria/aprovação
  (SPEC-199, 203, 204, 205, 209, 210, 223, 229…).
- O agente não consegue aprovar o environment (e não deve). O custo é o
  liga/desliga da variável + a espera + a repetição por spec.

## 2. Proposta

### C1 — Suíte em camadas (o que cada papel roda)

| Camada | Comando | Quem | Tempo alvo |
|---|---|---|---|
| 0 | `ruff check` + `pytest -q --lf -x` | subagente, a cada iteração (`/qa`) | < 30 s |
| 1 | `pytest -q tests/test_<escopo>*.py -p no:cacheprovider` (lista no prompt do executor) | subagente, antes do hand-back | 1–2 min |
| 2 | `pytest -q -n auto --ignore=tests/test_project_index.py` | **coordenador**, 1× por spec no `/spec-land`, em background com `timeout 1200` | 2–4 min com xdist |
| 3 | suíte completa + `project_index check` + Playwright | CI | como hoje |

Regra para o brief: subagente **não** roda a camada 2 (hoje 80 agentes rodaram
268 vezes). Ganho por onda de 10 specs: −60 a −70 min de parede e −112 estouros
de 120 s.

### C2 — `pytest-xdist` + `pytest-timeout` (30 min)

- `uv add --dev pytest-xdist pytest-timeout`; `addopts` ganha
  `--timeout=180 -p no:randomly`; `-n auto` só na camada 2/CI (local default
  continua serial para não disputar com agentes paralelos).
- Testes com estado compartilhado (Postgres local, `uvicorn` em porta fixa,
  `infra_local`/`browser_local`) recebem `@pytest.mark.xdist_group("stack")` ou
  ficam fora do `-n` (`-m "not infra_local and not browser_local"`); a suíte
  default já os pula sem stack.
- Rodar **uma vez** `--durations=40` e marcar `@pytest.mark.slow` tudo acima de
  5 s; camada 1/2 excluem `slow`, CI inclui.
- Estimativa: 667 s → ~150–200 s local (4–8 workers); CI `validate` −1 min.

### C3 — Project Index: parar de pagar por um artefato que não é usado

Opções, da mais simples à mais radical:

1. **Hash só de arquivos rastreados** (`git ls-files --cached`, sem `--others`):
   um `.zip` ou scratch solto deixa de tornar o índice stale; rebuild em
   worktree limpo fica desnecessário. 5 linhas em `generator.py`.
2. **Rebuild dentro do `/spec-land`** (na própria branch, antes do ff):
   some o commit separado (−65 commits) e a pasta `rpg-index-wt`.
3. **Não commitar `repo_graph.json`** (12,7 MB): manter só `manifest.json`
   (32 KB, com `source_tree_hash`) e os YAML curados; o CI regenera o grafo e
   compara o hash do manifesto; quem precisar do grafo roda `build` local
   (29 s). −482 K linhas de diff, clones e `git log -p` mais leves.
4. **Rebaixar o `check` para `continue-on-error`** no `deterministic-evals` e
   tirar `test_project_index.py` do conjunto default local (marker `index`).

Recomendação: 1 + 2 agora (1 h); 3 na próxima limpeza de repo.

### C4 — Governança de evals em 1 clique

1. Definir `EVALUATOR_CHANGE_APPROVED=true` **uma vez, como variável do
   environment `eval-governance`** (não do repositório). Jobs só enxergam essa
   variável depois que o reviewer aprova o deployment — a aprovação vira o único
   gate e some o liga/desliga por run (10 ciclos × `for t in 1 2 3`).
   Confirmar que `verify_protected_eval_change.py` lê `vars.*` do job (o
   helper D viu "repository/environment variable"); se ler só repo-level, trocar
   para `${{ vars.EVALUATOR_CHANGE_APPROVED }}` no step.
2. **Lotear** autoria de evals: 1 PR por onda com todos os `EVAL_AUTHORING_REQUIRED`
   (hoje 10 handoffs) → 1 aprovação em vez de 10.
3. Skill `/eval-publish` (ver `03`): checa que só caminhos protegidos mudaram,
   push, imprime o link do run **e o comando que o dono roda para aprovar**
   (`gh api -X POST repos/Batatao343/rpg-ia-master/actions/runs/<id>/pending_deployments -f environment_ids[]=<id> -f state=approved -f comment=ok`),
   depois `gh run watch --exit-status`. O dono aprova pelo app do GitHub ou pelo
   comando; o agente nunca espera em loop.
4. Tempo: de 15–60 min por ciclo para ~5 min + 1 clique do dono.

### C5 — Playwright estável entre worktrees (45 min)

- `playwright.config.ts`: porta de `RPG_E2E_PORT` (default 4173) e
  `webServer.port` igual; `/spec-new` exporta uma porta derivada do número da
  spec (`4000 + NNN % 1000`). Fim do "porta 4173 ocupada" e da config temporária.
- `retries: process.env.CI ? 1 : 0`, `trace: 'on-first-retry'`,
  `reporter: [['line'], ['json', {outputFile: 'test-results/results.json'}]]`
  (menos saída no tool-result; `test-results` criado pelo reporter → some o ENOENT).
- Brief: falha de e2e → ler **1×** o `results.json` filtrado (não o PNG 18×).
- `web/node_modules`: a junção já está no `wt.sh`; `/spec-new` falha cedo se
  `web/node_modules/.bin/vite` não existir.

### C6 — CI mais barato e menos vermelho (30 min)

- `validate.yml`: `enable-cache: true` no `setup-uv`; `timeout-minutes: 20`;
  `concurrency: {group: validate-${{ github.ref }}, cancel-in-progress: true}`.
- Filtro de caminhos: push/PR que só muda `docs/**`, `handoffs/**`,
  `proximas-specs/**`, `*.md` → job `docs-only` (validate_content + link check,
  < 1 min) em vez da suíte completa. Hoje 46 % dos commits são docs-only.
- Dependabot: `groups:` semanal (1 PR para pip, 1 para npm, 1 para actions) e
  investigar por que `validate` falha em 0,5 min nessas PRs (provável `uv sync
  --frozen` contra lock desatualizado → usar `uv lock --upgrade-package` no PR
  ou `--no-frozen` só nesse contexto).
- `pytest -n auto` no `validate` (C2).

## 3. Resumo

| # | Mudança | Ganho | Esforço | Risco |
|---|---|---|---|---|
| C1 | suíte em camadas; completa só no coordenador | −60–70 min de parede e −~200 execuções por onda; −112 estouros de timeout | brief + skill | médio (regressão cruzada vista no land, não no subagente) |
| C2 | xdist + timeout + `slow` | 667 s → ~3 min local; sem teste pendurado | 30 min + 1 run de `--durations` | baixo (isolamento já existe) |
| C3 | índice: hash só tracked + rebuild no land (+ não commitar o grafo) | −65 commits, −482 K linhas de diff, 0 CI vermelho por arquivo solto | 1 h (+1 h) | baixo |
| C4 | governança 1 clique + lote | 10 ciclos de 15–60 min → ~5 min | 30 min + confirmação do script | baixo |
| C5 | porta por worktree, retries, reporter | fim do conflito de porta e das 18 leituras de PNG | 45 min | nenhum |
| C6 | cache uv, docs-only, dependabot agrupado | −1 min/run; −46 % de suítes inúteis; fim do vermelho do dependabot | 30 min | nenhum |
