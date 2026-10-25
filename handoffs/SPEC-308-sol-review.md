# SPEC-308 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (re-revisão; a 1ª rodada, em `5a53d004`, foi `CHANGES_REQUIRED`)
> **Revisor:** Opus / Sol (revisão técnica independente, foco regra de ouro) · **Data:** 2026-10-24 · **Commit revisado:** `5a53d004` → re-revisão em `99ce47f8`

## Escopo

Branch `spec-308` (`a2c5c121..5a53d004`) contra `main`: `services/world_perception.py`
(`event_perceived`, `WORLD_EVENT_TYPES`), `context_builder.collect_dynamic_facts`,
`event_processor` (marco de crônica + `cause_event_id` na cascata), `chronicle.perceived_milestones`,
`archivist._event_memory_records`, `storyteller._perceive_world` (ledger 400),
`world_director`/`world_engine`/`world_calendar`/`npc_world` (`digest_item(event_ids=…)`),
`tests/test_spec308_filtro.py`. Também conferi R7 (API), que o executor não verificou:
`api._world_block`, `api._factions_block`, `services/map_view.py`, `services/state_views.py`,
`services/dossiers.py`. `evals/` não foi tocado.

**Oráculo próprio** (script fora do repo): eventos `source="engine"` reais (`wd._ev`) de outra
região — `faction_relation_changed` (Clãs de Combate × Tribos dos Devoradores de Sol),
`location_control_changed` em `sk_fortaleza_vorr`, `route_blocked` skallgard↔Vorr — aplicados
por `process_pending_events` (como no jogo, ou seja, **com projection**), herói em `nova_arcadia`,
dia +2, ledger vazio, Vorr em `visited`. Resultado igual com `RPG_NPC_WORLD` em `off` e em `on`:

- O texto do evento (`render_event`, "BLOQUEADA") some de todos os packs. O R4 vale para o
  **bloco de eventos**.
- **Mas o fato vaza pela projection** nos 4 packs (`story`, `npc`, `combat_narration`,
  `planning`), na seção `relations`:
  `Os Clãs de Combate —enemy_of→ As Tribos dos Devoradores de Sol` e
  `As Tribos dos Devoradores de Sol —controls→ Fortaleza de Vorr`.
- API: `world.controlled["sk_fortaleza_vorr"] = "As Tribos…"`,
  `world.map_overlays.control_changes = [{sk_fortaleza_vorr, As Tribos…}]`, dossiê do local com
  `{"outcome": "controle mudou"}` e `world.blocked_routes` com skallgard↔Vorr.
- Crônica e memória do arquivista ficaram corretas (vazias antes da percepção).

