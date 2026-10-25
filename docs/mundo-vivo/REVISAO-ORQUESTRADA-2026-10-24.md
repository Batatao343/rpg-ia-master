# Mundo vivo — revisão orquestrada das SPEC-296..307 (2026-10-24)

Revisão somente leitura, feita por um coordenador + 4 leitores paralelos (costuras,
munição dos prompts, lore não aproveitada, canais de criação). Todas as alegações
"críticas" foram reconferidas no source pelo coordenador. Nada foi alterado.

Pergunta do dono: *"a LLM ter munição para orquestrar um mundo vivo e ir criando
coisas, sempre relacionadas com a lore de Valoria"*.

**Resposta curta.** A onda 296–307 construiu um motor determinístico sólido
(pressões, diretor, estados de local, calendário, agenda de NPC, quests com prazo,
lei, reputação, patentes, companheiros, pool com quarentena). O que falta não é
motor: é **que o motor fale com a LLM e que a LLM possa criar**. Hoje:

- O estado vivo chega ao narrador quase só como **palavras de perigo**, 3 notícias de
  template e um `[ECOS DO MUNDO]` de 2–4 frases. Pressões, crises, estados de
  local, festa do dia, relações entre fações e agenda de NPC **nunca entram em
  prompt nenhum** (narrador, NPC, combate, loot, planner, arquivista).
- A LLM só pode **mutar** entidades existentes (matar NPC com prova, trocar
  controle, bloquear rota). Não há nenhum canal para **criar** item, local, rumor,
  criatura promovível ou evento novo. O padrão "semente → LLM costura → validador →
  quarentena" está implementado **só para NPC**, e desligado (`RPG_SHARED_POOL`
  `off`/`shadow`).
- Da lore, chega 2 chunks públicos por query (~525 tokens, descartáveis inteiros).
  Rumores com `confiabilidade`/`FONTE`, 114 blocos "Para o narrador:", 23
  perspectivas de fação, 15 dos 19 segredos, ~215 criaturas e 234 blocos de
  itens/materiais do `lore_nova/` não têm consumidor estruturado.

As 15 propostas da §4 atacam isso em duas camadas: **religar** (barato, 1–3 dias
cada, sem decisão do dono) e **novos pilares** (semente de criatura/item/rumor,
nós dinâmicos, quest ancorada em lore).

---

## 1. Revisão crítica das costuras

### 1.1 Achados confirmados no source (ordem de gravidade)

| # | Achado | Evidência | Efeito em "mundo vivo" |
|---|---|---|---|
| A1 | **Regra de ouro: eventos do motor vazam para o narrador.** `collect_dynamic_facts` renderiza `event_log[-100:]` e só pula eventos com `payload.offscreen` ou tipo em `OFFSCREEN_TYPES` (e só com `RPG_NPC_WORLD=on`). Os eventos do diretor (`route_blocked`, `location_control_changed`, `location_state_changed`) saem de `_ev()` **sem** `offscreen`, e o pack não consulta `world_sim.perceived_ids`. | `services/context_builder.py:276-284`; `services/npc_world.py:1310-1322`, `:37`; `services/world_director.py:307-316`, `:528-536`; `services/event_processor.py:420-425` | Um cerco em Brekmar bloqueia rota e o narrador em Skallgard recebe "[turno N] A rota entre X e Y está BLOQUEADA" sem o herói ter visto/ouvido. A API já foi corrigida para isso (`api.py:2900-2907`, 302 P2-2); o prompt não. |
| A2 | **Lei × patentes é gancho morto.** `_is_wanted()` retorna `False` sempre; `not_wanted_in_region` de `data/faction_membership.json:15` nunca barra. `buy_license`/`law_state.licenses` sem chamador. | `services/faction_membership.py:381-383`, `:507-509`; `services/law.py:1632-1634` | Procurado em Nova Arcádia entra na Guarda normalmente. Código de Ferro sem dente social. |
| A3 | **Criatura gerada em jogo nunca promove nem entra no sorteio.** `combat._grounded_template` fixa `name_origin="player"`; o pool recusa; `pick_encounter_enemy` só sorteia `gamedata.BESTIARY` curado. | `agents/combat.py:176-182`; `agents/bestiary.py:375-400`, `:426`; `world_utils.py:~937-1049`; `handoffs/SPEC-297-sol-review.md:126-130` (D7) | O pool de criaturas (namespace `CREATURE`) é inerte na prática. |
| A4 | **Item e local não têm produtor.** `save_custom_artifact` (ramo pool `ARTIFACT`) sem chamador em runtime; `PoolNamespace.LOCATION` tem allowlist e nada submete; grafo só aceita arestas dinâmicas, nunca nós. `items_gained` desconhecido é rejeitado. | `gamedata.py:59-111`; `services/shared_pool_models.py:25`; `services/graph_resolver.py:106-130`; `agents/storyteller.py:1812-1817` | Metade do escopo de abrangência do pool (VISAO.md §C2 "criaturas, itens, locais") não existe. |
| A5 | **Loot do inimigo é descartado.** `bestiary.json.loot` (59 entradas) e `EnemySchema.loot` só alimentam supressão ecológica e dossiê; `roll_loot` usa tabela por região/perigo; 8 de 12 regiões caem em `default`. | `services/economy.py:760-794`; `services/ecology.py:79-88`; `services/discovery.py:147`; `data/loot_tables.json` (5 chaves) | Contradiz VISAO §B "saque de partes de criatura" e deixa o crafting em 6 receitas. |
| A6 | **`npc_knowledge_block` (`<O_QUE_VOCE_SABE>`) está dormente.** Definido, testado, nunca chamado por agente. O NPC só recebe linhas `[VIU]/[OUVIU]/[BOATO]` via pack, e nem vê `world.news`. | `services/npc_knowledge.py:850`; único uso em `tests/test_npc_knowledge.py:410` | NPC não sabe sua própria agenda, facção, patente, crença (304) nem a festa de hoje. |
| A7 | **Eventos sem template são invisíveis.** `render_event` devolve `""` para `location_state_changed`, `world_crisis_warning`, `npc_*`, `companion_*`, `crime_*`, `unique_item_*`, `faction_membership_changed` (este só via `event_text`). Logo nunca entram no `<ESTADO_ATUAL_DO_MUNDO>` nem viram memória canônica do arquivista. | `services/context_builder.py:64-72`, `:177-188`; `agents/archivist.py:190-214` | O arquivista não lembra que a cidade caiu, que o companheiro saiu ou que o herói foi preso. |
| A8 | **Relações entre fações (302) não chegam a ninguém.** `relation_bands` só é lido por `npc_world` (deserção). Patente (301) usa `rivals` do catálogo estático; `faction_events` fica `[]` com motor `on` (P2-1 da 301). | `services/faction_membership.py:528-534`; `services/npc_world.py:946-951`; `handoffs/SPEC-301-sol-review.md:46` | Guerra/aliança decidida pelo diretor não muda missão, desconto, diálogo nem narração. |
| A9 | **Planner cego.** `campaign_manager` não vê quests ativas (inclusive de mundo), pressões, crises, estação, festa nem `world.news`; replan só por intervalo/região/`needs_replan`. | `agents/campaign_manager.py:78-106`, `:135-192` | Arco narrativo pode contradizer a crise regional em curso. |
| A10 | **Narração diária recebe só "FATO: <template>".** `narrate_day` não recebe pressão, estado do local, fase do diretor, estação nem onde o herói está; texto não vira `world.news` nem memória. | `agents/world_simulator.py:248-285`; `agents/storyteller.py:746-753`, `:1780` | A "LLM ocasional" da VISAO §3 existe, mas com munição mínima e sem rastro. |

