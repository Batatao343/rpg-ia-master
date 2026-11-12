# SPEC-415 — revisão terra (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sonnet (spec-reviewer, papel terra) · **Data:** 2026-11-12 · **Commit revisado:** `53d52897` (rodada 2; a rodada 1, em `3fd1439e`, reprovou por P1-1)

## Escopo

Branch `spec-415` (26 arquivos, +1368): `land_check.py`, `wt.sh`, `red_green.py/.sh`, `handoff.py`,
`.gitattributes`, `pyproject.toml`, template de spec, agentes, guia de casos. Fora: o caminho
ligado de `wt.sh ci` (RPG_WT_PUSH=1) foi lido, não exercitado; sem push; Postgres/CI não aplicáveis.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `scripts/dev/land_check.py` `last_verdict` (~l.92) e `review_problems` | `last_verdict` pega a ÚLTIMA ocorrência de qualquer token de veredito no texto inteiro, não a linha `> **Veredito:**`. Reproduzido: handoff com cabeçalho de reprovação e, na seção Pendências, a frase "re-revisar até <token de aprovação>" retorna `[]` (pouso liberado, falso negativo). O inverso trava pouso legítimo: cabeçalho de aprovação + "antes era <token de reprovação>" no corpo gera FAIL (falso positivo). Handoffs de 2 rodadas citam os dois tokens com frequência. | Ler só a(s) linha(s) `^>\s*\*\*Veredito:\*\*` (última delas, para 2 rodadas); sem essa linha, tratar como inválido. Teste: os dois casos acima. |
| P2-1 | P2 | `land_check.py` `review_problems` (retorno `problems if len(problems)==len(valid) else []`) | Desvio §9 ("ao menos um válido") deixa um handoff aprovado de papel qualquer anular outro revisor que reprovou (reproduzido com terra reprovando + luna aprovando). Aceito pelo dono como escrito; registro como risco residual: ao menos o papel mais alto presente deveria prevalecer. | Opcional: reprovação do papel de maior nível bloqueia. |
| P2-2 | P2 | `land_check.py` `_MEASURE_RE` | `(?<!`)<MEDIR:` só ignora a crase colada; `` `valor <MEDIR: x>` `` (marcador pendente dentro de crase) é FAIL e `` `<MEDIR:…` `` é ignorado de verdade. Falso positivo raro, falso negativo improvável. | Documentar a convenção na spec/agente (escape = crase imediatamente antes). |
| P2-3 | P2 | `.claude/agents/spec-reviewer.md` | Reviewer ganhou `Edit` e a regra "só edita o handoff" passou a ter exceção para o guia de casos; o corpo de `docs/guias/BRIEF_SUBAGENTE.md` não menciona isso (sem contradição direta, mas o reviewer passa a poder editar código). | Citar a exceção no BRIEF ("Arquivos que você não edita"). Não apliquei a linha do guia por CHANGES_REQUIRED: reviso só o handoff nesta rodada. |
| P3-1 | P3 | tabela red_green | Dois testes de `test_wt_sh.py` (`test_land_clean_fast_forwards`, `test_sync_clean_passes`) ficam verdes na `main`: são guardas de regressão, corretamente reprovados pela regra "não prova a mudança". Precisam de `--allow-green` na evidência da spec. | Registrar o `--allow-green` no handoff do executor. |
| P3-2 | P3 | editor | Diagnóstico `"subprocess" is not defined` em `red_green.py`: falso. O arquivo não usa `subprocess` (grep vazio); é diagnóstico obsoleto do editor. | Nenhuma. |

## Evidência verificada

Verificações pedidas, resultado:

- Collision: `-z` + `--untracked-files=normal` trata espaço/acento (`dirty_paths` reproduzido com `Área x/ç.py`) e diretório untracked (`d` terminando em `/`). Mutação sem o ramo de prefixo de diretório reprovou `test_collisions_by_path_and_dir_prefix`.
- `RPG_LAND_SKIP`: qualquer valor fora de `ram,ci` dá rc 2; nenhum outro check é pulável por variável. Mutação `if free < 0` reprovou `test_ram_below_floor_fails_unless_skipped`. `git status` limpo após as duas mutações.
- `wt.sh`: `land_check` roda depois do `sync` e antes do `cd "$MAIN"`/ff; falha faz `exit 1` sem tocar a branch rebaseada (sem rebase pela metade). `ci` sem `RPG_WT_PUSH=1` sai com 3 antes de qualquer `git`. Ramo ligado: `push --force-with-lease origin "$BR"` com `WT=…/rpg-$BR`; para `main` o worktree não existe, o `git -C` falha e nada é empurrado; só `spec-NNN` (ou outra branch com worktree próprio) é empurrada. Sugestão de endurecer: exigir `spec-[0-9]{3}` no `ci` (hoje só `land_check` filtra).
- `.gitattributes merge=union` só no guia de casos; `pyproject` só acrescenta `specs/**` e `handoffs/**` ao `[tool.ruff.format].exclude`; lint de `.py` intacto.
- Semente do guia: 3 amostras conferidas contra handoffs (410 P3-2 `42501`; 413 P2-1 `smoke_ab.py:326` e P3-1 asserção vácua; 413/410 P3-4 `schema_migrations`; 411 P3-3 guard largo): batem. Agentes não contradizem o BRIEF (P2-3).
- Worktree temporário: removido em `finally` (inclui exceção e Ctrl+C), `git worktree list` idêntico antes e depois da execução, checkout principal não tocado.

Saída de `bash scripts/dev/red_green.sh 415` (33/35; os dois FAIL são guardas, ver P3-1):

| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_handoff_file.py (3 testes) | vermelho (import) | verde | OK |
| tests/test_land_check.py (14 testes) | vermelho (import) | verde | OK |
| tests/test_red_green.py (7 testes) | vermelho (import) | verde | OK |
| tests/test_workspace_docs.py (6 testes) | vermelho | verde | OK |
| tests/test_workspace_hooks.py::test_context_size_points_to_handoff_file | vermelho | verde | OK |
| tests/test_wt_sh.py::test_ci_is_off_without_env, test_land_refuses_ff_on_collision, test_sync_fails_on_collision_with_dirty_main | vermelho | verde | OK |
| tests/test_wt_sh.py::test_land_clean_fast_forwards | verde | verde | FAIL: nao prova a mudanca |
| tests/test_wt_sh.py::test_sync_clean_passes | verde | verde | FAIL: nao prova a mudanca |

red_green: 33/35 OK

## Correções aplicadas

Nenhuma (revisor não edita código).

## Pendências

P1-1 antes do pouso. P2-1/P2-2/P2-3 viram follow-up ou ajuste de texto. Não rodou: caminho
`RPG_WT_PUSH=1` de `wt.sh ci` e o check `ci` contra o `gh` real (sem push autorizado).

## Comandos rodados

```text
bash scripts/dev/red_green.sh 415 → 33/35 OK
bash scripts/dev/pt.sh (6 arquivos de teste da spec) → 94 passed
mutação 1 e 2 em land_check.py + pt.sh test_land_check.py → cada uma reprovou 1 teste; git checkout; git status limpo
python (review_problems/dirty_paths/pending_measures) → P1-1 e P2-1 reproduzidos
```

## Rodada 2 (delta `53d52897`)

P1-1 resolvido: `last_verdict` lê só a última linha `> **Veredito:**`, aceita o valor entre crases
(`APPROVED_WITH_FOLLOWUPS` reproduzido) e handoff sem a linha é inválido. `review_problems` usa o mais
recente de cada papel e qualquer reprovação bloqueia (P2-1 resolvido). `<MEDIR:` entre crases não conta e
marcador cru depois de trecho com crase conta (reproduzido) (P2-2). `wt.sh ci` valida `spec-NNN` antes de
qualquer `git`. BRIEF ganhou a linha da exceção do revisor (P2-3). `_CODE_SPAN_RE` e `_VERDICT_LINE_RE` são
usados (linhas 164 e 102): o aviso do editor é falso. Testes: 30 passed (`test_land_check`, `test_wt_sh`,
`test_workspace_docs`).

Achados novos (nenhum P0/P1):

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-4 | P2 | `land_check.py` (`for name in sorted(valid)`, ~l.140) | "Mais recente = última pela ordem de nome" erra em caso real: SPEC-391 tem `sol-review` (reprovado, 04/11) e `sol-independent-review` (aprovado, 10/11); na ordem de nome `sol-review` vence, o re-review aprovado é ignorado e o pouso trava (falso positivo). SPEC-382 tem o par, ambos aprovados, sem efeito. | Desempatar pela linha `**Data:**` do handoff ou pelo `git log` do arquivo; no mínimo documentar "remova o handoff antigo". |
| P2-5 | P2 | `land_check.py` (`last_verdict`, ~l.100) | Linha com vários tokens (o template cru) retorna o primeiro (aprovado), e a seção Evidência do template cru já conta como preenchida: handoff copiado e não editado passa. Reproduzido com `docs/templates/handoff-review.md`. | Mais de um token distinto na linha = inválido. |

## Evidência verificada (rodada 2)

`bash scripts/dev/red_green.sh 415 --allow-green tests/test_wt_sh.py::test_land_clean_fast_forwards --allow-green tests/test_wt_sh.py::test_sync_clean_passes`:
37 testes, todos OK: 35 vermelhos na `main` (por import ou asserção) e verdes na branch, mais os 2 guardas
com `OK (allow-green)`. Incluem `test_last_verdict_uses_only_verdict_line`,
`test_review_problems_any_role_rejecting_blocks` e `test_ci_rejects_non_spec_target`. Worktree temporário
removido (mesma contagem de worktrees antes e depois).

red_green: 37/37 OK
