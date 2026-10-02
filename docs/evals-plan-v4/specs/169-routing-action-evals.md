# SPEC-169 — Routing e Action Interpretation Evals

> **Status:** `draft`
> **Depende de:** SPEC-168 `done`
> **Modelo executor mínimo:** Terra High
> **Revisão:** por escalada

## Objetivo

Medir route/intent/target e contratos estruturados independentemente da prosa gerada.

## Entregas

- corpus fechado de ações;
- confusion matrix;
- route accuracy;
- intent/target exact or set match;
- negative/metamorphic cases;
- structured-output failure diagnostics.

## Model routing

Luna pode auxiliar na expansão mecânica de variantes somente depois de categorias/expected serem definidos. Terra implementa corpus/evaluator. Sol só entra quando semântica de ação exige redefinir taxonomia.

## Aceite

- [ ] evaluator não chama router para gerar expected;
- [ ] corpus registra origem/racional;
- [ ] metamorphic variants preservam expected quando apropriado;
- [ ] nenhuma narrativa final entra no score.
