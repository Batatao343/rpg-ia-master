# SPEC-375 — revisão independente da spec (draft)

> **Veredito:** `CHANGES_REQUIRED` na spec. Classificação de risco: **SAFE-WITH-CHANGES** (o objetivo é seguro, mas o texto atual deixa três caminhos de quebra silenciosa)
> **Revisor:** spec-reviewer (Opus) · **Data:** 2026-11-03 · **Commit revisado:** `2a6e0945` (main) · spec `specs/SPEC-375-refactor-higiene-index-ci.md`

## Escopo

Revisão crítica da spec antes da aprovação, não de código implementado. Fiz o seguinte:
- conferi cada [F]/[H] contra o código e o `git log`;
- cacei consumidores do índice, dos jobs de CI e de `.tmp/`;
- rodei a trava W1;
- reproduzi em um repo descartável (scratchpad) o rebase modify/delete e o `git add` de arquivo ignorado;
- rodei `tests/test_project_index.py` (8 passed, 62 s).

Não editei spec, código, testes nem dados.

## Veredito por requisito

| R# | Veredito | Evidência | Mudança exigida |
|---|---|---|---|
| R1 | OK com ressalva | `git ls-files project_index` lista os dois artefatos. `generator.py:46-50,116` já exclui `GENERATED_PATHS` do scan, então branches que ainda versionam o arquivo continuam com o hash certo. Prova no scratch: ao fazer checkout (ou ff) de um commit que destrava o arquivo, o git **apaga** o arquivo da árvore de trabalho. | Registrar que, depois do pouso, o checkout principal e cada worktree rebaseado ficam sem índice até rodar `build`. A primeira `query` falha, e isso é esperado. |
| R2 | Já quase atendido | `__main__.py:59-61` captura `ProjectIndexError`, imprime 1 linha e sai com 1, sem traceback. `_read_json` (`generator.py:808-815`) converte `OSError` em `ProjectIndexError`. Falta só a dica "rode build". | Rebaixar R2 para "acrescentar a dica `build`" em dois casos: artefato ausente **e** artefato stale. Com artefato local, qualquer commit deixa o índice stale, porque `query.py:55`, `symbol`, `tests` e `state` chamam `check_index`. Hoje a mensagem de stale (`generator.py:827-829`) não diz o que fazer. |
| R3 | OK | `wt.sh:36-38,47-48`, `reindex.sh:11-21`. Prova no scratch: com o `wt.sh` antigo e o `.gitignore` novo, `git add` sai com rc=1 ("paths are ignored") e o `set -e` aborta. A §3 está certa ao exigir R1+R3+R4 no mesmo commit. | Proteção extra: `sync_branch` deve rodar `git rm -q --cached --ignore-unmatch project_index/repo_graph.json project_index/manifest.json` antes do commit, em toda execução. Isso conserta sozinho a ressurreição descrita em R4. |
| R4 | **Insuficiente (P1)** | 1) Commit de sync **sempre** toca `specs/index.yaml` e os dois artefatos juntos (`wt.sh:38`). No rebase, o conflito típico é `DU repo_graph.json` + `DU manifest.json` + `UU specs/index.yaml`. A regra "só quando **todos** os conflitos estão em `project_index/`" quase nunca dispara. 2) A skill atual (`.claude/skills/spec-land/SKILL.md:18-19`) manda `git checkout --theirs`. Reproduzi: num conflito DU, `--theirs` + `git add` **ressuscita** o arquivo como rastreado, o rebase segue sem erro, e o `land` faz ff na main com o arquivo de volta. O `.gitignore` não impede, e depois do R5 nenhum gate detecta. Outras sessões já têm esse texto da skill no contexto. | (a) Ampliar a autorresolução para conflitos ⊆ {`project_index/repo_graph.json`, `project_index/manifest.json`, `specs/index.yaml`}: `git rm --cached` nos dois artefatos, `git checkout --ours specs/index.yaml && git add specs/index.yaml` (o sync regenera logo depois). (b) Fazer em laço, porque o rebase para uma vez por commit. Usar `GIT_EDITOR=true git rebase --continue`. Testei no scratch: commit que fica vazio é descartado e o comando sai com rc 0. (c) `git rebase` dentro de `if !` por causa do `set -e`. (d) Adicionar o `git rm --cached --ignore-unmatch` de R3. (e) Teste novo na suíte: `git ls-files project_index/repo_graph.json project_index/manifest.json` vazio, para o CI pegar a ressurreição na main. (f) Apagar o "aceite qualquer lado (`--theirs`)" da skill **no mesmo commit** e avisar as sessões. |
| R5 | OK, com perda não declarada | `eval-gates.yml:69`. `check_index` (`generator.py:818-819`) também roda `validate_curated_files`, que falha se `domains.yaml`, `state_ownership.yaml` ou `eval_map.yaml` citam arquivo apagado. Hoje esse gate vive só no CI (`:69`) e em `test_real_index_*`. Nesta onda as specs 376/381/384 vão apagar e mover arquivos. | Declarar em R5/R6 que `validate_curated_files(ROOT)` continua coberto por um teste da suíte que **nunca** é pulado. Opcional: tirar `fetch-depth: 0` do job (`eval-gates.yml:63-65`), se ele só existia para o check. |
| R6 | **Design incompleto (P1)** | `build_index`/`check_index` têm caminho fixo `root/"project_index"` (`generator.py:798-805,820-821`), então o gerador **não** aceita diretório de saída alternativo. A suíte de CI roda com `-n auto` (`validate.yml:64`) e o job docs-only também roda este arquivo (`ci_docs_only.py --doc-tests` inclui `test_project_index.py`, `validate.yml:44`). Uma fixture de sessão é **por worker xdist**: dois workers podem gravar os 26 MB em `ROOT/project_index/` enquanto outro lê, o que dá `JSONDecodeError`/stale intermitente. Além disso, a fixture grava no checkout real. Já `:221`, `:231` e `:244` usam `_fixture_repo(tmp_path)` e não dependem do artefato versionado. | (a) Decidir já: parâmetro `index_dir` em `build_index`/`check_index`/`query`/`symbol`/`lookup_tests`/`state` (default `root/"project_index"`), com a fixture gravando em `tmp_path_factory`; ou `filelock` + escrita atômica (`os.replace`). Não deixar "se o gerador aceitar". (b) Manter `:221/:231/:244` **intocados**: são testes do gerador, e mudá-los viola W3 sem necessidade. (c) Proibir `skipif(not exists)` em `test_real_index_*`, que faria o critério "verde sem índice" passar vazio. (d) Custo: cada `check_index` regenera (~20 s). A fixture soma 1 build por worker que pegar esses testes. Aceitável, mas registrar. |
| R7 | Provável, com uma exceção | `scripts/ci_eval_scope.py:41-45`: `backend=true` exige um caminho em `agents/`, `evals/`, `playtest/`, `services/<prefixos>` ou `AI_FILES`. Nenhum desses é doc path para `scripts/ci_docs_only.py:25-29`. Base desconhecida leva a `docs_only=false` (`:38-39,72`). Logo, em `push`/`pull_request`, `backend` implica que `validate/test` roda (`validate.yml:49`). **Exceção:** `eval-gates.yml:7` tem `workflow_dispatch` e `validate.yml:2-7` não tem, então num dispatch manual os 9 testes deixam de rodar. | Registrar a exceção do dispatch e decidir (aceitar, ou manter os 9 testes só com `if: github.event_name == 'workflow_dispatch'`). A prova acima pode entrar direto na Etapa 0. |
| R8 | Provado | `npm-audit-full` (`validate.yml:136-153`) tem `if: docs_only != 'true'`, sem exclusão de schedule, ou seja, roda em ⊇ eventos de `test` (`:49`). `--audit-level=moderate` sobre a árvore inteira ⊇ `--omit=dev --audit-level=high` (`:84`). Histórico: SPEC-225 R6 criou os dois quando o full era informativo; SPEC-276 o tornou bloqueante (`handoffs/SPEC-276-review.md:30,44`). Nenhuma decisão do dono manda manter os dois. | Confirmar no GitHub se `test` é required check e `npm-audit-full` não é (branch protection). Se for, remover a linha do `test` enfraquece o merge gate. Nenhum teste lê essas linhas (procurei com `git grep` em `tests/`). |
| R9 | **Incompleto (P1/D2)** | `.tmp/s197_backup/` tem `database_app.dump`, `database_platform_data.dump`, `manifest.json`, `state.json` e `objects/` (15/10, backup do staging). `.tmp/spec191/` é o destino documentado de backup/restore em `docs/spec191/README.md:47-56` e o padrão de `scripts/staging/synthetic_data.py:4`. `evals/experiments/jev_router_ab.py:380-381` e `jev_target_loot.py:500` tratam `.tmp/spec176-clone` como checkout isolado do experimento (retomada). `.tmp/pytest-of-guilh` dá "Permission denied". Entrada mais recente: 15/10, não 13/10. Nenhum worktree registrado em `.tmp` (`git worktree list`). `git ls-files .tmp frontend de` = 0. `frontend/` e `de/` estão vazias. | D2 tem de listar explicitamente ao dono: os dumps do banco de staging (podem ter dados de usuário, e apagar pode ser desejável **ou** perder o único backup local); o clone 176 que os experimentos 176/179 congelados esperam; e as falhas de permissão (o executor não pode falhar no meio sem registro). Sugestão: apagar tudo menos `s197_backup/` e `spec191/` até o dono decidir sobre esses dois. |
| R10 | Lista incompleta | Faltam: `docs/guias/TESTES.md:13` ("`project_index check`" na camada 3) e `:32`; `AGENTS.md:311` ("GERADO no pouso") e `:387`; `CLAUDE.md:16` (lista `/reindex`); `.gitignore:42` (`!.claude/skills/reindex/`); `tests/test_dev_tooling.py:20` (`SKILLS` contém `"reindex"`: **quebra** se D3 = remover); `docs/HANDOFF-PROXIMA-SESSAO.md:74`; `scripts/dev/wt.sh:5-6` (cabeçalho). `tests/test_agents_contract.py:15` exige a string `project_index/domains.yaml` no AGENTS.md: manter. | Acrescentar todos à §3 e à lista de arquivos da W1. Se D3 = remover a skill, a mudança em `test_dev_tooling.py` é asserção, então declarar (W3). |

