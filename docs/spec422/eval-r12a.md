# SPEC-422 R12(a): `memory_context` off x on (22/11, MockLLM, mesma maquina)

`uv run python -m evals --root . run --dataset datasets/regression/memory_context.jsonl --run-id spec422-{off,on}`
com `RPG_ARCHIVE_RECORD=off` e `=on`; `compare --baseline spec422-off --current spec422-on`: exit 0,
`regressions: []`, `passed: true`, todas as metricas identicas (recall@5 1.0, mrr 0.833, write_precision 1.0,
secret_leak 0.0). Governanca (`governance check`): valida.

Limite (R12): o dataset nao exercita o arquivista (testa `validate_memory_fact`, ranking e contexto a
partir de estado pronto), entao a igualdade e esperada por construcao e NAO prova T1. A promocao a `on`
segue dependendo da suite de autoria de eval (`EVAL_AUTHORING_REQUIRED`), fora desta entrega.
