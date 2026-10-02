# SPEC-167 — Deterministic Eval Harness

> **Status:** `draft`
> **Depende de:** SPEC-166 `done`
> **Modelo executor mínimo:** Terra High
> **Revisão obrigatória:** Sol

## Objetivo

Construir runner/registry/report comum, reaproveitando `playtest/` e testes existentes, sem criar um segundo ecossistema duplicado.

## Entregas

- CLI de eval;
- case/result schema implementado;
- registry de métricas;
- manifest/hashes;
- per-case diagnostics;
- baseline comparison compatibility checks;
- adapters para invariantes/fixtures existentes.

## Model routing

Luna pode gerar fixtures derivadas e reportar runs. Terra implementa core. Sol revisa fronteiras do harness e garante que expected não é calculado pela implementação sob teste.

## Aceite

- [ ] roda sem API key;
- [ ] hard fail => exit non-zero;
- [ ] relatório traz SHA/dataset/evaluator version;
- [ ] known-good/known-bad cobrem runner;
- [ ] revisão Sol aprovada.