## Fatos errados ou desatualizados

- "commitado 492 vezes": hoje são **506** (`git log --oneline main -- project_index/repo_graph.json | wc -l`). Cresce rápido com os `chore: rebuild project index` da sessão 367 na main (3 em ~1 h). Pack: **321 MiB** (`git count-objects -vH`). Arquivo: 26,8 MB.
- "Depende de: SPEC-368 pousada (única branch com commit em `project_index/`)": não existem mais branches `spec-367`/`spec-368`. Os commits da 368 estão na main (status no cabeçalho ainda `in-progress`). A 367 está sendo trabalhada **direto no checkout principal** (`4b03a430`, `b278f6af`, `2a6e0945`) e roda `reindex.sh`. A dependência real: nenhuma sessão rodando `reindex.sh`/`wt.sh` no checkout principal no momento do pouso.
- `.tmp/` "de 27/09–13/10": vai até 15/10 (`s197_backup`, `spec191`).
- §3 "se o gerador aceitar diretório alternativo": não aceita (caminho fixo, `generator.py:798-805,820-821`).
- R6 diz que `:221/:231/:244` "dependem do artefato versionado": não dependem (usam o repo descartável `_fixture_repo`).
- Consumidores que a spec não lista: `scripts/project_index_ab_harness.py:16` (chama `query` etc. no ROOT real; benchmark histórico, passa a exigir `build` local); `tests/test_dev_tooling.py:20`; `docs/guias/TESTES.md`. `scripts/dev/eval_publish.py` **não** cita o índice. `tests/test_vercel_config.py:18` e `vercel.json` só excluem `project_index/**`, sem impacto. `.vercelignore:20`, `scripts/vercel_bundle_check.py:31` e `scripts/gen_event_catalog.py:22` também só excluem, sem impacto. `evals/experiments/jev_target_loot.py:44-53,422` usa o caminho só numa allowlist de diff (confirmado: não abre o arquivo).