### 1.2 Produzido e não consumido pelo jogo

| Campo / estrutura | Produtor | Quem lê |
|---|---|---|
| `world_sim.pressures`, `bands`, `crises`, fase do diretor | `services/world_engine.py:285-518` | só `location_states` → preço/perigo. Nenhum prompt, nenhuma UI (por desenho) |
| `world_projection.location_states.public_label` | `services/location_states.py:84-91` | só `api.py:2983` (mapa). Nenhum agente |
| `world_sim.faction_relations` / `relation_bands` | motor 302 | só `npc_world.py:946-951` |
| `npc_beliefs` (304) | `storyteller._npc_beliefs_update` | só UI via `npc_layers.py:266` |
| `world_sim.perceived_stats` | `storyteller.py:696-703` | só `playtest/telemetry.py` |
| `world.shelter` | `services/reputation.py:972, :1210` | nenhum leitor fora do próprio módulo (grep) |
| `reputation_notices` | 298 | API; toast no chat não implementado (`handoffs/SPEC-298-sol-review.md:113`) |
| `law_state.licenses`, `buy_license` | 299 | ninguém (`services/law.py:1632`) |
| `EnemySchema.loot`, `EnemySchema.regions` | LLM | copiados para a ficha, nunca validados/consumidos |
| `pool_used` | storyteller | só impede reuso; grava `[]` com flag `off` |

### 1.3 Pares que não conversam (resumo)

| Par | Estado | Evidência |
|---|---|---|
| Estado de local (cerco/praga/festa) × encontros/bestiário/combate | só `danger_delta` | `world_utils.py:686`; nenhum uso de `location_states` em `agents/combat.py`, `encounter_*` |
| Pressões × preço/estoque | **conversa**, via `location_states` → `price_mult`/`restock_mult`/loja fechada | `services/location_states.py:42-61`; `services/economy.py:227, :320-328` |
| Calendário × viagem × motor | **conversa** (passo fechado, hook `pre`, multiplicador sazonal de encontro) | `world_utils.py:210-232`; `services/world_engine.py:725-729`; `world_utils.py:1032-1035` |
| Agenda 304 × `npc_actor` | **conversa** (`present_here`, `npc_absent_known`) | `services/npc_layers.py:143-186`; `agents/npc.py:749-795` |
| Agenda 304 × notícias 215 | **conversa**, mas rumor exige `RPG_NPC_KNOWLEDGE=on` | `services/world_perception.py:50-86` |
| Lei × reputação | só lei → fama (`add_location_fame`) | `services/law.py:330-348, :651-667` |
| Lei × companheiros | nada | grep vazio |
| Quests de mundo × beats do planner | paralelos por desenho | `agents/storyteller.py:1040-1047`; grep `world_quest` em `campaign_manager.py` vazio |
| Pool × loot/locais/estados | pool só serve NPC; `gamedata.py:66` carrega itens/locais mas nada produz | — |
| Companheiro 300 × morte off-screen 304 | 304 usa exposição própria, não `companions_exposed` | `handoffs/SPEC-304-sol-review.md:47` (P2-7a) |