O teste `test_remote_siege_not_in_story_or_planning_context` não pega isso porque usa
`world_projection={}` e só procura "BLOQUEADA". Ele não monta o local nem a fação, e não testa
os packs `npc`/`combat_narration`. A Etapa 3 da spec pede que se confira "o local, a fação ou
a palavra do estado".

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P0-1 | P0 | `services/context_builder.py:316-335` | A seção `relations` lista **todas** as `dynamic_edges` da projection. Isso inclui as arestas `controls`/`enemy_of`/`allied_with` criadas por evento do motor não percebido (`created_by_event`, `event_processor.py:169,217`). A ocupação e a relação de fação de outra região chegam ao narrador e ao planner. É justamente o vazamento A1 que a spec existe para fechar, por outra via. Com `knowledge_filter=None` (story/combat/planning), nada filtra. | Monte um índice `event_id → ev` do `event_log` e pule a aresta cujo `created_by_event` é um evento em que `world_perception.event_perceived(state, ev)` é False (evento ausente do log e com `id` `dyn_*` de evento do motor: fail-closed). Faça o espelho em `disabled_edges`: se o evento que desativou a aresta base não foi percebido, o herói ainda "vê" o controlador antigo. Se isso for complexo demais, aceite omitir a aresta e registre o follow-up. Teste: o oráculo com `process_pending_events` (projection real), procurando o nome da fação e do local nos 4 propósitos, com `RPG_NPC_WORLD` off/on, e o fato aparecendo depois de pôr o `event_id` no ledger. |
| P1-1 | P1 | `api.py:2894` + `services/state_views.py:57-81`; `services/map_view.py:110` | `recent_control_changes` lê o `event_log` cru: `location_control_changed` do motor num local **visitado** (mas distante) aparece no overlay do mapa (`control_changes`) e como `contested` no `/data/map`. R7 pede exatamente isso ("mapa… aplicar o mesmo filtro"). | Passe `state` (ou um predicado) e pule os eventos com `event_perceived(state, ev)` False. Teste de API/`format_response`. |
| P1-2 | P1 | `services/dossiers.py:105-118` | `_events_about` filtra só pela SPEC-304. O `location_control_changed` do motor gera "controle mudou" no dossiê de um local distante. R7 cita o dossiê. | Adicione `if not event_perceived(state, dict(event)): continue` junto ao filtro da 304. |
| P1-3 | P1 | `api.py:2891` (`sv.visible_controllers`) e `api.py:2902-2906` (`blocked_routes`) | Vêm da projection ao vivo: o controlador de um local visitado muda (ou a rota com ponta visitada aparece bloqueada) no instante do tick, sem percepção. Não são `event_log`, mas "derivam de eventos do motor" (R7). | Mesma regra do P0-1: com aresta `controls` de evento não percebido, use o controlador anterior (ou omita). Na rota, filtre por `blocked_by_event` percebido. Se preferir manter o P2-2 da SPEC-302 por design, registre a decisão na spec (R7) e abra follow-up. Não deixe calado. |
| P2-1 | P2 | `services/event_processor.py:607-608` | O `elif event.get("source") == "engine"` põe `cause_event_id` nos derivados de **qualquer** evento do motor (quest, membership, law…). `_is_engine_derived` trata todo `rule_engine` com `cause_event_id` como do motor. Hoje é inócuo (as regras que emitem eventos disparam em `location_control_changed`/`npc_killed`, e `quest_completed` só faz `set_entity_state`). Mas uma regra futura em `quest_completed` (engine, SPEC-305) esconderia do herói a consequência do próprio feito. | Restrinja a `event.get("type") in world_perception.WORLD_EVENT_TYPES`. Teste: derivado de `quest_completed` engine segue visível. |
| P2-2 | P2 | `services/event_processor.py:406-416` | O `route_cleared` da conclusão de quest de mundo (SPEC-305 R13, `actor_id="player"`, feito do herói) é `source="engine"` e está em `WORLD_EVENT_TYPES`. Não tem `day` no payload nem item de digest com `event_ids`, então só é "testemunho" no próprio turno e some do contexto no turno seguinte. Se o herói concluir a quest longe da rota, nunca aparece. | Isente `actor_id == "player"` em `_is_engine_derived` ou inclua o id no ledger ao concluir. Teste. |
| P2-3 | P2 | `services/world_perception.py:227`, `services/companion_soul.py:988` | Em produção, `companion_fate` usa um `uuid4` que nunca entra em `npc_beliefs` (a crença guarda o `subject_id` = id do `npc_offscreen_fate`, `npc_world.py:1127`). Depois de percebido, ele continua oculto para sempre. Não é vazamento (`npc_fate_learned` informa), mas `test_companion_fate_decided_by_belief` prova um caminho que não acontece no jogo. | Ligue o `companion_fate` ao `fate_event_id` (`payload.cause_event_id`) ou documente que só `npc_fate_learned` dá voz. Ajuste o teste para o fluxo real. |
| P2-4 | P2 | `services/world_director.py:724,727` | Os eventos `ruin_rec`/`ruin_end` de `recovery_step` não têm item de digest e ficam ocultos para sempre (lado seguro). Idem `route_cleared` em `_close_state` sem `prev`. | Só registrar: SPEC-309 dá voz. Nenhuma correção exigida. |
| P2-5 | P2 | `services/chronicle.py:250` | `perceived_milestones` grava o marco com `turn` do **evento**. R6 diz "no turno da percepção". Além disso, ela só roda `if perceived_items`: a percepção por crença (`_npc_beliefs_update`) não dispara o marco. | Use o `turn_count` atual e chame também quando a crença mudar, ou ajuste o texto do R6. |
| P2-6 | P2 | `services/world_director.py:759-768` | A correção do `subject_id` da reocupação (`end_ev` em vez do `reocc`) não tem teste de regressão. | Teste: `recovery_step` com `prev_controller` vivo → `subject_id == end_ev` e `event_ids == [end_ev, reocc]`. |

Conferido e OK:
- R1: todos os sites de `digest_item` do motor levam `event_ids`: aviso, início (+ `route_blocked`), escala, ocupação (+ controle + rota), fim (+ `route_cleared`), relação, ascensão, festa, NPC `_item`. O `_close_state` só anexa a `digest[-1]` quando ele mesmo criou o item.
- R2: o ledger soma `subject_id/item_id` + `event_ids`, com teto 400 FIFO (testado).
- R3: há testemunho no mesmo local/família e no mesmo dia (`payload.day`, ou o mesmo turno quando não há `day`). Também conta pela ponta `other_location_id` da rota.
- R5: `cause_event_id` na cascata, também na recursão (raiz).
- R6: crônica e memória OK no oráculo. A ordem storyteller (ledger) → archivist (`process_pending_events`) faz o testemunho de hoje virar marco no mesmo turno.
- R8: um save antigo sem `event_ids` deixa os eventos do motor ocultos (correto). Com `RPG_WORLD_ENGINE=off` não há eventos `engine` de mundo.
- `RPG_NPC_WORLD` off/on: o filtro novo independe da flag (confirmado no oráculo).
- Não há structured output novo nem valor de LLM sem validação. Também não há writer persistente novo: `chronicle`/`perceived_ids` são campos já existentes. Não vi segredo em log.

