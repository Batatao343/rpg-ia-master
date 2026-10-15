# Núcleo do motor, grafo, agentes e camada LLM — como funciona

Escopo: `main.py`, `state.py`, `agents/*`, `services/turn_*`, `structured_outputs`, `input_normalization`, `social_direction`, `objectives`, `continuity`, `narrative_evidence`, `presentation_history`, `prologue`, `llm_setup.py`, `mock_llm.py`, `game_engine.py`, `character_creator.py`. Referências no formato `arquivo:linha`. Nada foi modificado no projeto.

---

## 0. Visão em uma página

O motor é um **StateGraph do LangGraph, síncrono**, compilado uma vez em `main.py:143` (`app = build_game_graph()`). A API importa esse objeto como `game_graph` (`api.py:34`), e o CLI e o harness de playtest usam o mesmo `app`. Isso significa que há um único caminho de jogo, e o que é testado offline é o que roda em produção.

Quatro princípios sustentam o desenho e aparecem em todo arquivo:

1. **A IA identifica e narra. O Python resolve os números.** Combate, economia, XP, viagem e descanso são código determinístico. A LLM devolve intenção, classificação ou prosa.
2. **A LLM propõe, o motor aplica.** Eventos de mundo, missões, itens narrados e reputação entram como propostas (`pending_world_events`, `proposed_quests`, `items_gained`). Um validador em Python aceita ou rejeita cada uma (`services/event_processor.py`, `services/quest_log.py`, `inventory.resolve_item_name`).
3. **Todo structured output tem guard de resiliência.** `FallbackLLM` e o último recurso do `RoutedLLM` devolvem `AIMessage`, não o modelo Pydantic. Cada nó faz `isinstance(res, Modelo)` ou usa `try/except`, e cai num caminho determinístico.
4. **Tudo que o jogador lê passa por guardas de prosa e de evidência.** `prose_guard`, `narrative_evidence` e `turn_outcome` limpam vazamentos de meta-instrução, alegações falsas de morte, posse ou localização, e reescrevem o recibo de recompensa a partir do delta mecânico real.

---

## 1. Diagrama do grafo

```
START ──(cond: game_over | death_pending | archived ? END : action_guard)  main.py:63
  │
  ▼
action_guard ──(cond: action_guard_blocked ? END : turn_prepare)           main.py:68
  │                          (jogador inconsciente/terminal/morto: mensagem fixa, sem LLM)
  ▼
turn_prepare        world.turn_count += 1; continuity.session_action_count += 1
  │                 turn_prepared=True                                      turn_pipeline.py:37
  │
  ├── modo SEQUENTE (default, RPG_TURN_EXECUTION=sequential)               main.py:82
  │      turn_prepare → campaign_manager → dm_router → dispatch
  │
  └── modo CONCURRENT (opt-in)                                             main.py:78
         turn_prepare ─┬─> campaign_manager ─┐
                       └─> dm_router ────────┴─> dispatch   (join)
  ▼
dispatch            só zera turn_prepared; a decisão está em state["next"]  turn_pipeline.py:79
  │
  ├─ cond sobre state["next"]                                              main.py:87
  │     "storyteller"  → storyteller
  │     "combat_agent" → combat_agent
  │     "npc_actor"    → npc_actor
  │     "loot"         → loot_agent
  │     END ("__end__")→ END         (router viu AIMessage por último)
  │
  ├─ storyteller ──(cond: next=="combat_agent" ? combat_agent : archivist)  main.py:114
  │                 (emboscada em viagem/descanso → combate no MESMO turno)
  │
  ├─ npc_actor  ──(cond: next=="storyteller" ? storyteller : archivist)    main.py:106
  │                 (sem interlocutor → storyteller narra a ausência)
  │
  ├─ combat_agent ─(cond: combat_simulation.enabled ? END
  │                       : next=="loot" ? loot_agent : archivist)         main.py:122
  │
  ├─ loot_agent ──────────────────────────────► archivist                   main.py:101
  │
  ▼
archivist ──► turn_finalizer ──► END                                        main.py:136-137
```

Observações sobre a topologia:

- O único nó que sempre roda antes de END (exceto bloqueio e laboratório de combate) é `archivist → turn_finalizer`. A regra "todo agente termina no arquivista" está respeitada.
- O gate do START é lido **antes** de qualquer nó. Por isso `game_over` (memorial), `death_pending` (tela de morte aberta) e `archived` impedem o grafo de processar turno com um herói morto ou campanha arquivada. A API também barra com 409, mas o gate protege runner, CLI e qualquer chamador direto.
- O "ciclo" npc_actor → storyteller → (combat_agent|archivist) é o único em que um nó de ação chama outro. Nunca há laço infinito: o `storyteller` não devolve `next="storyteller"`.
- Não existe aresta de `dispatch` para `archivist`. Se o router devolver `END`, o turno termina sem arquivamento nem finalizer. É o caso em que a última mensagem já é do narrador (`router.py:125`), por exemplo a chamada inicial do `/game/new` sobre um estado cuja última mensagem foi uma `AIMessage`.

### 1.1 O reducer de mensagens e o resto do estado

Só **um** campo tem reducer acumulativo: `messages: Annotated[List[BaseMessage], operator.add]` (`state.py:436`). Todo o resto é "último valor vence". Consequências práticas:

- Um nó que devolve `"messages": [AIMessage(...)]` **acrescenta** ao histórico. Para substituir mensagens (como o `turn_finalizer` e o `archivist` fazem ao reescrever prosa rejeitada) é preciso devolver `langgraph.types.Overwrite(messages)` (`turn_finalizer.py:23`, `archivist.py:232`).
- Todo campo que um nó devolve **sobrescreve** o valor anterior. Por isso o router devolve o payload completo, incluindo `combat_target: None`, `active_npc_name: None`, `loot_source: None`, `combat_origin_hint: None`, para que transitórios do turno anterior não sobrevivam (`router.py:48-57`). O comentário diz exatamente isso: "reducer não pode preservar transitórios antigos".
- `route_intent_node` descarta a chave `world` do router (`turn_pipeline.py:75`). O router nunca é dono do canal `world`. Isso é o que torna o modo concurrent seguro: `campaign_manager` e `dm_router` escrevem em canais disjuntos.

### 1.2 Modo sequencial vs. concurrent

O comentário em `main.py:73-75` explica a decisão: o benchmark R29 (2026-08-28) mostrou contenção de provider quando o planejamento SMART e a classificação CLASSIFY batiam na mesma rota DeepSeek ao mesmo tempo. O padrão de produção é sequencial. O modo concurrent existe como experimento e é ativado por `RPG_TURN_EXECUTION=concurrent`. A razão técnica pela qual os dois modos existem é que o `turn_prepare` foi extraído como nó puro: ele avança o relógio **uma vez** antes de qualquer leitura paralela. Sem isso, `campaign_manager` e `router` disputariam `world.turn_count`.

---

## 2. `state.py` — o contrato de estado

`state.py` é a fonte da verdade do schema. O `GameState` (`state.py:409`) é um `TypedDict` **sem `total=False`**, mas na prática os nós leem tudo com `.get()` e os saves antigos não têm todos os campos. Os sub-TypedDicts (`PlayerStats`, `WorldState`, etc.) são `total=False`.

### 2.1 Grupos de campos do `GameState`

| Grupo | Campos | Para que serve |
|---|---|---|
| Identidade e idempotência | `game_id`, `processed_action_ids` (ledger de 64), `visual_seen_entity_ids`, `visual_cue_ledger`, `art_generation_ledger`, `art_arc_budgets` | Isolar RAG por sessão; deduplicar retries SSE/POST; arte dinâmica |
| Memória narrativa | `narrative_summary`, `archivist_last_run`, `archive_due`, `memory_facts`, `pending_memory_facts`, `memory_rejections`, `memory_promotions`, `pending_npc_memory`, `memory_fact_policy`, `memory_canonical_facts`, `rag_persistence_error` | Resumo curto, ledger de fatos com proveniência, filas de retry de RAG |
| Ciclo de vida | `game_over`, `death_pending`, `archived`, `archived_reason`, `continuity` | Memorial, tela de morte, linha do tempo |
| Pipeline de turno | `action_guard_blocked`, `turn_prepared`, `last_action_outcome`, `turn_baseline`, `last_turn_outcome`, `last_interaction_outcome`, `presentation_history` | Gate de ação, delta de recompensas, recibo, histórico estável para o cliente |
| Conversa | `messages` (único com `operator.add`), `next` | Histórico LangChain e destino do `dispatch` |
| Entidades | `player`, `world`, `party`, `enemies`, `npcs`, `factions`, `faction_intel`, `bestiary_knowledge`, `quests` | Estado mecânico do jogo |
| Campanha | `campaign_plan`, `needs_replan`, `chronicle` | Arco de 3-5 beats, crônica por capítulos |
| Transições entre nós | `combat_target`, `combat_origin_hint`, `loot_source`, `active_npc_name`, `npc_fallback_hint`, `combat_flee_attempt`, `combat_flee_destination`, `combat_declaration`, `player_reaction_card_id`, `conflict_summary`, `consumed_conflict_ids`, `last_economy_action` | Canais efêmeros entre router/combate/loot/archivist |
| Combate | `combat`, `combat_simulation` | Dict aberto `{round, active, order, idle_turns, scene, chase, instance_id, ...}` |
| Mundo estruturado (2.5) | `event_log`, `world_projection`, `pending_world_events`, `event_rejections` | Event sourcing leve: o log é append-only, a projeção é derivada |
| Auditoria | `narrative_rejections`, `evidence_rejections`, `rejected_item_claims` | Buffers limitados do que os guardas removeram |

### 2.2 Os TypedDicts principais

