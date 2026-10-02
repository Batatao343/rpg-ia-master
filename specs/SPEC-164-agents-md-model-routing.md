# SPEC-164 — Atualizar AGENTS.md para specs, evals, index e model routing

> **Status:** `done`
> **Depende de:** SPEC-163 `done`
> **Modelo executor mínimo:** Terra High
> **Revisão obrigatória:** Sol

## Objetivo

Transformar `AGENTS.md` no roteador operacional do novo processo sem transformá-lo em um manual gigante.

## Entregas

- ordem de retomada por `SPEC-ID`;
- leitura de `specs/index.yaml`;
- project index como mapa, source como verdade;
- eval integrity policy;
- state ownership policy;
- fluxo deterministic-first;
- long-run estritamente opt-in;
- `minimum sufficient model` com Luna/Terra/Sol/Astra;
- `MODEL_HANDOFF_REQUIRED` quando reviewer/model mínimo não estiver disponível.

## Model routing

Terra implementa a alteração textual. Luna pode verificar referências e duplicações. Sol faz revisão independente procurando conflitos com instruções existentes, escopo excessivo e ambiguidades operacionais.

## Aceite

- [x] não duplica documentação especializada;
- [x] agente sabe onde achar spec ativa/model policy/index/evals;
- [x] nenhum texto implica long-run automático;
- [x] reviewer Sol aprovou ou spec permanece `review-pending`;
- [x] AGENTS não permite ao executor autoaprovar revisão independente.

## Execução — 2026-09-28

- Implementação textual concluída no `AGENTS.md`, com referências para os
  documentos especializados do pacote v4.
- Gate determinístico em `tests/test_agents_contract.py` cobre os pontos
  operacionais obrigatórios e a política opt-in de long-run.
- `execution_model: gpt-6`, acima do mínimo da etapa; custo de roteamento não
  otimizado porque este já era o contexto ativo.
- `MODEL_HANDOFF_REQUIRED: gpt-5.6-sol` — o executor não declarou revisão
  independente. Pacote em `handoffs/SPEC-164-sol-review.md`.
- Primeira revisão Sol `SPEC-164-SOL-20260928-01`: `CHANGES_REQUESTED` porque a
  regra legada ainda permitia `specs/<nome>.md`. Corrigido para exigir o próximo
  ID nunca utilizado, filename `SPEC-NNN-<slug>.md` e registro no índice; teste
  de regressão acrescentado. Re-review independente pendente.
- Re-review independente Sol `SPEC-164-SOL-20260928-02`: `APPROVED`; demais
  eixos aprovados e riscos residuais classificados como não bloqueantes.
- Gate final: **1809 passed, 35 skipped, 15 deselected**, zero falha; nenhuma
  chamada de provider ou long-run.
