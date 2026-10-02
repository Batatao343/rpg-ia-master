# SPEC-164 — Atualizar AGENTS.md para specs, evals, index e model routing

> **Status:** `draft`
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

- [ ] não duplica documentação especializada;
- [ ] agente sabe onde achar spec ativa/model policy/index/evals;
- [ ] nenhum texto implica long-run automático;
- [ ] reviewer Sol aprovou ou spec permanece `review-pending`;
- [ ] AGENTS não permite ao executor autoaprovar revisão independente.