- **`PlayerStats`** (`state.py:122`) é o maior. Mostra duas camadas coexistindo: a nova (Virtudes `mente/agilidade/forca/carisma/corpo`, `vitalidade`, `ferimentos` por categoria, `known_cards`/`prepared_cards`, `entropy`/`max_entropy`/`abyss_charge`, `virtue_cards`, `evolved_cards`, `pending_choices`) e aliases legados (`hp`, `max_hp`, `mana`, `stamina`, `attributes`). Os aliases `hp`/`max_hp` são derivados de `vitalidade` por `gamedata.sync_legacy_hp_aliases`. Flags de fase vital: `dead`, `estado_terminal`, `last_stand_pending`, `last_stand_resolved`, e (fora do TypedDict, lidas por `classify_actor`) `incapacitated` e `conscious`.
- **`WorldState`** (`state.py:229`) guarda localização (`current_location`, `current_location_id`), fog of war (`visited`), `world_clock{day,period}`, `turn_count`, clima (`weather_state`, `weather_global`), economia (`merchant_stocks`, `merchant_restock_day`), flags one-shot de encontro (`encounter_surprise`, `treasure_hint`), e o mundo que evolui (`controlled`, `danger_overrides`, `looming_threat`, `threat_alerts`).
- **`ConflictScene`/`SceneObject`/`Carta`/`EffectSpec`** (`state.py:66-119`) descrevem a cena tática por zonas e o catálogo fechado de efeitos. Vivem dentro de `combat["scene"]`.
- **`ContinuityState`** (`state.py:321`): `session_action_count` (nunca retrocede), `timeline_epoch` (sobe a cada restore de checkpoint), `last_checkpoint_turn`, `death_history`. É o "metatempo" que sobrevive ao rollback. Veja `services/continuity.py`.
- **`Quest`** (`state.py:304`) tem um `progress_log` (ledger `created → location_reached → investigation → completion_ready → completed`) e `reward_delivered`.
- **`GameEvent`/`WorldProjection`** (`state.py:350-407`) são o núcleo do "mundo vivo": a lore base é imutável; o que muda vive no `event_log` e na projeção.

### 2.3 Campos declarados mas nunca escritos

`active_plan_step`, `router_confidence` e `last_routed_intent` existem em `GameState` (`state.py:454-456`), mas uma busca no código de produção não encontra nenhuma escrita. Só `presentation_history.message_kind` lê `last_routed_intent` (`presentation_history.py:8`) e, como ele é sempre vazio, cai em `state['next']`. É um acoplamento frágil: `next` é transitório, então o `type` de uma mensagem gravada no histórico depende de `next` ainda valer no momento do `record_history`. Em `combat_agent`/`loot`/`npc_actor` isso funciona porque a API chama `record_history` depois do grafo e `next` ainda guarda a última rota. Em um turno que terminou em `combat` com vitória (`next="loot"` limpo?) vale conferir, mas isso está fora do escopo desta fatia.

---

## 3. A camada LLM (`llm_setup.py`)

### 3.1 Tiers e rotas

`ModelTier` (`llm_setup.py:77`) tem três níveis: `CLASSIFY` (temp 0, parse e roteamento), `FAST` (narração e roleplay), `SMART` (coerência: campanha, arquivista, ficha). `ROUTES` (`llm_setup.py:155`) é um dict `tier → lista ordenada de (provider, modelo)`:

- CLASSIFY: `deepseek-v4-flash` → Groq `openai/gpt-oss-20b` → Gemini `flash-lite`
- FAST: `deepseek-v4-flash` → Groq `gpt-oss-120b` → MiniMax `M2.5` → Qwen `plus` → Gemini `flash`
- SMART: `deepseek-v4-flash` → Groq `gpt-oss-120b` → Anthropic `claude-sonnet-5` → Gemini `pro`

DeepSeek é o primário nos três. Groq free é o fallback vivo em todos. Trocar provider é editar `ROUTES` ou apontar `RPG_ROUTES=<arquivo json>` (`llm_setup.py:894`). O override por arquivo faz merge: tiers não citados mantêm o default.

### 3.2 Ordem de resolução de `get_llm`

`get_llm(temperature=0.1, tier=FAST)` (`llm_setup.py:951`) segue esta cascata, e a ordem importa:

1. `RPG_FORCE_MOCK` → `MockLLM` (a suíte inteira usa isso via `tests/conftest.py`).
2. `LLM_PROVIDER=x` → `_legacy_get_llm`, que força **todos** os tiers num provider único e embrulha num `RoutedLLM` de um candidato. Gemini sem chave com esse override cai no `MockLLM` (ou `FallbackLLM` com `RPG_NO_MOCK`).
3. Nenhuma key de nenhum provider → `MockLLM` (zero-config) ou `FallbackLLM("Nenhuma key...")` com `RPG_NO_MOCK`.
4. Padrão → `RoutedLLM(tier, temperature, ROUTES[tier])`.

`is_simulated()` (`llm_setup.py:978`) espelha essa cascata para a API expor a flag `simulated` sem mentir.

Observação de uso: `storyteller_node` chama `get_llm(temperature=0.7)` **sem tier** (`storyteller.py:579`), então usa o default `FAST`. Todos os outros call sites passam o tier explícito.

### 3.3 `RoutedLLM` — o coração

`RoutedLLM` (`llm_setup.py:407`) é um objeto leve que **acumula transformações** (`with_structured_output`, `bind_tools`, `with_retry`) numa lista `_transforms` em vez de aplicá-las. Só no `.invoke()` ele instancia o client de cada candidato e reaplica as transformações. É assim que um mesmo `llm.with_structured_output(Schema)` funciona com providers diferentes: cada candidato resolve o método do seu jeito.

O que `_apply` faz de relevante (`llm_setup.py:437`):

- Para providers OpenAI-compat (`groq, qwen, glm, minimax, kimi, deepseek, openai`), injeta `method="function_calling"` em todo `with_structured_output` que não escolheu método. Motivo: o modo `json_schema` estrito do Groq rejeita schema com dict aberto (`StoryUpdate.payload`, `ProposedWorldEvent.payload`). Tool calling aceita qualquer schema.
- Para qualquer schema Pydantic, injeta `include_raw=True`. O `RoutedLLM` quer ver a mensagem crua para tentar **recuperar JSON válido do texto** quando o provider respondeu sem tool call. O formato público devolvido ao chamador é restaurado depois por `_normalize_internal_structured_result` (`llm_setup.py:574`).

O `invoke` (`llm_setup.py:614`) em ordem, por candidato:

