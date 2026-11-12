# SPEC-414 — medições da Etapa 0 (12/11/2026)

Máquina: Windows 11, uv 0.11.23, Python 3.13.14. MAIN = checkout principal (OneDrive).

## 0.1 Reusar o venv do principal em worktree (gate de R4.1) — PASSOU

Worktree descartável `spec-414-venv` (criado por `wt.sh new`, removido por `wt.sh drop`;
`git worktree list` confirma que sumiu). O worktree não tinha `.venv`, então `env.sh` antigo
já apontava `UV_PROJECT_ENVIRONMENT` para `<MAIN>/.venv`.

1. `grep -n "build-system\|^package" pyproject.toml` ⇒ vazio (projeto virtual). `*.pth` do venv do
   principal: só `_virtualenv.pth` e `a1_coverage.pth`; `grep -il "rpg\|Trabalho"` ⇒ nenhum (rc 1). OK.
2. `py.sh -c "import api, state, sys; print(...)"` no worktree ⇒
   `...\rpg-spec-414-venv\api.py ...\rpg-spec-414-venv\state.py` e `sys.prefix` = `<MAIN>\.venv`. OK.
3. `git rm -q world_utils.py` + `import world_utils` ⇒ `ModuleNotFoundError: No module named 'world_utils'`
   (sem fallback para o principal); restaurado com `git checkout HEAD -- world_utils.py`. OK.
4. `uv pip freeze --python <MAIN>/.venv` antes e depois de `py.sh -c "pass"` no worktree: 118 linhas,
   `diff` vazio. OK.
5. `uv run --help` lista só `--exact` (o default é inexato: instala o que falta sem remover; `uv sync`
   é exato e remove extras — daí R4.3 e o `cmp` do lock em R4.1).
6. Concorrência: `import api` no principal e no worktree ao mesmo tempo ⇒ ambos rc 0. OK.

Veredito: **R4.1 implementado.**

## 0.2 `POR_WORKER_GB`

Não medido pelo executor (é do coordenador, suíte completa). `full_plan.py` usa 1,0 GB provisório
(`POR_WORKER_GB`), a trocar pelo pico medido (arredondado para cima em 0,25 GB).

## 0.3 Formato do crash no xdist instalado

`<MAIN>/.venv/Lib/site-packages/xdist/dsession.py:436`:
`msg = f"worker {worker.gateway.id!r} crashed while running {nodeid!r}"` ⇒
`worker 'gw0' crashed while running 'tests/x.py::test'`. `tests/test_full_plan.py::
test_crashed_ids_from_real_xdist_crash` confirma o formato com um `os._exit(1)` real.

## 0.4 Lixo atual em `%TEMP%`

`ls -d "$TEMP"/pt-* | wc -l` ⇒ **149** diretórios `pt-*` (formato antigo, sem PID). `du -sh` não terminou
em 2 min (milhares de arquivos pequenos); tamanho não medido. A primeira execução do pytest com R3
removeu todos (mtime > 6 h); depois disso restavam 0 do checkout antigo.

## 0.5 Base do hook `Agent`

Comando que reproduz "34 de 166 sem tipo" (04–11/11), para a re-medição pós-pouso:

    bash scripts/dev/py.sh scripts/dev/agent_stats.py --since 2026-11-04 [--until 2026-11-11] [--json]
