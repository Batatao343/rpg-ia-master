# Auditoria de bugs funcionais — Área 01: Grafo LangGraph / ciclo do turno

Data: 2026-10-15 · Prefixo: `BUG-01-nn` · Somente leitura do código de produção.

**Arquivos cobertos:** `main.py`, `agents/router.py`, `agents/turn_finalizer.py`, `services/turn_outcome.py`,
`services/turn_effects.py`, `services/turn_pipeline.py`, `services/turn_execution.py`, `agents/campaign_manager.py`,
`agents/storyteller.py` (inteiro), `agents/action_guard.py`, `services/actor_lifecycle.py`, `services/continuity.py`,
`agents/npc.py` (`npc_actor_node`, `generate_new_npc`), `agents/world_simulator.py`, `services/narrative_evidence.py`
(parte usada pelo finalizer), `world_utils.is_travel_intent/is_rest/invalid_travel_message`, trechos de `agents/combat.py`
(saída de morte/gate), sites de `with_structured_output` (grep completo).

**Não cobertos (tempo):** `services/structured_outputs.py` além da leitura de classes (só modelos Pydantic, sem
recuperação de JSON raw — a recuperação mora em `llm_setup`), `agents/archivist.py` (fora da lista), `services/turn_effects.flush`
(lido, sem achado), caminho `RPG_TURN_EXECUTION=concurrent` só por leitura.

**Contagem:** crítica 0 · alta 3 · média 5 · baixa 3 (+ descartados ao final).

> Nota de honestidade: uma tentativa inicial de repro (`generate_new_npc` com `RPG_NO_MOCK=1`) carregou o `.env` via
> `load_dotenv` de `llm_setup` e fez UMA chamada real de geração de NPC (DeepSeek deu timeout, outro provider respondeu).
> Custo desprezível; as demais reproduções usam stubs/MockLLM (`RPG_FORCE_MOCK=1`).

---

### BUG-01-01 — Achado/baú de exploração perdido quando o beat é concluído no mesmo turno da viagem
- **Severidade:** alta
- **Categoria:** estado-inconsistente
- **Local:** `agents/storyteller.py:809-812` e `:859-860` (sobrescreve `updates["player"]` definido em `:857-858`)
- **Evidência:**
  ```python
  # :811  base_p ignora discovery_player
  base_p = rested_player if rested_player is not None else dict(state.get("player") or {})
  leveled_player, level_up_events = grant_xp(base_p, XP_PER_BEAT)
  ...
  elif discovery_player is not None: updates["player"] = discovery_player   # :857
  if leveled_player is not None: updates["player"] = leveled_player          # :859  <- descarta o achado
  ```
  `discover_on_arrival` muta `_pl` (ouro/itens) e `world["looted_locations"]` in-place; o XP de beat parte do `state.player`
  original, então o jogador novo (com XP) não contém o loot. Os `discovery_events` (claim de item ÚNICO) ainda entram em
  `pending_world_events` e `looted_locations` fica marcado → o baú é consumido sem o jogador receber nada (e único fica "reclamado" no projection).
- **Reprodução (executada, stub de LLM, `scratchpad/repro1.py`):** viagem a `pm_profundezas` (baú curado 40 ouro + espada_curta + pocao_cura_maior), turno 5, plano com 1 beat.
  ```
  sem beat: gold 40 inv [espada_curta, pocao_cura_maior] looted ['pm_profundezas']
  com beat: gold 0  inv []                                xp 150 looted ['pm_profundezas']
  ```
- **Impacto:** jogador chega ao local, a narração anuncia o baú, mas ouro/itens somem e o baú não pode ser saqueado de novo;
  itens únicos ficam marcados como reclamados sem dono. Silencioso (a linha "Recompensa confirmada" também some).
