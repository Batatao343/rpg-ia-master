# SPEC-177 — revisão Sol independente da correção TypeSafe

Data: 2026-10-05. Revisor: `/root/spec176_reviewer`, Sol High, read-only.
Decisão: **APPROVED técnico local** para a correção offline; live permanece
bloqueado até o usuário revogar/substituir a chave enviada ao host errado.

## Evidência

- Endpoint, contrato Score (`legend`, `probabilities`) e retry 429/529 conferidos
  na [API oficial TypeSafe](https://docs.typesafe.ai/api).
- 37 testes focados verdes; Ruff verde. Respostas Choice/Score incompatíveis,
  distribuições inválidas, média ponderada incoerente e Choice fora do argmax
  são rejeitados.
- `JEVMODEL_API_KEY` funciona como alias local; chaves divergentes falham
  fechado. Nenhum segredo foi exibido na revisão.
- Diff de `agents/router.py`, `llm_setup.py` e evals protegidos vazio.
- Preflight do corpus protegido preserva 21 casos route, 16 elegíveis, 5 gates
  e o hash aprovado.
- Runner `--max-calls 98 --max-cost-usd 0.98` respeita o saldo autorizado de
  chamadas. A reserva monetária não garante gasto real desconhecido.

Hashes do snapshot revisado:

- `services/jev_decision.py`: `8a47af4b2f0a1b3c12a2dc4645aa05a64238f0e8a379dc97b3a6fa4f550f8b8d`
- `tests/test_jev_decision_backend.py`: `ad2cc7dd871569b2c0ee9b5c8c06c651a0d26a4798ace80ae601c63970c6bce5`
- `tests/fixtures/jev_decision_success.json`: `bd5a5ad8d30817e390a1d413769b3d60515a8072c580df0ef34cff00325632c3`
- `evals/experiments/jev_router_ab.py`: `e4eb34856cfcb5401945821b65ec9cbf6b9e7263ef9a461e6716b3c1f41f9384`

O revisor também apontou que `SPEC-177` declarava incorretamente que a chave
não foi exposta. O texto foi corrigido: a chave TypeSafe foi enviada uma vez
como Bearer a `jevmodel.org`, domínio diferente, e o usuário foi notificado.
Nenhum POST de provider foi feito pelo revisor.
