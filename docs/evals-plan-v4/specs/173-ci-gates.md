# SPEC-173 — CI, Protected Gates e Execução Seletiva

> **Status:** `draft`
> **Depende de:** SPEC-172 `done`
> **Modelo executor mínimo:** Terra Medium/High
> **Revisão:** Sol se a semântica de segurança/protected paths mudar

## Entregas

- PR deterministic gate;
- path-selective backend/frontend evals;
- holdout privado fora do repo público;
- real-provider short gate manual/protected;
- artifacts para debugging;
- post-deploy smoke parametrizado.

## Proibição

Nenhum workflow automático executa 100/200-turn ou matriz 10x200.

## Model routing

Luna pode gerar reports/artifact indexes. Terra implementa workflows. Se protected-path bypass, secrets, permissions ou trust boundary forem alterados, revisão Sol obrigatória.

## Aceite

- [ ] long-run ausente dos required gates;
- [ ] protected evaluator/datasets não podem ser silenciosamente alterados;
- [ ] failures não viram pass por unavailable dependency;
- [ ] artifacts incluem manifest compatível.
