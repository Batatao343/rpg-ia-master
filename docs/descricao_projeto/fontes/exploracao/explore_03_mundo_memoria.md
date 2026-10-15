# Mundo Vivo, Lore, RAG e Memória — como funciona

Escopo: o mundo de Valoria (dados estáticos), o pipeline de lore → Codex → FAISS, o event sourcing do mundo, o montador de contexto, as camadas de memória (curto/longo prazo, por NPC), a proveniência de fatos, a crônica, facções/clima/segredos. Todas as referências são `arquivo:linha` do working tree em 2026-10-12. Contagens foram medidas no disco, não copiadas de docs.

---

## 0. Mapa mental em uma página

```
lore_nova/*.txt (11 arquivos, ~800 KB, FONTE editável)
   │  scripts/migrate_lore_nova.py  (+ data/codex_overrides.yaml, migration-safe)
   ▼
data/codex/**/*.md  (699 .md, frontmatter id/type/name/tags/visibility)   data/graph/entities.json (594 ents) + edges.json (101) + components.json + world_rules.json
   │  services/codex_loader.py (chunks 500/50)   │  services/graph_resolver.py (base − disabled + dynamic)
   ▼                                              ▼
faiss_lore_index/ (global, imutável)        world_projection (estado derivado do event_log)
faiss_rules_index/ (data/rules.txt)                ▲
   │                                               │ apply_event + rule_engine (cascata, depth<2)
   │      ┌────────── event_log (append-only) ◄────┤ process_pending_events (no archivist, todo turno)
   │      │                                        │ ◄ pending_world_events (LLM PROPÕE; Python valida)
   ▼      ▼
services/context_builder.build_context_pack()  ←  RAG global (lore pública) + RAG sessão + RAG NPC + memory_facts + narrative_summary + event_log
   │   (orçamento de tokens por seção)
   ▼
prompts: storyteller / npc_actor / combat / campaign_manager("planning" vê hidden)
   │
   ▼ fim de turno
agents/archivist.py: resumo curto (≤1200 chars) + fatos longos (FAISS da sessão) + crônica (milestones + prosa)
```

Princípio transversal ("LLM propõe, motor aplica"): nada que a LLM diz vira estado sem passar por validador Python. A memória semântica também segue isso: a *confiança* de um fato é função fechada da *proveniência*, nunca texto da LLM (`services/memory_provenance.py:33-39`).

---

## 1. O mundo de Valoria (dados estáticos)

### 1.1 `lore_nova/` — a fonte do lore

Onze `.txt`, todos intitulados "CODEX OMNIA: …" (confirmado por `head`). Tamanhos reais:

| Arquivo | Tema | Bytes |
|---|---|---|
| `npcs.txt` | personagens importantes: motivações reais e segredos (inclui os 13 Demônios e 7 Dragões, movidos de `creatures`) | 185 347 |
| `creatures.txt` | bestiário não-racional: fauna, assombrações, aberrações, forças primordiais | 152 496 |
| `timeline_completa.txt` | história do mundo, "ERA 0 — O MUNDO ANTES" até a era 7 | 95 885 |
| `items.txt` | recursos, materiais, armas, artefatos por local | 74 642 |
| `locations.txt` | descrições sensoriais e info do narrador | 67 477 |
| `races.txt` | as seis raças | 66 909 |
| `factions.txt` | facções: objetivos reais x declarados, organizado por região | 38 637 |
| `secrets.txt` | "Verdades que existem mas que os personagens raramente sabem. Uso exclusivo do narrador" | 30 572 |
| `daily_life.txt` | vida cotidiana ("o mundano como espelho do sistema") | 30 668 |
| `faction_perspectives.txt` | visões de mundo conflitantes | 29 169 |
| `rumors.txt` | rumores de "confiabilidade variável" | 24 689 |

Formato: blocos `[CATEGORIA: X]` + `[TAGS: a, b, c]` + título + corpo (parser em `scripts/migrate_lore_nova.py:143` `parse_categoria_blocks`, que também detecta cabeçalhos de seção `#### NOME ####` / `LOCAL: X`). A timeline tem parser próprio (`:257 parse_timeline`) que divide por era e subseção, e marca clusters de reveals como `hidden` (`_TIMELINE_HIDDEN_CLUSTERS`, `:216-232`): a destruição de Aethelgard pelo aprendiz (vira o Arauto da Névoa), o despertar do Rei Subterrâneo, o pacto Valerius↔Daruun e a Rede Carmesim sob Skallgard.

### 1.2 `data/codex/` — o Codex gerado (699 arquivos)

Estrutura por pasta (contagem real de `.md`): `monsters` 340, `npcs` 143 (inclui `npcs/mundo_vivo/`, NPCs "vivos" com id `npc_mv_*`, ex. `npc_mv_brunna_ponte_alta.md`), `items` 38, `factions` 29, `secrets` 19, `timeline` 14, `rumors` 13, `locations` 12, `world_story` 11, `races` 10.

Frontmatter obrigatório, validado em `services/codex_loader.py:19,23-47`: `id, type, name, tags, visibility` (+ `aliases`, `related_entities` opcionais). Exemplo real, `data/codex/npcs/npc_velha_magda.md`: `id: npc_velha_magda`, `type: npc`, tags `[Velha_Magda, Mão_Sombria, Víbora, Identidade_Secreta]`, `visibility: public`. A Magda é *pública* porque a identidade secreta dela mora num doc separado `hidden` (spec 7.3, "segredos de NPC": `migrate_lore_nova.split_npc_secrets`, `:398`).

Visibilidade (contagem por `grep`): **639 `public`, 41 `hidden`, 19 `secret`**; 36 arquivos `curated: true` (100% manuais, nunca sobrescritos). A timeline é toda pública *exceto* os quatro clusters acima — p.ex. `timeline_e5_2_em_aethelgard_o_aprendiz_havia_parado.md` é `visibility: hidden`.

Os segredos (`data/codex/secrets/`, `type: secret`, `visibility: secret`) trazem tags `quem_sabe:` e `impacto:`; ex.: "O Aprendiz que Destruiu Aethelgard Foi o Maior Herói da História" — a verdade que o narrador *nunca* deve vazar.