### 1.4 Flags: o que está desligado por default no código

| Flag | Default código | Staging | Efeito desligada |
|---|---|---|---|
| `RPG_WORLD_ENGINE` | `on` | `on` | — |
| `RPG_CALENDAR`, `RPG_WORLD_QUESTS` | `on` (seguem o motor) | `on` | — |
| `RPG_NPC_WORLD` (304) | **`off`** (`services/npc_world.py:35`) | `shadow` | sem agenda, perigo, morte off-screen, crença, mensageiro; `resgate` de 305 dormente; **filtro R23 do pack também desliga** (ver A1) |
| `RPG_LAW` (299) | **`off`** (`services/law.py:157`) | `on` (dono 24/10) | sem patrulha/procurado/`<LEI_NA_CENA>`; save não grava `law_state` |
| `RPG_SHARED_POOL` (297) | **`off`** | `shadow` | semente só nasce com pool ≠ `off` → no modo `off` NPC nasce **sem semente nem âncora** (caminho legado com a cena no prompt) |
| `RPG_NPC_KNOWLEDGE` (215) | **`off`** | `on` | sem rumor nenhum (`world_perception.py:50`) |
| `RPG_COMPANION_SOUL/ROMANCE` | `on` | `on` | — |
| 296/298/301/306 | sem flag | — | sempre ativos |

Consequência: o produto "default" (local, sem `.env`) roda **sem** rumor, sem lei, sem
semente, sem agenda — o mundo vivo só existe com 4 flags ligadas à mão. Vale
registrar em `.env.example` um perfil "mundo vivo completo".

### 1.5 Follow-ups abertos que importam para mundo vivo (deduplicados)

Bloqueiam `on`/`done`:
- Smoke real §6 pendente em 296–302, 305–307 (todos os handoffs).
- 297: D8 (dono aprova 25 linhas × 6 tabelas de `npc_seed_tables.json`), D3 (cláusula nos termos), grant por coluna do `rpg_api` (`handoffs/SPEC-297-sol-review.md:126-135`).
- 304: medir C1 da 302 com `npc_perigo` antes de `RPG_NPC_WORLD=on`; `LEADER_DEATH_GAP_DAYS` 30→60 (D6) (`handoffs/SPEC-304-sol-review.md:82-86`).
- 300: P2-4 (aviso/partida rodam para quem está em `waiting_at`) (`handoffs/SPEC-300-sol-review.md:69`).
- 299: P2-4 bloqueava `RPG_LAW=on`; staging já está `on` → confirmar tratamento (`handoffs/SPEC-299-sol-review.md:54-57`).

P2 que viram munição se fechados: 297 D7 (criatura do pool no encontro); 301 P2-1/P2-2
(`faction_events` vazio, promoção sem `rival_awareness`); 302 F-1 (decay em `on`);
305 P2-5 (esconder tipos engine-only do schema), `resgate`/`recuperar_objeto`
dormentes; 298 toast + keeper na 1ª visita; 307 P2-1 (`payable_cards` × frequência),
P2-4 (rótulo `Primavera/Verão` genérico — decisão do dono).

### 1.6 Riscos à regra de ouro (além de A1)

| Risco | Evidência | Gravidade |
|---|---|---|
| `<FACÇÕES_DO_MUNDO>` do NPC expõe `goal` de **todas** as fações não derrotadas, inclusive as que o jogador não conhece; contenção só textual + filtro `faction_reveals` a posteriori | `agents/npc.py:968-976, :1085-1091` | média |
| Planner (`purpose="planning"`) vê arestas/controladores `hidden`/`secret`; único gate é `sanitize_beat` | `services/context_builder.py:223`; `services/secret_signatures.py` | média (4 assinaturas cobrem 4 dos 19 segredos) |
| `relação com o herói={N}/10` em prompt (pré-298) | `agents/storyteller.py:397` | baixa (viola "rótulos sem números" na direção da LLM, não do jogador) |
| Rumor de dívida/aviso de reputação emitido com NPC fora de cena | `handoffs/SPEC-298-sol-review.md:55-56` | baixa |
| Verdade de NPC off-screen (`npc_sim`) × API/dossiê/pack | `services/npc_world.py:1230-1300`; `api.py:2193` | ok (P1 corrigidos) |
| Pressões/tensão/fase do diretor na API ou no prompt | `api.py:2911-2918`; grep vazio em `storyteller.py`/`ambient.py` | ok |

---

## 2. Mapa de munição — o que cada LLM recebe hoje

