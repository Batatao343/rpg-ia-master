# SPEC-388 — Workspace, fase 2: guardrails que esperam a onda 375–378

> **Status:** `in-progress` — B e C pousadas; A espera a SPEC-375 (04/11, dono: "vai executando o que puder"; etapas só quando a spec da etapa estiver `done`)
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** SPEC-386 § Fora de escopo · [auditoria do workspace](../docs/auditorias/auditoria-workspace-2026-11-03.md) §8
> **Depende de:** **por etapa** (cada etapa só começa quando a spec dela estiver `done` na `main`):
> Etapa A ← SPEC-375 · Etapa B ← SPEC-376 · Etapa C ← SPEC-378. As etapas são independentes entre si.
> **Desbloqueia:** nada obrigatório (a onda roda sem esta spec; esta só fecha a porta atrás dela)
> **Risco:** `baixo` (tooling e docs; B muda o lint de código novo) · **REVIEW_REQUIRED:** `true` só na Etapa B
> **Evidência:** A: `tests/test_agents_contract.py` + `test_dev_tooling.py` verdes e `AGENTS.md` < 200 linhas;
> B: `ruff check .` e `ruff_baseline.py --check` verdes com as regras novas; C: teste novo falha com um `def _fold` sintético fora de `services/text.py`
> **EVAL_AUTHORING_REQUIRED:** `false`

## 1. Contexto & Objetivo

A SPEC-386 armou hooks e gates, mas adiou três itens que esbarram em arquivos da onda de
refatoração (regra W1 da auditoria de código §6.2). Esta spec guarda os três, cada um preso à
spec que libera o terreno, para que quem orquestra a onda veja quando cada um pode rodar.
Não é refatoração de produto.

## 2. Requisitos

- **R1 (Etapa A, após 375)** — `AGENTS.md` com < 200 linhas. Arquitetura, tiers de LLM, RAG,
  persistência, GameState e árvore de pastas viram 1 linha + link para `REFERENCE.md` ou
  `docs/guias/ARQUITETURA.md`. Mantém todas as strings exigidas por
  `tests/test_agents_contract.py` e a § "Qualidade, revisão e evidência".
- **R2 (Etapa B, após 376)** — `pyproject.toml` `[tool.ruff.lint].select` ganha `C90`
  (`max-complexity = 15`), `SIM`, `PERF`, `C4`, `PIE`, `RET`, `ERA`, `BLE`. Uma rodada de
  `scripts/dev/ruff_baseline.py` congela o legado (commit próprio, W4), e código novo nasce sob
  as regras. Os `# noqa: BLE001` existentes passam a valer. `E501`, `PLR2004`, `T20`, `ARG`,
  `PLR0913` e `N` ficam fora.
- **R3 (Etapa C, após 378)** — `tests/test_no_new_fold.py`: falha se um `def _fold*`/`_norm*`
  novo aparecer fora de `services/text.py`, com uma baseline do que a 378 deixou por
  decisão (aliases/variantes).

### Fora de escopo

Qualquer mudança de comportamento; mexer em `evals/` protegido; refatorar além do que o lint
exige (violação nova em legado vai para a baseline, não é corrigida aqui).

## 3. Design técnico

- A: `AGENTS.md`, `REFERENCE.md` (ou `docs/guias/ARQUITETURA.md`), `CLAUDE.md` se citar seção movida.
- B: `pyproject.toml`, `ruff-baseline.toml` (gerado), `docs/guias/TESTES.md` § lint (1 linha).
- C: `tests/test_no_new_fold.py`, `tests/data/fold_allowlist.txt`.

## 4. Plano passo a passo

### Etapa A — AGENTS.md enxuto (pode começar quando: SPEC-375 `done`)
1. Testes: rodar `test_agents_contract.py`/`test_dev_tooling.py` antes (verdes) e depois.
2. Mover seções; conferir que nenhum `@import`/link quebrou (`spec_index.py check`).

### Etapa B — Ruff mais estrito para código novo (pode começar quando: SPEC-376 `done`)
1. `ruff check --select <novas> --statistics` para registrar o tamanho do legado.
2. Ligar as regras; `ruff_baseline.py`; `ruff_baseline.py --check` e `ruff check .` verdes.
3. Revisor confere que o diff da baseline só acrescenta códigos novos (não some dívida antiga).

### Etapa C — Anti-`_fold` (pode começar quando: SPEC-378 `done`)
1. Teste com fixture sintética que falha; allowlist com o que a 378 manteve.

## 5. Critérios de aceite

- [ ] Etapa A pousada (ou registrada como pendente com o motivo)
- [x] Etapa B pousada, baseline com diff só aditivo (04/11; legado: BLE001 447, PERF401 173, C901 130, ERA001 66, SIM105 62…; únicas remoções = encolhimentos pré-existentes em `archivist.py`/`prologue.py` e `E741` de `test_mvp.py` pago pela 376)
- [x] Etapa C pousada (04/11: `tests/test_no_new_fold.py` + `tests/data/fold_allowlist.txt` com as 52 definições que a 378 manteve; falha com `def _fold` sintético)
- [ ] `uv run pytest` verde a cada pouso de etapa

## 6. Smoke test com LLM real

Não se aplica (tooling).

## 7. Riscos & compatibilidade

- B pode reprovar specs em voo que tragam código novo complexo: avisar no ESTADO no dia do pouso.
- Cada etapa pousa sozinha; o status fica `in-progress` até a última, e `done` com as três.

## 8. Execução

- **Etapa B (04/11):** desvios declarados: (1) `tests/**` isento de `C90`/`PERF`; (2) avaliadores
  protegidos isentos das famílias novas por **lista exata** (revisão terra P2-1/P2-2: globs largos isentavam
  scripts comuns), com os 2 da `spec-372` já incluídos, porque o hash travado impede reescrever (achado: `scripts/fauna/eval_tramas.py` da
  branch `spec-372` teria 8 violações sem poder corrigir); gate `tests/test_ruff_protected_exempt.py`.
  Impacto medido nas branches vivas: `spec-359` 0, `spec-373` 0, `spec-372` 3 triviais (PERF401 em
  `services/fauna_tramas.py`, SIM115 em `tests/test_spec372_flags_off.py`, SIM102 em `world_utils.py`).
- Revisão terra (`handoffs/SPEC-388-terra-review.md`): P2-1/P2-2 → lista exata; P2-3 → o hook
  `ruff_after_edit.py` passa a ler `evals/protected-paths.txt` (antes só `evals/` e `web/e2e/contracts/`).
- **Etapa C (04/11):** padrão restrito a `_fold*`, `_norm` e `_norm_*` (o `_norm*` literal pegava 21
  `_normalize_*` legítimos). Allowlist só encolhe; migrar para `services.text.fold` = apagar a linha.