### 1.3 `data/codex_overrides.yaml` — curadoria migration-safe

Aplicado por `migrate_lore_nova.apply_overrides` (`scripts/migrate_lore_nova.py:458`) *depois* de gerar o Codex, de modo que re-rodar o migrate (que **sobrescreve** `data/codex/`) não perde a curadoria. Chaves por id: `aliases` (substitui), `tags_extra` (só adiciona), `visibility` (sobrescreve), `related_entities` (substitui), `append_body`. Id órfão é erro de lint; arquivo `curated: true` nunca recebe override. Caso real documentado no cabeçalho: `mon_verme_primordial_das_raizes_do_mundo → visibility: hidden`, para o narrador não vazar a criatura-segredo quando o jogador só *pergunta* (achado do playtest, turno 13 do `secret_rusher`). Autoria: `docs/guias/AUTORIA.md`.

### 1.4 `data/graph/` — o grafo do mundo

- `entities.json` (594 entidades: 340 monster, 177 npc, 28 faction, 27 artifact, 12 location, 10 race) — **gerado** pelo migrate. Cada entidade: `id, type, name, aliases, tags, visibility, components`.
- `entities_extra.json` (82) — curadoria manual (sublocais, combatentes de facção); o canônico vence em conflito de id (`graph_resolver.py:36-68`).
- `components.json` — *overlay* de componentes por entidade (ex.: `npc_valerius → power_vacuum_trigger {base_instability_delta: -50, rival_faction_override: "mao_sombria"}`). O `migrate` não toca neste arquivo; `load_entities` faz o merge no campo `components` (`graph_resolver.py:57-67`).
- `edges.json` (101 arestas): `located_in` 45, `operates_in` 24, `leads` 21, `enemy_of` 5, `controls` 4, `member_of` 1, `pact_with` 1; por visibilidade 92 public / 6 hidden / 3 secret. Curadas à mão. `relation_types.json` define os 7 tipos.
- `world_rules.json` — as 6 regras do rule engine (§3.4).

### 1.5 `data/world_map.json` — o mapa

35 nós em `locations`: 30 de overworld + **5 interiores** (`kind: "interior"` com `parent_id`, ex. `na_taverna_javali → na_anel_lama`, `sk_salao_do_jarl → skallgard`). Campos: `id, name, region, region_id, coords{x,y}, danger (1–4), tags, connections[], lore_seed, craft_tags, economy_tags, travel_times{}` (13 nós têm `travel_times`; 0 = custo de período zero entre anéis da mesma cidade) e `treasure` (2 baús curados: `pm_profundezas`, `ae_ruinas_submersas`, usados por `services/exploration.py`). Regiões (nós): Nova Arcádia 5, Skallgard 4, Montanhas Afiadas 4, Pradaria das Ruínas 4, Pântano 3, Selva de Xylos 3, Aethelgard 3, Deserto de Zhur 2, Floresta dos Sussurros 2, Costa Negra 2, Brekmar 2, Ophidia 1. `start_location: nova_arcadia`. Viagem e fog of war são determinísticos em `world_utils.py` (`apply_travel :154`, `visited[]` no `WorldState`).

### 1.6 Demais dados de mundo

- `data/origins.json`: 6 raças (traits mecânicos) × 12 regiões (cada uma com `bonus` inicial).
- `data/onboarding.json`: `world_intro`, 12 regiões, 5 classes, 6 raças — lore curado do wizard de criação (`GET /data/onboarding`).
- `data/traits.json`: 80 traits ocultos de NPC (id, name, description, `dc_modifiers`, `reveal_after`, `tags` de região).
- `data/bestiary.json`: **124** criaturas (schema v4, categorias Lacaio/Padrão/Elite/Chefe/Nomeado). `data/runtime/bestiary_runtime.json` e `data/runtime/npc_database.json` (hoje 1 NPC) são o *overlay de runtime* gitignored — NPCs/criaturas gerados em jogo não poluem os arquivos versionados.
- `data/factions.json`: 19 facções jogáveis (id, goal, progress/pace, disposition, reputation, `ascension` autorada).
- `data/weather.json`: tabelas de clima por região (cadeia de Markov) + `global_events` (Tempestade de Éter, Noite Sem Estrelas).
- `data/companions.json` (5), `merchants.json`, `loot_tables.json`, `traps.json`, `visual_assets.json` — fora do escopo desta fatia.

---

## 2. RAG (`rag.py`, 1294 linhas)

### 2.1 Cadeia de embeddings

`EMBEDDING_ROUTES = ["jina", "openai", "ollama", "gemini"]` (`rag.py:46`). Modelos: `jina-embeddings-v3`, `text-embedding-3-small`, `bge-m3`, `gemini-embedding-001` (`:48-53`). *Observação*: o CLAUDE.md ainda cita `models/text-embedding-004`; o código real mudou — Jina é o primário e Gemini o **último** fallback (decisão de 2026-07-16: Gemini sem créditos).

Diferença crítica para o `RoutedLLM` (docstring `:8-14`): **embeddings não têm fallback por request**, porque vetores de provedores diferentes são incompatíveis (espaço/dimensão). O fallback acontece só na *resolução*:

- `_provider_available` (`:340-354`): Jina exige `JINA_API_KEY` + dep; OpenAI idem; **Ollama exige `OLLAMA_HOST` explícito** (pacote instalado ≠ daemon rodando); Gemini exige `GOOGLE_API_KEY`.
- `_resolve_provider` (`:357-367`): `RPG_EMBEDDINGS=<p>` força; senão o primeiro disponível da cadeia; `None` = embeddings desativados (o jogo segue sem RAG, só com ledger/resumo).
- `get_embeddings_for(provider)` (`:370-385`) constrói com cache por provider; falha de init devolve `None` com warning.
- Jina tem cliente próprio via `httpx` (`_JinaEmbeddingsHTTPX`, `:219`; projeto não usa `requests`).

### 2.2 Pin do provider por índice (`embeddings_meta.json`)

