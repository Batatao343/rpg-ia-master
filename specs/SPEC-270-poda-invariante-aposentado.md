# SPEC-270 — Apagar o invariante de playtest aposentado

> **Status:** `draft` · **Revisão independente 2026-10-18:** SAFE as written (ver §8)
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** —
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Luna` (≡ Haiku) · **REVIEW_MODEL:** — · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

`playtest/invariants.py:1063` `check_zero_vitality_outside_terminal` saiu de `CHECKS`
no commit `2bbfd57` (2026-08-27). Motivo registrado ali: "Vitalidade 0 sozinha não é
morte"; o contrato de Ferimentos permite Vitalidade 0 sem morte e o substituto é
`check_actor_lifecycle`. A função ficou, junto com dois testes que a chamam
(`tests/test_remediacao_matriz_a.py:62-65`). Ela nunca roda no harness, mas um leitor
de `explore_06_qualidade.md:143` acha que roda.

## 2. Requisitos

- **R1** — Apagar `check_zero_vitality_outside_terminal` (~16 linhas) e as asserts que a
  chamam em `tests/test_remediacao_matriz_a.py`; se o teste ficar vazio, apagar o teste.
- **R2** — Conferir que `check_actor_lifecycle` e `check_false_player_death` cobrem o caso
  real descrito no commit (inconsciente pós-combate); se não houver teste disso, mover a
  intenção para um teste desses checks (sem mudar a lógica deles).

### Fora de escopo

`check_roundtrip` e `check_reproducibility`, que estão fora de `CHECKS` de propósito
(I/O e harness duplo) e têm testes.

## 5. Critérios de aceite

- [ ] `git grep -n check_zero_vitality_outside_terminal` só em docs
- [ ] `uv run pytest` verde; `uv run python -m playtest run --all --turns 3` sem violação

## 7. Riscos & compatibilidade

Risco **nulo** no runtime. Rollback: `git revert`.

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: SAFE as written.**

- `git grep check_zero_vitality_outside_terminal`: definição + `tests/test_remediacao_matriz_a.py:62-67` + docs.
- A string do código `player.zero_vitality_outside_terminal` só aparece em relatórios históricos
  (`docs/playtests/*`, guia interativo); nenhum dataset/registry de `evals/` nem o `playtest/report.py` a
  usa como chave. Os relatórios históricos continuam corretos como registro do passado.