## Riscos não cobertos

1. **Ressurreição via `--theirs`** (R4 acima): silenciosa e sem gate depois do R5. É o risco principal.
2. **Corrida xdist** na fixture de R6: CI vermelho intermitente em toda spec seguinte da onda.
3. **Autopouso do próprio `wt.sh`**: `wt.sh land 375` faz `git merge --ff-only` (`wt.sh:65`) no checkout principal, o que reescreve `scripts/dev/wt.sh` enquanto o bash o executa. O bash lê o script por offset depois do `case`, e no Windows o git pode falhar ao trocar o arquivo aberto. Mitigação: pousar a 375 com `git -C <main> merge --ff-only spec-375` manual, ou rodar uma cópia temporária do `wt.sh`.
4. **Gate de curadoria** (`validate_curated_files`) pode sumir junto com o check do CI (R5).
5. **Sessões com contexto antigo**: depois do pouso, quem ainda tiver o `/reindex` ou o `spec-land` antigo carregado vai tentar `git add` de arquivo ignorado (falha visível, ok) ou `--theirs` (silencioso, não ok). O aviso nas Notas da onda (R10) precisa dizer explicitamente "não use `--theirs` em `project_index/`".
6. **Dependabot** de `github_actions` (há PRs abertos em `origin/dependabot/github_actions/*`) mexe em `eval-gates.yml`/`validate.yml`. É conflito de rebase no lado do GitHub, baixo risco, mas vale citar.

