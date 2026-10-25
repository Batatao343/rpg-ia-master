# SPEC-308 — Regra de ouro para eventos do motor de mundo

> **Status:** `approved` (dono, 2026-10-24 — "escreva specs para isso"; proposta R1 da revisão orquestrada)
> **Criada:** 2026-10-24 · **Atualizada:** 2026-10-24
> **Depende de:** SPEC-302 (`done`), SPEC-304 (`done`), SPEC-305 (`done`)
> **Desbloqueia:** SPEC-309 (mundo percebido no narrador), SPEC-312 (rumores)

---

## 1. Contexto & Objetivo

A revisão orquestrada de 24/10 ([docs/mundo-vivo/REVISAO-ORQUESTRADA-2026-10-24.md](../docs/mundo-vivo/REVISAO-ORQUESTRADA-2026-10-24.md),
achado **A1**) encontrou um vazamento da regra de ouro do mundo vivo ("o jogador só sabe o que viu ou
ouviu", [VISAO.md](../docs/mundo-vivo/VISAO.md)). O coordenador confirmou no código:

- O motor de mundo (SPEC-302) grava no `event_log` eventos com `source="engine"`, criados por
  `world_director._ev()` (`services/world_director.py:307`): `location_state_changed`,
  `world_crisis_warning`, `route_blocked`/`route_cleared` de crise, `faction_relation_changed` de
  cruzamento, entre outros.
- `context_builder.collect_dynamic_facts` (`services/context_builder.py:274-284`) renderiza os 100
  últimos eventos para o narrador e para o planner.
- O único filtro é `npc_world.event_hidden_from_player`, que só age com `RPG_NPC_WORLD=on` e só cobre
  os tipos de NPC fora da tela (SPEC-304).

O resultado: um cerco ou uma rota fechada numa região distante entram no prompt do narrador mesmo que o
herói nunca tenha ouvido falar deles. O staging já roda com `RPG_WORLD_ENGINE=on`.

O que o herói percebeu do motor fica em `world_sim.perceived_ids`. O storyteller grava esse livro-razão a
partir do digest diário (`agents/storyteller.py:705-707`), mas grava `subject_id`/`item_id` do digest,
não o `event_id` do evento que originou o item. Por isso não dá para filtrar o `event_log` por ele hoje.

## 2. Requisitos

- **R1 — O digest liga ao evento.** `world_director.digest_item(...)` aceita `event_ids: list[str]`
  (opcional, default vazio). Todo item do digest criado junto com um evento do motor recebe o `event_id`
  desse evento: estado de local, aviso de crise, início, escalada e fim de crise, rota bloqueada ou
  reaberta, relação entre fações, festa.
- **R2 — O livro-razão guarda os eventos.** Quando o herói percebe um item
  (`agents/storyteller.py:705-707`), os `event_ids` do item entram em `world_sim.perceived_ids`, além do
  `subject_id`/`item_id` de hoje. O teto vai de 200 para 400, com descarte FIFO.
- **R3 — O filtro único.** Função pura `services/world_perception.event_perceived(state, ev) -> bool`:
  - **True** para todo evento sem `source="engine"` (e, entre os `engine`, para tipos que nao sao do motor de mundo: quest, membership, item unico etc.; `world_perception.WORLD_EVENT_TYPES` lista os filtrados, incluindo `companion_fate`), porque esses vêm do turno do jogador ou da
    narrativa e continuam como hoje.
  - **True** para evento do motor cujo `event_id` está em `world_sim.perceived_ids`, ou que é
    conhecido por `npc_world._known_sources` (crença da SPEC-304).
  - **True** para evento do motor cujo local (`target_id` ou `payload.location_id`) é o local atual ou
    um local da família dele (`world_perception._family`) **e** cujo dia é o de hoje: é testemunho
    direto.
  - **False** para todo o resto.
- **R4 — O contexto respeita o filtro.** `collect_dynamic_facts` pula o evento quando
  `event_perceived(state, ev)` é False. Isso vale com qualquer valor de `RPG_NPC_WORLD`, para os
  propósitos `story`, `npc`, `combat` e `planning`. O planner também não pode tramar com o que o herói
  não sabe. O filtro da SPEC-304 continua, depois deste.
- **R5 — Derivados herdam.** Os eventos derivados pelo `rule_engine` de um evento do motor (cascata de
  `location_control_changed` etc.) herdam `cause_event_id`. `event_perceived` usa o `cause_event_id`
  quando existe, no mesmo esquema da SPEC-304 P2-3.
- **R6 — Crônica e arquivista.** Os marcos de crônica e os `memory_fact` vindos de eventos do motor
  também passam por `event_perceived`. Evento não percebido não vira marco nem memória. Ao ser percebido
  depois, vira marco no turno da percepção, uma vez só (idempotente por `event_id`).
- **R7 — API.** `/game/state` não expõe `event_log` cru hoje; confirmar. Se algum bloco de API derivar de
  eventos do motor (mapa, dossiê, crônica), aplicar o mesmo filtro.
- **R8 — Saves antigos.** `perceived_ids` sem `event_ids` funciona: eventos antigos do motor sem
  percepção registrada ficam ocultos, o que é o comportamento correto. `RPG_WORLD_ENGINE=off` não tem
  eventos do motor, então nada muda.

### Decisoes da revisao Sol (24/10)

- **Projection percebida (P0-1/P1-3, decisao do coordenador):** a API e o prompt mostram o que o
  heroi SABE. `world_perception.perceived_projection` remove da projection as arestas dinamicas, as
  desativacoes de aresta base e as rotas bloqueadas escritas por evento do motor nao percebido
  (`created_by_event`/`disabled_by_event`/`blocked_by_event`; evento fora do `event_log` nao filtra).
  Usada na secao `relations` do contexto, em `controlled`/`blocked_routes` (`api._world_block`) e no
  `/data/map`. A viagem em si continua validada no servidor contra a projection real.
- **R7:** `recent_control_changes` (overlay e `contested`) e o dossie de local usam `event_perceived`.
- **P2-1:** `cause_event_id` so herda de `WORLD_EVENT_TYPES`. **P2-2:** evento com `actor_id="player"`
  (ex.: `route_cleared` por quest de mundo) e testemunho. **P2-5:** marco tardio usa o turno da
  percepcao e tambem roda quando a crenca muda.
- **P2-3 (registrado):** em producao o `companion_fate` usa `uuid4` que nao entra em `npc_beliefs`;
  quem da voz ao destino e o `npc_fate_learned`. **P2-4 (registrado):** `ruin_rec`/`ruin_end` e
  `route_cleared` sem item de digest ficam ocultos; a SPEC-309 da voz.

### Fora de escopo

- Novos templates de `render_event` e o bloco `<MUNDO_PERCEBIDO>` (SPEC-309).
- Rumores (SPEC-312).
- Mudar o que conta como percebido no digest (`world_perception.perceivable`), que segue como está.

## 3. Design técnico

- `services/world_director.py`: `digest_item(..., event_ids=None)` passa a gravar
  `item["event_ids"] = list(event_ids)` quando não vazio. As chamadas (`:424, :484, :542, :576, :644,
  :746`) passam o `event_id` do evento criado no mesmo passo. Conferir cada uma.
- `services/npc_world.py:430` (`_item`): mesmo campo, para os itens de NPC.
- `agents/storyteller.py:705-707`: o ledger inclui `i.get("event_ids", [])`.
- `services/world_perception.py`: nova `event_perceived(state, ev)`, pura e sem I/O.
- `services/context_builder.py:274-284`: `if not world_perception.event_perceived(state, ev): continue`
  antes do filtro da SPEC-304.
- `services/rule_engine.py` (`_new_event`): propagar `cause_event_id` do evento-causa quando ele vem do
  motor.
- `services/chronicle.py` / `agents/archivist.py`: o mesmo filtro nos caminhos que consomem
  `event_log` para marcos e memória.

## 4. Plano passo a passo

### Etapa 1 — Filtro puro
1. **Testes** (`tests/test_spec308_filtro.py`):
   - `test_non_engine_event_always_perceived`;
   - `test_engine_event_hidden_until_ledger`;
   - `test_engine_event_perceived_by_ledger_event_id`;
   - `test_engine_event_same_place_same_day_is_witness`;
   - `test_engine_event_other_region_hidden`;
   - `test_derived_event_uses_cause`;
   - `test_known_sources_from_304_count`.
2. **Implementação:** `event_perceived`.

### Etapa 2 — Digest e livro-razão
1. **Testes:**
   - `test_digest_items_carry_event_ids` (cada tipo de crise e estado);
   - `test_ledger_records_event_ids_on_perception`;
   - `test_ledger_cap_400_fifo`.
2. **Implementação:** `digest_item`, `_item`, storyteller.

### Etapa 3 — Contexto, crônica e arquivista
1. **Testes:** oráculo de vazamento `test_remote_siege_not_in_story_or_planning_context`:
   - monta uma crise em outra região;
   - confere que nem o pack `story` nem o `planning` contêm o local, a fação ou a palavra do estado;
   - depois da percepção, o fato aparece.
2. **Testes:**
   - `test_chronicle_milestone_only_after_perception`;
   - `test_memory_fact_only_after_perception`;
   - `test_rpg_npc_world_off_still_filters`.
3. **Implementação.**

### Etapa 4 — Regressão
- `test_fase2`, `test_fase26`/`27`, `test_spec302_*`, `test_spec304_*` e `test_spec305_*` verdes. Se algum
  teste antigo afirmar que o narrador vê um evento do motor não percebido, a afirmação era o vazamento:
  ajustar com nota no commit.
- Playtest `mundo` (Mock) com 2 seeds: 0 erros e 0 violações.

## 5. Critérios de aceite

- [ ] R1–R8 cobertos por teste; o oráculo de vazamento passa com `RPG_NPC_WORLD` em `off` e em `on`.
- [ ] O pack `planning` também filtra.
- [ ] Saves antigos carregam.
- [ ] Testes do escopo verdes com `-n 2`; a suíte completa roda 1× no pouso.
- [ ] Revisão independente aprovada.

## 6. Smoke test com LLM real

1. Cenário `mundo` (DeepSeek, 15 turnos). Conferir no transcrito que o narrador só cita crise ou estado
   de local de onde o herói está ou ouviu falar. Comparar com o run de 24/10 (`20261024-195914`).

## 7. Riscos & compatibilidade

- O narrador pode ficar "mais pobre" de contexto até a SPEC-309 dar voz ao que foi percebido. Isso é
  esperado: é o certo pela regra de ouro.
- O planner perde visão do mundo inteiro. A SPEC-311 (R8) dá a ele o mundo **percebido**.
- O custo é só CPU: um filtro por evento, com 100 eventos por turno no máximo.
