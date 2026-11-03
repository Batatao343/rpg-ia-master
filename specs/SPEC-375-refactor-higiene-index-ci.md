# SPEC-375 — Higiene do repositório: Project Index fora do git, CI sem passos repetidos, lixo local

> **Status:** `draft`
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** [auditoria 03/11](../docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md) §4.4 itens 1, 2, 6 · regras da onda §6.2 (W1–W8)
> **Depende de:** SPEC-368 pousada (única branch com commit em `project_index/` em 03/11)
> **Desbloqueia:** pousos mais leves para todas as specs seguintes (sem 25 MB por sync)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` (não toca caminho protegido; `eval-gates.yml` não está em `evals/protected-paths.txt`)

Rótulos: **[F]** fato com evidência · **[H]** hipótese a confirmar na Etapa 0 · **[D]** decisão do dono (§8).

---

## 1. Contexto & Objetivo

**[F]** `project_index/repo_graph.json` tem 25,3 MB e foi commitado 492 vezes; o pack do git tem 319 MiB.
Todo pouso regenera e commita o arquivo (`scripts/dev/wt.sh:37-38`, `scripts/dev/reindex.sh:11-13`).
O índice é de **consulta opcional** (AGENTS.md § Operação, item 3) e o ROADMAP já lista a decisão
"se `repo_graph.json` deixa de ser commitado" (`ROADMAP.md:56`). A auditoria de 18/10 não podou porque
"o gate `project_index check` do CI compara com a cópia versionada; gerar no CI exige redesenhar o gate".
Esta spec é esse redesenho, na forma mais simples: o artefato vira local, como um `.pyc`.

**[F]** CI repete trabalho: o job `backend-selective` de `eval-gates.yml:98-102` roda 9
`tests/test_eval_*.py` que a suíte completa de `validate.yml:64` já roda nos mesmos eventos (os dois
workflows disparam em `push: main` e `pull_request`). `validate.yml:84` (`npm audit --omit=dev
--audit-level=high`) parece subconjunto de `validate.yml:152` (`--audit-level=moderate`) **[H: os dois
rodam no mesmo evento? confirmar os `if:` dos jobs]**.

**[F]** Lixo local fora do git: `.tmp/` (120 entradas de 27/09–13/10, inclui `.tmp/spec176-clone` com
`.git`, `.venv`, `node_modules`; ignorado em `.gitignore:30`, mas sincronizado pelo OneDrive e tão grande
que `du` não termina em 4 min; viola `docs/guias/BRIEF_SUBAGENTE.md` "nunca crie clones dentro do repo"),
pastas vazias `frontend/` e `de/` na raiz.

**O que esta spec NÃO resolve:** o histórico. Os 319 MiB ficam no pack; reescrever histórico exige
force-push e quebra os 21 worktrees e as outras sessões (W8). A spec **para o crescimento**.

## 2. Requisitos

- **R1** — `project_index/repo_graph.json` e `project_index/manifest.json` deixam de ser versionados
  (`git rm --cached` + `.gitignore`), conforme D1. Ficam versionados os curados (`domains.yaml`,
  `state_ownership.yaml`, `eval_map.yaml`), `generator.py`, `query.py`, `__main__.py` e o schema.
- **R2** — `python -m project_index build` gera o índice localmente sob demanda; `python -m project_index
  query …` funciona depois do build. Sem índice, a query imprime uma linha dizendo para rodar `build`
  (exit ≠ 0), sem traceback.
- **R3** — `scripts/dev/wt.sh sync` e `scripts/dev/reindex.sh` deixam de construir/adicionar/checar o índice
  e **não falham** com os arquivos ignorados. `wt.sh sync` continua gerando e commitando `specs/index.yaml`.
- **R4** — Rebase de branch antiga com commit em `project_index/repo_graph.json` (conflito modify/delete)
  é resolvido por `git rm --cached project_index/repo_graph.json project_index/manifest.json` + `git rebase
  --continue`, automático em `wt.sh sync` quando o conflito é **só** em `project_index/`, e documentado em
  `.claude/skills/spec-land/SKILL.md` (que já diz "aceite qualquer lado" para `project_index/`).
- **R5** — CI: sai `uv run python -m project_index check` (`eval-gates.yml:69`). Nada entra no lugar: os
  testes do gerador já cobrem build determinístico em `tmp_path` (`tests/test_project_index.py:122`).
- **R6** — Testes que leem o índice real passam a gerá-lo antes de consultar (fixture de sessão):
  `tests/test_project_index.py:257` `test_real_index_excludes_content_and_queries_are_bounded` e `:275`
  `test_real_index_locates_symbols_tests_and_curated_state`. `:244`
  `test_committing_generated_artifacts_warns_without_infinite_staleness` é reescrito ou removido conforme a
  semântica nova (artefato deixa de ser commitado). `:221` e `:231` (staleness) idem, se dependerem do
  artefato versionado.
- **R7** — CI: `backend-selective` deixa de rodar os 9 `tests/test_eval_*.py` **somente se** a Etapa 0
  provar que `validate.yml` roda a suíte completa em **todo** evento em que `backend-selective` roda
  (inclusive quando `scripts/ci_docs_only.py` decide "só docs", `validate.yml:44`). O `playtest run --all
  --turns 3` fica.
- **R8** — CI: sai `validate.yml:84` **somente se** a Etapa 0 provar que `:152` roda nos mesmos eventos.
- **R9** — Limpeza local (D2): apagar `.tmp/`, `frontend/`, `de/` do checkout principal depois de provar
  que nada ali é rastreado (`git ls-files .tmp frontend de` vazio) e que nenhum processo usa a pasta.
- **R10** — Docs: AGENTS.md (item 3 de "Operação": "gere com `python -m project_index build` antes de
  consultar"; item 6 do "Fluxo de spec em 8 linhas" sem Project Index), `.claude/skills/reindex/SKILL.md`
  (D3), `.claude/skills/spec-land/SKILL.md` passo 2, `ROADMAP.md:56` (item resolvido), `ESTADO_ATUAL.md`
  § Notas da onda (aviso às outras sessões, pelo coordenador).

### Fora de escopo

- Reescrever histórico, `git filter-repo`, LFS (W8).
- Mídia de `docs/` (auditoria §6.4).
- Apagar worktrees ou branches de outras sessões.
- Fundir builds de `npm` entre workflows (§6.4).
- `evals/experiments/jev_target_loot.py:52` cita o caminho numa lista: experimento congelado (o `_source()`
  entra no digest, `pyproject.toml` per-file-ignores). **Não editar.** Etapa 0 confirma que ele não abre o
  arquivo.

## 3. Design técnico

- `.gitignore`: `+ project_index/repo_graph.json` e `+ project_index/manifest.json`.
- `project_index/__main__.py` / `query.py`: mensagem amigável quando o índice não existe (R2).
- `project_index/generator.py:48-49` lista os dois artefatos (provável exclusão do próprio scan): manter.
- `scripts/dev/wt.sh:6,37-38,48` e `scripts/dev/reindex.sh:11-21`: sem `project_index build/add/check`.
  `wt.sh sync` ganha a resolução automática de R4 (só quando **todos** os arquivos em conflito estão em
  `project_index/`; qualquer outro conflito continua parando o script, como hoje).
- `.github/workflows/eval-gates.yml`: R5, R7. `.github/workflows/validate.yml`: R8.
- `tests/test_project_index.py`: R6.

**Compatibilidade com as outras sessões:** elas chamam `bash scripts/dev/wt.sh …` do checkout principal a
cada pouso, então pegam a versão nova no próximo uso. Por isso R1, R3 e R4 vão **no mesmo commit**: se o
`.gitignore` entrar sem o `wt.sh` novo, o `git add project_index/repo_graph.json` do sync antigo falha
("paths are ignored") e trava o pouso de outra sessão.

## 4. Plano passo a passo

### Etapa 0 — Provas (só leitura)

1. W1 com os arquivos da §3; `project_index/` em alguma branch aberta ⇒ esperar.
2. `git grep -n "project_index check\|repo_graph.json\|manifest.json"` fora de `docs/historico`, `specs/`,
   `handoffs/`: listar todo consumidor; cada um entra na §3 ou é justificado no handoff.
3. Ler `scripts/ci_docs_only.py` e os `if:`/`needs` dos jobs de `validate.yml` e `eval-gates.yml` para
   R7/R8; registrar a prova (ou a refutação) no handoff.
4. `evals/experiments/jev_target_loot.py`: confirmar que só lista o caminho.
5. `git ls-files .tmp frontend de` vazio; `du -sh .tmp` em background com timeout de 10 min.

### Etapa 1 — Testes primeiro

1. `tests/test_project_index.py`: fixture de sessão `built_index` que roda o build (no próprio
   `project_index/`, agora ignorado, ou em diretório de saída alternativo se o gerador aceitar); os testes
   `test_real_index_*` passam a depender dela (R6). Ajuste de `:221/:231/:244` conforme R6.
2. Novo `test_query_without_index_is_friendly` (R2): sem artefato → exit ≠ 0, stderr com "build", sem traceback.
3. Teste manual de `wt.sh` (registrado no handoff): branch descartável com commit em `repo_graph.json`,
   rebaseada sobre a main nova via `wt.sh sync` → termina 0 e o arquivo sai do índice do git.

### Etapa 2 — Implementação (W4: um commit por bloco)

1. R1 + R3 + R4 + R2 (mesmo commit, ver §3).
2. R5 + R6.
3. R7 (só com prova). 4. R8 (só com prova). 5. R10.

### Etapa 3 — Limpeza local (R9), só com D2 aprovada

Fora do git; registrar o tamanho liberado no handoff.

## 5. Critérios de aceite

- [ ] `git ls-files project_index` não lista `repo_graph.json` nem `manifest.json`.
- [ ] `bash scripts/dev/wt.sh sync` termina 0 numa branch com e numa sem o arquivo versionado.
- [ ] `python -m project_index build && python -m project_index query <símbolo>` funciona; sem build, mensagem clara.
- [ ] `uv run pytest tests/test_project_index.py` verde num checkout **sem** o índice gerado.
- [ ] CI verde (`validate`, `eval-gates`) sem o passo `project_index check`.
- [ ] Prova da Etapa 0 para R7/R8 no handoff; sem prova, R7/R8 ficam de fora (registrado).
- [ ] `uv run pytest` completo verde.
- [ ] Revisão independente (W7).

## 6. Smoke test com LLM real

Não se aplica: nada muda no runtime do jogo. Substituto: o primeiro `/spec-land` de outra spec depois
desta pousa sem commit em `project_index/` e sem erro.

## 7. Riscos & compatibilidade

- **Branch antiga com o arquivo versionado**: conflito modify/delete no rebase. Mitigação: R4 automático e
  ordem (esta spec pousa depois da 368).
- **Alguém depende do índice sem saber**: Etapa 0 item 2.
- **Gate de staleness some**: ele existia para forçar o commit do artefato; com geração sob demanda a
  consulta é sempre fresca.
- Saves, MockLLM, quota, latência: não se aplica.

## 8. Decisões do dono

- **D1** — Tirar os dois artefatos do git (**recomendado**) ou manter `manifest.json` versionado com um
  `check` por hash de árvore? O manifest também muda a cada commit e sem o grafo não serve para consulta.
- **D2** — Autoriza apagar `.tmp/`, `frontend/` e `de/` do checkout principal? São locais, ignorados e
  irrecuperáveis depois. Recomendação: sim.
- **D3** — Skill `/reindex`: vira "gerar local" (1 linha) ou é removida? Recomendação: removida; o comando
  fica no AGENTS.md.
