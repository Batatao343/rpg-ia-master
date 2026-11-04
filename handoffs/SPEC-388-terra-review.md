# SPEC-388 — revisão terra (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** spec-reviewer (Opus/Sonnet) · **Data:** 2026-11-04 · **Commit revisado:** `4e886549` (Etapa B)

## Escopo

`main...HEAD` (4e886549): `pyproject.toml`, `ruff-baseline.toml`, `tests/test_ruff_protected_exempt.py`,
`docs/guias/TESTES.md`, §8 da spec. Fora: Etapa A, hook SPEC-386 (só avaliado o efeito).

## Verificações

1. Baseline: comparada por código via tomllib (main vs branch). Únicas remoções: `agents/archivist.py` F841,
   `services/prologue.py` F401/UP035, `tests/test_mvp.py` E741. Os três arquivos não mudaram na branch e
   `ruff --isolated --select` confirma que não violam esses códigos (entradas obsoletas na main). Resto aditivo.
2. `ruff check .` verde, `ruff format --check .` (1841 arquivos) verde, `ruff_baseline.py --check` current.
   `tests/test_ruff_protected_exempt.py` + `test_handoff_names.py`: 4 passed.
3. Globs: o gate cobre todo .py de `protected-paths.txt` da branch. `spec-372` acrescenta
   `scripts/fauna/eval_tramas.py` e `tests/test_spec372_eval.py`: ambos casam (`scripts/**/eval*.py`,
   `tests/test_spec*_eval.py`).
4. Hook: ruff 0.16.3; teste com `--fix` + SIM/RET/C4/PIE/ERA/PERF/BLE aplicou só RET505 (seguro); ERA001,
   RET504, C4 não-triviais, PIE e SIM inseguros são "unsafe" e não rodam sem `--unsafe-fixes`. Não falta
   `--unfixable`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | pyproject.toml (`scripts/**/eval*.py`) | Casa não-avaliadores, isentando-os das famílias novas: `scripts/ci_eval_scope.py`, `scripts/dev/eval_publish.py`, `scripts/frontend_eval_report.py`, `scripts/verify_protected_eval_change.py`. Também `tests/test_spec371_eval.py` (não está em protected-paths). São tooling/código de produto de CI. | Trocar por globs exatos (`scripts/fauna/eval.py`, `scripts/fauna/eval_tramas.py`, `scripts/bestiario/eval_geracao.py`) ou aceitar e documentar; o gate já garante cobertura. |
| P2-2 | P2 | pyproject.toml (`evals/**`) | Isenta também `evals/experiments/*.py`, `evals/gameplay_scan.py`, `evals/__init__.py` (não protegidos). | Restringir a `evals/core|evaluators|__main__.py|datasets` se o dono quiser lint neles; aceitável (já têm exceções antigas). |
| P2-3 | P2 | .claude/hooks/ruff_after_edit.py:20 | `PROTECTED_PREFIXES` só cobre `evals/` e `web/e2e/contracts/`; `scripts/fauna/eval.py`, `services/creature_gen_eval.py`, `tests/test_spec*_eval.py` protegidos podem ser reescritos por `format`/`--fix` (F/I/UP). Problema anterior à Etapa B, não agravado por ela. | Follow-up: ler `protected-paths.txt` no hook. |

## Correções aplicadas

Nenhuma (revisor só escreve o handoff).

## Pendências

P2-1..3 como follow-up (SPEC-388 Etapa C ou 386).

## Comandos rodados

```text
ruff check . / ruff format --check . / ruff_baseline.py --check → verdes
bash scripts/dev/pt.sh tests/test_ruff_protected_exempt.py tests/test_handoff_names.py → 4 passed
tomllib diff main vs branch da baseline → só 3 remoções obsoletas
git ls-files (globs de isenção) → lista acima
ruff --fix --diff em arquivo de teste → só RET505 aplicado
```
