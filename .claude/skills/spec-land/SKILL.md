---
name: spec-land
description: Pousa uma spec na main — ruff nos arquivos tocados, testes do escopo, rebase, regenera specs/index.yaml e Project Index NA PRÓPRIA BRANCH, suíte completa 1x em background, fast-forward da main e remoção do worktree. Use em "/spec-land NNN", "pousa a spec", "mergeia a spec NNN".
---

# /spec-land NNN

Substitui `wt.sh land` + `resolve_*` + `stateline.py` + `reindex.sh` + o commit
separado "chore: rebuild project index". Quem roda é o **coordenador**.

1. **Pré-checagem no worktree** (`bash scripts/dev/wt.sh path NNN`):
   - cabeçalho da spec com o status final (`done`/`in-progress`) — é a ÚNICA fonte;
   - `git status --porcelain --untracked-files=no` vazio (tudo commitado);
   - `uv run --frozen ruff check $(git diff --name-only main...HEAD -- '*.py')`.
2. **Sync** (rebase + `spec_index.py build` + `project_index build` + 1 commit
   `chore: sync spec index and project index` na branch):
   `bash scripts/dev/wt.sh sync NNN`
   Conflito no rebase em `specs/index.yaml`/`project_index/`: aceite qualquer lado
   (`git checkout --theirs …`) e rode o sync de novo — ambos são gerados.
3. **Suíte completa 1×** (camada 2, `docs/guias/TESTES.md`), em background com
   timeout longo, no worktree:
   `bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n auto` (Bash com
   `run_in_background: true`, `timeout: 1200000`). Espere com **uma** notificação; não
   faça `sleep` em loop. Vermelho → devolva ao executor, não pouse.
4. **Pouso**: `bash scripts/dev/wt.sh land NNN` (re-sincroniza se a `main` andou e
   faz `--ff-only`). Depois `bash scripts/dev/wt.sh drop NNN`.
5. **Estado**: rode `/estado` (gera "Decisões recentes" e confere o teto de 8 KB).
   ROADMAP só muda se o plano mudou.

Não faça push sem pedido do dono. Saída final: sha da `main`, contagem da suíte.
