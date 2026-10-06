# SPEC-178 — revisão Sol High independente

Data: 2026-10-05. Revisor: `/root/spec176_reviewer`, Sol High, contexto
independente do executor. Escopo: runner e testes em `evals/experiments/` e
`tests/test_jev_router_ab_experiment.py`; nenhuma chamada externa ou edição.

## Resultado

**APPROVED técnico local para a implementação offline.** O revisor executou
independentemente os testes focados: **8 passed**, exit 0. Hashes do código
revisado: runner SHA-256 `812d0b09f275c18aa0df3476cc30feef81b3ae415f59bdf0749b02710b68a245`;
testes SHA-256 `bc36711ffa0644dc5e3916c9317f551fbf2d77855a18258e2ba32224b9fcdf4c`.
O revisor reconfirmou `APPROVED` para o hash atual após a remoção de um
parâmetro `monkeypatch` não usado no teste.

O revisor confirmou input do candidato sem `expected`/`oracle`, elegibilidade
por instrumentação, ordem pareada sem seleção pós-score, raw persistido antes
do score, erro/usage/latência por caso e nenhum diff em `agents/router.py`,
`llm_setup.py` ou paths protegidos da régua.

## Achados resolvidos durante a revisão

- O sanity A agora aborta por auth/quota/config, inclusive `build_error`.
- Usage raw do CLASSIFY é preservado quando o provider o reporta.
- A e B medem a latência do wrapper completo.
- Budget excedido retém attempts/latência/modelo/usage observados.
- O teste simulado passou a refletir o campo de sanity obrigatório.

## Limite da aprovação

Esta aprovação cobre código e protocolo offline. **Não aprova resultado A/B**:
a chamada Jev anterior retornou HTTP 401, não houve três réplicas completas
nem score. O teto de chamadas é efetivo antes da rede; o teto em USD usa custo
reportado e uma reserva de parada, e não garante gasto real desconhecido. A
SPEC-178 permanece `blocked-by-provider`; após credencial válida e run completo,
o revisor precisa inspecionar os artifacts e a conclusão de score novamente.