Todo índice grava `embeddings_meta.json` ao lado (`_write_meta :419`, `_save_index :467`) com `{provider, model}`. Na abertura, `_embeddings_for_index` (`:443-464`) usa **o provider da meta**, nunca o ativo: índice legado sem meta assume `gemini` (`_LEGACY_PROVIDER`, `:56`); provider pinado indisponível ⇒ índice **desativado** com warning ("re-indexe") — nunca se consulta com vetor alheio. Para trocar de provider: `uv run python rag.py` (reindex). Free tier da Jina = 100k tokens/min, então o reindex do Codex pode esgotar o minuto (ESTADO_ATUAL).

`prepare_shared_query_vector` (`:670-714`) só devolve um vetor compartilhado se *todos* os índices existentes do contexto (lore + sessão + NPC) estão pinados no **mesmo** provider/modelo/dimensão; senão cada leitor cai no caminho textual próprio.

### 2.3 Três escopos de índice

| Escopo | Caminho | Quem escreve | Função de leitura |
|---|---|---|---|
| Lore global | `faiss_lore_index/` | `ingest_codex` (offline) | `query_global_by_vector :717`, `query_rag :886` |
| Regras global | `faiss_rules_index/` | `ingest_file(data/rules.txt)` (`:1227`) | `query_rag(index_name="rules")` |
| Sessão | `data/saves_memory/{game_id}/` (`_get_session_path :477`) | `add_memory_to_session :909` (archivist, world_simulator) | `query_session_by_vector :750`, `query_session_memory :655` |
| NPC | `data/saves_memory/{game_id}/{npc_id}/` (`_get_npc_path :1045`) | `add_npc_memory :1052` (npc_actor / retry do archivist) | `query_npc_by_vector :778`, `query_npc_memory :1190` |

Os componentes de caminho passam por `_safe_storage_component`/`_contained_storage_path` (`:164-216`) — proteção contra path traversal e nomes reservados do Windows. `reindex_global` (`:1254`) roda o **lint de conteúdo antes** e aborta com `exit 1` sem tocar nos índices se houver erro (spec 7.2).

### 2.4 Visibilidade

`vis_rank` (`:496-501`): `public=0 < hidden=1 < secret=2`; sem metadado = public; **valor desconhecido = secret** (falha fechada, não vaza por typo). O filtro roda *depois* da busca vetorial, por isso busca-se `k=6` e fica-se com 2 (`_query_rag_impl :859-866`; no caminho por vetor, `query_faiss_evidence(k=2, fetch_k=6, max_visibility=…)`, `:504-569`). O `query_faiss_evidence` devolve `RetrievedEvidence` com id estável (`entity_id#chunk_<sha256[:24]>` ou `content_<sha>`), score = −distância, visibilidade e metadados — usado também pelos evals offline com vetores de fixture. Todos os leitores de produção chamam `max_visibility="public"`; só o planejador (`purpose="planning"`) enxerga edges `hidden/secret` (ver §5.2).

### 2.5 Perfis de runtime

Se `RPG_RUNTIME_PROFILE != "legacy"` (perfil `local/portable/hosted`), tanto leitura quanto escrita desviam para `infrastructure.runtime.memory_store` (pgvector, dimensão 1024, `embedding_profile_id="local-1024"`): `add_memory_to_session` faz `stage(MemoryWriteIntent)` com `document_id = session:<sha256>` (idempotente) e `timeline_epoch` (`rag.py:931-960`). O caminho FAISS acima é o perfil `legacy` (CLI/testes).

### 2.6 Codex → FAISS (`services/codex_loader.py`)

- `load_codex` (`:50-72`): `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)`; cada chunk herda `{id, type, name, tags, visibility}` do frontmatter.
- `ingest_codex` (`:121-139`): pega `get_embeddings()`, indexa tudo em `faiss_lore_index/` e grava a meta do provider. Sem embeddings ⇒ aborta com mensagem, não quebra.
- `codex_index`/`codex_body` (`:75-109`): índice id→path (cache em módulo) para ler o corpo de uma entidade descoberta **sem** reindexar; devolve `""` para doc não-`public` (não-onisciência no Codex do jogador, fase 3.2). Corpo truncado a 2000 chars.

### 2.7 Validação de conteúdo

`services/content_validator.py` (lint, também em CI) cobre frontmatter, ids, referências, aliases, **visibilidade** (`:323`, impede segredo num doc público), encoding, overrides, cartas, bestiário e catálogo visual; `validate_all :855`. CLI: `scripts/validate_content.py`.

---

## 3. Event sourcing do mundo

Estado do jogo carrega: `event_log: List[GameEvent]` (append-only), `world_projection: WorldProjection` (derivada), `pending_world_events` (propostas ainda não validadas), `event_rejections` (auditoria de recusas) — `state.py:496-501`.

### 3.1 Tipos de evento e quem pode emiti-los

`services/structured_outputs.py:18-46` (`EventType`): `npc_killed, secret_revealed, location_control_changed, quest_completed, faction_relation_changed, reputation_changed, level_up, subclass_chosen, class_apex_unlocked, player_died, player_downed, route_blocked, route_cleared, unique_item_claimed, unique_item_lost`. `ProposedWorldEvent` (`:46-51`) tem apenas `type, actor_id, target_id, detail, payload` — **não tem campo `source`**, então a LLM não consegue forjar origem. Em `validate_proposal` (`world_validators.py:209-249`): `level_up/subclass_chosen/class_apex_unlocked` exigem `source="progression"`; `player_died/player_downed` exigem `"combat"`; `unique_item_*` exigem `"engine"` — proposta da LLM é recusada.

### 3.2 Validadores (`services/world_validators.py`)

Revalida o schema do zero (dict malformado ⇒ `ValidationResult(False, …)`, nunca levanta), barra duplicata (mesmo type+target no mesmo turno; exceções para `level_up` por `new_level` e `route_*` por par), e delega a um validador por tipo. Exemplos: `_v_npc_killed :30` (id existe em `entities.json`, é `type npc`, ainda está vivo); `_v_secret_revealed :41` (o segredo precisa **existir no grafo** como edge `hidden/secret` ligada ao alvo e ainda não revelado); `_v_location_control_changed :55` (alvo é `location`); `_v_route_blocked :138` (conexão direta real, par ainda não bloqueado).

