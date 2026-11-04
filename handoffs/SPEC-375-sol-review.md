# SPEC-375 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sol (Opus, spec-reviewer) · **Data:** 2026-11-04 · **Commit revisado:** `7e2b2372`

## Escopo

Branch `spec-375`, `ca5f2921..7e2b2372` (5 commits): `c27a819b` (index_dir + dicas build),
`40857de1` (artefatos fora do git, `wt.sh sync` com autorresolução, `.gitignore`, skill spec-land,
`reindex` removido, `project_index check` fora do CI), `583889e7` (R7), `093bbe7d` (R8),
`7e2b2372` (docs R10). Lidos: diff inteiro de `scripts/dev/wt.sh`, workflows, `.gitignore`,
`generator.py`/`query.py`, `tests/test_project_index.py`, docs. Fora: R9 (não executado, D2), pouso.

## Verificação por requisito

- **R1** — `git ls-files project_index` lista só `__init__`, `__main__`, `domains.yaml`, `eval_map.yaml`,
  `generator.py`, `query.py`, `repo_graph.schema.json`, `state_ownership.yaml`. `.gitignore` usa caminhos
  ancorados (`/project_index/repo_graph.json`, `/project_index/manifest.json`): não esconde curados nem o
  schema. OK.
- **R2** — dica `run: python -m project_index build` em ilegível/ausente e stale; testes novos cobrem
  (subprocess sem traceback; `match="stale"` + "build"). OK.
- **R3/R4** — `wt.sh`: `rebase_main` só autorresolve se o conjunto em conflito ⊂ {2 artefatos,
  `specs/index.yaml`}; `--ours` (lado da main) no `index.yaml`, regenerado em seguida; teto
  `rev-list --count + 1`, aborta ao estourar; `git rm -q --cached --ignore-unmatch` incondicional no sync.
  O `git rm -qf` do laço (desvio declarado na §10) só atinge os dois caminhos de `GENERATED_IDX`: não
  apaga curado nem arquivo do produto; efeito colateral = índice local some (regenerável). Uncommitted
  tracked change continua barrada antes do rebase. OK.
- **R5** — `project_index check` sai de `eval-gates.yml`; `test_curated_files_reference_existing_paths`
  chama `validate_curated_files(ROOT)` sem skip e roda na suíte default e no docs-only. Gate de staleness
  deixa de ter sentido (artefato não versionado). Sem perda real.
- **R6** — fixture `built_index` em `tmp_path_factory`; `test_real_index_*` sem skip, só mudou a chamada;
  `:221/:231/:244` sem diff. Nenhum teste lê `ROOT/project_index/*.json`.
- **R7** — `backend-selective`: os 9 `test_eval_*` só em `workflow_dispatch`. `validate.yml` não tem
  dispatch, e em push/PR `backend=true` implica não-docs ⇒ `test` roda a suíte completa. Cobertura
  equivalente. `playtest --turns 3` mantido.
- **R8** — removido `npm audit --omit=dev --audit-level=high` do job `test`. `npm-audit-full` tem a mesma
  condição (`docs_only != 'true'`, roda até no schedule) e é estritamente mais forte
  (`--audit-level=moderate`, árvore inteira). `main` sem proteção (404 / `[]`, Etapa 0) ⇒ nenhum gate de
  merge obrigatório perdido.
- **R10** — referências a `reindex.sh`, `/reindex`, `project_index check` removidas de `.claude/`,
  `AGENTS.md`, `CLAUDE.md`, `docs/guias/TESTES.md`, `scripts/`, `.github/`, `tests/`. Sobras só em
  docs históricos/planos (`docs/melhorias_workspace`, `docs/spec176`, `docs/planos`, auditorias) e em
  `evals/experiments/jev_target_loot.py` (fora de escopo, congelado). `.claude/hooks/reindex-reminder.js`
  é o lembrete do RAG (`rag.py`), não do Project Index. `AGENTS.md:24` mantém `project_index/domains.yaml`
  (`test_agents_contract.py` verde).
- `evals/` protegido: sem diff. Sem segredo em log. Funções novas < 60 linhas; `generator.py` 842 linhas.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `specs/SPEC-375-refactor-higiene-index-ci.md` §10 | Critério "teste manual (a)–(d) com saída no handoff" só tem "todos como esperado", sem saída. | Suprido por esta revisão (saídas em "Comandos rodados"); executor não precisa refazer. |
| P2-2 | P2 | `docs/guias/BRIEF_SUBAGENTE.md:59-60` | Ainda diz "`project_index/` (gerado no pouso)"; agora o artefato é local e os curados são versionados. | Trocar por "`project_index/` (curados por spec; artefatos locais)". Não está na lista de R10, então é follow-up. |
| P2-3 | P2 | `scripts/dev/wt.sh:50-51` | Ao parar por conflito fora do conjunto gerado, a mensagem não diz o próximo passo. Resolver à mão e rodar `rebase --continue` pode cair de novo no conflito dos artefatos. | Acrescentar "resolva, `git rm` nos artefatos se aparecerem, `git rebase --continue`, rode `sync` de novo". Opcional. |

## Notas para o pouso (coordenador)

- Seguir a Etapa 4: **não** rodar `wt.sh land 375`. Sync com uma cópia temporária do `wt.sh` da branch,
  depois ff manual.
- A `main` andou 3 commits (`70c7ebc3 chore: rebuild project index` mexe em `repo_graph.json`).
  `git merge-tree --write-tree main spec-375` mostra conflito **só** em `project_index/manifest.json` e
  `repo_graph.json` (modify/delete). É exatamente o caso que `rebase_main` autorresolve.
- Branches vivas: nenhuma além de `backup/docs-reorg-local` tem commit em `main..` que toque os
  artefatos. `spec-372` (e `spec-359`/`spec-373`) já têm o último commit de sync na base.

## Correções aplicadas

Nenhuma (o revisor só edita este arquivo).

## Pendências

- P2-2 e P2-3: follow-up de docs/tooling, sem bloquear o pouso (coordenador decide a spec de destino,
  por exemplo a próxima de workspace/higiene).

## Comandos rodados

```text
git diff main...HEAD --stat → 19 arquivos, +175/-873291
for-each-ref + git log main..$b -- project_index/{repo_graph,manifest}.json → só backup/docs-reorg-local e spec-375
repo descartável (a): branch com 2 commits de sync antigos (3 arquivos) + domains.yaml curado alterado, main destrava → rebase_main rc=0; commits de sync descartados; artefatos não rastreados; domains.yaml preservado (d, d2)
repo descartável (c): commit misto a.txt + repo_graph.json em conflito → "rebase stopped; conflicts outside generated files: a.txt", rc=1, rebase em andamento
repo descartável (d): branch que re-rastreia repo_graph.json (add -f) → rebase rc=0; git rm --cached incondicional → ls-files vazio, arquivo local mantido
git merge-tree --write-tree --name-only main spec-375 → conflito só nos 2 artefatos (modify/delete)
bash scripts/dev/pt.sh tests/test_project_index.py tests/test_dev_tooling.py tests/test_agents_contract.py tests/test_handoff_names.py → 33 passed in 56.36s
```
