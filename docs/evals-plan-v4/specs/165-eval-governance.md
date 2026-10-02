# SPEC-165 — Eval governance, schemas e integridade da régua

> **Status:** `draft`
> **Depende de:** SPEC-164 `done`
> **Modelo executor mínimo:** Sol High
> **Revisão obrigatória:** **Astra**

## Objetivo

Definir a fronteira que impede o optimizer de alterar a régua junto com o produto.

## Escopo

- case/result schemas;
- metrics registry;
- evaluator version;
- dataset hashes;
- protected paths;
- baseline compatibility;
- experiment log;
- dev/regression/private holdout policy;
- regras para LLM-as-judge.

## Fora de escopo

Gameplay, prompts, embeddings ou melhoria de score.

## Revisão Astra

Astra revisa somente semantics/governance, não reimplementa. Perguntas obrigatórias: há leakage? Goodhart risk? denominador manipulável? evaluator depende da implementação sob teste? holdout está realmente separado? judge pode substituir oráculo determinístico?

## Aceite

- [ ] runner falha fechado em dataset/evaluator incompatível;
- [ ] protected paths detectados;
- [ ] known-good/known-bad para evaluator;
- [ ] Astra review `approved` registrada;
- [ ] nenhuma métrica subjetiva blocking sem calibração.