### 3.3 Aplicação (`services/event_processor.py`)

- `apply_event` (`:62-139`) é **pura**: copia a projeção e aplica o efeito direto. `npc_killed → entities[id].alive=False`; `secret_revealed → revealed_facts[event_id]`; `location_control_changed` desativa a edge `controls` vigente (`disabled_edges`) e cria uma `dynamic_edges` nova; `route_blocked/cleared` mexem em `blocked_routes`; `unique_item_*` gravam o holder.
- `process_pending_events` (`:208-341`) é o **único escritor** do `event_log`/`world_projection`. Roda no `archive_node` em **todo turno**, antes da guarda de cadência do arquivista (`agents/archivist.py:200-208, 236-250`). Para cada proposta: valida → constrói `GameEvent` (uuid4, turn, source) → `apply_event` → (quest_completed: recompensa de XP/ouro via `quest_log.complete_quest_with_reward`) → milestone de crônica → `rule_engine.run_rules` → (npc_killed: `quest_log.fail_orphan_quests`). Rejeitada ⇒ vai para `event_rejections` limitado a 100 (`_bounded_rejections :40`). Quest concluída soma `XP_PER_QUEST`, possível `level_up` (eventos gerados pelo motor entram direto, sem revalidar).
- `prevalidate_event_batch` (`:159-205`): **pré-validação read-only** usada pelo storyteller *antes* de exibir a narração (`agents/storyteller.py:696-735`). Ela trabalha sobre cópias e roda até a cascata, de modo que a proposta N+1 vê os efeitos válidos de N. Política atômica: **uma proposta inválida põe em quarentena todo o payload livre** da resposta (as irmãs aparentemente válidas viram envelopes `_prevalidation_rejected` só para auditoria), porque a prosa que afirmava a mudança foi descartada.

### 3.4 Rule engine (`services/rule_engine.py`) — cascata anti-loop

Regras declarativas em `data/graph/world_rules.json` (6): 
1. `rule_faction_leader_death` (trigger `npc_killed`, condição `target_has_component power_vacuum_trigger`): marca morto, `adjust_faction_stability` pelo `base_instability_delta` do componente, e **emite** `location_control_changed` para cada local controlado pelo NPC.
2. `rule_npc_death_generic`: NPC sem o componente só morre.
3. `rule_control_change_ripple`: o novo controlador ganha +5 de estabilidade.
4. `rule_secret_revealed_v1`: −10 de estabilidade.
5. `rule_quest_completed_v1`: marca `quest_completed` na entidade.
6. `rule_hostile_port_blockade`: local com tag `porto` tomado por controlador hostil ⇒ emite `route_blocked` para as conexões do mapa.

Segurança: sem `eval/exec`; valores dinâmicos só via `resolve_path` (`:69`), um resolvedor *whitelisted* (`event.<campo>`, `target.<campo>`, `component:<comp>.<campo>[N]`); string fora disso ⇒ `RuleActionError`, regra ignorada com log, turno não quebra (`:358-363`). Modelo **híbrido**: quem lidera/controla/é rival é *derivado* das edges `leads/controls/enemy_of/operates_in` (`_led_faction :176`, `_controlled_locations :184`, `_rival_faction :197`); o componente só guarda o que edge não tem (delta, sucessor, override de rival).

Anti-loop: `run_rules` (`:344-374`) retorna `[]` se `depth >= 2`; cada evento derivado é aplicado na projeção via `apply_event`, entra na lista plana e recursa com `depth+1`. O `event_processor` só *anexa* os derivados ao log (`source="rule_engine"`) — não reaplica. Cadeia típica: Valerius morre ⇒ Legião de Ferro perde 50 de estabilidade ⇒ `location_control_changed` em Nova Arcádia → Mão Sombria ocupa ⇒ (depth 1) `rule_control_change_ripple` + `rule_hostile_port_blockade` se for porto.

### 3.5 Resolver do grafo (`services/graph_resolver.py`)

`resolve_edges(projection, entity_id, edge_type, include_hidden)` (`:97-124`) = **base − `disabled_edges` + `dynamic_edges`**, com filtro de visibilidade (default exclui `hidden/secret`). `get_current_controller` (`:127`): a edge dinâmica mais recente vence a base. `is_alive` (`:142`): default `True`. Há `services/state_views.py` com as visões *para o jogador* (reputação, `stability_label` qualitativo — o número interno nunca sai —, `recent_control_changes` limitado a locais visitados, `active_threats`, `visible_controllers` com `include_hidden=False`).

### 3.6 Quest log (`services/quest_log.py`)

Side quests propostas pela LLM (`ProposedQuest`) são validadas em Python (`register_proposed_quests :57`: ids de local/entidade reais). Progresso verificável: `sync_location_progress :129` grava `location_reached` uma vez; `sync_action_progress :154` detecta objetivo cumprido por investigação (duas ações distintas no alvo) e o storyteller enfileira `quest_completed` com `source="system"` (`storyteller.py:~985-1010`). Conclusão com recompensa Python idempotente (`complete_quest_with_reward :223`, 20 ouro além do XP). NPC-origem morto ⇒ quests órfãs falham (`fail_orphan_quests :243`).

---

## 4. Camadas de memória e proveniência

São **cinco** camadas, cada uma com papel e política distintos:

1. **Curto prazo** — `narrative_summary` (`state.py:415`), limitado a 1200 chars por `compact_summary` (`services/memory_summary.py:8-22`, mantém o *final* e tenta começar em fronteira de frase). Reescrito pelo archivist.
2. **Ledger durável** — `memory_facts` (≤500) + `pending_memory_facts` (≤100, retry) + `memory_rejections` + `memory_promotions` (`state.py:487-488`; limites em `memory_provenance.py:28-31`). Vive no save; independe do FAISS estar de pé.
3. **Longo prazo vetorial da sessão** — FAISS `data/saves_memory/{game_id}/` (cópia derivada do ledger, com metadados).
4. **Memória vetorial por NPC** — FAISS por `npc_id`; fatos "este NPC viveu com o jogador".
5. **Eventos canônicos** — `event_log` (fonte da verdade do mundo; a memória só espelha).

