# SPEC-375 — Higiene do repositório: Project Index fora do git, CI sem passos repetidos, lixo local

> **Status:** `approved` (04/11 madrugada, dono: "vai executando o que puder"; D1=tirar do git, D2=nenhum item respondido ⇒ Etapa 3 NÃO roda (tudo fica), D3=(b), D4=recomendação (só `workflow_dispatch`), D5: se a Etapa 0 cair no caso, R8 fica pendente do dono (marcar `npm-audit-full` obrigatório no GitHub))
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03 (revisão independente aplicada, ver §9)
> **Origem:** [auditoria 03/11](../docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md) §4.4 itens 1, 2, 6 · regras da onda §6.2 (W1 revisada, W2–W8) · correções §6.5
> **Depende de:** nenhuma sessão ativa usando `scripts/dev/reindex.sh` ou `scripts/dev/wt.sh` no checkout principal no momento do pouso (a SPEC-367 roda `reindex.sh` direto na `main`: commits `4b03a430`, `b278f6af`, `2a6e0945`). A antiga dependência "SPEC-368 pousada" já está cumprida: os commits da 368 estão na `main` e não há mais branch `spec-367`/`spec-368`.
> **Desbloqueia:** pousos mais leves para as specs seguintes (sem 26,8 MB por sync); SPEC-380 (`eval-gates.yml`) · **SPEC-388 Etapa A** (guardrail de workspace que espera esta spec)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` (não toca caminho protegido; `eval-gates.yml` não está em `evals/protected-paths.txt`)

Rótulos: **[F]** fato com evidência · **[H]** hipótese a confirmar na Etapa 0 · **[D]** decisão do dono (§8).

---

## 1. Contexto & Objetivo

**[F]** `project_index/repo_graph.json` tem 26,8 MB e foi commitado **506** vezes
(`git log --oneline main -- project_index/repo_graph.json | wc -l`, em `2a6e0945`). O pack do git tem
**321 MiB** (`git count-objects -vH`). A conta cresce rápido: a sessão da 367 fez 3 commits
`chore: rebuild project index` em ~1 h. Todo pouso regenera e commita o arquivo
(`scripts/dev/wt.sh:37-38`, `scripts/dev/reindex.sh:11-13`). O índice é de **consulta opcional**
(AGENTS.md § Operação, item 3), e o ROADMAP já lista a decisão "se `repo_graph.json` deixa de ser
commitado" (`ROADMAP.md:56`). A auditoria de 18/10 não podou porque "o gate `project_index check` do CI
compara com a cópia versionada; gerar no CI exige redesenhar o gate". Esta spec faz esse redesenho na
forma mais simples: o artefato vira local, como um `.pyc`.

**[F]** O CI repete trabalho. O job `backend-selective` (`eval-gates.yml:98-102`) roda 9
`tests/test_eval_*.py` que a suíte completa de `validate.yml:64` já roda em `push: main` e
`pull_request`. A exceção é o `workflow_dispatch` (`eval-gates.yml:7`), que `validate.yml:2-7` não tem.
`validate.yml:84` (`npm audit --omit=dev --audit-level=high`) é subconjunto de `validate.yml:152`
(`--audit-level=moderate` sobre a árvore inteira). O job `npm-audit-full` (`validate.yml:136-153`) roda
com `if: docs_only != 'true'`, ou seja, em ⊇ eventos do job `test` (`:49`). Os dois passos vêm da
SPEC-225 R6, quando o full era informativo. A SPEC-276 o tornou bloqueante
(`handoffs/SPEC-276-review.md:30,44`).

**[F]** Lixo local fora do git:
- `.tmp/` tem 120 entradas de 27/09 a **15/10**. É ignorado (`.gitignore:30`), mas o OneDrive sincroniza a
  pasta, e ela é tão grande que `du` não termina em 4 min.
- Dentro dela há itens que **não são lixo** e exigem decisão do dono (D2): `.tmp/s197_backup/` (dumps do
  banco de staging), `.tmp/spec191/` (destino documentado de backup/restore) e `.tmp/spec176-clone`
  (clone esperado por dois experimentos congelados). Detalhes em R9.
- As pastas `frontend/` e `de/` na raiz estão vazias.

**O que esta spec NÃO resolve:** o histórico. Os 321 MiB ficam no pack. Reescrever histórico exige
force-push e quebra os 21 worktrees e as outras sessões (W8). A spec **para o crescimento**.

## 2. Requisitos

- **R1** — `project_index/repo_graph.json` e `project_index/manifest.json` deixam de ser versionados
  (`git rm --cached` + `.gitignore`), conforme D1. Continuam versionados os curados (`domains.yaml`,
  `state_ownership.yaml`, `eval_map.yaml`), `generator.py`, `query.py`, `__main__.py` e o schema.
  `generator.py:46-50,116` já exclui `GENERATED_PATHS` do scan, então o hash fica certo mesmo em branches
  que ainda versionam o arquivo. **Efeito esperado:** ao fazer checkout ou ff de um commit que destrava o
  arquivo, o git o apaga da árvore de trabalho (o revisor reproduziu isso num repo descartável). Por isso,
  depois do pouso, o checkout principal e cada worktree rebaseado ficam sem índice até alguém rodar
  `python -m project_index build`. A primeira `query` falha com a mensagem de R2, e isso é o comportamento
  correto.
- **R2** — *(rebaixado: ajustar texto, não implementar.)* Hoje `__main__.py:59-61` já captura
  `ProjectIndexError` e imprime uma linha com exit 1, sem traceback. `_read_json` (`generator.py:807-814`)
  já converte `OSError` em `ProjectIndexError`. Falta acrescentar a dica `run: python -m project_index build`
  em dois casos:
  1. artefato ausente ou ilegível (`generator.py:811`);
  2. artefato stale (`generator.py:827-829`).

  O caso 2 passa a ser o normal: com artefato local, qualquer commit deixa o índice stale, porque
  `query`, `symbol`, `tests` e `state` chamam `check_index` (`query.py:55`). A asserção existente
  `match="stale"` (`tests/test_project_index.py:227,240`) continua valendo, porque a dica é acrescentada ao
  texto atual e não substitui nada.
- **R3** — `scripts/dev/wt.sh sync` e `scripts/dev/reindex.sh` deixam de construir, adicionar e checar o
  índice, e **não falham** com os arquivos ignorados. `wt.sh sync` continua gerando, commitando e checando
  `specs/index.yaml`. Proteção incondicional: `sync_branch` roda
  `git rm -q --cached --ignore-unmatch project_index/repo_graph.json project_index/manifest.json` em
  **toda** execução, depois do rebase e antes do `git diff --cached`/commit. Assim, se algum caminho
  ressuscitar o rastreio, o próximo sync desfaz. `reindex.sh` segue D3.
- **R4** — Autorresolução, em `wt.sh sync`, do conflito de rebase de branch antiga.
  - **Conflito típico:** o commit de sync antigo toca sempre os três arquivos juntos (`wt.sh:38`), então o
    rebase para com `DU repo_graph.json` + `DU manifest.json` + `UU specs/index.yaml`.
  - **Quando autorresolve:** só se o conjunto de arquivos em conflito
    (`git diff --name-only --diff-filter=U`) for subconjunto de {`project_index/repo_graph.json`,
    `project_index/manifest.json`, `specs/index.yaml`}. Qualquer outro arquivo em conflito faz o script
    parar como hoje, com o rebase em andamento e uma mensagem.
  - **O que faz:**
    1. `git rm -q --cached --ignore-unmatch` nos dois artefatos;
    2. se `specs/index.yaml` estiver em conflito: `git checkout --ours specs/index.yaml && git add specs/index.yaml`.
       No rebase, `--ours` é o lado da `main`, e o sync regenera o arquivo logo depois;
    3. `GIT_EDITOR=true git rebase --continue`.
  - **Em laço:** o rebase para uma vez por commit, então o passo se repete. Teto de iterações =
    `git rev-list --count main..HEAD` + 1 no início; estourou, aborta com mensagem. O revisor confirmou no
    scratch que commit que fica vazio é descartado e o comando sai com rc 0.
  - **`set -e`:** `git rebase` e `git rebase --continue` ficam dentro de `if ! …; then`.
  - **Teste na suíte** (CI pega ressurreição na `main`):
    `test_generated_index_artifacts_are_untracked` afirma que
    `git ls-files project_index/repo_graph.json project_index/manifest.json` sai vazio em `ROOT`.
  - **Skill:** no **mesmo commit**, sai de `.claude/skills/spec-land/SKILL.md:18-19` a instrução "aceite
    qualquer lado (`git checkout --theirs …`)". O revisor reproduziu: num conflito DU, `--theirs` +
    `git add` volta a rastrear `repo_graph.json` sem erro, e o `land` leva o arquivo de volta à `main`. No
    lugar entra: "conflito só em `specs/index.yaml`/`project_index/` é resolvido pelo próprio `wt.sh sync`;
    nunca use `--theirs` em `project_index/`".
- **R5** — CI: sai `uv run python -m project_index check` (`eval-gates.yml:69`). O build determinístico
  segue coberto em `tmp_path` (`tests/test_project_index.py:122`). **Perda declarada e compensada:**
  `check_index` também roda `validate_curated_files(root)` (`generator.py:819`). Essa função falha se
  `domains.yaml`/`state_ownership.yaml`/`eval_map.yaml` citarem arquivo apagado ou movido. Hoje ela só roda
  no CI (`:69`) e dentro de `test_real_index_*`, e nesta onda a 376, a 381 e a 384 apagam e movem
  arquivos. Por isso entra o teste novo `test_curated_files_reference_existing_paths`, que chama
  `validate_curated_files(ROOT)` direto, **sem skip**, e roda na suíte default e no job docs-only
  (`scripts/ci_docs_only.py --doc-tests` já inclui `tests/test_project_index.py`). **Opcional (P2):** tirar
  `fetch-depth: 0` de `deterministic-evals` (`eval-gates.yml:63-65`), mas só se a Etapa 0 provar que
  `evals.core.governance check` e `evals run` não precisam de histórico git. Sem prova, fica.
- **R6** — Testes que leem o índice real. **Design escolhido: parâmetro `index_dir`**, não lock.
  - **Por quê:** `build_index`/`check_index` gravam e leem em caminho fixo `root/"project_index"`
    (`generator.py:796-803,820-821`). A suíte do CI roda com `-n auto` (`validate.yml:64`), e uma fixture de
    sessão é **por worker xdist**: dois workers gravariam os 26 MB em `ROOT/project_index/` enquanto um
    terceiro lê, dando `JSONDecodeError`/stale intermitente, além de sujar o checkout real.
  - **Assinatura:** `build_index(root, index_dir=None)`, `check_index(root, index_dir=None)` e, em
    `query.py`, `query`/`symbol`/`lookup_tests`/`state`/`impact` ganham `index_dir: Path | None = None`
    (default `root / "project_index"`: CLI e `scripts/project_index_ab_harness.py` não mudam).
    `validate_curated_files` continua lendo os curados de `root/"project_index"`, porque eles são
    versionados, não gerados.
  - **Fixture:** `built_index` (escopo `session`) chama `build_index(ROOT, index_dir=tmp_path_factory.mktemp("project_index"))`.
    O `basetemp` é por worker, então não há corrida.
  - **Testes que mudam:** `test_real_index_excludes_content_and_queries_are_bounded` (`:257`) e
    `test_real_index_locates_symbols_tests_and_curated_state` (`:275`) passam a usar a fixture e
    `index_dir=built_index`. Muda só a chamada, não as asserções (W3).
  - **Proibido:** `skipif(not exists)` ou qualquer skip nesses testes. Isso faria o critério "verde sem
    índice" passar vazio.
  - **Intocados:** `:221`, `:231` e `:244`. Eles usam `_fixture_repo(tmp_path)` e não dependem do artefato
    versionado. São testes do gerador, e o `:244` segue válido porque `GENERATED_PATHS` continua excluído do
    scan.
  - **Custo registrado:** 1 build (~20 s) por worker que pegar esses testes, mais o `generate` que cada
    `check_index` já faz hoje. Hoje o arquivo leva 62 s com `-n 0` (8 passed). Aceitável.
- **R7** — CI: os 9 `tests/test_eval_*.py` de `backend-selective` (`eval-gates.yml:98-102`) passam a rodar
  **só** com `if: github.event_name == 'workflow_dispatch'`. Em `push`/`pull_request`, a suíte completa de
  `validate.yml` já cobre esses testes. Prova (revisor, a reconfirmar na Etapa 0):
  - `backend=true` exige caminho em `agents/`, `evals/`, `playtest/`, `services/<prefixos>` ou `AI_FILES`
    (`scripts/ci_eval_scope.py:41-45`);
  - nenhum desses é doc path (`scripts/ci_docs_only.py:25-29`);
  - base desconhecida resulta em `docs_only=false` (`:38-39,72`);
  - logo, `backend` implica que `validate/test` roda (`validate.yml:49`).

  O `playtest run --all --turns 3` (`:103`) fica como está. Se a Etapa 0 refutar a prova, R7 sai da spec
  (registrado no handoff).
- **R8** — CI: sai `validate.yml:84` **somente se** a Etapa 0 (item 6) mostrar, pelos checks obrigatórios do
  merge na `main`, que remover a linha não enfraquece o gate. Isso vale se não houver proteção, se
  `npm-audit-full` for obrigatório, ou se `test` não for. Se `test` for obrigatório e `npm-audit-full` não
  for, R8 depende de D5.
- **R9** — Limpeza local, **item a item conforme D2**. Nada em `.tmp/s197_backup/`, `.tmp/spec191/` ou
  `.tmp/spec176-clone` é apagado por padrão. Pré-condições para cada remoção:
  1. `git ls-files .tmp frontend de` vazio (hoje: 0);
  2. nenhum worktree registrado no caminho (`git worktree list`; hoje nenhum em `.tmp`);
  3. nenhum processo usando a pasta.

  Entradas com "Permission denied" (ex.: `.tmp/pytest-of-guilh`) são **puladas e registradas** no handoff
  com o caminho. O executor não para no meio sem registro e não força ACL. Mover os dumps (D2c) é cópia
  verificada (contagem de arquivos e bytes iguais) e só depois remoção da origem.
- **R10** — Docs e referências, todas no commit de docs (ou no commit de R1/R4 quando indicado):
  - `AGENTS.md:22-23` (item 3 de "Operação": "gere com `python -m project_index build` antes de consultar"),
    `:58` (item 6 do "Fluxo de spec em 8 linhas", sem Project Index), `:311` ("GERADO no pouso" →
    "gerado localmente sob demanda; não versionado"), `:316` (`reindex.sh`, conforme D3) e `:387` (vale só
    para `specs/index.yaml`; `project_index/` curado continua editável por spec).
    **Manter** a string `project_index/domains.yaml`, que `tests/test_agents_contract.py:15` exige;
  - `CLAUDE.md:16` (lista `/reindex`, conforme D3);
  - `.claude/skills/spec-land/SKILL.md`: linha 3 (descrição), linhas 8-9 e passo 2. A remoção do `--theirs`
    vai no commit de R4;
  - `.claude/skills/reindex/SKILL.md` e `.gitignore:42` (`!.claude/skills/reindex/`), conforme D3;
  - `tests/test_dev_tooling.py:20`: se D3 = remover, sai `"reindex"` de `SKILLS`. É **mudança de asserção
    declarada** (W3), não refatoração pura;
  - `docs/guias/TESTES.md:13` (camada 3 sem `project_index check`) e `:32` (staleness agora é de artefato
    local);
  - `docs/HANDOFF-PROXIMA-SESSAO.md:74` (passo `project_index build` sai do ritual);
  - `scripts/dev/wt.sh:5-6` (cabeçalho);
  - `scripts/project_index_ab_harness.py`: docstring com uma linha "exige `python -m project_index build`
    local". Benchmark histórico da SPEC-175, sem mudança de lógica;
  - **Pelo coordenador, fora do executor** (subagente não edita esses arquivos): `ROADMAP.md:56` (item
    resolvido) e `ESTADO_ATUAL.md` § Notas da onda. O aviso às sessões tem de dizer explicitamente:
    "`project_index/repo_graph.json` e `manifest.json` não são mais versionados; nunca use `--theirs` em
    `project_index/`; rode `python -m project_index build` antes de consultar".

### Fora de escopo

- Reescrever histórico, `git filter-repo`, LFS (W8).
- Mídia de `docs/` (auditoria §6.4).
- Apagar worktrees ou branches de outras sessões.
- Fundir builds de `npm` entre workflows (§6.4).
- `evals/experiments/jev_target_loot.py:44-53,422` cita o caminho numa allowlist de diff, sem abrir o
  arquivo (confirmado pelo revisor). É experimento congelado: o `_source()` entra no digest, e
  `pyproject.toml` tem per-file-ignores. **Não editar.** O mesmo vale para
  `evals/experiments/jev_router_ab.py:380-381` e `jev_target_loot.py:500`, que esperam `.tmp/spec176-clone`
  (ver D2e).
- Opção `--index-dir` na CLI do `project_index`. O parâmetro é só programático (testes); a CLI continua
  usando `project_index/`.
- Consumidores que só **excluem** `project_index/**` e não precisam mudar: `vercel.json`,
  `tests/test_vercel_config.py:18`, `.vercelignore:20`, `scripts/vercel_bundle_check.py:31`,
  `scripts/gen_event_catalog.py:22`. `scripts/dev/eval_publish.py` não cita o índice.
- Dependabot `github_actions` (PRs abertos em `origin/dependabot/github_actions/*`): conflito de rebase do
  lado do GitHub, baixo risco, não tratado aqui.

## 3. Design técnico

- `.gitignore`: `+ project_index/repo_graph.json` e `+ project_index/manifest.json`; `:42` segue D3.
- `project_index/generator.py`:
  - parâmetro `index_dir` em `build_index`/`check_index` (R6);
  - dica `build` nas mensagens de `:811` e `:827-829` (R2);
  - `GENERATED_PATHS` (`:46-50`) fica como está.
- `project_index/query.py`: `index_dir` repassado a `check_index` (R6). `__main__.py`: sem mudança (já trata
  `ProjectIndexError`).
- `scripts/dev/wt.sh`:
  - `sync_branch` sem `project_index build/add/check` (`:37-38,47-48`);
  - `git add specs/index.yaml` só;
  - `git rm --cached --ignore-unmatch` incondicional (R3);
  - laço de autorresolução de R4 em volta do `git rebase -q main` (`:35`);
  - cabeçalho `:5-6`.
- `scripts/dev/reindex.sh`: conforme D3.
- `.github/workflows/eval-gates.yml`: R5 (sai `:69`; `fetch-depth` só com prova) e R7 (`if:` de dispatch no
  passo `:98-102`). `.github/workflows/validate.yml`: R8.
- `tests/test_project_index.py`:
  - fixture `built_index`;
  - `:257`/`:275` com `index_dir`;
  - testes novos `test_generated_index_artifacts_are_untracked`, `test_curated_files_reference_existing_paths`,
    `test_query_without_index_is_friendly` e `test_stale_index_message_suggests_build`;
  - `:221/:231/:244` intocados.

**Compatibilidade com as outras sessões:** elas chamam `bash scripts/dev/wt.sh …` do checkout principal a
cada pouso, então pegam a versão nova no próximo uso. Por isso R1, R3, R4 e R5 e a correção da skill
spec-land vão **no mesmo commit**:
- se o `.gitignore` entrar sem o `wt.sh` novo, o `git add project_index/repo_graph.json` do sync antigo
  falha com "paths are ignored" (rc 1, o `set -e` aborta; reproduzido pelo revisor) e trava o pouso de
  outra sessão;
- se o check do CI ficar, o CI fica vermelho sem o artefato.

Sessões com a skill antiga já carregada podem ainda usar `--theirs`. O `git rm --cached` incondicional do
próximo sync desfaz isso, e o teste de R4 acusa na `main`.

## 4. Plano passo a passo

### Etapa 0 — Provas (só leitura; registrar tudo no handoff)

1. **W1 (versão revisada, §6.2)**, com as três fontes (branches vivas, mudanças não commitadas em todos os
   worktrees **inclusive o principal**, commits recentes na `main`), sobre todos os arquivos da §3 e de R10.
   Se a interseção não for vazia, espere. O revisor rodou em `2a6e0945` e a interseção saiu vazia; refazer
   antes de cada etapa.
2. `git grep -n "project_index check\|repo_graph.json\|manifest.json\|reindex"` fora de `docs/historico`,
   `specs/` e `handoffs/`: todo consumidor novo (além dos de §2/R10 e "Fora de escopo") entra na §3 ou é
   justificado.
3. R7: reler `scripts/ci_eval_scope.py:41-45`, `scripts/ci_docs_only.py:25-29,38-39,72` e os
   `if:`/`needs` de `validate.yml` e `eval-gates.yml`. Confirmar ou refutar a prova.
4. R5 opcional: ver se `evals.core.governance check` e `evals run` usam `git log`/histórico (`git grep -n
   "subprocess\|git " evals/core`). Sem uso, `fetch-depth: 0` pode sair de `deterministic-evals`.
5. `evals/experiments/jev_target_loot.py`: confirmar que só lista o caminho.
6. R8, checks obrigatórios do merge, **só leitura**:
   `gh api repos/{owner}/{repo}/branches/main/protection/required_status_checks` e
   `gh api repos/{owner}/{repo}/rules/branches/main`. Anotar a resposta. 404 = sem proteção. 403 = sem
   permissão: R8 fica de fora e vira pergunta ao dono. Nada de `gh api -X PUT/PATCH`.
7. R9: `git ls-files .tmp frontend de` vazio; `git worktree list` sem caminho em `.tmp`; `du -sh` por
   subpasta de `.tmp` em background com timeout de 10 min, com a lista que der "Permission denied".

### Etapa 1 — Testes primeiro (vermelhos antes da Etapa 2)

1. `tests/test_project_index.py`:
   - fixture `built_index` com `tmp_path_factory` (R6). Fica vermelha até o `index_dir` existir;
   - `:257/:275` passam a usá-la, sem skip;
   - `:221/:231/:244` intocados.
2. `test_curated_files_reference_existing_paths`: chama `validate_curated_files(ROOT)` (R5). Verde já hoje,
   como guarda.
3. `test_query_without_index_is_friendly` (R2): roda `python -m project_index query x` como subprocess num
   `_fixture_repo` sem build. Espera exit ≠ 0, saída com "build" e sem "Traceback".
   `test_stale_index_message_suggests_build`: build no fixture repo, editar arquivo rastreado,
   `check_index` → `ProjectIndexError` com "stale" **e** "build".
4. `test_generated_index_artifacts_are_untracked` (R4): `git ls-files` dos dois artefatos vazio em `ROOT`.
   Fica vermelho até o commit de R1.
5. Teste manual de `wt.sh`, rodado num **repo descartável no scratchpad** ou em branch descartável com
   worktree próprio, com saída registrada no handoff:
   - (a) branch com commit de sync antigo (os 3 arquivos) rebaseada via `wt.sh sync` novo: termina 0, os
     dois artefatos não rastreados, `specs/index.yaml` regenerado;
   - (b) branch sem o arquivo versionado: termina 0;
   - (c) conflito em arquivo fora do conjunto de R4: o script para com rc ≠ 0 e o rebase fica em andamento;
   - (d) ressurreição: branch que re-rastreia `repo_graph.json` via `--theirs`. O sync seguinte destrava, e
     `test_generated_index_artifacts_are_untracked` acusa antes do sync.

Só testes do escopo, `-n 2` no máximo (regra de RAM).

### Etapa 2 — Implementação (W4: um commit por bloco, cada um verde e revertível sozinho)

1. **Commit A — R6 + R2.** `index_dir` no gerador/query, dicas `build` e os testes da Etapa 1, itens 1-3.
   Funciona com o artefato ainda versionado.
2. **Commit B — R1 + R3 + R4 + R5 + skill spec-land sem `--theirs` + teste da Etapa 1, item 4.**
   Obrigatoriamente juntos (§3). `reindex.sh` conforme D3 entra aqui também, porque o `reindex.sh` antigo
   faz `git add` de arquivo ignorado e quebraria.
3. **Commit C — R7**, só com a prova da Etapa 0, item 3.
4. **Commit D — R8**, só com a prova da Etapa 0, item 6, ou com D5.
5. **Commit E — R10** (docs; inclui `test_dev_tooling.py:20` se D3 = remover).

### Etapa 3 — Limpeza local (R9), só com D2 respondida item a item

Fora do git. Registrar no handoff o tamanho liberado, o que foi movido e para onde, e o que foi pulado
(permissão).

### Etapa 4 — Pouso da 375 (manual, **sem `wt.sh land`**)

`wt.sh land 375` faria `git merge --ff-only` (`wt.sh:65`) no checkout principal. Isso reescreve
`scripts/dev/wt.sh` enquanto o bash o executa: o bash lê o script por offset, e no Windows o git pode
falhar ao trocar arquivo aberto. O `wt.sh sync` **antigo** (o do checkout principal) também não serve:
na branch 375 os artefatos já estão ignorados, e o `git add` dele sai com rc 1. Procedimento do
coordenador:

1. Confirmar a dependência: nenhuma sessão ativa rodando `reindex.sh`/`wt.sh` no checkout principal
   (`ListAgents` + avisar a sessão da 367). Refazer a W1.
2. Sync com **cópia temporária** do `wt.sh` da branch:
   `cp "$WT/scripts/dev/wt.sh" "<scratchpad>/wt-375.sh" && bash "<scratchpad>/wt-375.sh" sync 375`.
   A cópia não é reescrita pelo rebase. `MAIN` e `WT` vêm de `git worktree list`, então funciona de
   qualquer cwd.
3. Suíte completa 1× no worktree (`-n auto`, em background, timeout de 20 min), uma por vez.
4. Fast-forward manual: `git -C "$MAIN" rev-parse --abbrev-ref HEAD` = `main`, e depois
   `git -C "$MAIN" merge --ff-only spec-375`. Se o ff recusar por mudança local em arquivo tocado pela 375,
   parar e resolver com a sessão dona da mudança; nunca stash de mudança alheia.
5. Pós-pouso:
   - `git -C "$MAIN" ls-files project_index/repo_graph.json project_index/manifest.json` vazio;
   - os dois arquivos somem da árvore de trabalho da `main` (esperado, R1);
   - `bash scripts/dev/py.sh -m project_index build` se alguém precisar consultar;
   - `bash scripts/dev/wt.sh drop 375`, que já é o script novo;
   - aviso nas Notas da onda (R10).

## 5. Critérios de aceite

- [ ] `git ls-files project_index` não lista `repo_graph.json` nem `manifest.json`; o teste
      `test_generated_index_artifacts_are_untracked` está na suíte default e verde.
- [ ] Teste manual de `wt.sh`, cenários (a)–(d) da Etapa 1, com saída no handoff.
- [ ] `.claude/skills/spec-land/SKILL.md` sem `--theirs`, no mesmo commit de R1/R4.
- [ ] `python -m project_index build && python -m project_index query <símbolo>` funciona. Sem build ou com
      índice stale, a mensagem tem 1 linha com "build" e não há traceback.
- [ ] `tests/test_project_index.py` verde num checkout **sem** o índice gerado, com `-n 2`, sem skip nos
      `test_real_index_*` e sem arquivo novo em `ROOT/project_index/` depois da execução.
- [ ] `test_curated_files_reference_existing_paths` verde e sem skip.
- [ ] `:221/:231/:244` sem diff.
- [ ] CI verde (`validate`, `eval-gates`) sem o passo `project_index check`.
- [ ] Prova da Etapa 0 para R7 (inclui o `if:` de `workflow_dispatch`) e para R8 (resposta do `gh api`)
      no handoff; sem prova, o requisito fica de fora, registrado.
- [ ] R9 executado só nos itens autorizados em D2; pulados por permissão listados.
- [ ] Pouso pela Etapa 4 (sem `wt.sh land`).
- [ ] `uv run pytest` completo verde (coordenador, 1×).
- [ ] Revisão independente (W7).

## 6. Smoke test com LLM real

Não se aplica: nada muda no runtime do jogo. Substitutos:
1. o primeiro `/spec-land` de **outra** spec depois desta pousa sem commit em `project_index/` e sem erro;
2. o primeiro sync de uma branch criada **antes** do pouso da 375 (se houver) passa pela autorresolução
   de R4 com rc 0.

## 7. Riscos & compatibilidade

- **Ressurreição via `--theirs`** (risco principal): mitigada em três camadas. A skill corrigida no mesmo
  commit, o `git rm --cached` incondicional em todo sync e o teste de suíte que acusa na `main`.
- **Corrida xdist na fixture**: eliminada pelo `index_dir` em `tmp_path_factory` (R6).
- **Autopouso do `wt.sh`**: Etapa 4 (cópia temporária + ff manual).
- **Gate de curadoria**: preservado por `test_curated_files_reference_existing_paths` (R5).
- **Branch antiga com o arquivo versionado**: R4 automático. W1 em `2a6e0945` não achou nenhuma.
- **Sessões com contexto antigo**: com `/reindex` ou `reindex.sh` antigo, o `git add` de arquivo ignorado
  falha de forma visível (ok). Com `--theirs`, coberto pelas três camadas acima. O aviso nas Notas da onda
  diz isso explicitamente.
- **Checkout sem índice depois do pouso**: esperado (R1). A mensagem de R2 diz o que fazer.
- **SPEC-379** edita `.gitignore` e workflows. W6 serializa, e quem pousar depois rebaseia.
- **SPEC-380** depende desta (`eval-gates.yml`); ordem compatível.
- **Alguém depende do índice sem saber**: Etapa 0, item 2.
- **Gate de staleness some do CI**: ele existia para forçar o commit do artefato. Com geração sob demanda,
  a consulta é sempre checada contra a árvore (`check_index` em toda `query`).
- Saves, MockLLM, quota e latência: não se aplica.

## 8. Decisões do dono

- **D1** — Tirar os dois artefatos do git (**recomendado**) ou manter `manifest.json` versionado com um
  `check` por hash de árvore? O manifest também muda a cada commit e sem o grafo não serve para consulta.
- **D2** — Limpeza local, item a item. Sem resposta, o item **fica**.
  - **D2a** — `frontend/` e `de/` (vazias). Recomendação: apagar.
  - **D2b** — Resto de `.tmp/`, menos D2c–D2e: clones temporários, saídas de pytest e scratch de 27/09–15/10
    não citados por runbook ou experimento. Recomendação: apagar. "Permission denied" é pulado e
    listado.
  - **D2c** — `.tmp/s197_backup/` (`database_app.dump`, `database_platform_data.dump`, `manifest.json`,
    `state.json`, `objects/`; backup do staging de 15/10, pode ter dados de usuário). Recomendação:
    **mover para fora do OneDrive**, num caminho que você escolhe (ex.: `%LOCALAPPDATA%\rpg-backups\s197`
    ou disco externo), com cópia verificada antes de remover a origem. Não apagar: pode ser o único backup
    local. Como a pasta já foi sincronizada, você também pode querer limpar a cópia da nuvem e a lixeira do
    OneDrive; isso é ação sua.
  - **D2d** — `.tmp/spec191/`: é o destino documentado de backup/restore (`docs/spec191/README.md:47-56`) e
    o padrão de `scripts/staging/synthetic_data.py:4`. Recomendação: **manter**. Se quiser tirar do
    OneDrive, isso pede atualizar o runbook e o script (fora desta spec, só se você decidir).
  - **D2e** — `.tmp/spec176-clone` (com `.git`, `.venv` e `node_modules`). Viola "nunca crie clones dentro
    do repo" (`docs/guias/BRIEF_SUBAGENTE.md`), mas os experimentos congelados 176/179
    (`evals/experiments/jev_router_ab.py:380-381`, `jev_target_loot.py:500`) o tratam como checkout isolado
    para retomada. Recomendação: **manter** enquanto você quiser poder retomar esses experimentos. Apagar
    = aceitar que eles não retomam sem recriar o clone.
- **D3** — Skill `/reindex` e `scripts/dev/reindex.sh`. Opções: (a) a skill vira "gerar local" (1 linha)
  e `reindex.sh` passa a só rodar `project_index build`, sem add/commit/check; (b) os dois são removidos e
  o comando fica no AGENTS.md. Recomendação: **(b)**. Implica mudar a asserção de
  `tests/test_dev_tooling.py:20` (declarada), `.gitignore:42`, `CLAUDE.md:16` e `AGENTS.md:316`. Quem
  chamar `reindex.sh` depois do pouso recebe "No such file" (falha visível).
- **D4** — R7 com dispatch manual. Recomendação: manter os 9 testes só com
  `if: github.event_name == 'workflow_dispatch'` (zero perda de cobertura). A alternativa é aceitar que o
  dispatch manual do `eval-gates` não roda esses testes.
- **D5** — Só se a Etapa 0, item 6, mostrar `test` obrigatório e `npm-audit-full` não: (a) você marca
  `npm-audit-full` como check obrigatório no GitHub e R8 entra; ou (b) R8 sai da spec. Recomendação: (a),
  porque o full já é bloqueante desde a SPEC-276 e só falta constar no merge gate.

## 9. Resposta à revisão

Parecer: [handoffs/SPEC-375-independent-review.md](../handoffs/SPEC-375-independent-review.md)
(SAFE-WITH-CHANGES). Todos os P0/P1 foram aceitos:
- **R4:** autorresolução de {2 artefatos + `specs/index.yaml`} em laço com `GIT_EDITOR=true`, `git rm
  --cached --ignore-unmatch` incondicional, teste de suíte de não rastreio e `--theirs` fora da skill no
  mesmo commit.
- **R6:** `index_dir` + `tmp_path_factory`, proibição de skip, `:221/:231/:244` intocados,
  `validate_curated_files(ROOT)` coberto.
- **R9/D2:** item a item, com dumps, `spec191` e clone 176 explícitos e permissão tratada.
- **R7:** exceção do `workflow_dispatch` tratada por `if:`.
- **R8:** checagem dos required checks via `gh api` só leitura.
- **Pouso e dependência:** pouso sem `wt.sh land`; dependência trocada.

Os P2 foram aceitos:
- dica `build` também no stale, com R2 rebaixado;
- R10 completo, mais `AGENTS.md:316` e a nota de que `ROADMAP.md:56` é do coordenador;
- números atualizados (506 commits, 321 MiB, 26,8 MB, `.tmp` até 15/10);
- `fetch-depth: 0` condicionado a prova;
- Dependabot citado em "Fora de escopo";
- aviso explícito às sessões.

Aceites parciais e rejeições:
- **"Apagar tudo menos `s197_backup/` e `spec191/` até o dono decidir"** — aceito em parte. Também
  `.tmp/spec176-clone` fica por padrão, porque dois experimentos congelados o exigem para retomar. O
  padrão passa a ser "sem resposta do dono, fica", inclusive para D2b.
- **"Pousar com ff manual *ou* cópia temporária do `wt.sh`"** — não é escolha excludente: a spec usa as
  duas. A cópia serve para o sync, porque o sync antigo quebra na branch 375 com o `.gitignore` novo. O ff
  é manual, para não reescrever o script em execução.
- **Nota de escopo (não é pedido do parecer):** a autorresolução do `wt.sh` não ganha teste automatizado
  na suíte. Montar worktree + rebase com conflito dentro do pytest é caro e frágil no Windows/OneDrive. A
  regressão principal (ressurreição) já é pega por `test_generated_index_artifacts_are_untracked`. Os 4
  cenários ficam como teste manual registrado no handoff.

## 10. Registro de execução (executor, 04/11)

- **Etapa 0:** `main` sem proteção (`required_status_checks` 404, `rules/branches/main` = `[]`) ⇒ R8 entra sem depender de D5. R7 confirmado (`ci_eval_scope` backend ⊂ não-doc; base desconhecida ⇒ `docs_only=false`). R5 opcional (`fetch-depth`) **não** aplicado: `evals/core/hashing.py` usa `git rev-parse/ls-files/status`. W1: `spec-359`/`spec-372`/`spec-373` não tocam `project_index/`, `scripts/dev`, `.claude`, `AGENTS.md`, `CLAUDE.md` vs `main`.
- **Desvio de R4:** no laço de rebase usa-se `git rm -qf` (remove também da árvore), não `--cached`: sobras do conflito modify/delete ficam untracked e bloqueiam o `pick` seguinte ("untracked working tree files would be overwritten"). Efeito: o índice local gerado some em branch que passe por conflito; basta `python -m project_index build`.
- **Branches vivas no rebase:** sem commit de sync antigo, nada a resolver; com ele, R4 autorresolve. Teste manual (a)–(d) em repo descartável: todos como esperado.
- **Etapa 3 (R9):** não executada (D2).
