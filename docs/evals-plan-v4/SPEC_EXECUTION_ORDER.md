# Ordem oficial das novas specs

As novas specs deste pacote começam em **SPEC-163**. Os IDs 001–162 serão atribuídos retrospectivamente pela SPEC-163 a partir do histórico Git atual. A ordem abaixo é rígida para esta migração.

| Ordem | Spec | Modelo executor mínimo | Revisão obrigatória |
|---:|---|---|---|
| 1 | SPEC-163 — normalização histórica das specs | Terra High; Luna para inventário/metadata | — |
| 2 | SPEC-164 — contrato AGENTS.md + model routing | Terra High | Sol |
| 3 | SPEC-165 — eval governance | Sol High | **Astra** |
| 4 | SPEC-166 — project index core | Terra High | Sol |
| 5 | SPEC-167 — deterministic eval harness | Terra High | Sol |
| 6 | SPEC-168 — state/rules evals | Terra High | por escalada |
| 7 | SPEC-169 — routing/action evals | Terra High | por escalada |
| 8 | SPEC-170 — memory/RAG/context evals | Sol High | **Astra** |
| 9 | SPEC-171 — narrative/NPC evals | Sol High | **Astra** |
| 10 | SPEC-172 — frontend evals | Terra High | por escalada |
| 11 | SPEC-173 — CI/gates | Terra Medium/High | Sol se security/gate semantics mudar |
| 12 | SPEC-174 — baseline-v1 | Luna para execução/reporting; Terra só para harness bug | — |
| 13 | SPEC-175 — A/B project-index | Terra High; Luna para agregação mecânica | Sol |

## Regra de avanço

Não iniciar a próxima spec até a atual estar:

```text
implemented
+ required deterministic gates green
+ required model review complete (when applicable)
+ docs/index updated
+ status = done
```

Exceção: nenhuma. Se a revisão requerida não puder ser executada, marcar `review-pending` e parar a sequência.

## Depois da SPEC-175

Não existe SPEC-176 pré-reservada. A próxima spec recebe o próximo ID quando houver um objetivo real derivado da baseline/benchmark. Não inventar target antes de medir.

## Long-run

Long-run não aparece nesta sequência. Só roda por solicitação explícita do usuário ou por uma futura spec de horizonte longo explicitamente aprovada.