### 4.1 Proveniência (`services/memory_provenance.py`)

`MemoryFactRecord` (`:52-98`): `memory_id` (hash estável), `text` (≤480), `provenance`, `confidence`, `source_id`, `source_turn`, `canonical_entity_ids`. Cinco proveniências → confiança **derivada** (`_CONFIDENCE_BY_PROVENANCE :33-39`, aplicada por um `model_validator` que sobrescreve qualquer valor recebido):

| provenance | confidence | emitida por |
|---|---|---|
| `canonical_event` | `confirmed` | eventos do `event_log`, `ConflictSummary`, política `engine_policy` |
| `player_observation` | `reported` | observação do jogador |
| `npc_claim` | `reported` | falas de NPC (npc_actor) |
| `inference` | `speculative` | `important_facts` livres do LLM do archivist |
| `legacy_unverified` | `speculative` | strings antigas sem metadado |

`make_memory_fact` (`:101`) ignora qualquer tentativa de elevar `confidence`. Strings antigas normalizam para `legacy_unverified` (`normalize_memory_facts :122`).

**Validação antes de gravar** (`validate_memory_fact :455-494`), fecha-falha: (a) contradição de evidência narrativa (`narrative_evidence`: localização atual, delta de recompensa, morte do jogador, posse de inventário, identidade de NPC); (b) **segredo não revelado** (`find_strict_unrevealed :170`, usa as assinaturas — §6); (c) "downed ≠ morto" (`player_downed_not_dead`); (d) contradição região↔local pelo mapa canônico; (e) posse de item que não está no inventário mecânico; (f) NPC com espécie/porte trocado em relação a `appearance`; (g) `confirmed` sem fonte aplicável no estado (`source_is_applicable :200`).

`commit_memory_facts` (`:497`): merge idempotente por texto casefold; se o mesmo texto reaparece com **maior** confiança, promove (`speculative → reported → confirmed`) e conta em `memory_promotions`. Repetição por si só nunca promove.

`memory_metadata` (`:518`) achata o registro em primitivos aceitos pelo docstore do FAISS: `memory_id, memory_provenance, memory_confidence, memory_source_id, memory_source_turn (-1 = None), memory_entity_ids`. `format_memory_fact` (`:533`) renderiza para o prompt: `[CONFIRMADO | canonical_event | fonte <event_id> | turno 7] texto`; legado vira `[NÃO VERIFICADO | legacy_unverified] texto`.

### 4.2 Arquivista (`agents/archivist.py`, 918 linhas)

Entrada `archive_node` (`:200`): (1) `process_pending_events` (sempre); (2) `guard_current_messages` — valida a prosa recém-gerada contra a evidência (`services/narrative_evidence.py:19-113`) *antes* de realimentá-la ao modelo; (3) `_archive_node` com os updates; (4) revalida `narrative_summary` e entradas de crônica de prosa do turno e acumula `evidence_rejections` (≤64).

`_archive_node` (`:236`):
- Sem `game_id` ⇒ `{}`.
- **Cadência** (`_should_archive :183`): só chama a LLM (tier SMART) se `archive_due`, há `conflict_summary`, política `canonical_only`, fila pendente de fatos/NPC, ou passaram ≥10 turnos (`_ARCHIVE_EVERY`). Turno trivial retorna cedo. Mesmo sem LLM, se houve **evento novo**, os registros `canonical_event` já são validados e enfileirados em `pending_memory_facts` para o próximo arquivamento (`:267-296`) — a memória derivada nunca perde um fato canônico por cadência.
- **Retry antes de novidade**: `pending_memory_facts` são revalidados e reescritos primeiro; se a escrita física falha, o estado fica *exatamente* com os mesmos ids pendentes e `rag_persistence_error` (`:313-330`). O ledger só avança *depois* do write físico (`persist_records :606-636`).
- **Retry da memória de NPC** (`pending_npc_memory`, `services/memory_retry.py`, fila ≤50): sucessos saem da fila imediatamente; falhas travam `archive_due=True` (`:375-406`).
- **Prompt** (`:640-665`): `<ROLE>Memory Manager`, resumo anterior, histórico recente (6 msgs) e `CANONICAL_GROUNDING` (local→região do mapa, inventário mecânico atual, aparência canônica dos NPCs em cena). Saída estruturada `MemoryUpdate{new_summary, important_facts[], chronicle_entry}` (`:34-72`), com `field_validator(mode="before")` que coage dicts da LLM em strings e descarta wrappers de transcript (bug real de 2026-07-18).
- **Guard**: se `result` não for `MemoryUpdate` (FallbackLLM devolve `AIMessage`) cai em `_extract_summary_plain` — preserva ao menos o resumo e persiste os fatos *autoritativos* (`:673-745`).
- **Política de gravação**: `important_facts` livres viram `inference` (speculative). Em turno de conflito, com rejeições de evento/narrativa ou `canonical_only`, **os fatos livres são suprimidos** (`suppress_free_facts :628`): a prosa não pode reintroduzir fato rejeitado. O resumo sofre `sanitize_location_grounding`, `sanitize_inventory_grounding`, `sanitize_npc_identity_grounding` (corte de frases que contradizem mapa/inventário/aparência).
- **Crônica**: `ConflictSummary` entra como `kind="conflict"` (idempotente via `consumed_conflict_ids`); a prosa do menestrel entra como `kind="prose"` apenas se não houve supressão (`:895+`).

### 4.3 Retrieval de volta ao prompt

- `_format_memory_documents` (`rag.py:610-652`): reconstrói o registro a partir dos metadados do FAISS (documento sem metadado = legado); para o mesmo texto prefere maior confiança; devolve só os **2** primeiros (`order[:2]`).
- `context_builder.build_context_pack` (§5) adiciona, em ordem: `[RESUMO NARRATIVO | speculative]`, os últimos 20 `memory_facts` ativos (especulação com ≥20 turnos é descartada, `active_memory_facts :539-553`), depois as leituras de sessão e de NPC (rotuladas `legacy_unverified` quando sem prefixo). Todo item passa por `validate_narrative(channel='context')` e por `find_strict_unrevealed` (fail-closed).