Pipeline comum: `build_context_pack` (`services/context_builder.py:554-734`), 3.500 tokens,
cotas `current_state` 25% · `active_location` 20% · `relations` 15% · `entities` 15% ·
`lore` 15% · `session_memory` 10%; `max_visibility="public"` fixo; ranking léxico
(sem embedding). Lore: FAISS k=6 → 2 chunks, injetados como **um fato indivisível**
(se não couber na cota de ~525 tokens, cai inteiro — `context_builder.py:388-403, :437-447`).

### 2.1 Por chamada

| Chamada | Recebe de **estado vivo** | Recebe de **lore** | NÃO recebe (existe no estado) |
|---|---|---|---|
| **Storyteller** (`agents/storyteller.py:1438-1516`) | `<AMBIENTE>` (período, clima local, luz, perigo em palavras, saídas); `<OUVIU_DIZER>` = `world.news[-3:]`; `<EVENTOS_DESTE_TURNO>` (viagem/descanso/`[ECOS DO MUNDO]`); estação regional + data; `<FAMA_LOCAL>`; `<LEI_NA_CENA>`; `<FAÇÃO_DO_JOGADOR>`; `<COMPANHEIROS>`; `<QUESTS_ATIVAS>`/`<GANCHO_NOVO>`; `<ELENCO_POSSIVEL>` (pool `on`); `<FACÇÕES_CONHECIDAS>`; `<ENTIDADES_CANONICAS>`; pack (eventos com template, controlador, arestas, entidades) | `<LORE_PUBLICO_CANONICO>` = 2 chunks por query `"{loc} {último input}"` | pressões/bandas, crises e fase, **estado do local** (`public_label`), **festa de hoje**, agenda/posição de NPCs ausentes, relações entre fações, preços/estoque, fama em outros locais, crônica, eventos sem template (A7), lore `hidden`/`secret`, lore por região/estação/crise |
| **NPC actor** (`agents/npc.py:1046-1114`) | `<ROLE>` (só traços revelados), `<ATITUDE>` (rótulo + motivos: raça, origem, fama, feitos), `<MEMORIA>`, `<LEI_NA_CENA>`, `<AMBIENTE>` sem saídas, `<FACÇÕES_DO_MUNDO>` (todas), patente **do jogador**, pack com gate `[VIU]/[OUVIU]/[BOATO]` (215 `on`) | 2 chunks por `"nome + local + última fala"` | **própria facção/patente/agenda/posição/crença**, semente (desejo/medo/segredo/contradição/maneirismo — só na persona textual), `world.news`, estação/data/festa, preços mesmo sendo mercador, quests do jogador além do beat, lore da **origem** do NPC |
| **Combate** — `prepare_encounter` (só Elite/Chefe/Carga alta) e `_narrate` (`agents/combat.py:463-496, :908-973`) | `world_state_block` cortado a **400 chars** (cena) / 1.200 tokens (narração); `<AMBIENTE>` combat; elenco canônico; `withhold` | RAG só no gerador de inimigo (`bestiary.py:464`) | estado do local (cerco/praga), estação, festa, `bestiary_knowledge` (o que o jogador já sabe do inimigo), clima real na cena preparada, loot do inimigo |
| **Loot** (`agents/loot.py:114-146`) | resumo mecânico de 1 linha | nada | **tudo**: preço, estoque, motivo do preço (reputação, cerco, estação), pressões, keeper |
| **Campaign manager** (`agents/campaign_manager.py:135-192`) | local, clima legado, pack `planning` (vê hidden) | 2 chunks | quests ativas, pressões/crises, estação/festa, `world.news`, crônica; replan não dispara por crise |
| **Archivist** (`agents/archivist.py:853-884`) | resumo, histórico, conflito, âncoras de local/inventário/aparência | nada | nenhum estado do motor; eventos sem template nunca viram memória; `[ECOS DO MUNDO]` não vira memória |
| **Narração diária** `narrate_day` (`agents/world_simulator.py:248-285`) | "FATO: <texto do template>" por item percebido | nada | pressão, estado do local, fase, estação, posição do herói, o que o herói já sabia (para contrastar) |
| **Gerador de NPC** (`agents/npc.py:446-459`) | semente estruturada (pool ≠ off) | RAG `nome + local de origem` | estado da região (crise/fome/guerra), fação dominante no local, estação; traços raciais × região (raça sorteada uniforme, `npc_seed.py:128`) |
| **Gerador de criatura** (`agents/bestiary.py:419-510`) | `"hint; local; nível"` | RAG `nome + contexto` | região validada, bioma, Abismo/saturação de Éter, pressão `abismo`, estação; sem semente |

### 2.2 O que a LLM pode propor hoje (e o que não existe)

Canais aceitos (`services/structured_outputs.py:15-100`; validação em
`services/world_validators.py:643-803`; aplicação única em `services/event_processor.py:428`):
`npc_killed`/`secret_revealed`/`quest_completed` (com prova), `location_control_changed`,
`route_blocked`/`route_cleared` (conexão real), `faction_relation_changed` (não
`neutral`/`allied_with`), `proposed_quests` (texto livre, dedupe 0,75, sem prazo/recompensa/âncora),
`introduced_npcs` (só o nome), `items_gained` (só catálogo), `faction_impacts`,
`membership_action`, `crime_claims` (enum 5), `faction_reveals`, `relationship_change` (±1).

