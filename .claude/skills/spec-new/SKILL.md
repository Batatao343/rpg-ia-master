---
name: spec-new
description: Reserva o próximo SPEC-NNN, cria specs/SPEC-NNN-<slug>.md do TEMPLATE, commita a reserva na main e abre um worktree spec-NNN fora do OneDrive. Use quando o usuário pedir "/spec-new <slug>", "nova spec", "abre spec" ou antes de implementar uma feature nova.
---

# /spec-new <slug>

Spec antes de código (CLAUDE.md § Fluxo de spec). A reserva acontece **antes** do
worktree, na `main`, para duas sessões nunca escolherem o mesmo número.

```bash
. scripts/dev/env.sh                                   # raiz do repo, uv, PYTHONUTF8
uv run --frozen python scripts/spec_index.py next-id   # mostra SPEC-NNN (vê arquivos, index, branches spec-*, worktrees)
uv run --frozen python scripts/spec_index.py next-id --slug <slug> --create
uv run --frozen python scripts/spec_index.py build      # adiciona a entrada gerada em specs/index.yaml
git add specs/SPEC-NNN-<slug>.md specs/index.yaml
git commit -m "spec: reserve SPEC-NNN <slug>"           # + linha Co-Authored-By
bash scripts/dev/wt.sh new NNN                          # imprime o caminho do worktree
```

Regras:
- Rode na `main` do checkout principal (`git rev-parse --abbrev-ref HEAD` = `main`).
- Slug em kebab-case minúsculo. Status nasce `draft`; só o dono aprova.
- Worktree fica em `%LOCALAPPDATA%\Temp\claude\rpg-spec-NNN` com junção de
  `web/node_modules`; Python do worktree: `bash scripts/dev/py.sh …` (usa o `.venv`
  do checkout principal quando o worktree não tem um).
- Devolva só: `SPEC-NNN`, caminho do arquivo, caminho do worktree.