## Correções aplicadas

Re-revisão do delta `5a53d004..99ce47f8` (`f2f8226e` fix + `99ce47f8` style). Rodei o mesmo
oráculo de novo, agora sem a ressalva da projection vazia: eventos reais via `process_pending_events`,
`RPG_NPC_WORLD` off e on, com resultado idêntico.

| ID | Status | Como foi fechado / verificado |
|---|---|---|
| P0-1 | fechado | `world_perception.perceived_projection` tira `dynamic_edges`/`disabled_edges`/`blocked_routes` cujo evento de origem do motor não foi percebido. A seção `relations` usa isso. Oráculo **antes** da percepção: nenhum dos 4 packs (story/npc/combat_narration/planning) contém `enemy_of` Clãs×Tribos, `controls→ Fortaleza de Vorr` nem "BLOQUEADA". **Depois** (ids no ledger): os três aparecem nos 4 packs. Teste: `tests/test_spec308_oraculo.py::test_remote_world_event_does_not_leak_through_projection` (4 propósitos × off/on, projection real). |
| P1-1 | fechado | `recent_control_changes(..., state=)` filtra por `event_perceived`; é usado no overlay (`api._world_block`) e no `contested` (`map_view`). Oráculo: `[]` → aparece após a percepção. |
| P1-2 | fechado | `dossiers._events_about` filtra por `event_perceived`. Oráculo: `[]` → "controle mudou" após a percepção. |
| P1-3 | fechado | `_world_block` e `build_map_view` trocam a projection pela percebida: `controlled` e `blocked_routes` = canônico + mudanças percebidas. A decisão ficou registrada na spec (§ "Decisões da revisão Sol"). Por design, a viagem continua validada no servidor contra a projection real. Teste: `test_api_blocks_hide_unperceived_engine_facts`. |
| P2-1 | fechado | Só herda `cause_event_id` de `WORLD_EVENT_TYPES`. Teste: `test_cascade_inherits_cause_only_from_world_types`. |
| P2-2 | fechado | `actor_id="player"` conta como testemunho. Os derivados do `rule_engine` herdam o `actor_id` da causa (`"engine"` nos eventos do motor), então isso não abre brecha. Teste: `test_route_cleared_by_hero_is_witnessed_anywhere`. |
| P2-3, P2-4 | registrados na spec | `companion_fate` fica voz do `npc_fate_learned`; `ruin_rec`/`ruin_end` vão para a SPEC-309. Os dois estão do lado seguro (oculto). |
| P2-5 | fechado | O marco tardio usa o `turn_count` da percepção e roda também quando `npc_beliefs` muda. Idempotência conferida no oráculo (2ª chamada → `None`). |
| P2-6 | fechado | Teste: `test_recovery_reoccupy_digest_links_state_event`. |

## Pendências

- **F1 (P2, SPEC-309):** `perceived_projection` é fail-open quando o evento de origem não está no
  `event_log`. Hoje o log nunca é truncado, então isso é seguro. Se um dia houver compactação do
  log, passar a fail-closed para `dyn_*` de eventos do motor.
- **F2 (P2):** o mapa pode mostrar como alcançável uma rota que um evento não percebido bloqueou.
  O servidor recusa a viagem, e é aí que o herói "descobre" o bloqueio. Aceito por design, mas vale
  dar a essa recusa uma narrativa clara na SPEC-309.
- §6 da spec (smoke DeepSeek, 15 turnos) segue com o coordenador.

## Comandos rodados

```text
git diff main...HEAD --stat → 12 arquivos, +537/-85; evals/ intocado (1ª rodada)
py.sh -m pytest -n 2 tests/test_spec308_* test_spec302_* test_spec304_* test_spec305_* test_context* → 310 coletados, exit 0 (1ª rodada)
py.sh <scratchpad>/r308/oracle308.py off|on (1ª rodada) → vazamento via relations (4 packs) + API
git diff 5a53d004..99ce47f8 --stat → 12 arquivos, +370/-11 (sem evals/)
py.sh <scratchpad>/r308/oracle308.py off|on (re-revisão) → 0 vazamentos antes da percepção (packs, controlled, control_changes, blocked_routes, dossiê, contested); tudo aparece depois; crônica 1×, idempotente
py.sh -m pytest -n 2 test_spec308_* test_spec302_* test_spec304_* test_spec305_* test_context* test_map_view* test_dossier* test_fase34* → 429 coletados, exit 0
```