**Não existe proposta de:** rumor/notícia; local/sublocal; item/artefato; criatura
fora de combate; fação; rota nova; mudança de preço/estoque; estado de local ou
pressão; festa/clima; agenda/destino de NPC; revelação de traço oculto; aliança
entre fações; gancho de quest com âncora de lore.

### 2.3 Canais de criação existentes × padrão alvo

Padrão alvo (VISAO §C2 + 297): **motor sorteia semente ancorada → LLM costura →
validadores → quarentena → pool**.

| Canal | Semente do motor | LLM costura | Validador | Quarentena/pool | Veredito |
|---|---|---|---|---|---|
| NPC (297/306) | sim: raça, origem, local, fação 50%, profissão, desejo, medo, segredo, contradição, maneirismo (`services/npc_seed.py:33-43, :119-148`; tabelas 42–61 linhas cada, `data/npc_seed_tables.json`) | persona, aparência, lenda | 8 validadores + embedding ≥0,90 + juiz LLM (`services/shared_pool_validators.py:387-404`; `shared_pool.py:496-606`) | sim (24 h) | **completo, desligado** |
| Criatura | não | conceito (`EnemySchema`) | schema fechado, librarian, identidade | `CREATURE`, mas `name_origin="player"` → nunca (A3) | **meio** |
| Item | não | nenhum produtor | allowlist pronta | `ARTIFACT` sem produtor (A4) | **morto** |
| Local/sublocal | não | nenhum | `parent_location_id` checado pelo validador | `LOCATION` sem produtor; grafo sem nós dinâmicos (A4) | **inexistente** |
| Rumor | templates (43 em `data/world/signals.json` + 10 `npc_templates.json`) | só `narrate_day` (não persiste) / legado `WorldPulse.rumor` | guarda de nomes | — | **só motor; sem boato falso** |
| Quest de mundo | 9 kinds em `data/world/world_quests.json` | nada | prova, prazo, `heard_via` | — | **só motor** |
| Quest proposta pela LLM | não | tudo | título/dedupe/ids | — | **sem âncora, prazo, recompensa** |
| Fação | não | não | — | — | inexistente (28 na lore, 19 em `factions.json`) |

---

## 3. Lore ainda não aproveitada

Inventário (`lore_nova/`, ~790 KB; `data/codex/` 699 .md; `visibility`: public 639,
hidden 41, secret 19; grafo 594+82 entidades e **só 101 arestas**, 7 tipos usados —
`allied_with`, `neutral`, `member_of` quase vazios).

| Veio | Riqueza na lore | Uso no código hoje | Munição possível |
|---|---|---|---|
| **Itens e materiais** | 119 `[ITEM]` + 115 `[MATERIAL]` em `lore_nova/items.txt`, com "Origem/Uso/Valor/Perigo" (127 "Perigo:") | 66 artefatos + 6 receitas (`data/recipes.json`); 8/12 regiões sem `loot_tables` | gerar receitas regionais, materiais como drop de criatura, "Perigo" como efeito colateral |
| **Rumores com metadado** | 40 rumores com `confiabilidade: alta/média/baixa` (13/15/12) e `[FONTE: …]` (`rumors.txt:5-16`) | nada lê `confiabilidade`/`FONTE` (grep 0); só RAG | tabela rumor → {verdadeiro?, fonte, região, gatilho}; alimentar `signals.json` e boato falso com crença×verdade |
| **"Para o narrador:" / "Voz:" / "O que sabe:"** | 114 / 20 / 49 blocos em `npcs.txt` (ex. `:560`, `:775`, `:1403`) | nenhum consumidor estruturado | campos `hook`/`voice`/`knows` por NPC curado → `npc_knowledge` + persona |
| **Fações só no grafo** | Casa das Marés (29 hits, 0 no código), Três Sindicatos (Helvira/Thesk/Brynja), Guilda dos Corvos, Quadrilha dos Telhados, Encapuzados da Fornalha, Resistência Operária, Mercadores de Curiosidades, cultos do Despertar | `factions.json` tem 19; campos "Ponto fraco"×7, "Papel real"×28, "Liderança"×15 sem leitor | completar as 9 fações (patentes, rivais, missões); "Ponto fraco" → alvo de quest; Sindicatos → economia por rota |
| **Segredos** | 19 `secrets/` + 14 `npc_secret` + 3 timelines `hidden` (e5_2, e7_2, e7_4) | `secret_signatures.py` cobre **4** (`data/secret_entities.json`); `discovery.py`/`player_knowledge.py` existem sem trilha pista→revelação | cada segredo = assinatura + 2–3 pistas descobríveis + `visibility` hidden→public por `secret_revealed` |
| **Criaturas** | 337 em `creatures.txt` (5 categorias), 340 `monsters/` no codex | `bestiary.json` 124 (`regions` 12, sem sentidos/hábitos/fraqueza narrativa) | promover ~215 por região/categoria; `ecology.py` já consome |
| **Perspectivas de fação** | 23 `hidden` (o que X pensa de Y) | só `content_validator.py:54` | modular `faction_relations` iniciais e diálogo de NPC membro |
| **Timeline/eras** | Eras 0–7 (`timeline_completa.txt:6…416`), Guerra do Céu Vermelho | só o ano em `world_calendar.py:189` | ruínas/relíquias/veteranos datados; aniversários de era como festas (303 já suporta) |
| **Éter/Abismo regional** | Éter 290 hits, Abismo 98; Pântano = Éter dos mortos (`locations.txt:96-101`); "o Abismo tem ritmo, transborda" (`timeline:50-52`) | pressão `abismo`, `abyss_events.py`, estado `corrompido`; **Éter sem mecânica** | estado de local `ether_saturado` (preço, clima, criaturas), ciclo de transbordamento como relógio de era |
| **Código de Ferro / lugares de Nova Arcádia** | Oubliette ("quanto mais fundo, pior o crime", `locations.txt:65`), Mercado de Carne (contratos de servidão, `:63`), licença de armas (`:452`), caligrafia desconhecida do Código (`rumors.txt:199`) | `law_codes.json` 5 jurisdições; `prison_location_id: null`; descrições só no mapa | prisão = Oubliette com níveis; contrato de servidão como item/quest; rumor do escriba |
| **Locais citados sem nó** | Casa das Marés, Casa dos Espelhos, Câmara do Sinal, Beco do Sussurro, Boca do Fundo, Maré-Funda, Ermo Branco/Thessavar | `world_map.json` 35 nós; `entities_extra.json` 23 sublocais | nós novos ligados às fações; alvo natural do canal "local" do pool |
| **Raças × região** | eugenismo de Skallgard (`races.txt:344`), humanos geram cultistas/bandidos (`:337`) | `race_attitudes.json` com `source` (bom); semente sorteia raça uniforme | pesos de raça por região na semente; ritos raciais como eventos |