---

## 5. Contexto: `context_builder.py` e `context_sources.py`

### 5.1 Aquisição concorrente (`services/context_sources.py`)

- `embed_context_query` (`:44`) faz **um** embedding do texto da consulta (`rag.prepare_shared_query_vector`), limitado por semáforo (`RPG_EMBEDDING_MAX_CONCURRENCY`, default 2).
- `_default_readers` (`:63`) monta leitores `lore` (global, `max_visibility="public"`), `session` (se `game_id`) e `npc` (se `npc_id`). Se o vetor compartilhado falhou mas existia provider compatível, os leitores devolvem `""` — **não** repete a mesma chamada ao provider por escopo (multiplicaria latência).
- `acquire_context_sources` (`:100`) roda os leitores em `ThreadPoolExecutor` (≤3 workers, semáforo global `RPG_CONTEXT_GLOBAL_CONCURRENCY` 12), com `copy_context().run` por tarefa (preserva identidade/correlação sem vazar atribuições). Falha de um leitor ⇒ `status="degraded"`, não derruba o turno; ordem do resultado é determinística (lore, session, npc).

### 5.2 Montagem com orçamento (`services/context_builder.py`)

`build_context_pack(state, query, purpose, token_budget=3500, game_id, npc_id)` (`:430`), `purpose ∈ {story, npc, combat_narration, planning}`:

1. `scene_entities = npcs_for_context(state)` (+ local atual) — evita arrastar NPC de outra cena (§7).
2. `collect_dynamic_facts` (`:181-252`) renderiza em `ScoredFact`s: controlador do local atual; últimos 100 eventos do `event_log` (`render_event`); `revealed_facts`; resumo dinâmico do local; edges efetivas (`resolve_edges`, com `include_hidden = purpose == "planning"` — só o **planejador de campanha** vê edges `hidden/secret`); `EntityState` notável (mortos/deslocados).
3. Pontuação (`score_fact :124`): `0.35·relevância(termos da query) + 0.25·mesmo-local + 0.20·entidades-em-cena + 0.10·impacto(tipo de evento) + 0.10·recência (1 − turnos/50)`. Sem embeddings, offline. Impacto: `npc_killed`/`location_control_changed`=1.0, `secret_revealed`/`route_blocked`=0.8, `route_cleared`=0.6, resto 0.4.
4. Orçamento (`ContextBudget :79`, 3500 tokens): cotas por seção `current_state 25% · active_location 20% · relations 15% · entities 15% · lore 15% · session_memory 10%`. `_assemble` (`:255-319`) preenche seção a seção por score decrescente; **sobra de cota rola para a próxima**; teto global = 105%; tokens = `ceil(chars/4)` (`estimate_tokens :115`). Item cortado vai para `discarded_evidence` com razão (`visibility`, `section_or_global_budget`, `unknown_section`).
5. Lore e memória entram como "fatos" de score alto, a memória particionada em linhas ≤600 chars para que um bloco grande não seja indivisível.
6. `ContextPack` (`:102`): `world_state_block` (`<ESTADO_ATUAL_DO_MUNDO>…`, ou "Sem mudanças registradas…"), `lore_block`, `memory_block`, `total_tokens_est`, `dropped`, `evidence_ids`, `discarded_evidence`.

No prompt do storyteller (`agents/storyteller.py:659-668`): `{pack.world_state_block}` + a frase "se o ESTADO ATUAL contradisser o lore/fatos, o ESTADO ATUAL VENCE", depois `<MEMORIA_RECENTE>{memoria_recente}</MEMORIA_RECENTE>` e `<LORE_PUBLICO_CANONICO>{lore_context}</LORE_PUBLICO_CANONICO>`. Consumidores: storyteller (`:534`), npc_actor (`npc.py:428`, com `npc_id`), combat (`combat.py:282,942`), campaign_manager (`campaign_manager.py:118`, `purpose="planning"`).

Também no módulo: `utility_context_block` (`:398`) injeta as capacidades utilitárias da ficha no prompt do narrador (gate determinístico).

---

## 6. Segredos e não-onisciência

Três camadas independentes de proteção:

1. **No índice**: chunks `hidden/secret` nunca saem de `query_rag/query_global_by_vector` (default `public`; `vis_rank` falha fechada). Segredos de NPC ficam em docs `hidden` separados do doc público.
2. **Por assinatura de texto** (`services/secret_signatures.py`): `SECRET_SIGNATURES` guarda frases da *verdade oculta* de quatro segredos — `pacto_valerius` ("pacto com daruun", "em troca de imortalidade"…), `rede_carmesim`, `arauto_identidade`, `rei_subterraneo` (`:17-33`); `PUBLIC_RUMOR` dá a versão neutra de cada um. `find_unrevealed` (`:71`) compara com o `revealed_corpus` (`:45`): eventos `secret_revealed`, `projection.facts`, **o `narrative_summary`** e `player.known_secrets` — se o jogador já ouviu a Magda contar o pacto, a narração repetindo isso não é vazamento (fix D da sessão 23). `sanitize_beat` (`:85`) substitui o beat inteiro por "Investigue os boatos em torno da ascensão de Valerius." quando vaza. É consumido pelo `campaign_manager` (beats/clímax/título do arco), pelo invariante `knowledge.secret_leak` do playtest e pela validação de memória (`find_strict_unrevealed`, `memory_provenance.py:170`). `looks_english` (`:107`) detecta beat em inglês para regenerar.
3. **Por evento**: `secret_revealed` só é aceito se existir edge `hidden/secret` no grafo para o alvo (validador), e grava `revealed_facts` na projeção — única forma "oficial" de o segredo passar a poder aparecer no `current_state` do contexto (`collect_dynamic_facts :210-215`).

O planejador (`campaign_manager`) vê hidden por design: ele *conhece* o mundo, mas o beat que ele escreve é sanitizado antes de chegar ao jogador/narrador.

---

## 7. NPCs em 3 camadas (`services/npc_layers.py`)

