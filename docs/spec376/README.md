# SPEC-376 — log de execução

## W1 (04/11, base `1b4dca5c`)
Fontes: (1) branches vivas `spec-370/372/373/374` (+ `bst-*`, `spec-359`, `spec-350c`); (2) status dos worktrees;
(3) `git log --since=2.days main`.
- Interseção real: só `docs/guias/AUTORIA.md` com `spec-374` (diff à frente da main) -> **Etapa A3 espera**.
- O worktree `C:/Users/guilh/AppData/Local/Temp/wtidx5` (branch `idx5`, 3 semanas) está com 2273 arquivos apagados
  (worktree quebrado); ele só gera falso positivo em todas as etapas. Ignorado; candidato a `git worktree remove` (dono).
- Fonte 3: arquivos tocados por commits já pousados na `main` (SPEC-361/377/379/371/362/350), todos `done`/landed
  e sem sessão com mudança pendente; liberados.
- Branches paradas sem relação: `spec-349-pre-sync`, `spec-350-fix`, `dependabot/*`, `bst-*` (arquivar).
