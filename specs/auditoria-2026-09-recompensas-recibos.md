# SPEC — Recompensas elegíveis e contagem canônica

> **Status:** `in-progress`
> **Criada:** 2026-09-22 · **Atualizada:** 2026-09-26
> **Aprovação:** usuário pediu “transforma tudo em specs e começa a executar”.
> **Depende de:** Nenhuma
> **Desbloqueia:** fechamento da auditoria de consistência e frontend.

## 1. Contexto & Objetivo

A reprodução concedeu 150 XP com campaign_plan vazio, duplicou art_adaga_vidro_dragao em um lote e omitiu do recibo uma segunda unidade não empilhável. Correções determinísticas devem preceder qualquer campanha longa.

## 2. Requisitos

- **R1** — XP de beat somente quando há beat corrente válido, ainda não concluído, efetivamente avançado; sem prêmio no prólogo. Plano vazio/esgotado ou current_step negativo não premia.
- **R2** — Item unique concedido no máximo uma vez por lote, incluindo aliases nome/ID; conferir inventário atual e projeção. Não confundir alias duplicado com recusa da concessão válida.
- **R3** — Recibo soma todas as entradas de mesmo ID, empilháveis ou não; ignora entradas sem ID e quantidades não positivas.
- **R4** — Não mutar estado de entrada; manter ganhos válidos, eventos únicos e recibo idempotente. Sem adicionar prêmio por texto.
- **R5** — Nomes válidos do catálogo não constituem autorização ilimitada: evolução futura para concessões vinculadas a fonte ocorre na spec de evidências, não escondida neste patch.

### Fora de escopo

Deploy, migração de dados reais, nova campanha paga e mudança de provider. Implementar Python para domínio/infra; TypeScript apenas para interface.

## 3. Design técnico

agents/storyteller.py: calcular elegibilidade do beat antes de grant_xp e reutilizar a mesma decisão para avançar plano; resolver itens antes da deduplicação de unique, considerando inventário atualizado. services/turn_outcome.py: Counter acumulativo, não dict comprehension. Formato persistido do recibo inalterado; usar fixtures já existentes, sem lore novo.

## 4. Plano passo a passo

1. tests/test_audit_reward_contracts.py: plano vazio/esgotado/done/negativo/prólogo, controle válido; unique por nome/ID/aliases e já possuído.
2. Testar baseline → aquisição de segunda arma → recibo +1; quantidades, zero/negativas, replay e input intacto.
3. Implementar mínima correção em Python; testar integração storyteller → processor/finalizer e save/load.
4. Suite offline + smoke de grafo mock; provider real dirigido separado.

## 5. Critérios de aceite

- [x] R1–R4 cobertos e implementados.
- [ ] Suíte offline e smoke determinístico verdes; compatibilidade preservada.
- [ ] Smoke real dirigido do storyteller executado sem regressão.

## 6. Smoke test com LLM real / integração aplicável

Uma conclusão real de beat e uma aquisição real (2–3 turnos), com orçamento autorizado. Não necessário para desenvolver/testar regras locais, obrigatório antes de done desta integração.

## 7. Riscos & compatibilidade

Não rebalancear XP nem mudar política inteira de loot neste lote. Duplicatas de unique existentes em saves não são apagadas silenciosamente; remediação futura precisa política própria.

## Execução — 23/09

Elegibilidade do beat compartilhada entre avanço e XP; unique deduplicado pelo ID resolvido e conferido contra inventário/projeção; Counter do recibo agora acumula entradas repetidas positivas. **15 casos novos** em `tests/test_audit_reward_contracts.py`, incluindo replay, input intacto e serialização. Suíte completa: **1743 passed, 18 skipped, 14 deselected**. Suíte focada conjunta com contexto/grounding/MVP: **57 passed**.

Pendente: smoke dedicado de grafo e smoke dirigido com provider real. Nenhuma chamada paga foi feita; esta validação offline não fecha o aceite real. Concessões narrativas vinculadas a evidência continuam na spec de consistência narrativa.

## Execução — 26/09 (prevalece sobre as pendências históricas)

Regras determinísticas seguem validadas na suíte completa. Nenhum smoke dirigido pago foi executado; ainda falta o smoke dedicado storyteller→finalizer. Não houve rebalanceamento nem remoção de duplicatas em saves existentes.