Divergências lore↔código a registrar: "Cinco Sinos", "Entropia", "Ano 112", "Guerra das
Cinzas" (`traits.json`) **não existem** em `lore_nova/` — são camadas do código. Um lint
lore↔data evitaria o narrador citar nomes que a lore não sustenta.

---

## 4. Propostas priorizadas

Custo: **P** = 0,5–1 dia · **M** = 2–3 dias · **G** = 1 semana+ (spec própria).
Risco RO = regra de ouro; L = letalidade (SPEC-285).

### 4.1 Religar / costurar (barato, sem decisão do dono salvo onde indicado)

| # | Problema | Ideia | Encaixe | Custo | Risco | Dono? |
|---|---|---|---|---|---|---|
| **R1** | A1: eventos do motor vazam ao narrador/planner | No `collect_dynamic_facts`, para eventos `source="engine"`, só renderizar se `event_id` ∈ `world_sim.perceived_ids` ∪ `_known_sources`, **independente** de `RPG_NPC_WORLD`; marcar `offscreen=True` em `_ev()` do diretor e dos estados de local | `services/context_builder.py:276-284`; `services/world_director.py:307`; `services/world_perception.py` já grava `perceived_ids` (305 R6) | P | RO ↓↓ | não |
| **R2** | A7/A10: motor sem voz no prompt e sem memória | (a) templates de `render_event` para `location_state_changed`, `world_crisis_warning`, `companion_*`, `crime_*`, `faction_membership_changed`, `npc_fate_learned`; (b) gravar o texto de `narrate_day` como `memory_fact` `canonical_event`; (c) bloco `<MUNDO_PERCEBIDO>` no storyteller: `public_label` do local atual + festa de hoje + rótulo de crise percebida (sem severidade) | `context_builder.py:64-72`; `archivist.py:190-214`; `services/location_states.py:84-91`; `world_calendar.festival_schedule` | M | RO neutro (só percebido) | não |
| **R3** | A6: NPC não sabe de si | Chamar `npc_knowledge_block` no `npc_actor`; acrescentar linhas "você é de {facção} ({patente})", "hoje você está {agenda}", "ouviu: {news da sua região}", semente (desejo/medo/contradição/maneirismo) como `<MOTIVACOES_INTERNAS>` (nunca o segredo literal) | `agents/npc.py:1046-1114`; `services/npc_knowledge.py:850`; `services/npc_world.py` (`location_of`, `npc_faction`); `services/npc_seed.py` | M | RO ↑ cuidado: segredo da semente só como "evita o assunto X" | não |
| **R4** | A2: lei × patentes morto; Código de Ferro sem dente | Implementar `_is_wanted` lendo `law.wanted_level(state, region)`; `buy_license` chamado por `membership_action`/loja; `prison_location_id` = `na_oubliette` com nível por severidade | `services/faction_membership.py:381`; `services/law.py:1632`; `data/law_codes.json` | P | L neutro | não |
| **R5** | A3 + 297 D7: criatura do pool inerte | `name_origin="engine"` quando a espécie vem do motor (encontro sorteado/`enemy_id` ausente), não do texto do jogador; `pick_encounter_enemy` inclui promovidas da região com peso baixo e teto 1 por encontro | `agents/combat.py:176-182`; `agents/bestiary.py:236-248`; `world_utils.py:937-1049`; `services/ecology.py` | M | L: manter `categoria ∈ {lacaio,padrao,elite}` já imposto pelo validador | sim (letalidade 285 — spec própria pedida pelo handoff 297) |
| **R6** | A5: loot não vem do inimigo; 6 receitas | `roll_loot` mistura 1 drop de `bestiary.loot` (validado contra `ARTIFACTS_DB`/materiais) com a tabela regional; script lore→`recipes.json`/`loot_tables.json` a partir de `[MATERIAL]`/`[ITEM]` (Origem/Uso/Valor) com `source` arquivo:linha como nas sementes | `services/economy.py:760-794`; `data/bestiary.json.loot`; `lore_nova/items.txt` | M | L neutro; economia: revisar `gold_value` | revisão de conteúdo (como D8) |
| **R7** | A8: relações entre fações não chegam a 301/NPC/narrador | `faction_membership` lê `relation_bands` para rival efetivo e requisito ("em guerra com X" bloqueia entrada); `faction_events` preenchido pelo digest percebido; NPC membro recebe "sua fação está em {guerra/trégua} com Y" **só se percebido** | `services/faction_membership.py:528-534`; `services/world_director.py`; `data/codex/factions/perspectivas_*` como relação inicial | M | RO: só bandas percebidas | não |
| **R8** | A9: planner cego, replan não reage ao mundo | Pack `planning` recebe `<QUESTS_ATIVAS>` + `<MUNDO_PERCEBIDO>`; `needs_replan=True` ao abrir crise percebida na região atual, falhar quest de mundo ou cair cidade | `agents/campaign_manager.py:78-106, :160`; `storyteller._world_quests_tick` | P | RO: usar só percebido | não |
| **R9** | Loot/mercador mudo: preço sem motivo | Passar ao `_narrate` de loot e ao NPC-mercador os **motivos qualitativos** do preço (`price_mult` → "preços altos por causa do cerco/estação/sua fama"), nunca o número | `services/economy.py:201-240`; `agents/loot.py:114-146`; `services/reputation.attitude_block` | P | RO ok (rótulos) | não |
| **R10** | Lore chega em 2 chunks cegos a contexto | Query RAG composta: `{local} {região} {estado do local} {estação} {input}`; fatiar lore em linhas ≤600 chars como já se faz com memória; filtro por tag de região no metadado do chunk | `services/context_sources.py:86`; `rag.py:1154-1158`; `context_builder.py:437-447` | P | — | não |
| **R11** | Default "morto": 4 flags `off` | Perfil `.env.example` "mundo vivo" + `conftest`/playtest com as 4 ligadas; semente também no modo pool `off` (só não submete) | `services/npc_seed.py`; `agents/npc.py:462-571`; `scripts/staging/vercel_env.py:100` | P | — | não |