- **Correção sugerida:** `base_p = rested_player or discovery_player or dict(state.player)` (mesma precedência do `base_p` do encontro, `:437-439`); idealmente aplicar o XP sobre `updates.get("player")` já montado.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_audit_reward_contracts.py::test_valid_beat_rewards_once_and_does_not_mutate_input` (beat sem viagem/descoberta); nenhum cobre viagem+descoberta+beat.

---

### BUG-01-02 — `generate_new_npc` aceita `AIMessage` como ficha e persiste NPC lixo no cache de templates
- **Severidade:** alta
- **Categoria:** guard-fallback
- **Local:** `agents/npc.py:252-266` (`res.model_dump()` sem `isinstance(res, NPCSchema)`)
- **Evidência:**
  ```python
  designer = llm.with_structured_output(NPCSchema)
  res = designer.invoke([...])
  data = res.model_dump()          # AIMessage também é Pydantic: NÃO levanta
  data["name"] = name; data["id"] = f"npc_{...}"
  ```
  O `except` de fallback nunca dispara porque `AIMessage.model_dump()` existe. Violação direta da convenção CRÍTICA do projeto
  (todos os outros sites — bestiary, prologue, tactical_profile, death_flow, etc. — têm `isinstance`).
- **Reprodução (executada, `scratchpad/repro6.py`, get_llm stub devolvendo `AIMessage` — o que `RoutedLLM` esgotado/`FallbackLLM` fazem):**
  ```
  role: None | persona: None | content: 'erro: todos os providers falharam' | id: npc_zed_teste | saved: 1
  ```
- **Impacto:** com providers fora do ar (quota/timeout — situação documentada), todo NPC introduzido pelo storyteller ou criado pelo `npc_actor` nasce sem `role`/`persona` (prompt do ator vira "Ocupação: None. Persona: None"), com o texto de erro em `content`, e a ficha é **gravada no `npc_database` de runtime**: cache hit futuro reutiliza o NPC quebrado para sempre (`find_existing_entity` por nome).
- **Correção sugerida:** `if not isinstance(res, NPCSchema): raise TypeError(...)` (cai no fallback seguro) e só chamar `save_npc_template` quando a geração foi real (não persistir o fallback `id: "fallback"`).
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum cobre `generate_new_npc` com AIMessage (MockLLM sempre devolve `NPCSchema`).

---

### BUG-01-03 — `is_travel_intent` classifica movimento local como viagem inválida e recusa a ação ("Não há rota direta")
- **Severidade:** alta
- **Categoria:** regra-divergente
- **Local:** `world_utils.py:69-98` (regex) → `agents/storyteller.py:299-319` (recusa antes da LLM)
- **Evidência:** o regex aceita `vou|entro|saio|fujo|volto|ir ...(até 5 palavras)... para|a|em|no|na + palavra`. Qualquer ação de deslocamento DENTRO da cena que não cite um nó conectado vira "destino explícito inválido" e o storyteller devolve só a recusa canônica, sem narrar nem processar a ação.
- **Reprodução (executada, `scratchpad/repro7.py`, mundo em `nova_arcadia`):**
  ```
  'Não há rota direta a partir de Nova Arcádia. Saídas conecta' <- Vou até a fogueira observar o fogo
  'Não há rota direta a partir de Nova Arcádia. Saídas conecta' <- Entro na taverna e peço uma bebida
  'Não há rota direta a partir de Nova Arcádia. Saídas conecta' <- Vou em direção ao mercador
  ```
  (Com o router: "Vou para cima do goblin e ataco" → `storyteller` → mesma recusa; ver BUG-01-04.)
- **Impacto:** ações cotidianas ("entro na taverna", "vou até o balcão") são bloqueadas com mensagem de erro de mapa; o turno é consumido (turn_count já foi incrementado) sem efeito. Muito visível em jogo real.
- **Correção sugerida:** só recusar quando o texto citar um **nome de local conhecido do mapa** que não é saída (ou exigir verbo de viagem forte `viajo/parto/sigo para` + local do mapa); caso contrário seguir como ação livre.
- **Confiança:** confirmado por execução (função de recusa); caminho completo confirmado por leitura (`storyteller.py:306-319`).
- **Testes existentes relacionados:** testes de `invalid_travel_message` afirmam a recusa para destino de mapa não conectado; nenhum cobre movimento local.

---

### BUG-01-04 — `_EXPLICIT_STORY_RE` do router tem precedência sobre hostilidade/conversa e casa palavras inocentes
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `agents/router.py:29-32` e `:144-146`
- **Evidência:** `\b(descans\w*|durm\w*|acamp\w*|viaj\w*|vou\s+para|sigo\s+para)\b` roda **antes** do classificador e retorna STORY, sem olhar `_EXPLICIT_HOSTILITY_RE`.
- **Reprodução (executada, `scratchpad/repro2.py`/`repro3.py`):**
  ```
  Pergunto ao viajante sobre a estrada   -> storyteller   (NPC perdido: "viajante" casa viaj\w*)
  Vou para cima do goblin e ataco        -> storyteller   (+ recusa de rota, ver 01-03)
  Ataco o acampamento dos bandidos       -> storyteller   (acamp\w*)
  Compro uma barraca de acampar          -> casa a regex (LOOT perdido)
  ```
- **Impacto:** conversa com "viajante", ataque a "acampamento", compra de "barraca de acampar" nunca chegam às rotas NPC/COMBAT/LOOT.
- **Correção sugerida:** usar verbos conjugados em 1ª pessoa (`descanso|durmo|acampo|viajo|vou para`), não prefixos livres; e checar `_EXPLICIT_HOSTILITY_RE` primeiro (hostilidade vence "vou para").
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** nenhum cobre "viajante"/"acampamento".

---

### BUG-01-05 — Exceção no storyteller devolve narração de descanso/achado sem aplicar o estado
- **Severidade:** média
- **Categoria:** exceção-engolida
- **Local:** `agents/storyteller.py:1017-1028`
- **Evidência:** o `except Exception` devolve só `messages` (e `world/needs_replan/npcs` apenas se `dest`). `rested_player`, o `world` do descanso/relógio, `discovery_player`, dano de armadilha e `factions` calculados antes do `try` são descartados, enquanto o texto vem de `rest_note`/`travel_note`.
- **Reprodução (executada, `scratchpad/repro4.py`, invoke levantando RuntimeError):**
  ```
  keys retornadas: ['messages']
  texto: "O jogador DESCANSOU. O tempo avançou para Dia 1 — Anoitecer e ele recuperou parte das forças."
  ```
  Estado: Vitalidade 3/8 e relógio inalterados. (Além disso `_player_facing_note` não converte a nota de descanso: o jogador lê "O jogador DESCANSOU... ele recuperou", 3ª pessoa e promessa falsa.)
- **Impacto:** narra recuperação/tempo que não ocorreram; spam do mesmo comando fica "grátis". Viagem preserva o mundo, mas perde o achado do baú (`world.looted_locations` já mutado in-place → baú consumido sem entrega).
- **Correção sugerida:** no `except`, devolver `player` (`rested_player`/`discovery_player`), `world`, `factions` sempre que mecânica foi aplicada; converter `rest_note` em texto diegético.
- **Confiança:** confirmado por execução (provider é injetado para lançar; `RoutedLLM` real não levanta, então depende de bug em pós-processamento)
- **Testes existentes relacionados:** nenhum para o ramo `except` com descanso.

---

### BUG-01-06 — Laboratório de combate encerrado: próximas ações caem nos nós LLM normais (router/NPC/storyteller/arquivista)
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `main.py:63-71` (gate de START não conhece `combat_simulation`), `main.py:122-134` (só o ramo `combat_agent` vai a END); `api.py` não bloqueia ação após `simulation.finished` (`api.py:1083-1090` só marca na view)
- **Evidência / Reprodução (executada, `scratchpad/repro5.py`):** estado do simulador com `combat.active=False` + mensagem "Examino a sala e converso com alguém":
  ```
  nós: action_guard, turn_prepare, campaign_manager, dm_router, dispatch, npc_actor, archivist, turn_finalizer
  🚦 [ROUTER] npc_actor -> Alvo: Velha Maren / 🎭 [NPC] Criando ... / 🧠 [RAG] Memória de NPC ...
  ```
- **Impacto:** a spec 090 promete "nenhum provider/RAG" no laboratório; após a vitória/derrota qualquer texto livre gera chamadas CLASSIFY/FAST reais, cria NPC, grava RAG e archivist. Gasto de crédito e save de laboratório poluído.
- **Correção sugerida:** no gate de START (`main.py`) ou em `action_guard`, se `combat_simulation.enabled` e `not combat.active` → `__end__` com mensagem "simulação encerrada"; mesmo bloqueio na API.
- **Confiança:** confirmado por execução (graph); API provável por leitura.
- **Testes existentes relacionados:** `tests/test_combat_simulator.py` cobre criação/combate, não ação pós-fim.

---

### BUG-01-07 — NPC morto por evento (`npc_killed` do storyteller) continua `in_scene` e conversável
- **Severidade:** média
- **Categoria:** estado-inconsistente
- **Local:** `services/event_processor.py:71-73` (só marca `projection.entities[id].alive=False`); `agents/router.py:205-221` e `agents/npc.py:315-349` (nunca consultam `alive`/`status`)
- **Evidência:** a única sincronização com `state.npcs` é `combat._reflect_scene_allies` (`combat.py:1205-1207`, `status:"morto"`, `in_scene:False`) — e só para aliados transitórios. Para morte narrada/validada via `proposed_events`, `state.npcs[nome]` permanece `in_scene` e sem `status`. `grep alive agents/npc.py agents/router.py` → vazio. Mesmo no caso de combate, `status:"morto"` não é lido: o NPC morto responde "X não está aqui. Foi visto pela última vez em ..." (corpo tratado como ausente).
- **Reprodução:** hipótese por leitura (não executada end-to-end): processar `npc_killed` para um NPC canônico presente e depois "Falo com <NPC>" → router casa `npcs_in_scene` → `npc_actor` gera diálogo.
- **Impacto:** NPC canônico morto conversa normalmente; quests/`known` inconsistentes; contradição com `world_state_block`.
- **Correção sugerida:** ao aplicar `npc_killed`, marcar `state.npcs[...]` (`in_scene False`, `status "morto"`); `npcs_in_scene`/`npc_actor` rejeitam `status=="morto"` com narração própria.
- **Confiança:** provável
- **Testes existentes relacionados:** nenhum.

---

### BUG-01-08 — Falha do planejador substitui plano bom por beats genéricos, zera `current_step` e reabre XP de beat
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `agents/campaign_manager.py:178-181` + `:207-224`
- **Evidência:** `plan = _invoke(); if not isinstance(plan, CampaignPlanModel): raise ValueError` cai no `except` que devolve plano genérico de 3 beats pt-BR com `last_planned_turn = turn_count` e `current_step=0`, e o nó grava `needs_replan=False` (`:294-300`). Já o caminho "beats em inglês após retry" retorna `None` e **mantém o plano anterior** (`:187-191`, `:287-293`). Comportamento inconsistente para o mesmo tipo de falha transitória.
- **Reprodução:** hipótese por leitura (provider esgotado em turno de replan por intervalo, p.ex. turno 15): arco existente é trocado por "Explore os mistérios de X / Enfrente um desafio / Faça uma descoberta", sem retry por 15 turnos; cada beat genérico concluído concede `XP_PER_BEAT` (150) de novo.
- **Impacto:** arco narrativo perdido por falha de rede; progressão de XP reaberta.
- **Correção sugerida:** se já existe plano com beats, retornar `None` (mantém plano, `needs_replan=True`); usar o template só quando não há plano.
- **Confiança:** provável
- **Testes existentes relacionados:** `tests/test_beats_visibilidade.py` (cobre o caminho inglês, não o de AIMessage).

---

### BUG-01-09 — `npc_fallback_hint` nunca é limpo
- **Severidade:** baixa
- **Categoria:** estado-inconsistente
- **Local:** `agents/npc.py:327` (grava), `agents/storyteller.py:174` (lê); nenhum `None` em lugar algum; fora do whitelist de `persistence._state_to_save_data`
- **Evidência:** `grep npc_fallback_hint` só acha gravação/leitura. Em chamadores que mantêm o estado em memória entre turnos (CLI `game_engine`, playtest harness), todo turno STORY seguinte injeta "SEM INTERLOCUTOR: o jogador tentou falar com alguém…" no prompt. Na API (recarrega do save) o campo morre entre requisições, então o impacto é CLI/harness. (Um doc interno já levantava a suspeita: `docs/descricao_projeto/fontes/roteiro/p5.py:584`.)
- **Reprodução:** hipótese (não executada).
- **Impacto:** narração do storyteller passa a "narrar a ausência de interlocutor" em turnos não relacionados.
- **Correção sugerida:** `_base_route_payload` e o retorno do storyteller devem zerar `npc_fallback_hint`.
- **Confiança:** provável
- **Testes existentes relacionados:** `tests/test_npc_fallback.py` (cobre o caminho feliz).

---

### BUG-01-10 — Pulso do mundo com `danger_shift=-1` eleva local de perigo 0 para 1
- **Severidade:** baixa
- **Categoria:** off-by-one
- **Local:** `agents/world_simulator.py:66-78`
- **Evidência:** `new = max(1, min(4, cur + shift))` — o clamp de piso 1 contradiz `world_map.json`, que contém um nó com `"danger": 0`. Com `shift=-1`, `max(1, -1)=1` grava `danger_overrides[loc]=1` e `world["danger_level"]=1` (o mundo ficou "menos perigoso" e subiu). Um shift 0 não afeta (retorno antecipado).
- **Reprodução:** lógica pura, por leitura (`cur=0, shift=-1 → 1`).
- **Impacto:** zona segura (perigo 0) passa a poder gerar encontro/dano de armadilha e perde o benefício de descanso seguro.
- **Correção sugerida:** clamp do piso em `min(cur, 1)` quando `shift<0`, ou piso 0 para locais com base 0.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** nenhum para danger 0.

---

### BUG-01-11 — Guard `reward_delta` compara frase isolada com delta líquido do turno
- **Severidade:** baixa
- **Categoria:** contabilidade
- **Local:** `services/narrative_evidence.py:88-93`
- **Evidência:** cada frase "Você recebeu N ouro/xp" é comparada com `player.gold - turn_baseline.gold` do turno inteiro. Turno que ganha 30 e 20 ouro em frases separadas, ou ganha 50 e gasta 30, rejeita frases verdadeiras e reescreve a mensagem (`finalizer` aplica `Overwrite`).
- **Reprodução:** hipótese por leitura.
- **Impacto:** narração legítima de loot múltiplo/venda é cortada.
- **Correção sugerida:** aceitar a frase se N ≤ ganho bruto conhecido (soma de eventos positivos) em vez do delta líquido.
- **Confiança:** hipótese
- **Testes existentes relacionados:** `tests/test_narrative_evidence.py` (caso de delta único).

---

## Verificado, sem bug

- **Arestas condicionais** (`main.py`): todo retorno mapeado existe (`END`, `loot`→`loot_agent`); `RouteType.NONE` é normalizado para STORY (`router.py:188`); `dispatch` com `next=None` só ocorre se o router levantar (try/except cobre).
- **`messages`/reducer:** nenhum nó devolve lista inteira; `Overwrite` só em `turn_finalizer` e `archivist` (intencional).
- **`turn_count` duplicado:** `prepare_turn` incrementa 1× e `campaign_manager` só incrementa quando `turn_prepared` é falso; `dispatch` zera a flag. Planner pulado (combate/simulação) ainda devolve `world` com o turno já contado.
- **Snapshot do finalizer:** `turn_baseline` é tomado em `action_guard` antes de qualquer mutação do grafo (inclusive fuga do router); recibo usa deltas de player/quests/event_log.
- **Guards `with_structured_output`:** router, storyteller, campaign_manager, world_simulator, loot, combat (scan e PlayerMove), bestiary, archivist, prologue, tactical_profile, death_flow, encounter_preparation, chronicle_compression, character_creator (checa `inventory`), librarian (AttributeError engolido pelo except) — todos protegidos. **Única exceção real: `npc.py:262` (BUG-01-02).**
- **Replan por viagem entre regiões:** storyteller marca `travel_needs_replan` por `_same_region` (`:388-395`) e o fallback de exceção também propaga.
- **`action_guard`:** turno bloqueado não incrementa `turn_count`/`session_action_count`; mensagem de bloqueio entra no histórico (intencional) e `last_action_outcome` tem precedência em `player_facing_message`.
- **Finalizer `RuntimeError` por fronteira não pronta:** possível só com `dead`/`estado_terminal`/`last_stand` sem `death_pending`; combate e armadilha (`resolve_trap` conclui estabilização em ≤2 tentativas) sempre definem `death_pending` ou limpam o estado — não reproduzido.

## Descartados / falsos positivos

- `receipt_id` sem `action_id`: pode repetir após restore de checkpoint (turno e deltas iguais), mas não é consumido por nenhum código (`grep` só acha a geração) — baixa, sem impacto hoje.
- `_combat_gate` não zera `active_npc_name`/`loot_source`: combat_node consome apenas `combat_target`/`combat_origin_hint` (esse zerado em `combat.py:991`); sem efeito observável.
- Router `chosen = decision.target` sem validação (NPC fora de cena): o `npc_actor` trata (gera/carrega) e o gate `in_scene` retorna "não está aqui"; comportamento de design.
- `XP delta` com level-up: `grant_xp` acumula XP (não reseta), então `xp_delta` do recibo é correto.
- Rota concorrente (`RPG_TURN_EXECUTION=concurrent`): `route_intent_node` descarta `world` do router corretamente; não há escrita duplicada de `world` identificada (só leitura).
- Cobertas por specs draft (não detalhadas): XP/[RESULTADO] na prosa (SPEC-199), NPC onisciente (SPEC-215).