- **Camada 1**: todos os NPCs da sessão (`state["npcs"]`). **Camada 2**: `known_by_player` (API só mostra estes, **sem** `hidden_traits`: `visible_npc_view :192`). **Camada 3**: `in_scene` — gate do `npc_actor` (`is_in_scene :90`: só `in_scene=False` *explícito* bloqueia; ausente = legado presente).
- **Traits ocultos**: `roll_hidden_traits` (`:37`) sorteia 1–3 de `data/traits.json` por semente `sha256(npc_id|game_id)` (replay estável, peso 2 para traits da região). `tick_interaction` (`:149`) incrementa `interaction_count` e move traits maduros (`reveal_after`) de hidden para revealed; `trait_dc_modifier` (`:178`) soma os modificadores de DC de **hidden + revealed** (o mundo é real antes de ser conhecido).
- `npcs_in_scene` (`:104`) resolve alvo quando o router não nomeou ninguém (NPCs `in_scene` + party presente); sem candidato, o `npc_actor` delega ao storyteller (spec npc-fallback-sem-alvo).
- `npcs_for_context` (`:126`): elegíveis ao contexto = em party, `in_scene` com `home_location_id` compatível, ou vinculados ao local atual. Um NPC gerado fica preso ao local onde surgiu (anti-carrossel de "Sobrevivente moribundo"). `reset_scene` (`:154`): viagem ⇒ `in_scene=False` para todos.
- `services/entity_identity.py` unifica referências a NPC runtime (`npc_x`, `mv_x`, nome, alias) em chaves normalizadas (`normalize_runtime_npc_ref :18`), faz `coalesce_runtime_npcs` e resolve entidade canônica (`resolve_npc_entity_id :154`) — base do dedupe e do catálogo visual.

---

## 8. Mundo reativo: facções, clima, world simulator

- **Facções** (`world_utils.py`): `advance_factions :286` avança `progress += pace × períodos` (determinístico, sem RNG); ao cruzar 100, `resolve_faction_completions :331` aplica a *ascensão* autorada em `factions.json` — `dominar_local`, `expandir_regiao`, `elevar_perigo`, `invocar_entidade`, `eliminar_faccao`. A nota ao narrador só nomeia a facção se `faction_intel[id].known`; senão descreve só a consequência sentida (`perceived`). `apply_faction_reveal :416` (por NPC, em níveis existência → objetivo → progresso) e `apply_reputation :472` (via `faction_impacts` do storyteller, validadas por Python) alimentam `reputation_changed`.
- **Clima**: Markov por região (`advance_weather :827`) a cada mudança de período; fenômeno **global** tica/expira e, sem evento ativo, rola `maybe_start_global_weather :807` (6% base + 3% por nível de perigo acima de 1, via rng determinístico). `weather_effects :912` afeta percepção/ataque/DoT/descanso; luz (`light_level :888`) soma à percepção.
- **World simulator** (`agents/world_simulator.py`): ao descansar/viajar, `propose_world_pulse :77` pede à LLM (FAST) um `WorldPulse{rumor, fact, danger_shift}` com a regra "só sinais sem nome para facções que o jogador não conhece". `apply_world_pulse :115` é determinístico: clampa `danger_shift` a [−1,+1] e o perigo do local a [1,4] (`_apply_danger_shift :61`, `danger_overrides` em `world`), prefixa o rumor com `[ECOS DO MUNDO]` e **só** a consequência realmente aplicada vira memória (`"[mundo] O perigo de X mudou de 2 para 3."`) — o `fact` da LLM é prosa não verificada e não é promovido. Cai em `WorldPulseProposal(status="degraded")` se a estrutura falhar (guard de FallbackLLM). `simulate_world :141` chama `add_memory_to_session` direto, sem metadado de proveniência (cai como `legacy_unverified` ao ser relido; ponto de atenção).

---

## 9. Crônica

- `services/chronicle.py`: capítulos abertos quando muda `arc_title` do campaign_manager (`open_chapter :151`). Duas fontes de entrada: **milestones** determinísticos, gerados por template Python a partir de eventos *aplicados* de `CHRONICLE_EVENT_TYPES` (`npc_killed, location_control_changed, quest_completed/failed, secret_revealed, level_up, player_died/downed, unique_item_claimed, subclass_chosen, class_apex_unlocked`, `:27-42`); e **prosa** do menestrel (`kind="prose"`) vinda do archivist. `faction_relation_changed` está fora de propósito (ruído). Funções puras (devolvem cópia). `ensure_chronicle_ids` (`:110`) faz backfill idempotente de `chapter_id`/`entry_id` via uuid5.
- `chronicle_compression.py`: digest derivado (`ChronicleDigestLLM`: título, resumo ≤1800, personagens/locais/quests/itens únicos); dispara com ≥20 entradas não cobertas ou capítulo fechado (`should_compress :35`); fallback extrativo preserva milestones; o **raw e os milestones continuam autoritativos**, o digest nunca os substitui (hash de origem `chapter_source_hash :28` detecta digest obsoleto).
- `chronicle_search.py`: busca híbrida sem geração — léxica (termos ASCII normalizados) + semântica opcional fundidas por **RRF** (`reciprocal_rank_fusion :53`, k=60); devolve hits rastreáveis (`chapter_id`, `entry_ids`, `event_ids`, `source_kind`, faixa de turnos); `mode: "lexical_fallback"` quando não há vetores.
- `chronicle_repository.py`: persistência *derivada* (digests + documentos de busca) só no perfil Postgres, escopada por owner/campanha/epoch; as entradas raw continuam no `GameState`.

---

## 10. Exemplo ponta a ponta: de uma fala de NPC a um prompt futuro

Cenário: o jogador conversa com a Velha Magda no turno 12 (`world.turn_count = 12`).

1. **Roteamento**: `dm_router` classifica NPC e resolve o alvo (`active_npc_name`; sem alvo, `npcs_in_scene`). `npc_actor` chama `build_context_pack(state, query="Velha Magda <local> <fala>", purpose="npc", game_id, npc_id)` (`agents/npc.py:428`), que traz estado do mundo, lore pública e **a memória vetorial desta NPC** (`query_npc_by_vector`).
2. **Geração**: a LLM (FAST) devolve diálogo, `relationship_change`, `faction_reveals`, etc. O Python limita `relationship` a 0–10 (`npc.py:549`).
3. **Fato de memória** (`npc.py:552-558`): em vez de gravar o `memory_update` livre da IA, grava a **experiência observável**:
   `Turno 12: o jogador disse "Quem é você de verdade?"; Velha Magda respondeu "Há coisas que o Anel de Lama não esquece, forasteiro."`
