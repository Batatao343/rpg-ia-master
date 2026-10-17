# SPEC-215 — handoff de autoria de eval (`npc_knowledge`)

`evals/` NÃO foi editado (protegido pela governança SPEC-165). Este arquivo é a
especificação para a tarefa separada de autoria do dataset `npc_knowledge` e dos
oráculos `knowledge_teleport` / `knowledge_leak`. Até lá, os mesmos oráculos
existem como testes pytest (ver §4) e como invariantes do playtest
(`knowledge.teleport`, `knowledge.rumor_promoted`, severidade `error`).

> SPEC-215 NÃO faz bump de `SCHEMA_VERSION` (regra da onda; o caso protegido
> `state.persistence.migration-idempotent` segue em 8). O ledger é aditivo:
> save sem as chaves carrega com ledger vazio + `legacy_knowledge=true`.

## 1. Superfície a medir (adapter)

- Entrada: `GameState` fixture + sequência de passos `{action: "event"|"advance_clock"|"reload"|"player_says", ...}`.
- Executor determinístico: `services.npc_knowledge.turn_updates(state)` por turno,
  `deliver_due(state, clock)` ao avançar relógio, round-trip
  `persistence._state_to_save_data` → `_raw_to_state` no passo `reload`.
- Observável: `services.context_builder.build_context_pack(state, query,
  purpose="npc", npc_id=...)` → `world_state_block`/`memory_block` (texto do
  prompt do NPC) com `RPG_NPC_KNOWLEDGE=off|on`. RAG com leitores fixos (sem embeddings).
- Probabilidade: casos de propagação devem fixar `SUBJECT_PARAMS` com p=1.0 (o
  sorteio seeded continua determinístico; p real é `[BALANCEAR]`).

## 2. Casos sugeridos (`npc_knowledge.*`)

Mapa real: brekmar -3-> ophidia; nova_arcadia -2-> brekmar; clock = day*5+período.

| id | cenário | expected (`on`) | baseline `off` |
|---|---|---|---|
| testemunha-morte | `npc_killed` em brekmar, NPC A em cena | pack de A contém `[VIU]` + nome do morto + `: morto` | contém (onisciente) |
| distante-desconhece | idem; NPC B em ophidia, clock = origem | pack de B sem nome do morto e sem "morto" | **falha esperada** (contém) |
| mensageiro-antes-due | B, clock = due-1 | sem o fato | falha esperada |
| mensageiro-depois-due | B, clock = due | `[OUVIU DE viajantes de Brekmar]` + fato | contém |
| reload-nao-antecipa | B, reload no clock due-1 | sem o fato; fila preservada | falha esperada |
| mentira-acreditada | `npc_claim` falso dito em cena a C | C tem `[BOATO, não confirmado]`; `memory_facts[*].confidence` inalterado; nenhum `GameEvent`; nada em `revealed_facts` | — |
| jogador-conta-rel5 | jogador conhece evento (crônica) e conta a D (rel 5) | `told_to` sem `believed_by`; linha `[BOATO …]` | — |
| jogador-conta-rel6 | idem, rel 6 | `told_to`+`believed_by`; linha `[OUVIU DE o viajante]` | — |
| jogador-inventa | jogador fala de evento que NÃO conhece | nenhum link, nenhum fato | — |
| segredo-nao-propaga | `npc_claim` com assinatura `rede_carmesim` | sem link, sem fila, ausente do pack de qualquer NPC | — |
| save-legado | save v8 sem ledger com eventos antigos | `legacy_knowledge=true`; zero links/fila após turno | — |
| spoiler-nao-sai | `/game/state`, codex, `visible_npc_view` | nenhuma chave `knowledge_*`/`location_heard` | idem |
| limite-8 | 12 testemunhos | ≤ 8 linhas `[VIU]`; `total_tokens_est ≤ 3675` | — |

Identidade (pedido "Halveth" do prompt 12): usar NPC genérico com `aliases`;
`holder_id` por alias == por nome == por id (`npc:<id>`).

## 3. Oráculos

- `knowledge_teleport`: para todo link com `origin_location_id`/`origin_clock`/
  `location_id`: `acquired_clock ≥ origin_clock + travel_periods(origin, location)`.
- `knowledge_leak`: texto do pack de NPC sem relação não contém nome do alvo do
  evento nem o status "morto"; nenhum texto com assinatura hidden/secret não
  revelada (`find_strict_unrevealed`) no pack de nenhum NPC.
- `rumor_promoted` (estado): nenhum `memory_fact` `npc_claim|inference` com
  `confidence=confirmed`, `memory_id` ∈ event_log ou ∈ revealed_facts.

Métricas: `teleport_count=0`, `leak_count=0`, `rumor_promoted_count=0` com `on`;
`off` documentado como baseline (falha nos casos de teleporte/distância).

## 4. Equivalentes já em pytest (não substituem o dataset travado)

`tests/test_npc_knowledge.py`, `tests/test_context_npc_gate.py`,
`tests/test_npc_knowledge_migration.py`, `tests/test_api_npc_knowledge_private.py`,
`tests/test_world_distance.py`.
