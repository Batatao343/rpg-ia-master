# SPEC-179 — Jev para target e loot_context dinâmicos

> **Status:** `draft`
> **Depende de:** SPEC-178 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: agregação de métricas e inventário read-only de candidatos após regras canônicas estarem definidas.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-179` é source of truth para subtarefas/review focus

## Objetivo

Testar se `RouterDecision` pode ser decomposto em decisões fechadas sem perder resolução canônica de alvo/loot context.

## Requisitos

- **R1 — IDs canônicos:** target é Choice entre IDs realmente válidos na cena + `unknown` + `none`; display name não é autoridade.
- **R2 — candidatos:** derivar de `npc_layers.npcs_in_scene`, inimigos/atores canônicos e source real. Não usar Project Index como fonte de opções.
- **R3 — loot_context:** Choice `{TREASURE, SHOP, CRAFT, none}`.
- **R4 — cardinalidade:** validar limite atual da API; se excedido, marcar `unrepresentable`, nunca truncar silenciosamente.
- **R5 — aliases:** normalizar aliases para canonical ID antes do score.
- **R6 — benchmark/corpus:** reutilizar casos protegidos quando suficientes. Para gaps de target/loot, criar corpus **experimental** derivado de contratos/source e congelar hash/commit **antes da primeira chamada Jev**. Esse corpus não vira regression automaticamente; promoção para regression exige eval-authoring separado.
- **R7 — scoring:** target/loot_context avaliados somente quando semanticamente elegíveis.
- **R8 — segurança:** opções não podem revelar NPC secreto/fora da cena.
- **R9 — experimento:** usar runner/artefatos de `evals/experiments/`, sem tocar na régua protegida.
- **R10 — nenhuma promoção:** produção continua inalterada.

## Critérios de aceite

- [ ] nenhum target fora do conjunto canônico pode sair do adapter;
- [ ] target e loot_context têm métricas separadas;
- [ ] opções dinâmicas não vazam segredo/fora-da-cena;
- [ ] não representáveis aparecem no denominador/relatório apropriado;
- [ ] paths protegidos intactos;
- [ ] nenhuma mudança de produção.

## Casos mínimos do corpus experimental (congelados antes de live call)

- zero candidato; um NPC; múltiplos NPCs; alias -> canonical id;
- NPC fora da cena e NPC secreto não podem aparecer nas opções;
- inimigo canônico elegível;
- `TREASURE`, `SHOP`, `CRAFT`, `none`;
- mais de 20 targets válidos => `unrepresentable` + fallback, sem truncamento;
- input ambíguo/unknown.

## Gate de fechamento

- [ ] hash do corpus experimental é registrado antes da primeira chamada Jev;
- [ ] nenhum resultado Jev é usado para editar expected/opções do mesmo experimento;
- [ ] invalid/secret/out-of-scene target count = 0;
- [ ] >20 candidates é tratado como `unrepresentable`, nunca seleção parcial;
- [ ] produção permanece inalterada e revisão Sol independente aprova.
