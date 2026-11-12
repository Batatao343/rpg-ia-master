# SPEC-414 — revisão terra (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sonnet (terra) · **Data:** 2026-11-12 · **Commit revisado:** `98584105`

## Escopo

Branch `spec-414`, `git diff main...HEAD` (22 arquivos): hook `guard_tools.py`, `full.sh`/`full_plan.py`,
`conftest.py`/`basetemp_support.py`, `env.sh`/`wt.sh`, testes e docs. Fora: medição 0.2 de
`POR_WORKER_GB` (coordenador, no pouso, decisão do dono). Nenhuma mudança em `evals/`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `.claude/hooks/guard_tools.py` `_after_pytest`/`_runs_full_suite` | Falso positivo para subagente: o token `pytest`/`full.sh` é procurado em qualquer posição do segmento. Negam: `echo pytest -n auto`, linha de heredoc com `pytest -n auto`, `echo full.sh`. Reproduzido ao vivo: meu próprio heredoc de teste foi negado pelo hook. Só afeta subagente, o custo é uma reescrita do comando. | Exigir que o token de pytest seja o 1º word do segmento (após `env`/`VAR=x`/`uv run`/`python -m`), ou ignorar segmentos que começam por `echo`/`grep`/`cat`. |
| P2-2 | P2 | idem `XDIST_RE` | Falso negativo: `pytest -n=auto` e `bash -c 'pytest -n auto'` (aspas viram 1 palavra) passam. É heurística de RAM, não segurança. | Aceitar `-n=` e reparsear o argumento de `bash -c`; ou registrar a limitação em `TESTES.md`. |
| P2-3 | P2 | `guard_tools.py` `main` (`except Exception: return`) | Hook **falha aberto** em qualquer exceção, inclusive `NameError` de bug do próprio hook (o que o executor viu). Intencional ("hook nunca derruba a sessão") e tem `silent-ok`, mas um bug no detector vira "sem proteção" sem sinal. | Escrever 1 linha em stderr (`guard_tools: erro interno <tipo>`) no `except`; sem negar. |
| P2-4 | P2 | `check_agent` | Dentro do esperado (R6): `subagent_type` ausente/`None`/`general-purpose`/`claude` sem `Motivo sem tipo: <>=10 chars>` é negado; tipos nomeados, `Explore`, `Plan` e tipo desconhecido passam; payload malformado passa (rc 0). Nota: o coordenador precisa lembrar de escrever o motivo; mensagem de negação é clara. Sem ação. | — |
| P2-5 | P2 | `full_plan.py` `verdict` / `full.sh` | `final` após rerun vira 0/1 do `verdict`, não o rc literal do pytest (comentário do script diz "rc = o da pytest"). Sem crash, `final=$prc` preservado (inclui 2/5). Só diverge no ramo de crash, onde 0/1 é o desejado. Ajustar o comentário. | Reformular a linha 5 de `full.sh`. |
| P2-6 | P2 | `env.sh` + `uv run --frozen` | Com `uv.lock` igual o worktree usa o venv do principal; `--frozen` evita reescrever o lock, mas `uv run` ainda sincroniza o venv compartilhado (instala o que faltar). Risco baixo (lock idêntico), mas dois worktrees concorrentes podem disputar. `wt.sh new` avisa para não rodar `uv sync`. Sem venv no principal e sem `.venv` local, `uv` cria `.venv` no worktree (aceitável). `uv.lock` diferente: aviso e venv próprio (testado). | Considerar `UV_NO_SYNC=1`/`--no-sync` quando `UV_PROJECT_ENVIRONMENT` aponta para o principal (follow-up). |

Sem P0/P1. Verificações dos pontos pedidos:

1. Hook: falha aberta (P2-3). Tabela real (subagente): `uv run pytest -n auto`, `env FOO=1 pytest -n 8`, `python -m pytest -n4`, `--numprocesses auto`, `-nauto`, `--dist loadfile -n logical`, `pt.sh -n 6`, `bash [./|/x/]scripts/dev/full.sh`, `FULL_N=2 bash …full.sh` negados corretamente. Permitidos corretamente: `grep -n "pytest -n auto" f`, `git log --grep=pytest -n 5`, `pytest tests/a.py -n 2`, `pytest -n 2 | tail`, `pt.sh tests/x.py`. Falsos: P2-1/P2-2.
2. `full.sh`: rc correto nos ramos (verde 0; falha comum 1 sem rerun; crash + rerun verde 0; crash + falha real 1 por `verdict`; >20 mortos 1; piso de RAM rc 3 sem chamar pytest; testes cobrem). `eval` só alcançável via env `FULL_PYTEST` (seam de teste, mesma confiança do shell do usuário); default sem caminhos. Caminhos com espaço/acento: `$log`, `$@`, `"${ids[@]}"` e `$RPG_ROOT` estão entre aspas; `env.sh` usa `pwd -P` entre aspas.
3. Basetemp: nome `pt-<sha8>-<pid>`, controlador apenas (worker e `--basetemp` explícito retornam None; workers herdam o do controlador). A poda usa mtime do diretório > 6 h e só nomes `pt-<hex8>[-<pid>]`; pode, em tese, apagar o basetemp de um run vivo parado >6 h sem criar tmp novo (diretório não tocado) e de outro checkout (efeito desejado para lixo). Aceitável; falha de `rmtree` é engolida (testado).
4. `env.sh`: ver P2-6.
5. Mutações (cada uma restaurada com `git checkout --`, `git status` limpo): `pick_workers` piso → `test_pick_workers_table` FALHA; poda sem checar idade → `test_prune_removes_only_old_pt_dirs` FALHA; `env.sh` sem `cmp` do lock → `test_worktree_with_different_lock_keeps_own_env` FALHA. Os testes têm poder. (A mutação de `verdict` ficou mascarada pelo `-x` do `pt.sh` e não foi provada separadamente; coberta por `test_verdict` por leitura.)

Qualidade: funções novas ≤ 60 linhas; `ruff` ok pelo hook; sem helper duplicado evidente; sem segredo em log; escopo condizente com a spec.

## Correções aplicadas

Nenhuma (revisor só edita este arquivo).

## Pendências

P2-1/P2-2/P2-3 (hook) e P2-6 (`--no-sync`) podem ir para spec de follow-up de tooling (dono: coordenador). P2-5 é só comentário. Medição `POR_WORKER_GB` 0.2 no pouso (coordenador).

## Comandos rodados

```text
bash scripts/dev/pt.sh tests/test_full_plan.py tests/test_basetemp.py tests/test_dev_env.py tests/test_workspace_hooks.py tests/test_dev_tooling.py → 89 passed
hook via stdin (script no scratchpad), 20 comandos Bash + 10 payloads Agent → tabela acima
3 mutações com pt.sh -n 0 → 3 falhas esperadas; git checkout restaurou; git status limpo
```
