# SPEC-180 — inventário CLASSIFY e decisão de rollout

Data: 2026-10-07. Evidência: SPEC-178 e SPEC-179; ambas são de
desenvolvimento/regressão, sem holdout privado. Nenhuma nova chamada externa
foi feita nesta spec.

## Inventário de source

Busca: `rg -n 'tier=ModelTier.CLASSIFY' agents` no HEAD de partida (SPEC-179).
Foram encontrados **cinco** callsites reais. `llm_setup.py`, playtest e testes
referenciam o tier para configuração/instrumentação; não são callsites de
decisão de gameplay.

| Callsite | Contract | Jev-fit / bucket | Evidência e delta de qualidade | p95 backend A → B | Custo observado | Decisão |
|---|---|---|---|---|---|---|
| `agents/router.py:167` — rota | `RouterDecision.route` enum de cinco opções | `bounded_decision`, mas o DTO completo é misto | SPEC-178: A 48/48, B 46/48 nas três réplicas; **−2** casos B. `FALO COM CORVO` virou combate em duas réplicas. | 1.607,45 → 319,65 ms | indisponível | **NO_GO** para promoção; modo `off` padrão |
| Mesmo callsite — alvo | `target` textual, identidade canônica e presença na cena | `bounded_with_dynamic_candidates`; limite experimental 20, sem truncar | SPEC-179: A 5/8, B 6/8 representáveis; **+1 líquido**, mas B perde dois acertos de A (`alias`, `enemy`). 2/10 não representáveis. | 1.716,8 → 630,2 ms | indisponível | Sem migração; fallback CLASSIFY |
| Mesmo callsite — loot | `loot_context` em `{TREASURE,SHOP,CRAFT,none}` | `bounded_decision` | SPEC-179: A 4/4, B 4/4; corpus pequeno, sem teste do DTO combinado | 1.675,8 → 504,8 ms | indisponível | Sem migração isolada do router |
| `agents/combat.py:167` | `EncounterScanner`: nomes/quantidades de inimigos e flavor livre | `mixed/free_form` | Sem corpus/oráculo A/B por callsite | não medido | não medido | CLASSIFY atual |
| `agents/combat.py:409` | `PlayerMove`: kind/manobra/direção fechados + IDs dinâmicos de carta, item e alvo | `bounded_with_dynamic_candidates` | Sem corpus/oráculo A/B por callsite | não medido | não medido | CLASSIFY atual |
| `agents/librarian.py:48` | `EntityMatch`: booleano + ID de lista dinâmica após pré-filtro Python | `bounded_with_dynamic_candidates` | Sem corpus/oráculo A/B por callsite | não medido | não medido | CLASSIFY atual |
| `agents/loot.py:80` | `TradeIntent.mode`, `qty` e **`item_ref` livre** | `mixed/free_form` | Sem decomposição equivalente nem corpus/oráculo próprio | não medido | não medido | CLASSIFY atual; não converter `item_ref` em Choice |

As latências de SPEC-179 acima são p95 da tentativa A e do provider B nas
amostras representáveis, calculadas do raw final. São estimativas pequenas e
não representam p95 de produção. Custo real é `unavailable` nos dois runs;
reserva de budget não é cobrança.

## Regra pré-declarada e decisão

**NO_GO**. A regra da spec veta promoção diante de qualquer regressão pareada
sem fallback seguro: a rota B perde dois acertos de A e o alvo B perde dois
acertos de A. O ganho de latência observado não compensa esse gate. Além
disso, o custo real não foi informado, então não é possível demonstrar que a
outra dimensão operacional piorou no máximo 10%. Não há alegação de
generalização nem limiar calibrado para `primary`.

Mesmo antes de aplicar um limiar de confiança, o rollout primário
implementado só representaria `storyteller`/`none`: no raw da SPEC-178 são
**2/16 elegíveis (12,5%) em cada réplica**, abaixo do gate de 80%. A flag
de ambiente sozinha jamais contorna `PRIMARY_CALIBRATION=None`.

## Implementação reversível

`services/jev_rollout.py` integra Jev somente ao router, após gates Python de
combate ativo, recovery e viagem. A pergunta de rota reproduz o contrato
experimental da SPEC-178; apenas `DecisionState` mínimo cruza a fronteira da
TypeSafe. Nenhum save/schema ou outro callsite CLASSIFY foi alterado.

- `RPG_JEV_ROUTER_MODE=off` (padrão): CLASSIFY atual; zero chamada Jev.
- `shadow`: Jev observa o turno, mas não fornece rota nem altera GameState.
  Falha, timeout e configuração ausente não mudam o resultado. **Opt-in de
  custo/latência**, com deadline total de 2 s; sem orçamento de chamadas live
  nesta spec. A execução síncrona acrescenta uma chamada; 2 s é o deadline
  interno do adapter, além do pequeno overhead de construção/fechamento do
  cliente e do hook.
- `primary`: exige também `RPG_JEV_ROUTER_PRIMARY_APPROVED=1` e
  `PRIMARY_CALIBRATION` congelado em código com ID de evidência e limiar
  revisados. **Hoje `PRIMARY_CALIBRATION=None`** após NO_GO; qualquer tentativa
  de ativar `primary` usa CLASSIFY sem chamar Jev. Após uma tarefa futura
  aprovada que preencha o gate, erro/timeout/resposta inválida,
  confiança abaixo do limiar e escolhas que precisariam de target/loot livre
  caem para CLASSIFY. Somente `storyteller`/`none` confiantes cabem no
  contrato atualmente; `none` normaliza para `storyteller`. O limiar **não foi
  calibrado**: habilitar primary em produção requer tarefa de eval-authoring
  separada e aprovação explícita de promoção. Testes do caminho hipotético
  usam backend simulado e monkeypatch do gate em memória.
- Rollback: mudar modo para `off` no ambiente. Não há migração de dados nem
  recomputação de saves. A mudança de env em um processo já iniciado depende
  do gerenciador de configuração/deploy; o código lê o modo a cada decisão.

O adapter conserva timeout total, idempotência e validação de Choice. O hook
`set_jev_rollout_telemetry_hook` expõe modo, outcome, escolha, confiança,
modelo, latência, tokens e custo quando reportado, sem prompt/chave; é o ponto de integração
para o usage metering da SPEC-182. Jev é backend de decisão, **não** entra em
`ModelTier` como LLM/chat provider.

## Verificação

- Testes de `off`, `shadow`, `primary` manual, fallback por erro/timeout,
  confiança e não representável, idempotência, precedência de gate Python,
  rollback e ausência de mutação de GameState: `tests/test_jev_rollout.py`.
- A regressão protegida permanece byte-identical; nenhuma expected, corpus,
  evaluator, denominador ou baseline foi ajustado.
- Sem long-run e sem chamada externa nesta spec.
- `uv run python -m evals.core.governance check`: seis datasets válidos.
- Smoke real local com `RPG_FORCE_MOCK=1` e modo `off`: `dm_router_node`
  devolveu `npc_actor` para uma fala social, sem tocar Jev.
- O primeiro full pytest encontrou apenas dois testes do Project Index gerado
  stale após adicionar o serviço. Regenerado do source canônico; os sete
  testes focados de índice e `project_index check` passaram.

Suíte completa final: **1.964 passed, 35 skipped, 15 deselected**, 1 warning,
209,89 s. Revisão Sol High independente: **APPROVED técnico local**,
`SPEC-180-SOL-b25bed2-final-01`;
`handoffs/SPEC-180-SOL-independent-review.md`. O revisor confirmou o inventário,
a decisão `NO_GO`, os p95, fallback e ausência de promoção.