1. **Circuit breaker.** Se `(provider, modelo)` está em `_OPEN_CIRCUITS`, pula e emite evento `circuit_open`. Um circuito só abre por erro **permanente** (`_permanent_provider_error`, `llm_setup.py:323`): 401, 402, 403, 404, "insufficient balance", "invalid api key", chave não configurada, dependência não instalada. O harness chama `reset_llm_circuit_breakers()` no início de cada campanha.
2. **Build do client**, com cache por `(provider, model, temperature)` (`_get_cached_client`, `llm_setup.py:350`). Falha de build vira `build_error` e passa ao próximo candidato.
3. **Aplicação das transformações** (`_apply`). Falha vira `build_error` também.
4. **Regeneração semântica** (`llm_setup.py:680-740`): se houve schema Pydantic e a rede respondeu mas o resultado não passou na pós-condição (`_validate_structured_result`), regenera no **mesmo** provider até `STRUCTURED_SEMANTIC_MAX_ATTEMPTS = 3` gerações no total. A segunda e a terceira tentativa acrescentam uma mensagem humana dizendo qual contrato falhou e por quê (`_input_for_structured_retry`). Erro de transporte (timeout, 429, 5xx) **não** regenera: dá `break` e vai para o próximo provider. A diferença é deliberada: HTTP/quota não melhora no mesmo provider; um parse ruim às vezes melhora.
5. **Recuperação local de JSON** (`_json_object_from_text`, `llm_setup.py:545`): se o modelo devolveu o objeto em texto (inclusive em cerca de código ```` ```json ````), extrai o primeiro objeto JSON bem formado (até 64 KiB) e valida com `schema.model_validate`. Se passar, retorna como sucesso com `recovery="local_json"` e **sem nova request**. Rejeita `wrong_tool` se o provider chamou uma ferramenta de outro nome.
6. **Semáforo por provider** (`_provider_slot`, `llm_setup.py:51`): limita chamadas em voo por provider (`RPG_LLM_MAX_CONCURRENCY`, padrão 2). Observa o tempo de espera na fila como métrica.
7. **Último recurso:** esgotou tudo → `AIMessage(content="")` (`llm_setup.py:759`). Nunca levanta. Por isso o guard `isinstance` nos nós é obrigatório e é por isso que os nós de narração simples (`llm.invoke`) tratam conteúdo vazio como falha.

Há também `ainvoke` (apenas `asyncio.to_thread(self.invoke)`, `llm_setup.py:761`) e `stream` (`llm_setup.py:773`), que não regenera nem recupera JSON. A API de streaming SSE **não** usa `RoutedLLM.stream` para o texto: ela usa `graph.stream(stream_mode=['updates','values'])` por nó e fatia a narração final em pedaços de 80 caracteres (`api.py:2539`, `2599`).

### 3.4 Timeouts

`_build_openai` (`llm_setup.py:263-268`): se `LLM_TIMEOUT_SECONDS` existe, vale para todos; senão DeepSeek usa `DEEPSEEK_TIMEOUT_SECONDS` (default **12 s**) e os demais 90 s. Gemini e Anthropic usam `LLM_TIMEOUT_SECONDS` (default 90). Todos com `max_retries=0`: o fallback é trocar de provider, não repetir. Para DeepSeek v4, o `extra_body={"thinking": {"type": "disabled"}}` (`llm_setup.py:257-261`) preserva o comportamento do antigo alias não-pensante `deepseek-chat`, evitando raciocínio oculto e latência extra. Anthropic omite `temperature` porque os modelos Claude 5+ a rejeitam com 400 (`llm_setup.py:290`).

### 3.5 Telemetria

Dois hooks globais:

- `set_llm_telemetry_hook` recebe `(provider, model, tier, latency_ms, fell_back)` **só em sucesso**.
- `set_llm_attempt_telemetry_hook` recebe um `LLMAttemptEvent` por tentativa, inclusive `build_error`, `invoke_error`, `invalid_structured`, `circuit_open` e o `structured_failure_code` (`transport`, `no_tool_call`, `wrong_tool`, `parsing_error`, `schema_validation`).

Ambos são envolvidos em `try/except`: "telemetria NUNCA derruba o turno". A API usa esses hooks para somar custo real por turno (`api.py:311`, `335`, `llm_pricing.turn_cost`) e o harness de playtest usa para medir provider/modelo/custo.

### 3.6 `FallbackLLM` e `MockLLM`

- **`FallbackLLM`** (`llm_setup.py:180`): `is_fallback=True`. `with_structured_output` devolve `self` e `invoke` devolve `AIMessage(content=<erro>)`. É o que torna o guard obrigatório: `res.campo` estoura num `AIMessage`.
- **`MockLLM`** (`mock_llm.py:475`): `is_mock=True`. `invoke` puro sorteia uma de quatro narrativas e ecoa a ação (`_acao_eco`). `with_structured_output(Model)` devolve um `_StructuredMock` cujo `invoke` despacha por **nome da classe** para um construtor (`_DISPATCH`, `mock_llm.py:~440`): `RouterDecision` → `_route_decision` (palavras-chave em PT), `StoryUpdate` → `_story_update`, `CampaignPlanModel`, `MemoryUpdate`, `NPCResponse`, `EncounterScanner`, `TradeIntent`, `WorldPulse`, `StartScenario` etc. Schemas sem builder caem em `_fill(model, {})`, que introspecciona os tipos Pydantic e fabrica valores neutros.

Dois pontos importantes sobre o mock:

- **Ele esconde bugs de mapeamento.** Devolve instâncias Pydantic sempre válidas, então `res.campo` nunca quebra. A convenção do projeto exige validar caminhos novos de structured output com chave real.
- **Ele exerce os caminhos de proposta.** `_story_update` propõe quests em ~15% dos turnos, propõe a **conclusão** de uma quest ativa em ~50% (lendo o bloco `<QUESTS_ATIVAS>` do prompt), marca `beat_completed` em ~30% e ecoa impacto de facção por palavras-chave. Sem isso, o harness offline nunca fecharia uma quest.
- O `PlayerMove` do combate é uma classe local dentro de `_parse_turn_declaration` (`combat.py:380`) e **não está no `_DISPATCH`** (que ainda cita `CombatAction`, `mock_llm.py:~447`). Cai em `_fill`, que devolve `kind=""`, e o código converte `""` em `attack` (`combat.py:412`). O resultado é correto, mas o `_combat_action` do mock (`mock_llm.py:387`) parece ser código morto desde a migração para `PlayerMove`.

---

## 4. Os nós, um por um

Legenda de tiers: C = CLASSIFY, F = FAST, S = SMART.

### 4.1 `action_guard` (`agents/action_guard.py`)

**Entrada:** o estado cru, antes de qualquer processamento. **LLM:** nenhuma.

Consulta `services/actor_lifecycle.py`, que classifica o jogador numa fase (`classify_actor`, `actor_lifecycle.py:90`): `active`, `unconscious`, `incapacitated`, `last_stand`, `terminal`, `death_pending`, `dead`. A ordem de teste dá precedência a `game_over` e `death_pending` sobre as flags do próprio `player`.

Fluxo:

1. **Transição órfã** (`orphan_transition`): se o jogador está em `last_stand`, `terminal` ou `dead` mas **sem dono** (não há combate ativo, nem `death_pending`, nem `game_over`), é um save legado ou corrompido. O guard repara com `sanitize_interturn_state` (limpa as flags efêmeras, devolve o herói inconsciente se tiver Ferimento crítico, ou com 1 de vitalidade se não houver ferimento que explique o zero), liga `needs_replan` e **bloqueia o turno** com uma mensagem explicando.
2. **`evaluate_action`**: com combate ativo, sempre permite (`combat_resolution`). Com jogador `active`, permite (`ok`). Inconsciente ou incapacitado só passa se o texto, normalizado sem acentos, casar por completo (`fullmatch`) com a regex de recuperação (`_RECOVERY`: descansar, repousar, dormir, aguardar socorro, pedir ajuda/tratamento, e combinações "X e Y"). Nesse caso `action_kind="recovery"`. Qualquer outra ação nessas fases, ou qualquer ação em `last_stand`/`terminal`/`death_pending`/`dead`, é bloqueada com mensagem fixa em português.
3. Se permitido: devolve `turn_baseline = capture_baseline(state)` (ouro, XP, nível, inventário, quests concluídas e IDs de eventos **antes** do turno) e `last_action_outcome`.

O `turn_baseline` é a peça que permite ao `turn_finalizer` calcular o recibo como diferença de estados em vez de confiar em marcadores de texto.

**Exemplo.** Jogador inconsciente após combate digita "vou até a taverna". `evaluate_action` devolve `{allowed: False, code: "blocked_unconscious", message: "Você está inconsciente..."}`; o guard retorna `action_guard_blocked=True` + `AIMessage` com essa mensagem; a aresta condicional leva a END. Nenhuma LLM foi chamada, nenhum turno avançou. Se ele digitar "descanso", passa com `action_kind="recovery"`, e depois o router e o storyteller tratam como passagem de tempo, não como permissão para outra ação.

### 4.2 `turn_prepare` (`services/turn_pipeline.py:37-64`)

`prepare_turn` incrementa `world.turn_count` e chama `continuity.advance_action`, que incrementa `session_action_count`. Retorna `{"world", "continuity", "turn_prepared": True}`. Roda dentro de um `span("turn.prepare")` de observabilidade.

Como o contador canônico de turnos e o contador de ações da sessão vivem em canais distintos, é possível o `turn_count` retroceder num restore de checkpoint enquanto `session_action_count` e `timeline_epoch` seguem. Isso é a razão de existirem os dois.

### 4.3 `campaign_manager` (`agents/campaign_manager.py`)

**Tier:** SMART, temp 0.4 (`campaign_manager.py:~110`). **Schema:** `CampaignPlanModel` (`location`, `beats` com mínimo 3, `climax`, `arc_title`). **Retorno:** `world`, `campaign_plan`, `needs_replan`, `continuity` (e `chronicle` quando o título do arco muda).

**Quando replaneja** (`_should_replan`, `campaign_manager.py:65`): `needs_replan` explícito; não há plano; o local mudou **para outra região** (`_same_region` resolve ids/nomes via `gamedata`; local irresolvível conta como "mesma região" para não replanejar à toa); `turn_count - last_planned_turn >= REPLAN_INTERVAL` (15); ou todos os beats foram cumpridos.

**Curtos-circuitos** em `_campaign_manager_node` (`campaign_manager.py:233`):

- Se `turn_prepared` está ligado, **não** incrementa `turn_count` (já foi feito). Senão (chamada direta de um teste) incrementa — compatibilidade.
- `combat_simulation.enabled` → só devolve o plano existente.
- Combate ativo e precisaria replanejar → adia (devolve `needs_replan=True`). O comentário justifica: gastar uma request SMART num plano que o combate não consome, descrevendo uma cena ainda instável.
- Não precisa replanejar → devolve o plano como está. É o caso de 14 em cada 15 turnos, e por isso este nó raramente custa uma chamada.

**`_build_plan`:** monta um `ContextPack` com `purpose="planning"` (única visão que enxerga edges hidden/secret do grafo), faz o prompt em inglês com regras em pt-BR, e executa o structured output. Camadas de proteção, em ordem:

1. `isinstance(plan, CampaignPlanModel)`; senão `ValueError`.
2. **Idioma:** `looks_english` nos beats/clímax. Reexecuta uma vez com instrução reforçada. Se ainda falhar, devolve `None` e o nó mantém o plano antigo com `needs_replan=True` (tenta de novo no próximo turno).
3. **Segredo:** cada beat, o clímax e o título passam por `sanitize_beat` (`services/secret_signatures`), que remove verdades ocultas do texto que o jogador lê.
4. **Grounding:** `location` do plano é sempre `current_loc` do mundo, nunca o que o modelo propôs ("o modelo propõe conteúdo, não geografia ativa").
5. Falha em qualquer ponto (exceção) → plano fallback de 3 beats em pt-BR e clímax genérico, mantendo o título de arco atual para não fragmentar a crônica.

O validador do Pydantic em `CampaignPlanModel` (`campaign_manager.py:38`) normaliza saída de provider: mantém os 5 primeiros beats não vazios, e só recusa se sobrarem menos de 3. A razão é registrada: um sexto beat do DeepSeek já derrubou um plano inteiro.

Se o título do arco mudou, o nó chama `open_chapter` e abre um capítulo novo na crônica.

### 4.4 `dm_router` (`agents/router.py`)

**Tier:** CLASSIFY, temp 0.0. **Schema:** `RouterDecision` (`route`, `loot_context`, `target`, `reasoning`, `confidence`). Validadores normalizam `loot_context` para maiúsculas e `target` via `optional_entity_ref` (que converte "null", "none", "nenhum", "n/a" etc. em `None`, para sentinelas de provider não virarem entidades reais).

O router tem **cinco atalhos determinísticos antes de chamar a LLM**, nesta ordem:

1. Sem mensagens → `STORY`. Última mensagem é `AIMessage` sem tool calls → `END` (`router.py:125`).
2. **`combat.active`** → `_combat_gate` (`router.py:60`), nunca a LLM:
   - Se `idle_turns + 1 >= COMBAT_IDLE_EXPIRE (3)`: combate órfão expira, limpa `enemies`, `combat_target`, e injeta `SystemMessage("COMBAT EXPIRED...")`; segue como STORY.
   - Senão: força `next="combat_agent"`, mantém `idle_turns` incrementado (o `combat_node` zera).
   - **Viagem durante combate vira tentativa de fuga:** se o texto casa com um destino (`find_travel_destination`), liga `combat_flee_attempt` e `combat_flee_destination`. Se uma borda estruturada (API/harness) já resolveu o id exato do destino, usa esse e não reparseia o texto, porque "nomes de interiores contêm o nome da região" e seriam reduzidos ao nó pai.
   - Isso fecha dois bugs históricos: teleporte em combate e combate zumbi.
3. **`is_recovery_turn`** (inconsciente + `action_kind == "recovery"`) → `STORY`.
4. **`_EXPLICIT_STORY_RE`** (descansar, dormir, acampar, viajar, "vou para", "sigo para") → `STORY`, sem LLM. Isso evita que contexto hostil antigo reabra um conflito logo depois de uma fuga.
5. Só então o prompt de classificação. Usa `messages[-3:]`.

Pós-processamento do resultado:

- `try/except Exception` em torno do invoke → `STORY`.
- `not isinstance(decision, RouterDecision)` → `STORY` (modo degradado).
- `RouteType.NONE` → `STORY` (o LLM real escolhe `none` para emojis, SQL e "ignore as instruções"; `none` não é nó do grafo e causaria `KeyError`). Esse bug só aparecia com LLM real porque o mock nunca escolhe `none`.
- **LOOT:** copia `loot_context` para `loot_source` (padrão `TREASURE`).
- **NPC:** tenta casar `decision.target` com os NPCs em cena (`npc_layers.npcs_in_scene`) por substring bidirecional; se só há um NPC em cena, usa esse; se há alvo mas nenhum casa, repassa o alvo bruto ("deixa o ator tentar carregar do DB"). Grava `active_npc_name`.
- **COMBAT:** `combat_target = target or "Inimigos"`; `combat_origin_hint` = `player_provoked` se o texto casa com `_EXPLICIT_HOSTILITY_RE` (atac, golpe, apunhal, dispar, saco a arma, inicio combate, enfrent), senão `regional_danger`; e acrescenta `SystemMessage("SYSTEM: COMBAT START. TARGET_HINT: ...")`, que o `combat_node` detecta (`is_start`).

**Exemplo.** Jogador diz "Ataco o goblin" com o mock: `_route_decision` casa "atac" → `combat_agent`, `target="Inimigo"`. O payload sai com `next="combat_agent"`, `combat_target="Inimigo"`, `combat_origin_hint="player_provoked"`, mais a `SystemMessage` de início.

### 4.5 `dispatch` e a roteirização central

`dispatch_node` apenas zera `turn_prepared`. A decisão é a aresta condicional `lambda state: state.get("next")` (`main.py:87`). Se `next` tiver qualquer valor fora do mapeamento (`storyteller`, `combat_agent`, `npc_actor`, `loot`, `END`), o LangGraph levanta erro; por isso o router normaliza `NONE`.

### 4.6 `storyteller` (`agents/storyteller.py`) — o nó mais denso

**Tier:** FAST (default), temp 0.7. **Schema:** `StoryUpdate` (`storyteller.py:42`) com `narrative`, `introduced_npcs`, `npcs_left_scene`, `faction_impacts`, `beat_completed`, `proposed_events`, `proposed_quests`, `items_gained`. Todos têm default, e `narrative` default `""`, porque o Gemini real às vezes omite um campo num schema grande e é melhor narrar pelo fallback do que perder o turno.

O nó faz **muito trabalho determinístico antes da LLM**. Em ordem:

**(a) Entrada e recuperação.** Se o turno é de recuperação, o texto do jogador é substituído por "Descanso e aguardo socorro." (`storyteller.py:288-290`).

**(b) Viagem** (`storyteller.py:299-358`). `is_travel_intent` + `find_travel_destination`. Se o texto parece viagem mas não resolve para um destino, `invalid_travel_message` devolve **recusa canônica antes da LLM** (return imediato, `storyteller.py:306-319`): um destino impossível nunca aparece como chegada na mensagem, no resumo nem na memória. Com destino válido: `travel_cost` (calculado **antes** de mover), `apply_travel`, `advance_factions`, `resolve_faction_completions`, e para primeira visita (fog of war) ou baú curado, `exploration.discover_on_arrival` (achado ambiental). Gera `travel_note` ("O jogador VIAJOU para X..." ou "ENTROU em X (mesma cidade — o tempo não passou)" quando o custo é 0).

**(c) Descanso** (`storyteller.py:359-379`). `apply_rest` (cura, recompõe Entropia, insônia do Devoto mitigada por aliados), 2 períodos de fações, e bloqueio de descanso por clima (`weather_effects(world).rest_block`).

**(d) Cena zerada em viagem.** `npc_layers.reset_scene` limpa `in_scene` de todos os NPCs: "ninguém teleporta junto". Calcula `travel_needs_replan` (viagem entre regiões).

**(e) O tempo passou: encontro ou "respiração" do mundo** (`storyteller.py:404-521`). Só quando houve viagem com custo >= 1 ou descanso.

- Descanso em early-game (nível ≤ 3) em zona não-apex de perigo baixo recupera sem sortear encontro (`recovery_rest_safe`).
- Caso contrário `check_encounter` faz sorteio ponderado (pressão de caça, facção, migração), com dedupe: mesmo template no mesmo local duas vezes seguidas é descartado.
- Com encontro: percepção (`detection_check`, afetada por clima e luz) decide surpresa. `roll_encounter_type` escolhe `combat`/`trap`/`track`/`social`. Reforços e facção dominante sempre são combate.
- **Combate:** retorna imediatamente com `SystemMessage("COMBAT START. ...")`, `combat_target`, `combat_origin_hint` (`combat_origin.from_encounter`), `next="combat_agent"`, `archive_due=True`. A aresta `storyteller → combat_agent` pega isso. **Não há chamada de LLM do narrador nesse caminho**: a emboscada nasce de notas determinísticas, e o `combat_node` narra a cena de entrada.
- `trap` → `resolve_trap` aplica dano e XP; `track` → `resolve_track` atualiza o Codex; `social` → nota de abordagem tensa.
- Sem encontro de combate, `simulate_world` (`world_simulator`, FAST) gera um evento off-screen ("[ECOS DO MUNDO]").

**(f) Contexto e prompt** (`storyteller.py:523-680`). Monta `ContextPack` (`purpose="story"`) com bloco de estado do mundo, memória e lore pública, mais blocos explícitos: `ESTADO_DO_HEROI` (vitalidade e ouro exatos, "se mencionar o saldo use EXATAMENTE esse Ouro"), `AMBIENTE_DE_LUZ`, `CLIMA_GLOBAL`, `FACÇÕES_CONHECIDAS` (só as que o jogador sabe, via `faction_intel.known`), `ENTIDADES_CANONICAS` (ids do `entities.json` que a LLM pode usar), `QUESTS_ATIVAS`, `CAPACIDADES_DO_HEROI` (utilitárias da ficha, gating determinístico), cláusula de "sem interlocutor" quando veio do `npc_actor`, e as cláusulas de prosa (varie a abertura; feche com 2-3 opções `— ...` e `— Ou outra ação.`).

**(g) A chamada** (`storyteller.py:682-684`): `llm.with_structured_output(StoryUpdate).invoke([sys] + messages[-3:])`. Guard: se `not isinstance(update, StoryUpdate)`, constrói um `StoryUpdate` com `_deterministic_story_fallback(...)` a partir das notas do turno (viagem, descanso, mundo, facção, clima, luz). O jogador nunca vê erro de provider.

**(h) Pós-processamento — o motor valida a LLM** (`storyteller.py:692-770`):

- `prevalidate_event_batch` valida **antes** de gravar as propostas de evento. Política **atômica**: se qualquer proposta é inválida, **todo** o payload livre da resposta é posto em quarentena (eventos, impactos de fação, NPCs introduzidos/saídos, quests, itens, beat), a narrativa é substituída por uma versão determinística e acrescenta-se um rodapé `[SISTEMA]`. Só as propostas inválidas ficam na fila, marcadas `_prevalidation_rejected`, para auditoria. A lógica: não deixar a prosa afirmar uma mudança permanente que o processor vai rejeitar logo depois.
- `prose_guard.sanitize_player_facing`, `reconcile_player_gold_claims` (corrige ouro narrado errado), `vary_repeated_opening`, `log_if_repeats`.

**(i) Efeitos mecânicos das propostas válidas:**

- Impactos de facção → `apply_reputation` (Python fixa o delta) → evento `reputation_changed`.
- `beat_completed` só vale se o beat atual é elegível, não houve quarentena; concede `XP_PER_BEAT` apenas a partir do turno 2 (para o narrador generoso não dar XP grátis na criação). Avança `current_step`; esgotou beats → `needs_replan`.
- NPCs introduzidos → `_with_new_npc` (que chama `generate_new_npc`: cache + `librarian` + designer LLM). NPC já conhecido é **relocalizado** para o local atual. `npcs_left_scene` desliga `in_scene`.
- **Itens narrados:** `items_gained` passa por `_is_monetary_claim` (ouro/moedas nunca viram item), `resolve_item_name` (só entra o que existe no `ARTIFACTS_DB`), e item único já reclamado é recusado (`is_unique_available`, `claim_event`). Itens recusados são removidos da prosa (`remove_rejected_claims`) e vão para `rejected_item_claims`.
- `_reward_confirmation` acrescenta "Recompensa confirmada: +N de ouro, ..." calculada do delta real de jogador.
- Missões: `quest_log.register_proposed_quests`, `sync_location_progress`, `sync_action_progress` (que pode marcar `completion_ready` e emitir `quest_completed` com `source="system"`).
- Se o descanso/armadilha deixou o herói morto → `death_pending=True` e evento `player_downed`.

**(j) Marcação de arquivamento:** `archive_due=True` em viagem, descanso, beat concluído, evento pendente ou quest nova.

**(k) Falha geral** (`storyteller.py:1017-1028`): `except Exception` devolve o fallback determinístico; se houve viagem, **a viagem mecânica sobrevive** (retorna `world` e limpa a cena de NPCs).

**O que o storyteller devolve:** `messages` (a narração), `npcs`, `world`, `factions`, `campaign_plan`, `needs_replan`, e condicionalmente `player`, `quests`, `pending_world_events`, `archive_due`, `memory_fact_policy="canonical_only"` (quando houve "ecos do mundo", para o arquivista não promover rumor a fato), `narrative_rejections`, `rejected_item_claims`, `bestiary_knowledge`, `death_pending`. Note que **não define `next`**; a aresta cai em `archivist` porque `next != "combat_agent"`.

### 4.7 `npc_actor` (`agents/npc.py:306`)

**Tier:** FAST, temp 0.8. **Schema:** `NPCResponse` (`dialogue`, `action_description`, `memory_update`, `relationship_change`, `faction_reveals`, `proposed_quests`).

Árvore de decisão antes da LLM:

1. **Sem alvo:** tenta o primeiro NPC em cena (`npcs_in_scene`). Se não há ninguém: `return {"next": "storyteller", "npc_fallback_hint": <texto>}`. A aresta `npc_actor → storyteller` entra, e o narrador cria a ausência + gancho concreto via `build_social_direction` (conexão adjacente de menor perigo + `public_objective`). Resposta seca "Ninguém responde" aposentada.
2. **NPC conhecido mas fora de cena e fora da party:** resposta determinística, **zero LLM**: "X não está aqui. Foi visto pela última vez em Y."
3. **NPC inexistente:** `generate_new_npc` na hora.
4. **Comandos de party** (`party.detect_party_command`): recrutar, dispensar, esperar, seguir são resolvidos em Python (`recruitment_decision`, `recruit`, etc.). A LLM nunca decide se o NPC aceita.
5. Só depois monta o prompt, com persona, traços já revelados, `MEMORIA` (3 últimas linhas), `SUA_ULTIMA_FALA` (anti-repetição verbatim), memória relevante vetorial + lore pública via `ContextPack(purpose="npc", npc_id=...)`, facções do mundo (com a regra "um camponês não conhece planos de cultos distantes"), orientação sobre missão (`_mission_hint_block` quando a pergunta casa `_MISSION_RE`), e a regra de ouro **"NÃO SEJA UMA WIKIPÉDIA"** com filtro de conhecimento.

Pós-processamento: `isinstance(res, NPCResponse)` senão `TypeError` (e o `except` externo devolve `"..."`). Limpa preâmbulo meta, aspas externas, varia a abertura. Atualiza relação (clamp 0-10), memória do NPC com a **experiência observável** (fala do jogador e resposta), nunca com o `memory_update` livre da IA. `tick_interaction` pode revelar um traço. Grava no índice vetorial do NPC (`add_npc_memory`, com `make_memory_fact(provenance="npc_claim")`); falha entra em `pending_npc_memory` (retry pelo arquivista). Reveals de facção viram `faction_intel` por `apply_faction_reveal`. Quests propostas recebem `origin_name`/`origin_entity_id` carimbados **em Python**, não confiados à LLM.

Retorna `messages` com o formato `**Nome:** "fala"\n*(ação)*`, `npcs`, `faction_intel`, `archive_due=True`, `memory_fact_policy="canonical_only"` (conversa livre não vira fato global), além do ledger de memória.

### 4.8 `combat_agent` (`agents/combat.py:607`)

É um nó fino sobre `services/conflict_orchestrator` (`orch`), `conflict_scene` (`cs`), `conflict_summary` (`summ`), `encounter_preparation` (`prep`), `death_flow`, `party`. Usa a LLM em **quatro** pontos, todos de identificação ou narração:

| Ponto | Tier | Schema | Função |
|---|---|---|---|
| `_spawn_v4_enemies` (`combat.py:162`) | C | `EncounterScanner` | Quais inimigos e quantos a partir da narrativa |
| `generate_new_enemy` (bestiário) | F ou S | `EnemySchema` | Conceito narrativo da criatura nova |
| `_parse_turn_declaration` (`combat.py:341`) | C | `PlayerMove` (local) | Fala livre → `TurnDeclaration` |
| `_narrate` (`combat.py:561`) | F | texto livre | Prosa do round a partir do log |
| `death_flow.generate_scar` | S | (no serviço) | Cicatriz obrigatória após queda |

**Fluxo do nó**, em ordem:

1. **Inconsciente e sem combate ativo:** recusa iniciar conflito (`combat.py:622`).
2. **Preparação (1x):** se a última mensagem é `SystemMessage` contendo "COMBAT START" ou não há cena, spawna inimigos (só se não vierem já em `state["enemies"]`), monta aliados (party ativa + `scene_allies`, que são NPCs amigos em cena que viram aliados transitórios), constrói a cena (`_prepare_scene`) com zonas mínimas **em Python**, sem um segundo invoke FAST, aplica orçamento de encontro (`encounter_budget.clamp_encounter`/`fill_encounter`), registra no bestiário do jogador, materializa a origem causal, define `instance_id = game_id:epoch:session_action`.
3. **Sem inimigos ativos:** vitória. Constrói `ConflictSummary` (sem LLM), `next="loot"`, `combat.active=False`.
4. **Declaração do jogador:** `state["combat_declaration"]` (vem da UI/harness, `_apply_action_options` em `api.py:2327`) tem prioridade; senão `_parse_turn_declaration`, que resolve **localmente** nomes de Carta preparada e de consumível presentes no texto (chips da UI), e só então chama CLASSIFY. Guard: `isinstance(res, PlayerMove)`; qualquer falha → ataque básico no primeiro inimigo.
5. **Fuga:** regex em PT (`fuj|fugir|escap|retir|recu|corr`) ou `combat_flee_attempt` do router ou `declaration.kind == "flee"`. `_attempt_flee` usa o `chase` determinístico; há teto de tentativas (`_enforce_flee_attempt_limit`, 6 seguidas). Se o jogador não pode fugir por condição (`_can_attempt_flee`), a rodada consome a ação.
6. **Rodada:** `orch.run_round(scene, actors_by_id, sides, round_state, declarations, prepared_abyss, initiator, rng)`. É aqui que vivem iniciativa, 2d10, reações, dano, ferimentos, IA tática dos inimigos. `rng = random` global, reprodutível por seed do harness.
7. **Pós-rodada:** espelha vitais (`_mirror_vitals`), gera cicatriz via SMART se necessário, registra kills no bestiário, calcula `combat_over`/`player_dead`/`victory`, atribui XP determinístico (`pg.xp_for_kills`, não em simulação), calcula consciência pós-combate.
8. **Narração:** `player_dead` → `_narrate_fall` (template). Simulação → texto mecânico sem LLM. Caso contrário `_narrate` (FAST, **só** com base no log, "não invente dano"). `prose_guard.openings_clause` pede variação. Falha/`is_fallback` → log mecânico como prosa. Se o combate acabou, `summ.narrative_or_fallback` impõe os fatos canônicos do resumo.
9. **Resultado:** `messages`, `player`, `enemies` (vazio se terminou), `combat` (com `last_player_action` canônico para o harness, `last_reactions`, `last_tactics`), `next="loot"` só na vitória fora de simulação, `archive_due`, `party`, `combat_declaration=None` (consumida), `conflict_summary`. Morte: `death_pending=True`, evento `player_downed`, `combat.death_context`. Fuga bem-sucedida + destino válido: `_apply_flee_travel` move o mundo no mesmo turno.

**Exemplo.** Jogador usa o chip "Golpe Sombrio" (nome de uma Carta preparada). `_parse_turn_declaration` encontra o nome em `prepared_cards`, devolve `TurnDeclaration(kind="card", card_id=..., target_id=<padrão>)` sem gastar CLASSIFY. Cartas benéficas (cura, proteção) herdam o próprio jogador como alvo (`_default_card_target`), não o primeiro inimigo.

### 4.9 `loot_agent` (`agents/loot.py:138`)

Entra por duas portas: depois de vitória em combate (`combat_agent → loot_agent`) ou pela rota `LOOT` do router. Três modos, definidos por `loot_source`:

- **SHOP/CRAFT:** `_parse_trade_intent` (CLASSIFY, `TradeIntent{mode, item_ref, qty}`). Antes da LLM, regras de palavra-chave determinam o modo (vendo/vender, forjo/criar, compro/comprar, ou "consultar" → `observe`, que apenas lista cotações sem transacionar). Guard `isinstance(res, TradeIntent)`; um modo explícito detectado em Python **sobrescreve** o que a LLM devolveu. Execução em `economy.execute_trade`/`execute_craft` (preço, estoque, receitas e raridade determinísticos). Narra com `_narrate` (FAST) e anexa rodapé `[SISTEMA] +1x item | Ouro -X (total Y)`. Registra `last_economy_action` com antes/depois de ouro, inventário e estoque, consumido pelo harness do comerciante.
- **TREASURE:** raridade/item/ouro saem de `economy.roll_loot(region_id, danger, rng, projection, bestiary_knowledge, turn, boost)`. O `danger` vem de `conflict_summary_service.loot_context` (nível do encontro). A LLM narra apenas a atmosfera; `_validated_narrative` descarta a prosa livre se já existe loot aplicado e usa o resumo canônico (impede "inventar" um item na prosa).
- Itens únicos geram evento `unique_item_claimed` (`economy.claim_event`).

Sempre zera `loot_source` e define `archive_due=True`.

### 4.10 `archivist` (`agents/archivist.py`)

**Tier:** SMART, temp 0.3. **Schema:** `MemoryUpdate` (`new_summary`, `important_facts`, `chronicle_entry`). `important_facts` tem um `field_validator(mode="before")` que coage dicts (`{fato, type}`, `{role, content}`) a strings e descarta o que parece transcrito ou passa de 320 caracteres: era o motivo de o arquivista perder fatos no LLM real.

`archive_node` (`archivist.py:200`) é um wrapper em volta de `_archive_node`:

1. `process_pending_events(state)` (`services/event_processor.py:208`) roda **todo turno**, antes da cadência. Valida cada proposta de `pending_world_events` contra o grafo/projeção, aplica ao `event_log` e à `world_projection`, cria milestones de crônica, concede XP/ouro de quest. Nunca levanta; proposta inválida vira linha em `event_rejections`.
2. `guard_current_messages` e `build_evidence` fixam um snapshot de evidência **pós-eventos**.
3. Roda `_archive_node` e valida o `narrative_summary` e a prosa da crônica com `validate_narrative`. Se mensagens mudaram, devolve `Overwrite`.

`_archive_node`:

- **Cadência** (`_should_archive`, `archivist.py:183`): só chama a LLM se `archive_due`, ou há `conflict_summary`, política `canonical_only`, fatos pendentes ou NPC-memória pendente, ou passaram 10 turnos desde a última rodada. Turnos triviais custam zero SMART.
- Se há eventos novos mas fora da cadência, não força SMART: **enfileira** o registro canônico em `pending_memory_facts` e devolve (a cópia derivada no RAG sai no próximo arquivamento).
- **Retries antes de gerar candidatos novos:** `pending_memory_facts` (fatos de sessão) e `pending_npc_memory` (índices por NPC). Cada sucesso sai da fila; falha mantém a fila e devolve cedo com `rag_persistence_error`.
- **Dedupe de conflito:** `conflict_summary` com `conflict_id` já em `consumed_conflict_ids` é limpo sem LLM.
- **Proveniência:** registros `canonical_event` (eventos novos, fatos do `ConflictSummary`, fatos de política) são autoritativos. Fatos livres da LLM entram como `inference` com confiança especulativa. Em turno de conflito ou `canonical_only`, **só** o contrato canônico é persistido: a prosa livre não pode reintroduzir um fato recusado.
- **Grounding do resumo:** `sanitize_location_grounding`, `sanitize_inventory_grounding`, `sanitize_npc_identity_grounding` removem contradições com o mapa, inventário mecânico e aparência de NPC em cena.
- Prompt: resumo anterior + 6 últimas mensagens + fatos canônicos do conflito + âncoras de localização/inventário/identidade.
- **Guard:** se `not isinstance(result, MemoryUpdate)`, usa `_extract_summary_plain` (um `llm.invoke` sem schema) para manter ao menos o `narrative_summary`; se isso também falha, mantém o estado e devolve só os `event_updates`. Exceção geral → `dict(event_updates)`.
- A crônica ganha um capítulo-entry `conflict` (fatos canônicos) e, se permitido, uma entry `prose` do menestrel.
- **Atomicidade do contrato canônico:** se a persistência RAG falha e havia `conflict_summary` ou `canonical_only`, o nó **não consome** o resumo nem escreve crônica; reforça `archive_due=True` para retry.

Retorna `memory_facts`, `pending_memory_facts`, `memory_rejections`, `memory_promotions`, `rag_persistence_error`, `narrative_summary`, `chronicle`, `archivist_last_run`, `archive_due`, mais tudo que `process_pending_events` produziu (`event_log`, `world_projection`, `quests`, `player`, etc.).

### 4.11 `turn_finalizer` (`agents/turn_finalizer.py`)

Último nó. **Sem LLM.**

1. `guard_current_messages`: reaplica `validate_narrative` às mensagens de IA deste turno (desde a última mensagem humana). Frase a frase, remove alegações explícitas de contradição crítica (morte falsa do jogador, localização, posse de item, identidade de NPC, segredo não revelado, ouro/XP que não bate com o delta). Citações, falas e frases qualificadas ("talvez", "dizem que", "se") ficam. O `EvidenceSnapshot` (`narrative_evidence.py:38`) é construído apenas do estado confirmado, nunca de propostas pendentes.
2. `transition_readiness`: se o estado não está pronto (por exemplo um `last_stand` sem dono) e não é um dos três limites aceitos (`ready`, `combat_active`, `transition_death_pending`), **levanta `RuntimeError("turn_boundary_not_ready:...")`**. É uma defesa dura contra salvar um estado jogável sem o dono da transição.
3. `finalize_outcome` (`turn_outcome.py:75`): calcula `gold_delta`, `xp_delta`, `level_delta`, `items_gained`, `quests_completed`, `event_ids` comparando o `turn_baseline` do guard com o estado final. Gera `receipt_id` (SHA-256 truncado) e `player_message` = última mensagem de IA, com marcadores reservados `[RESULTADO]` removidos (nunca confiados a modelo) e linhas negativas ("nada novo foi obtido") apagadas se houve ganho, depois recibo `[RESULTADO] +N ouro · +N XP · +1 item ...` anexado.
4. Retorna `last_turn_outcome` (e `messages=Overwrite` + `evidence_rejections` se reescreveu).

`player_facing_message(state)` (`turn_outcome.py:94`) é a função que CLI e API usam para decidir o texto final: bloqueio do guard → recibo do turno → última mensagem de IA.

### 4.12 Serviços auxiliares de agentes

- **`bestiary.generate_new_enemy`** (`agents/bestiary.py:188`): cache-first via `librarian.find_existing_entity`; se achou com ficha v4, reidrata a vitalidade e devolve; se legado, rematerializa. Senão: RAG de lore + designer LLM (`EnemySchema`, tier SMART para dragon/lich/boss/god/lord, senão FAST). O prompt proíbe números mecânicos ("a ficha é calculada exclusivamente pelo motor Python"), e `materialize_enemy_concept` converte conceito → ficha determinística por categoria/arquétipo/nível do encontro. Guard: `isinstance(res, EnemySchema)`; falha → ficha fallback `fallback_<slug>`.
- **`librarian.find_existing_entity`** (`agents/librarian.py:15`): deduplicação semântica em 4 camadas, com a LLM só na última. (1) lista vazia → `None`; (2) slug exato; (3) pré-filtro por sobreposição de tokens e `difflib` (sem candidato plausível = entidade nova, sem LLM); (4) CLASSIFY `EntityMatch`. Observação: o acesso a `result.match_found` está dentro de `try/except`, mas sem `isinstance`; o guard funciona porque `AIMessage.match_found` levanta `AttributeError`, capturado.
- **`world_simulator`** (`agents/world_simulator.py`): `propose_world_pulse` (FAST, `WorldPulse{rumor, fact, danger_shift}`) é uma função pura de proposta; `apply_world_pulse` aplica em Python (clampa `danger_shift` a ±1 e perigo a [1,4], só a consequência realmente aplicada vira fato de memória; `pulse.fact` é descartado como prosa não verificada). `simulate_world` compõe os dois e grava a intenção de memória no RAG da sessão.

---

## 5. Serviços de pipeline em detalhe

### 5.1 `services/turn_execution.py`

- `execute_graph(graph, state, progress=None)`: sem `progress`, `graph.invoke(state)`. Com `progress`, itera `graph.stream(state, stream_mode=['updates','values'])`, repassa cada chunk ao callback e guarda o último `values` como estado final. Falta de `values` → `RuntimeError`.
- `operation_scope(coordinator, claim)`: gerenciador de contexto que mantém o lease vivo com `keep_lease_alive` (heartbeat a cada `lease_seconds/4`) e, em exceção, chama `coordinator.fail(claim, ...)`, engolindo erros porque a posse pode já ser de outro worker. Só faz algo no perfil durável (Postgres); no perfil legado `claim` é `None`.

### 5.2 `services/turn_effects.py`

`TurnEffects` é um **outbox por requisição**, via `ContextVar` (`_effects`). Guarda intenções de memória (`MemoryIntentCollector`) e escritas diferidas. Seu `flush` só é chamado dentro do commit transacional do perfil Postgres: confere que `game_id` e `principal` de cada intenção batem com os do commit (`effect_scope_mismatch`), anota `commit_version` e `timeline_epoch`, e acrescenta `:epoch:N` ao `document_id` para que fatos de uma linha do tempo descartada não colidam. A API envolve `_run_turn` em `effect_scope()` (`api.py:2389`). No perfil legado, a escrita no RAG é direta, não passa por este outbox.

### 5.3 `services/structured_outputs.py`

Schemas Pydantic de **proposta**: `ProposedWorldEvent` (tipo de um `Literal` fechado `EventType`, `actor_id`, `target_id`, `detail`, `payload` dict aberto) e `ProposedQuest`. Os tipos `level_up`, `subclass_chosen`, `class_apex_unlocked`, `player_died`, `player_downed`, `unique_item_claimed`, `unique_item_lost` estão no `Literal`, mas o comentário deixa claro que o LLM não pode produzi-los de forma útil: `validate_proposal` exige `source` específico (`progression`, `combat`, `engine`), e o schema de proposta do LLM **não tem campo `source`**, então o `model_dump` nunca o carrega. É a defesa por estrutura: a LLM só consegue propor `npc_killed`, `secret_revealed`, `location_control_changed`, `quest_completed`, `faction_relation_changed`, `reputation_changed`, `route_blocked`, `route_cleared`, e mesmo esses passam pelo validador contra o grafo.

### 5.4 `services/input_normalization.py`

Uma única função: `optional_entity_ref(value)`. Faz `strip` e converte sentinelas de ausência (`null`, `none`, `nil`, `n/a`, `undefined`, `nenhum`, `ninguém`) em `None`. Usada no router (alvo, contexto de loot) e no `npc_actor`. Resolve o bug em que providers devolviam a string `"null"` e ela era materializada como NPC.

### 5.5 `services/social_direction.py` e `services/objectives.py`

- `objectives.public_objective(plan, quests, world)` deriva o objetivo **público**: se há side quest ativa, usa a descrição dela; senão "Investigue os acontecimentos em {local}. Arco atual: {arc_title}." **Nunca copia beat nem clímax** do `CampaignPlan`, porque são privados do diretor. A API usa isso para a UI; o `npc_actor` para orientação; o `social_direction` para o gancho.
- `social_direction.build_social_direction(state)` escolhe, entre as conexões do local atual, a de **menor perigo** (desempate por nome) e produz "Não há interlocutor aqui. O destino conectado X é uma direção concreta...". Sem conexões, "dê uma pista ambiental útil".

### 5.6 `services/continuity.py`

Quatro funções puras: `normalize`, `advance_action` (usado pelo `turn_prepare`), `mark_checkpoint` e `after_restore`. Essa última é a que conta a história: ao restaurar de uma morte, grava um registro em `death_history` (época, ação da sessão, turno da morte, turno restaurado, turnos canônicos perdidos, local, causa, listas `retained`/`reverted` em português), **incrementa `timeline_epoch`** e ajusta `last_checkpoint_turn`. `session_action_count` não regride. A UI usa isso para dizer ao jogador exatamente o que se manteve e o que foi revertido. Limite de 32 mortes no histórico.

### 5.7 `services/narrative_evidence.py`

Guarda conservadora, "não é um oráculo de verdade". Só estado e eventos **confirmados** são evidência. `_reason(sentence, evidence)` testa, em ordem: segredo estritamente não revelado (mesmo entre aspas); depois, se a frase é qualificada ou citação (`"`, `“`, `—`), aceita; depois morte falsa do jogador, contradição de localização/região, posse de item, identidade de NPC, "você chegou a X" onde X não é o local atual, e "você ganhou N ouro/xp" cujo N diverge do delta do baseline. Razões nunca registram o texto privado, só o motivo e o turno. Se tudo for removido, substitui por "Você observa a cena e pondera seu próximo passo."

### 5.8 `services/presentation_history.py`

Histórico estável para o cliente, **separado do transcript curto da LLM**. `record_history` gera um id determinístico `sha256(game_id:epoch:turn:role)[:24]` e acrescenta linhas `player` e `narrator` sem duplicar. O `type` da linha do narrador vem de `message_kind` (`COMBAT`/`NPC`/`LOOT`/`STORY`) a partir de `last_routed_intent` ou `next`. `history_page` pagina com cursor `época:offset` e recusa cursor de outra época (`history_cursor_stale`), de modo que um restore não mistura linhas de linhas do tempo diferentes. Saves antigos sem histórico caem no `legacy:` reconstruído de `messages` com `partial_history=True`.

### 5.9 `services/prologue.py`

Usado só na criação (`POST /game/prologue` e `POST /game/new` com `scenario`).

- `build_start_scenario(char_input)`: SMART, temp 0.7, `StartScenario{prologue, opening_scene_brief, arc_title, beats, climax, seed_npcs}`. Guard `isinstance` + `try/except`: em qualquer falha devolve `fallback_scenario` (template determinístico). **Nunca levanta**, nunca dá 500. Retorna também o flag `mock`.
- O schema voltado à LLM **não tem `max_length` duro**: o smoke real mostrou que DeepSeek/Groq/Anthropic escrevem acima do limite e o validador derrubava todos os candidatos. Limites viram dica na `description`, e `_normalize` trunca em Python. Os limites estritos (`StartScenarioIn`, `SeedNPCIn`) vivem só na borda da API: excedente de cliente vira 422.
- `scenario_to_state_seed(scenario, char_input, start_loc_id)`: função pura que traduz o cenário aprovado em seed: `campaign_plan` pessoal (beats `pending`, `current_step=0`), NPCs com `initial_relationship` por mapa fixo (`hostil=2`, `neutro=5`, `aliado=8`), já `in_scene` e `known_by_player`, a `opening_message` que substitui a `HumanMessage` inicial, e `chronicle_title`.

**Padrão a replicar em todo schema novo:** tamanho vira dica e Python trunca; o MockLLM não detecta esse tipo de erro.

---

## 6. Criação de personagem

### 6.1 `character_creator.create_player_character` (`character_creator.py:270`)

Monta a ficha em ordem fixa:

1. Dados oficiais da classe (`_get_class_data` de `classes.json`).
2. **Virtudes** da escolha do jogador (validada por `validate_virtude_distribution`) ou da recomendação da classe.
3. Entropia: `base_stats.entropy + level_gains.entropy * (level-1)`.
4. **Flavor via SMART** (`PlayerFlavorSchema`: inventário temático da região + 2 habilidades). A LLM **não** define Virtudes, vitalidade nem cartas. Guard: `if stats:` + `isinstance(dumped, dict) and "inventory" in dumped`; senão inventário `["Kit Básico"]`. Esse guard mostra o padrão de leitura defensiva: o `model_dump()` de um `AIMessage` não tem `inventory`.
5. Cartas iniciais (`_resolve_starting_cards`) substituem integralmente `known_abilities`.
6. `gamedata.sync_player_vitals(sheet, heal_to_full=True)`: vitalidade e espaços de Ferimento derivados de Corpo.
7. Inventário estruturado: `starting_equipment` da classe + itens livres do flavor via `add_item`.
8. Traits raciais (`apply_racial_traits`), `backfill_inventory` (auto-equipa uma vez), defesa e bônus de ataque derivados de Virtude.

`use_llm_flavor=False` existe para testes e harness determinístico.

### 6.2 `/game/new` (`api.py:1848`) e o CLI

A API e o wizard CLI (`game_engine.create_character_wizard`, `game_engine.py:170`) montam um `initial_state` quase idêntico, com mensagens iniciais `[SystemMessage, HumanMessage("Descreva o cenário ao meu redor...")]` e `next="storyteller"`. Diferenças: a API acrescenta `processed_action_ids`, ledgers visuais, `continuity`, `art_*` e o `scenario` opcional; o CLI não inicializa `continuity` (o `turn_prepare` cria via `normalize`).

A criação **roda o grafo uma vez** (`api.py:1973`). Como a última mensagem é humana, o router classifica (normalmente STORY), o `campaign_manager` gera o primeiro plano (turno 1), e o storyteller narra a cena de abertura. A criação então zera `session_action_count`: a abertura posiciona a linha do tempo mas não é ação do jogador. Depois grava o save e **o checkpoint inicial** (para que a morte sempre tenha ponto de retorno).

---

## 7. O fluxo de UM turno, ponta a ponta (API)

Cenário: jogador de nível 2 em Nova Arcádia digita **"Vou para a Floresta Cinzenta"** (viagem). O cliente chama `POST /game/action` com `action_id` UUID. Os números de linha referem-se a `api.py` salvo indicação.

**1. Borda HTTP.** Middlewares de sessão, correlação e rate limit (`api.py:87`, `123`, `437`). `game_action` chama `_execute_action(req)` (`api.py:2463`).

**2. Lock e carga.** No perfil legado, `_game_lock(game_id)` (RLock por jogo) serializa turnos do mesmo jogo. `load_game_state(_resolve_save_file(game_id))` desserializa o JSON (mensagens viram objetos LangChain, migrações por `schema_version`, hoje 8, `persistence.py:59`).

**3. Idempotência e operação.** `_begin_turn_operation`: no perfil durável exige `action_id`, procura recibo prévio e, se existir, devolve a resposta guardada sem reexecutar; senão `claim` com lease. No legado retorna `(None, "", None)`. Depois, `_action_already_processed(state, action_id)`: se o UUID está em `processed_action_ids`, devolve `format_response` do estado atual sem rodar o grafo (retry seguro após confirmação perdida).

**4. Gates de API.** `_reject_memorial` (409 se `game_over`), `_reject_archived`, 409 se `death_pending`. `_apply_action_options`: se há combate ativo, traduz `card_id`/`maneuver`/`action_kind`/`target_id`/`reaction_card_id` da UI em `state["combat_declaration"]` e `player_reaction_card_id`. Fora de combate, não faz nada.

**5. `_run_turn` → `_run_turn_collected`** (`api.py:2386-2395`), dentro de `effect_scope()`.

   a. `_append_player_input`: acrescenta `HumanMessage(input_text)` e mantém no máximo 20 mensagens (o CLI usa 15).

   b. Abre acumuladores de custo/tentativas LLM em `ContextVar`s e tira um `deepcopy` do estado (`previous_state`) para comparar arte/visual e checkpoint.

   c. `execute_graph(game_graph, state, progress=...)`:

   | Ordem | Nó | O que acontece neste exemplo |
   |---|---|---|
   | 1 | START | `game_over`/`death_pending`/`archived` falsos → `action_guard` |
   | 2 | `action_guard` | jogador `active` → `ok`; grava `turn_baseline` (ouro, XP, inventário, quests, event_ids) |
   | 3 | `turn_prepare` | `turn_count` 17→18; `session_action_count`+1; `turn_prepared=True` |
   | 4 | `campaign_manager` | `_should_replan`: local mudou para outra região? `_same_region(plan.location, current_location)` ainda compara com o local *antes* de viajar, então sim → mas o storyteller só altera o mundo depois; na prática o replan por região é marcado em `travel_needs_replan`. Se `turn_count - last_planned_turn < 15` e há beats, devolve o plano sem LLM |
   | 5 | `dm_router` | `_EXPLICIT_STORY_RE` casa "vou para" → STORY **sem LLM**; payload completo com transitórios zerados; `world` descartado |
   | 6 | `dispatch` | `turn_prepared=False`; aresta lê `next="storyteller"` |
   | 7 | `storyteller` | `is_travel_intent` + `find_travel_destination` resolvem "Floresta Cinzenta"; `travel_cost`, `apply_travel` (marca `visited`, move `current_location_id`, avança o relógio), facções avançam, `discover_on_arrival` (1ª visita → achado), `reset_scene` limpa NPCs. `check_encounter` rola; suponha que não há combate: `simulate_world` (FAST) gera um rumor. Monta o `ContextPack`, chama FAST `StoryUpdate`. LLM devolve narrativa, `introduced_npcs=["Guarda-florestal Ilse"]`, `beat_completed=false`. `prevalidate_event_batch` nada a validar. `generate_new_npc("Guarda-florestal Ilse")` (cache miss: `librarian` sem candidato, designer LLM) e entra em cena. `_reward_confirmation` não adiciona nada se não houve ganho. `archive_due=True` (viagem) |
   | 8 | aresta pós-storyteller | `next != "combat_agent"` → `archivist` |
   | 9 | `archivist` | `process_pending_events` (vazio → `{}`); `_should_archive` → True (`archive_due`); SMART `MemoryUpdate` gera resumo novo + fatos; fatos viram `inference`; `persist_records` grava no FAISS da sessão (`add_memory_to_session` com metadata); resumo passa por grounding; crônica pode ganhar linha de menestrel; `archivist_last_run=turno` |
   | 10 | `turn_finalizer` | revalida mensagens de IA; `transition_readiness` pronto; `finalize_outcome`: `gold_delta`/`xp_delta` do `turn_baseline` — um baú achado na chegada entra aqui como `+N ouro`; gera `last_turn_outcome.player_message` |
   | 11 | END | |

   d. De volta à API: `resolve_turn_visual_state` e `_enqueue_turn_art` decidem retrato/cena/arte; `_mark_action_processed(new_state, action_id)` insere o UUID no ledger; `_prepare_checkpoint` decide checkpoint (`should_checkpoint`: a cada 10 turnos ou ao entrar em zona segura, e só se `transition_readiness` estiver `ready`; atualiza `continuity.last_checkpoint_turn`); `_prepare_chronicle_derivatives` (digest extrativo no legado); `format_response` monta o `GameResponse` (HUD, mapa, quests, combate, mensagem = `player_facing_message`).

   e. `_commit_turn` (`api.py:2254`): `record_history` acrescenta as linhas player+narrator ao histórico estável; no legado, `save_game_state(state)` (`persistence.py:636`: `_state_to_save_data` serializa mensagens e acrescenta `schema_version`, grava de forma atômica `_atomic_write_json` com temp + `fsync` + `os.replace`, em `saves/<uuid>.json`) e, se houver checkpoint, `checkpoints.maybe_write` grava o `*.checkpoint.json` e a árvore FAISS da sessão. No perfil durável, `turn_coordinator.commit_game` faz tudo numa transação Postgres com recibo, custo (`llm_pricing.turn_cost`) e `flush` do outbox de efeitos.

   f. `_log_turn`: linha JSON `rpg.turn` com rota, latência, eventos aplicados/rejeitados, custo e eventos de LLM.

**6. Resposta.** `GameResponse` ao cliente. Em falha de qualquer etapa: métrica de erro, `coordinator.fail`, log, `HTTPException(500)` genérica (sem vazar detalhe interno).

### 7.1 Variante SSE (`POST /game/action/stream`)

O mesmo `_execute_action`, mas dentro de uma **thread worker** (`_stream_turn`, `api.py:2546`): ela é dona do lock, da execução e do save, então um cliente que desconecta não corta o turno ao meio. O gerador consome uma `queue`: para cada chunk `updates` do LangGraph, emite `phase {node, status: "done"}` (exceto `action_guard`, `turn_prepare`, `dispatch`, `turn_finalizer`) e, se o nó foi `dm_router`, `route {route}`. No final, `visual`, a narração em pedaços de 80 caracteres (`narrative`, `done:false` … `done:true`) e o `state` completo. O texto **não** é streamado token a token do provider: é fatiado da resposta pronta. `ping` a cada 10 s evita timeout de proxy. O `action_id` torna seguro o fallback para POST.

### 7.2 Variante CLI (`game_engine.run_game_loop`, `game_engine.py:246`)

Sem API: `load_game_state()` ou wizard; boot (`app.invoke(state)` se a última mensagem é de sistema ou há só 2 mensagens) + `save_checkpoint`; loop de input com comandos locais (`sair`, `status`, `equipar X`, sem gastar turno); acrescenta `HumanMessage` (corta em 15), `app.invoke(state)`, imprime `player_facing_message(state)` com cor por heurística, resolve escolhas de nível pendentes (`_resolve_pending_choices`), `_save_or_raise(state)`, trata `death_pending` com o menu `[1] Continuar do checkpoint [2] Aceitar o fim` via `checkpoints.resolve_death_choice`, e `should_checkpoint`/`maybe_write` na cadência. O `except Exception` do loop imprime "Erro Crítico" e **continua** o loop, mas o estado do turno falho não foi salvo, o que é uma diferença de robustez em relação à API.

---

## 8. Fluxos alternativos importantes

### 8.1 Emboscada durante viagem (storyteller → combat no mesmo turno)

Mesmo comando de viagem, mas `check_encounter` devolve `enc` e `roll_encounter_type` dá `combat`. O storyteller retorna imediatamente (`storyteller.py:463-490`) com `SystemMessage("COMBAT START. <flavor> <sur_txt>")`, `combat_target`, `combat_origin_hint`, `next="combat_agent"`, o mundo já movido e `world.encounter_surprise` ("player" se percebeu, "enemy" senão). A aresta condicional manda para `combat_agent`, que vê `is_start`, spawna inimigos, monta cena e resolve a primeira rodada. O jogador recebe no mesmo response a chegada e o primeiro round, sem nenhuma chamada FAST de narrador exploratório. Um herói de nível ≤ 2, com vitalidade cheia, fora de apex, recebe iniciativa da primeira rodada mesmo se foi surpreendido (`_early_game_reaction_initiator`).

### 8.2 Combate em andamento

Todo input vira rota COMBAT pelo `_combat_gate`, qualquer que seja o conteúdo. Conversa com NPC ou saque durante combate são bloqueados (o combate narra). Viagem vira fuga. `combat_node` incrementa `round`, zera `idle_turns`, e o texto do jogador vira `TurnDeclaration` (UI ou CLASSIFY).

### 8.3 Morte e tela de morte

Queda letal: `combat_node` seta `death_pending=True`, evento `player_downed`, `combat.death_context`. O START barra o próximo turno. O cliente chama `POST /game/death {choice}` (`api.py:2497`): `continue` restaura o checkpoint (ou o início da sessão) com `continuity.after_restore` incrementando `timeline_epoch`; `accept` marca `game_over` e escreve `player_died` + milestone na crônica. A suíte e o CLI usam `checkpoints.resolve_death_choice` diretamente.

### 8.4 Jogador inconsciente após combate

O combate termina, `post_combat_consciousness` pode deixar o herói inconsciente. No turno seguinte, o `action_guard` bloqueia qualquer coisa que não seja descanso/socorro. Quando passa como `recovery`, o router força STORY, o storyteller troca o texto por "Descanso e aguardo socorro." e roda `apply_rest`.

### 8.5 Rota NPC sem interlocutor

Router devolve `npc_actor` sem alvo e sem NPC em cena. `npc_actor` devolve `{"next": "storyteller", "npc_fallback_hint": <texto do jogador>}`. A aresta leva ao `storyteller`, que injeta `_npc_fallback_clause` (solidão, sem inventar NPC, gancho de destino conectado). Observação: o hint **persiste** em `state["npc_fallback_hint"]` até ser sobrescrito, e o `storyteller` o lê sempre via `scene_state`. Como o router e o `npc_actor` só o escrevem neste caminho, vale conferir se ele é limpo depois (não achei limpeza explícita no storyteller). Isso pode repetir a cláusula "SEM INTERLOCUTOR" em turnos seguintes até outro `npc_actor` sobrescrever; é uma suspeita, não verificada com teste.

### 8.6 Laboratório de combate

`combat_simulation.enabled` altera o grafo e os nós: `campaign_manager` só preserva o plano; `combat_agent` não spawna via LLM nem narra via LLM, não concede XP, não gera eventos de mundo, e a aresta pós-combate vai a END, pulando loot, archivist e finalizer. Texto livre vira ataque básico (`_apply_action_options`).

---

## 9. Mapa de LLM por nó (custo e risco)

| Nó / função | Tier | Schema | Chamadas por turno típico | Fallback quando a LLM falha |
|---|---|---|---|---|
| `campaign_manager._build_plan` | S | `CampaignPlanModel` | 0 (1 a cada ~15 turnos; até 2 se beat em inglês) | Plano de 3 beats pt-BR; mantém plano antigo se inglês persiste |
| `dm_router` | C | `RouterDecision` | 0 a 1 (atalhos determinísticos cobrem combate, descanso, viagem, recuperação) | `STORY` |
| `storyteller` | F | `StoryUpdate` | 1, mais 1 FAST do `simulate_world` em viagem/descanso, mais NPCs novos | Narração determinística a partir das notas do turno |
| `generate_new_npc` | F (S p/ king/lord/etc.) + C (librarian) | `NPCSchema`, `EntityMatch` | por NPC introduzido, com cache | Ficha `fallback` genérica v4 |
| `npc_actor` | F | `NPCResponse` | 1 | `"..."` |
| `combat_node` spawn | C (+ bestiário F/S) | `EncounterScanner` | 1 no início do combate | `Inimigo Sombrio` |
| `combat_node` parse | C | `PlayerMove` | 0 quando UI declara; 0 se nome de Carta/item no texto; senão 1 | Ataque básico no 1º inimigo |
| `combat_node` narração | F | texto livre | 1 por round | Log mecânico como prosa |
| `death_flow.generate_scar` | S | (serviço) | só em queda | determinístico no serviço |
| `loot_node` parse | C | `TradeIntent` | 0 a 1 (SHOP/CRAFT) | Heurística por palavra-chave |
| `loot_node` narração | F | texto livre | 1 | Texto mecânico |
| `archivist` | S | `MemoryUpdate` | 0 a 1 por turno (cadência) | Resumo em texto plano; senão estado mantido |
| `world_simulator` | F | `WorldPulse` | 1 em viagem/descanso | Proposta `degraded`, sem rumor |
| `character_creator` | S | `PlayerFlavorSchema` | 1 na criação | `Kit Básico` |
| `prologue` | S | `StartScenario` | 1 no preview | Cenário template |

Um turno de exploração em cidade sem evento custa tipicamente 1 CLASSIFY (router) + 1 FAST (narrador); o arquivista só entra quando algo relevante marcou `archive_due` ou a cada 10 turnos.

---

## 10. Observações, riscos e inconsistências encontradas

Itens abaixo são achados da leitura. Os marcados "verificado" têm evidência direta no código lido; os marcados "suspeita" não foram confirmados por execução.

1. **Verificado: campos mortos em `GameState`.** `active_plan_step`, `router_confidence`, `last_routed_intent` nunca são escritos (`state.py:454-456`). `presentation_history.message_kind` depende deles e na prática cai em `state['next']`.
2. **Verificado: `PlayerMove` fora do dispatch do mock.** O `MockLLM` não tem builder para `PlayerMove` e o `_combat_action` parece órfão. O parse de combate no mock funciona por acaso (kind vazio → attack).
3. **Verificado: `narrator` em `dispatch` não há aresta para `archivist`.** Se o router devolver END (última mensagem já é IA), o turno não passa por `archivist`/`turn_finalizer`. Não é um bug no fluxo normal (a API sempre acrescenta uma `HumanMessage`), mas é uma saída do grafo que pula o finalizer.
4. **Verificado: o router descarta `world` mesmo no modo sequencial.** `_base_route_payload` coloca `world` no payload e `route_intent_node` o remove. Funciona, mas o `world` no payload é código sem efeito (existe para compatibilidade com chamadas diretas do `dm_router_node` em testes).
5. **Verificado: diferença de robustez CLI × API.** O `except Exception` do loop do CLI imprime o erro e segue sem salvar; a API converte em 500 e mantém o save anterior. O CLI também trunca a 15 mensagens e a API a 20.
6. **Verificado: `librarian` sem `isinstance`.** Funciona pelo `try/except` por acaso do `AttributeError`. Uma mudança futura que mova o acesso para fora do `try` quebraria o guard.
7. **Verificado: timeout DeepSeek de 12 s por padrão.** Uma geração SMART longa (planejamento, arquivista) pode estourar 12 s e cair no Groq mesmo com o provider saudável. O custo é latência e troca de modelo. `LLM_TIMEOUT_SECONDS` sobrepõe tudo, inclusive para DeepSeek.
8. **Suspeita: `npc_fallback_hint` pode persistir** além do turno em que foi usado (ver 8.5).
9. **Suspeita: replan por viagem no mesmo turno.** O `campaign_manager` roda **antes** do storyteller, então no turno de viagem ainda compara o plano com o local de partida. A correção está no próprio storyteller (`travel_needs_replan`), que marca `needs_replan` para o turno seguinte. Ou seja, o replan de região acontece com um turno de atraso, o que é intencional (comentário em `storyteller.py:388-395`), mas significa que o turno de chegada narra com o arco da região anterior.
10. **Verificado: diretório `.tmp/spec176-*` contém clones do repositório** (aparecem no grep). Se forem indexados por ferramentas de busca ou testes com `rootdir` amplo, produzem resultados duplicados.
11. **Padrão forte a destacar:** a combinação **atômica** de quarentena do payload livre no storyteller (uma proposta inválida derruba todas as irmãs) é conservadora; garante coerência ao custo de perder, num turno, NPCs/itens/quests legítimos propostos na mesma resposta.
12. **Padrão forte a destacar:** `RoutedLLM` separa claramente falha de transporte (troca de provider) de falha semântica (regenera até 3x no mesmo provider, com recuperação local de JSON sem custo). Isso é o que mantém o jogo estável com DeepSeek como primário.

---

## 11. Guia de leitura para quem vai mexer no núcleo

| Quero... | Comece por |
|---|---|
| Entender a topologia | `main.py` inteiro (146 linhas) |
| Mudar o que o jogador pode fazer em cada fase vital | `services/actor_lifecycle.py` (`evaluate_action`, regex `_RECOVERY`) |
| Mudar como a intenção é classificada | `agents/router.py` (atalhos primeiro, prompt por último) |
| Mudar narração e efeitos mecânicos de viagem/descanso | `agents/storyteller.py:299-521` |
| Adicionar um novo tipo de proposta da LLM | `services/structured_outputs.py` + `services/world_validators.py` + `services/event_processor.py` |
| Adicionar um nó novo | Conectar ao `archivist` (CLAUDE.md), tratar `next` na aresta do `dispatch`, guard de fallback, `memory_fact_policy` se a prosa não deve virar fato |
| Trocar provider/modelo | `llm_setup.ROUTES` ou `RPG_ROUTES` |
| Diagnosticar structured output falhando só com LLM real | Hook de tentativas (`set_llm_attempt_telemetry_hook`) e `structured_failure_code` |
| Garantir que um recibo de recompensa está certo | `services/turn_outcome.py` + `agents/action_guard.py` (baseline) |

Arquivos centrais com linhas-chave:

- `C:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master\main.py` (grafo)
- `C:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master\state.py` (schema)
- `C:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master\llm_setup.py` (`RoutedLLM` 407, `ROUTES` 155, `get_llm` 951)
- `C:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master\agents\router.py` (`_combat_gate` 60, `dm_router_node` 119)
- `C:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master\agents\storyteller.py` (`storyteller_node` 281)
- `C:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master\agents\combat.py` (`combat_node` 607)
- `C:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master\agents\archivist.py` (`archive_node` 200)
- `C:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master\api.py` (`_execute_action` 2463, `_run_turn_collected` 2395, `_commit_turn` 2254, `_stream_turn` 2546, `_create_game` 1848)