## Choques com outras specs e branches

- W1 rodada agora (main `2a6e0945`), sobre a lista de arquivos da §3 mais os que faltam em R10: **interseção vazia**. Nenhuma branch local à frente da main tem commit (nem no diff líquido, nem por commit) em `project_index/repo_graph.json`/`manifest.json`. `spec-214` só toca `specs/index.yaml`.
- SPEC-380 depende da 375 por causa do `eval-gates.yml`. Ordem compatível.
- SPEC-379 edita `.gitignore` (R1.3) e workflows (`coverage.yml` novo). Pode conflitar em `.gitignore` se correr em paralelo. W6 já serializa, ok.
- SPEC-381 cita `project_index/domains.yaml:35` e `scripts/project_index_ab_harness.py:40`. Depende do gate de curadoria do risco 4.

## Mudanças que o autor deve fazer na spec

1. R4: autorresolver o conjunto {2 artefatos + `specs/index.yaml`} em laço com `GIT_EDITOR=true`. Adicionar `git rm --cached --ignore-unmatch` incondicional no `sync_branch`. Criar teste de suíte "artefatos não rastreados". Remover `--theirs` da skill no mesmo commit.
2. R6: escolher o design (`index_dir` + `tmp_path_factory`, ou lock + escrita atômica). Proibir skip. Não mexer em `:221/:231/:244`. Garantir que `validate_curated_files(ROOT)` segue coberto.
3. R9/D2: separar `s197_backup/` (dumps do banco) e `spec191/` como decisão explícita do dono. Citar os experimentos que esperam `.tmp/spec176-clone`. Tratar "Permission denied".
4. R7: registrar a exceção `workflow_dispatch` e decidir. R8: checar os required checks.
5. R2: dica `build` também na mensagem de stale. Rebaixar de "implementar" para "ajustar texto".
6. R10: incluir `TESTES.md:13,32`, `AGENTS.md:311,387`, `CLAUDE.md:16`, `.gitignore:42`, `tests/test_dev_tooling.py:20`, `docs/HANDOFF-PROXIMA-SESSAO.md:74`, cabeçalho do `wt.sh` e `scripts/project_index_ab_harness.py` (nota de que precisa de `build`).
7. Dependência: trocar "SPEC-368 pousada" por "nenhuma sessão ativa no checkout principal usando `reindex.sh`/`wt.sh` no momento do pouso". Pousar a 375 sem `wt.sh land` (risco 3).
8. Atualizar os números (506 commits, 321 MiB, 26,8 MB, `.tmp` até 15/10).

## Comandos rodados

```text
W1 (auditoria §6.2) com os arquivos da §3 + faltantes → interseção vazia
git log main..<b> -- project_index/{repo_graph,manifest}.json por branch → nenhuma
scratch repo: rebase DU + git rm --cached + checkout --ours + GIT_EDITOR=true continue → rc 0, commit vazio descartado
scratch repo: DU + checkout --theirs + add → arquivo volta a ser rastreado (ressurreição)
scratch repo: git add de arquivo ignorado e não rastreado → rc 1 ("paths are ignored")
scratch repo: checkout de commit que destrava o arquivo → arquivo removido da árvore de trabalho
py.sh -m pytest -n 0 tests/test_project_index.py → 8 passed em 62 s
py.sh scripts/ci_docs_only.py --doc-tests → inclui tests/test_project_index.py
git grep project_index|repo_graph (código, CI, .claude, docs/guias, scripts, tests) → consumidores listados acima
```
