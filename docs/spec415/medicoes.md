# SPEC-415 — medições (12/11/2026, worktree da spec, após rebase na 414)

1. **R5** — `ruff --version` = `ruff 0.17.4`; `ruff format --check .` na árvore da branch: `1994 files already formatted` (nenhum `.md` de `specs/`/`handoffs/` reprovado hoje; a exclusão é preventiva e o teste `test_ruff_format_excludes_specs_and_handoffs` a trava).
2. **§6.1** — tempo de parede do `land_check.sh 415`: 7,9 s (meta < 15 s).
3. **§6.3** — tempo de parede do `red_green.sh 415` (35 testes novos, 2× `-n 2`): 39,4 s (meta < 3 min); `git worktree list` sem `rpg-redgreen-415` ao fim.
4. **§6.5** — `ram.sh | head -3`: `RAM livre: 2,8 GB de 15,7 GB` (separador decimal vírgula; `parse_free_ram_gb` aceita os dois).
5. **§6.6** — `gh --version`: `gh version 2.95.0 (2026-06-17)`.
6. **§7.2** — `spec_index.py summary`: 418 specs; `approved`/`in-progress` sem `Risco` preenchido: 197, 198, 222, 297, 359, 379, 380, 384 (todas anteriores à regra de `Risco`). Precisam do campo antes de pousar sob `land_check` (o coordenador/autor preenche; o `review` reprova com "campo Risco não preenchido").
7. **Achado de execução** — `subprocess` no Windows resolve `bash` pelo `System32` (WSL) antes do `PATH` (CreateProcess); `default_run` usa `shutil.which`. Sem isso o `ram.sh` imprimia só o banner do PowerShell.
