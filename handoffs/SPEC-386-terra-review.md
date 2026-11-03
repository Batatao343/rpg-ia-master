# SPEC-386 — revisão terra (review)

> **Veredito:** APPROVED_WITH_FOLLOWUPS
> **Revisor:** Sonnet (terra) · **Data:** 2026-11-03 · **Commit revisado:** `ae3846a6`

## Escopo

`git diff main...HEAD`: hooks `.claude/hooks/*`, `settings.json`, `size_budget.py` + baseline + teste, textos em AGENTS/CLAUDE/BRIEF/agentes/TEMPLATE. Fora: suíte completa.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | .claude/hooks/guard_tools.py:~95 | `shlex posix` consome barras de caminho Windows sem aspas (`cat C:\x\y`): tamanho 0, falso negativo (só deixa passar, nunca bloqueia indevido). | Aceitável; opcional: `posix=False` ou normalizar `\`. |
| P2-2 | P2 | .claude/hooks/guard_tools.py (SEGMENT_SPLIT) | Corpo de heredoc é dividido por \n e cada linha tratada como comando (`cat grande.md` dentro do texto de um heredoc seria negado). Raro. | Ignorar segmentos após `<<`. |
| P2-3 | P2 | .claude/hooks/ruff_after_edit.py | `ruff check --fix` não tem exclude de lint para `evals/core|evaluators` (só o format). Verificado: `--fix --diff` em evals/core, evals/evaluators, evals/__main__.py, scripts/fauna/eval.py hoje não gera mudança (per-file-ignores I/UP; sem F/B corrigível), mas regra futura corrigível reescreveria protegido. | Follow-up: `extend-exclude` ou `--unfixable` p/ esses caminhos. |
| P2-4 | P2 | AGENTS.md:373 | Seção nova inserida após as linhas citadas pela SPEC-375 (22-23, 58, 311, 316); o 387 passa a 402 (texto "Não editar specs/index.yaml…" presente, só deslocado). | SPEC-375 deve localizar por texto, não por número. |

Sem P0/P1.

## Verificações

- Hooks: heredoc (`cat <<EOF > f`) permitido; Read de imagem/PDF liberado por extensão; caminho Git Bash `/c/…/Área de Trabalho/…` convertido e 205 KB negado; `-n4` em subagente negado, fora de subagente liberado; todos os mains saem 0 com stdin inválido/exceção (`silent-ok`).
- ruff: `--force-exclude` presente em format e check; `--unfixable F401,F811`; format exclui evals protegidos (pyproject:70).
- size_budget: lê UTF-8, usa `git ls-files`, contagem por "\n" insensível a CRLF; baseline confere (script sem estouro); JSON gravado com newline LF.
- settings.json válido, matchers Edit|Write / Read|Bash|PowerShell, `$CLAUDE_PROJECT_DIR` em todos.
- Textos: coerentes com W7 (citado explicitamente), `-n 2`, pt.sh; /qa não contradito.

## Correções aplicadas

Nenhuma (revisor não edita código).

## Pendências

P2-1..P2-3 como follow-up de tooling; P2-4 para a SPEC-375.

## Comandos rodados

```text
bash scripts/dev/pt.sh tests/test_workspace_hooks.py tests/test_size_budget.py tests/test_spec_index_tool.py tests/test_dev_tooling.py tests/test_agents_contract.py → 55 passed
ruff check --fix --diff nos protegidos de eval → sem diff
size_budget.py → sem estouro
```
