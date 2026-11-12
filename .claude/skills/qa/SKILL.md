---
name: qa
description: Roda testes do projeto de forma token-lean (só falhas + resumo), em camadas. Use durante iteração de código, quando o usuário pedir "roda os testes", "/qa", ou antes de começar uma tarefa. Para o ritual de fim de tarefa use /wrap-up.
---

# /qa — pytest token-lean, em camadas

Funciona em qualquer worktree (sem caminho fixo). Camadas em `docs/guias/TESTES.md`.

| Camada | Quando | Comando |
|---|---|---|
| 0 | a cada iteração | `bash scripts/dev/pt.sh --lf` |
| 1 | antes do hand-back de um executor | `bash scripts/dev/pt.sh tests/test_<escopo>*.py` |
| 2 | `/qa --full` — suíte completa: só coordenador / fim de tarefa, 1× | `bash scripts/dev/full.sh` em background (`run_in_background: true`, `timeout: 1200000`); escolhe `-n` pela RAM, rc 3 abaixo do piso (`FULL_N=<n>` força) |

Lint rápido antes de rodar teste: `bash scripts/dev/py.sh -m ruff check <arquivos tocados>`.

Regras:
1. Verde: reporte só a contagem ("146 passed").
2. Falhou: nome do teste + linha decisiva; re-rode só ele com `-x` sem `tail`.
3. Subagente executor não roda a camada 2 (o coordenador roda no `/spec-land`).
4. Comando > 2 min sempre em background com timeout explícito; espere com uma
   notificação, nunca `sleep` em loop.