4. **Proveniência**: `make_memory_fact(fato, provenance="npc_claim", source_id="npc:velha_magda", source_turn=12, canonical_entity_ids=["velha_magda"])` ⇒ `confidence="reported"` (derivada, não escolhida). `memory_metadata` achata para `{memory_provenance:"npc_claim", memory_confidence:"reported", memory_source_id:"npc:velha_magda", memory_source_turn:12, …}`.
5. **Persistência física**: `add_npc_memory(game_id, npc_id, [fato], metadatas=[…])` (`rag.py:1052`) abre o índice `data/saves_memory/<game_id>/<npc>/` **pinado ao provider da meta** (ou cria com o provider ativo e grava `embeddings_meta.json`), faz `add_texts` e `save_local`. Se falhar, o fato vai para `pending_npc_memory` (fila ≤50, deduplicada, `services/memory_retry.py:51`) e `rag_persistence_error` é setado.
6. **Ledger**: só se o write físico teve sucesso, `commit_memory_facts` espelha o mesmo registro em `state["memory_facts"]` (`npc.py:614-628`) — mesmo `memory_id`, portanto sem duplicata se o archivist reescrever. O `updates` também seta `archive_due=True` e `memory_fact_policy="canonical_only"`: neste turno o archivist **não** extrairá fatos livres da conversa (a fala de NPC não pode virar fato global por inferência).
7. **Fim de turno**: o `archive_node` processa `pending_world_events` (se o diálogo gerou `secret_revealed`, só passa se o validador achar a edge hidden/secret e ainda não revelado), valida a prosa, atualiza `narrative_summary` (≤1200 chars, sanitizado contra mapa/inventário/aparência) e registra milestones na crônica.
8. **Volta ao prompt (turno 14)**: o jogador pergunta de novo a ela. `build_context_pack(… npc_id)`:
   - `embed_context_query` gera 1 vetor; `acquire_context_sources` lê em paralelo lore (pública), sessão e NPC;
   - `query_npc_by_vector` → `_format_memory_documents` reconstrói o registro dos metadados e rende `[RELATO | npc_claim | fonte npc:velha_magda | turno 12] Turno 12: o jogador disse …`;
   - passa por `validate_narrative(channel='context')` e `find_strict_unrevealed` (se o texto contivesse "pacto com daruun" sem `secret_revealed`, seria descartado);
   - entra em `memory_parts` junto do `[RESUMO NARRATIVO | speculative] …` e dos `memory_facts` ativos; a seção `session_memory` tem 10% do orçamento (350 tokens de 3500; sobra rola);
   - o `npc_actor` lê `pack.memory_block` como `relevant_memory`. O storyteller, quando narrar a próxima cena, vê o mesmo bloco como `<MEMORIA_RECENTE>` — rotulado como RELATO, para a LLM tratar como "o que ela disse", não como verdade do mundo.

Segundo exemplo curto (evento canônico): o storyteller propõe `npc_killed` para `npc_comandante_thrace`. A pré-validação (`storyteller.py:696`) passa ⇒ vai a `pending_world_events`. No archivist: `validate_proposal` (alvo existe, `type npc`, vivo) ⇒ `apply_event` marca `alive=False` ⇒ milestone "Comandante Thrace tombou por suas mãos." ⇒ `run_rules`: `rule_faction_leader_death` ⇒ estabilidade da facção cai, `location_control_changed` derivado, ripple. `_event_memory_records` converte cada evento novo em `canonical_event`/`confirmed` com `source_id=<event_id>` (`archivist.py:145-168`) e o grava no FAISS da sessão. Nos turnos seguintes, `collect_dynamic_facts` renderiza `[turno 15] Comandante Thrace foi morto (por: player).` com impacto 1.0 na seção `current_state` e a lore estática sobre ele perde para o "ESTADO ATUAL VENCE".

---

## 11. Pontos de atenção e riscos observados

- **Documentação desatualizada**: CLAUDE.md fala em `models/text-embedding-004`; o código usa Jina como primário (`rag.py:46-53`). O reindex depende de provider único por índice — misturar é proibido e a falta da key desativa o índice silenciosamente (só um warning).
- **Limite de retrieval baixo**: lore devolve no máximo 2 chunks (`k=2, fetch_k=6`), memória de sessão/NPC rende no máximo 2 documentos (`order[:2]`, `rag.py:652`) apesar de buscar 6 — a continuidade longa depende muito do `memory_facts` (últimos 20) e do resumo.
- **`simulate_world` grava sem proveniência** (`world_simulator.py:152-153`): o fato "[mundo] O perigo…" é lido de volta como `legacy_unverified`, embora seja consequência aplicada pelo motor (candidato a `canonical_event`).
- **Cache em módulo** (`_entities_cache`, `_codex_index_cache`, `_traits_cache`): mudanças de `data/` em runtime exigem `clear_cache`/`clear_codex_index_cache`.
- **Assinaturas de segredo são curadas à mão** (4 segredos, frases-chave em minúsculas, matching por substring): cobre os segredos mapeados, mas um novo segredo `hidden` exige atualizar `SECRET_SIGNATURES` além de marcar o doc — o lint de visibilidade (`content_validator.py:323`) não gera assinaturas.
- **Quarentena atômica de eventos** é conservadora por desenho: uma proposta inválida descarta também as válidas irmãs da mesma resposta.
- **Perfis de runtime**: o caminho pgvector exige vetores 1024-d; `prepare_shared_query_vector` recusa outras dimensões — Jina v3 (1024) é compatível, `text-embedding-3-small` (1536) não.
- **Reindex**: `python rag.py` aborta com erros de lint e, em caso de sucesso, apaga o pin anterior; os índices de sessão antigos continuam pinados no provider antigo e só reabrem se aquele provider ainda estiver disponível.