### 4.2 Novos pilares (spec própria)

| # | Problema | Ideia | Encaixe | Custo | Risco | Dono? |
|---|---|---|---|---|---|---|
| **N1 Rumores com semente e boato falso** | Só 43 templates de crise; nenhum boato, nenhuma lenda; 40 rumores da lore sem metadado lido | Tabela `data/world/rumor_seeds.json` gerada de `rumors.txt` (`confiabilidade`, `FONTE`, região, assunto, `truth`); motor sorteia 0–1 rumor/dia por região frequentada (taxa da calibração VISAO: sinal pequeno a cada 1–2 dias) e a LLM diária costura em 1 frase; `truth=false` entra em `npc_knowledge` como `[BOATO]` e **nunca vira fato** (já é regra); `ProposedRumor` do narrador validado contra entidades do grafo + dedupe | `services/world_perception.record_news`; `services/npc_knowledge.py` (canal RUMOR p=0,35); `services/world_quests._resolve_channel` (rumor → gancho) | M–G | RO ok (é o canal certo); risco de spam → teto/TTL em `world.news` | sim: taxa e se rumor falso pode gerar quest |
| **N2 Semente de criatura** | Criatura nasce sem âncora (região/bioma/Abismo), sem sentidos/hábitos, sem promoção | `creature_seed`: espécie-base (das ~215 do codex por região), categoria do bestiário, hábito, sentido, 1 fraqueza/1 resistência pela lore, parte de criatura (material); LLM costura descrição/nome; validador schema + lore_refs + unicidade; pool `CREATURE` via R5; encontros sorteiam por estado do local (praga → carniçais, corrompido → aberrações) | `agents/bestiary.py:96-167` (números já no motor); `data/bestiary.json.resistances/vulnerabilities`; `services/ecology.py`; `location_states` | G | L: manter `materialize_enemy_concept`; sem "chefe" no pool | sim (letalidade; VISAO §B naturezas de dano) |
| **N3 Semente de item/artefato** | Item novo impossível; `ARTIFACT` morto | `item_seed`: material (lore), origem (fação/era/região), raridade **do motor**, tipo, 1 propriedade de catálogo fechado, "Perigo" opcional; LLM costura nome/descrição/lenda; `save_custom_artifact` ganha chamador (tesouro raro, recompensa de quest de mundo, craft); único por mundo | `gamedata.py:59-111`; `services/economy.roll_loot`; `shared_pool_models.ARTIFACT`; `lore_nova/items.txt` | M–G | economia: `gold_value` só do motor (já previsto em `economy.py:10`) | revisão de conteúdo |
| **N4 Sublocais dinâmicos** | Local novo impossível; 1–2 locais em 5 regiões; locais da lore sem nó | (a) curar 6–8 nós da lore (Casa das Marés, Casa dos Espelhos, Câmara do Sinal, Beco do Sussurro, Boca do Fundo, Maré-Funda) em `world_map.json`/`entities_extra`; (b) `dynamic_nodes` em `world_projection` (sublocal `kind=interior`, `parent_id` obrigatório, tags de catálogo) proposto pela LLM só como `ProposedSublocation` com validador de pai/região/unicidade, pool `LOCATION`; ruína de cidade caída (302) vira sublocal "ruínas de X" | `services/graph_resolver.py:106-130`; `shared_pool_validators.py:173`; `services/location_states` (`ruina`) | G | RO ok; mapa UI precisa suportar nós novos | sim (escopo: só interiores) |
| **N5 Segredos com trilha** | 15/19 segredos sem assinatura nem pista; `discovery.py` sem caminho pista→revelação | Para cada segredo: assinatura em `secret_entities.json`, 2–3 pistas (`clue`) ligadas a local/NPC/item, `secret_revealed` com prova = N pistas coletadas; timelines hidden viram `public` na revelação; NPC "O que sabe:" alimenta pistas | `services/secret_signatures.py`; `services/discovery.py`; `services/player_knowledge.py`; `world_validators._secret_proof` | G | RO: é o próprio mecanismo da regra | revisão (quais segredos são "jogáveis") |
| **N6 Quests ancoradas em lore** | Quests de mundo só de crise; quests da LLM sem âncora/prazo | Kinds novos a partir da lore: `cacar_criatura` (N2), `entregar_material` (N3/rotas dos Sindicatos), `escoltar` (agenda 304), `investigar_rumor` (N1), `enterrar` (Corvos), `ponto fraco` de fação; `ProposedQuest` da LLM ganha `kind`, prazo e recompensa **do motor** por template | `services/world_quests.py` (templates/prazo/`heard_via` prontos); `services/quest_log.register_proposed_quests` | M | RO ok; dureza: prazo telegrafado já existe | sim (quais kinds) |
| **N7 Éter como estado de local** | Éter = 290 hits de lore, 0 mecânica | `location_state` `ether_saturado` (Pântano, Costa Negra, Pradaria) com `price_mult` de reagentes, clima, multiplicador de aberrações, sinal próprio; pressão `abismo` o alimenta; ciclo de "transbordamento" como relógio de longo prazo | `services/location_states.py`; `services/abyss_events.py`; `data/world/signals.json` | M | L: multiplicador de encontro limitado | não |
| **N8 Fações da lore completas** | 9 fações só no grafo; 101 arestas | Entrar em `factions.json`/`faction_membership.json` (patentes, rivais, HQ, aceita membro?), relações iniciais a partir das 23 perspectivas, "Ponto fraco" como alvo de missão; arestas `allied_with`/`member_of` populadas | `data/factions.json`; `data/faction_membership.json`; `data/graph/edges.json`; `services/faction_relations.py` | M | — | sim (classificação de fações aceita membro — VISAO §C) |
| **N9 Calendário vivo com eras** | Festas desligadas da lore; eras sem uso | Aniversários de era/Guerra do Céu Vermelho como festas regionais; cada festa com `lore_tags` → RAG e sinal; `Cinco Sinos` ou documentar na lore (divergência) | `data/world/festivals.json`; `services/world_calendar.py`; `lore_nova/timeline_completa.txt` | P–M | — | sim (307 P2-4 e lore dos Sinos) |

### 4.3 Ordem sugerida

1. **R1** (regra de ouro) → **R2 + R3** (motor e NPC ganham voz) → **R8, R9, R10**
   (planner/loot/RAG) — ~1 semana, sem decisão do dono, efeito imediato na prosa.
2. **R4, R7, R11** — costuras de sociedade (lei/patente/relações) e default vivo.
3. **N1 + N6** — rumor com semente e quests ancoradas: é a "munição" literal pedida.
4. **R5/R6 → N2/N3** — criatura e item com semente, reaproveitando 100% do pool 297.
5. **N5, N4, N7, N8, N9** — segredos, sublocais, Éter, fações, eras.

---

## 5. Método e limites

- Leitura: `docs/mundo-vivo/VISAO.md`, cabeçalhos/§ das SPEC-296..307, handoffs
  296–307, source dos módulos citados. Lore só via grep + trechos (≤60 linhas).
- Nenhum teste rodou; nenhum processo Python; nada alterado além deste arquivo.
- Alegações A1–A10 reconferidas pelo coordenador no source; contagens de lore e
  tabelas vêm dos leitores (grep/contagem) e podem variar ±5%.
- Não verificado: comportamento real com todas as flags `on` num playtest (fora do
  escopo e do custo autorizado).
