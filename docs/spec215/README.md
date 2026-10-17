# SPEC-215 — evidência (conhecimento por NPC e propagação limitada)

**Data:** 2026-10-16 · **Flag:** `RPG_NPC_KNOWLEDGE=off|shadow|on` (default `off`).

## O que mudou

- `services/npc_knowledge.py` (novo, owner único): ledger privado de relações
  `observed_by`/`told_to`/`believed_by` sobre `event_id`/`memory_id`; testemunhas
  (NPCs em cena + party ativa presente), propagação seeded
  `sha256(game_id|subject|from|to|hop)`, atraso = distância + `1 + seed%3`,
  ≤ 2 saltos, raio por tipo, ≤ 4 destinos/hop (locais com NPC primeiro), tetos
  2000 links / 200 fila / 100 por local; herança local (R10); jogador conta (R9,
  limiar de relação 6); `knowledge_lines` (≤ 8, rotuladas `[VIU]`/`[OUVIU DE …]`/
  `[BOATO, não confirmado]`); `context_gate` com fail-closed.
- `services/world_distance.py` (novo): Dijkstra cacheado sobre a regra de `travel_cost`.
- `services/context_builder.py`: `collect_dynamic_facts(..., knowledge_filter)`; com
  `on` para `purpose="npc"`, eventos/segredos revelados só entram rotulados pelo
  ledger, "morto" só para quem sabe, e resumo/ledger/memória de sessão do jogador
  saem (D2). `shadow` loga `rpg.npc_knowledge` (known/filtered) sem mudar o pack.
- `agents/npc.py`: R9/R10 antes do invoke; texto "verdade de AGORA" vira "só o que
  você sabe" apenas com `on`; devolve `knowledge_links`.
- `agents/turn_finalizer.py`: ponto único por turno (`turn_updates`): testemunhas +
  agendamento dos assuntos **do turno** + entrega do que venceu (cobre viagem,
  descanso e fuga). Erro interno é logado; o turno segue.
- `state.py`/`persistence.py`: `KnowledgeLink`, `KnowledgeDelivery`, 4 campos
  **aditivos sem bump** (`SCHEMA_VERSION` fica 8, regra da onda). Save sem as chaves
  → ledger vazio + `legacy_knowledge=true`.
- `playtest/invariants.py`: `knowledge.teleport` e `knowledge.rumor_promoted` (`error`).
- `handoffs/SPEC-215-eval-authoring.md`: dataset `npc_knowledge` + oráculos (evals/ protegido).

## Testes

51 novos: `test_npc_knowledge.py` (27), `test_context_npc_gate.py` (11),
`test_npc_knowledge_migration.py` (5), `test_api_npc_knowledge_private.py` (3),
`test_world_distance.py` (5) + fixture `tests/fixtures/spec215_npc_pack_off.txt`
(pack de NPC capturado do HEAD **antes** da mudança — `off` é comparado byte a byte).
Diff de prompt antes/depois (testemunha × distante): [prompt_diff.md](prompt_diff.md).

## Smokes

| run | modo | resultado |
|---|---|---|
| `20261016-213232-747485` | offline `--all --turns 30`, `on` | 14×30, 0 erro, 0 violação; saves: 52 links (48 witness, 4 local_rumor; 28 told_to/24 believed_by), 45 entregas pendentes, 41 assuntos ouvidos por local |
| `20261016-213409-485282` | offline `--all --turns 30`, `shadow` | 14×30, 0 erro, 0 violação; mesmo ledger (shadow registra), prompt inalterado |
| `20261016-213749-354935` | **real** DeepSeek, `diplomatico` 8 turnos, `on` | 8/8, 0 erro/violação, `mock=false`, 29 requests, US$ 0,00812 (teto 0,05); rumores entregues a 4 locais |

Cenário dirigido (morte em Brekmar, NPC em Ophidia a 3 períodos, antes/depois do
`due_clock`): `test_context_npc_gate.py::test_directed_distant_city_before_and_after_due`.

## Limites / desvios

- SPEC-214 fechou `NO_GO` (`docs/spec214/gate.md`): sem cache de cena; a 214 era
  "recomendada", não obrigatória. Nada desta spec depende dela.
- Sem bump de schema (spec previa 8→9): campos aditivos + normalização idempotente.
- Witness/agendamento rodam no `turn_finalizer` (não no `event_processor`): eventos
  do turno são identificados por `event.turn == world.turn_count`, o que também
  garante a não-retroatividade (R13) sem cursor. Idempotente por `link_id`/`delivery_id`.
- Segredo (R7) é mais estrito que a spec: texto com assinatura não revelada nunca
  entra no prompt de NPC algum, nem do observador direto (o link existe; o conteúdo não).
- Rumor = `memory_fact` `npc_claim`/`inference` do turno; como toda conversa com NPC
  gera um `npc_claim`, o volume de rumor é dominado por registros de diálogo
  (p=0,35, raio 5, 1 salto) — ajustar em `shadow` (D3).
- Dataset `npc_knowledge` e revisão Astra independente: pendentes (tarefa separada).
