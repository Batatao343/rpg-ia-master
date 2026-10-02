# SPEC-165 — Eval governance, schemas e integridade da régua

> **Status:** `done`
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

- [x] runner falha fechado em dataset/evaluator incompatível;
- [x] protected paths detectados;
- [x] known-good/known-bad para evaluator;
- [x] Astra review `approved` registrada;
- [x] nenhuma métrica subjetiva blocking sem calibração.

## Execução — 2026-09-28

- Execução no contexto ativo `gpt-6`, acima do mínimo Sol; custo de roteamento
  não otimizado registrado conforme política.
- Nenhuma alteração de gameplay, prompts, embeddings ou score autorizada.
- Entregas: schemas Pydantic + JSON gerado; manifesto SHA-256; registry com
  unidade/numerador/denominador/exclusões; compatibilidade de baseline; detecção
  de paths protegidos; evaluator exato independente; política pública/private
  holdout e template de experimento.
- Gates: `uv run python -m evals.core.governance check --root .` verde; 12 testes
  focados e Ruff verdes, sem provider.
- `MODEL_HANDOFF_REQUIRED: gpt-6-astra`; revisão independente solicitada.
- Primeira revisão Astra `SPEC-165-ASTRA-20260928-01`: `CHANGES_REQUESTED` por
  quatro bloqueadores demonstrados adversarialmente: identidade incompleta da
  régua, proteção autorremovível/case-sensitive, judge autocalibrável e igualdade
  Python `true == 1`. Correções implementadas; re-review pendente.
- Segunda revisão Astra `SPEC-165-ASTRA-20260928-02`: `CHANGES_REQUESTED`; o hash
  da seleção não estava vinculado aos casos elegíveis e regras em `evals/core`
  ficavam fora da identidade. Corrigido com hash canônico validado no resultado e
  bundle congelado de `core + evaluators`. Novo re-review pendente.
- Terceira revisão Astra `SPEC-165-ASTRA-20260928-03`: `APPROVED`, sem achado
  bloqueante restante; revisão confirmou os cenários adversariais offline.
- Gate final: **1825 passed, 35 skipped, 15 deselected**, zero falha; governance
  check e Ruff verdes, sem provider ou long-run.
