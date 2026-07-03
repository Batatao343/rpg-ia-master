# CHANGELOG — histórico de sessões

> Histórico detalhado das sessões de desenvolvimento. NÃO é carregado automaticamente
> no contexto — consultar sob demanda. Estado atual: `ESTADO_ATUAL.md`.

---

## 2026-07-03 (5) — Fase 3.3: Quest log (`done`)

- **`state.py`:** `Quest(TypedDict, total=False)` (`id/title/description/status/
  origin_name/origin_entity_id/location_id/created_turn/resolved_turn/reward_hint`);
  `GameState.quests: List[Quest]` (só side quests — main quest continua view pura do
  `campaign_plan`, zero estado novo).
- **`services/structured_outputs.py`:** `ProposedQuest` — schema de CRIAÇÃO de side
  quest. Conclusão não ganhou schema novo: reusa `ProposedWorldEvent(type=
  "quest_completed", target_id=quest_id, payload={"quest_id": ...})`, mesmo canal já
  usado por `npc_killed`/`secret_revealed` desde a 2.6.
- **`services/quest_log.py`** (novo, puro): `register_proposed_quests` (dedupe por
  `difflib.SequenceMatcher≥0.75` contra ativas, zera `location_id`/`origin_entity_id`
  inválidos em vez de rejeitar a quest, teto `MAX_ACTIVE_QUESTS=8`), `complete_quest`,
  `fail_orphan_quests` (gera `GameEvent` `quest_failed`, `source="system"`),
  `quest_markers`.
- **Hooks nos agentes:** `StoryUpdate`/`NPCResponse` ganham `proposed_quests`, lidos
  dentro dos trys já existentes (mesmo guard de `proposed_events`/`faction_reveals`).
  No `npc_actor`, `origin_name`/`origin_entity_id` são SOBRESCRITOS em Python
  (`_canonical_npc_id`, match por nome no grafo) — o LLM só controla title/description/
  location_id/reward_hint. `storyteller` ganha bloco de prompt `<QUESTS_ATIVAS>`
  (análogo a `<ENTIDADES_CANONICAS>`, Fase 2.6).
- **`services/world_validators.py`:** `_v_quest_completed` ganha branch `payload.
  quest_id` no topo (checa `state.quests` ativas); ausência de `quest_id` cai no modo
  beat original (Fase 2.6, sem mudança — `test_fase26.py` continua verde).
- **`services/event_processor.py`:** `apply_event` ficou INTOCADO (contrato "só mexe
  em projection" preservado — quest completion/failure não é efeito de projection).
  `process_pending_events` ganha variável local `quests`/`quests_changed`, mesmo
  padrão de `chronicle`/`chronicle_changed`: ao aplicar `quest_completed` com
  `quest_id`, embute `payload["quest_title"]` (lookup em `state.quests`) ANTES do
  milestone; ao aplicar `npc_killed`, chama `fail_orphan_quests` e anexa os
  `quest_failed` resultantes ao `event_log`.
- **`services/chronicle.py`:** `quest_failed` entra em `CHRONICLE_EVENT_TYPES`/
  `CHRONICLE_TEMPLATES`; `render_milestone` usa `payload.get("quest_title") or
  _name(target_id)` — `target_id` de quest é um uuid (quest_id), não id de grafo,
  `_name()` não resolveria (mudança no-op pros outros tipos de evento).
  `_v_npc_killed` só aceita NPC canônico → falha sistêmica (R4) só existe pra quests
  com origem no grafo; NPC gerado em runtime nunca falha quest por essa via (aceitável).
- **API/frontend:** `_quest_block(plan, quests)` vira `{main, side, markers}` (main =
  shape antigo + `arc_title`; side = ativas + até 5 resolvidas mais recentes; markers =
  `[{quest_id, location_id}]` pro mapa). Achado da exploração: o bloco `quest` antigo
  NUNCA teve componente React consumindo — aba "Missões" (`QuestsTab.tsx`) é
  greenfield puro, não migração. `WorldMap` ganha prop `markers` (selo ◆ no local).
- **Suíte:** 258 → **290 verdes** (+32 em `tests/test_fase33.py`, ids reais de
  `data/graph/entities.json` — `npc_valerius`/`npc_grum`/`nova_arcadia`). `npm run
  build` ok. `smoke_api.sh` ok.
- **Smoke com LLM real executado e verde** (4 requests): NPC "Valdir" (Gemini SMART)
  propôs quest real ("A Sede do Quebrado") com `origin_name` corretamente sobrescrito
  pelo código a partir do `npc_data`, `origin_entity_id=""` (NPC runtime, não
  canônico — comportamento esperado); turno seguinte concluiu a quest via
  `quest_completed` proposto pelo LLM com `quest_id` correto; milestone na crônica
  mostrou "A missão "A Sede do Quebrado" foi concluída." — título, não uuid.
  Confirma mapeamento correto de `proposed_quests` nos DOIS agentes (risco clássico
  "MockLLM esconde bug de mapeamento" — mitigado).

---

## 2026-07-03 (4) — Fase 3.2: Codex do jogador + bestiário progressivo (`done`)

- **`state.py`:** `BestiaryKnowledge(TypedDict, total=False)` (`seen/fought/defeated/
  first_seen_turn/last_update_turn`); `GameState.bestiary_knowledge: Dict[str,
  BestiaryKnowledge]` (chave = id de `data/bestiary.json`).
- **`services/discovery.py`** (novo, puro): `normalize_bestiary_id` (id de instância
  `{bestiary_id}_{N}` → id real, valida contra `gamedata.BESTIARY`), `record_encounter`/
  `record_kills`/`record_rumor` (contadores aditivos, dict novo), `knowledge_tier`
  (`BESTIARY_TIERS`: 1 Rumores/seen≥1, 2 Encontrada/fought≥1, 3 Estudada/defeated≥3,
  4 Dominada/defeated≥7), `bestiary_view` (campos crescentes por grau: nome+regiões →
  +descrição/tipo → +HP/defesa/nomes de ataque → +dano/behavior/loot), `player_codex`
  (agrega locations/factions/characters/creatures/secrets — 100% derivado do save já
  existente, zero estado novo para essas 4 categorias).
- **`services/codex_loader.py`:** `codex_index()` (cache módulo-level, id→path, mesmo
  padrão de `os.walk` de `load_codex`) e `codex_body(entity_id)` (corpo truncado a
  2000 chars, `""` se `visibility != "public"` ou id não achado — não-onisciência).
- **Hooks de combate (`agents/combat.py`):** spawn (`is_combat_start and not active`) →
  `record_encounter` (1x/combate, contorna dupla contagem por round); bloco de `dead`
  (fim de round) → `record_kills`.
- **Rumor sem combate (R3) — desvio da spec original:** a leitura literal ("threat_alert
  cria rumor") não fechava — a criatura que fugiu já teria `fought≥1` nesse combate,
  contradizendo "seen sem fought". Resolvido em `check_encounter` (`world_utils.py`):
  os branches que NOMEIAM uma criatura concreta ANTES do combate (reforços consumindo
  `threat_alert.enemy_id`; `ruler`/`danger>=4` via `pick_encounter_enemy`) agora
  retornam `enemy_id`; `agents/storyteller.py` (onde o `SystemMessage("COMBAT START")`
  é montado) chama `record_rumor` só quando `enemy_id` existe — antes do spawn real.
  `register_flee_alert` ganhou parâmetro `enemy_id` (opcional, retrocompatível) pra
  carregar o id do bestiário no alerta até o consumo.
- **Persistência/API:** `bestiary_knowledge` com default `{}` em save/load (sem
  migração — save antigo simplesmente não tem o campo); `initial_state` em
  `game_engine.py` E `api.py::new_game` (duas cópias independentes); `_world_block`
  ganhou `turn_count` (não existia — necessário pro refetch da aba); `GET /game/codex`
  segue o padrão real de `/game/state` (`f"saves/{game_id}.json"`, não
  `load_game_state(game_id)` como a spec sugeria de forma simplificada).
- **Frontend:** `CodexTab.tsx` (novo) — 5 categorias com sub-nav, selo I–IV por
  criatura (silhueta CSS em cinza no grau 1), corpo do Codex renderizado via `mdLite`;
  primeira aba do HUD com fetch próprio (`useEffect` + `getCodex`), refeito quando
  `world.turn_count` muda com a aba aberta (`ChronicleTab`, por comparação, só usa
  props — não tinha esse padrão antes).
- **Suíte:** 228 → **258 verdes** (+30 em `tests/test_fase32.py`, usando ids reais de
  `data/bestiary.json`/`data/codex/` — zero fixture inventada, evita mascarar bug de
  id/path). `npm run build` ok. `smoke_api.sh` com checagem nova de `/game/codex`
  (200 OK) — smoke completo verde numa API local (mock, sem chave).
- **Zero LLM na fase** — sem guard de `FallbackLLM` necessário (100% Python
  determinístico). Detalhe completo dos desvios: `specs/fase-3.2-conhecimento-
  revelavel.md` §8.

---

## 2026-07-03 (3) — Fase 3.1: Diário + Crônica por capítulos (`done`)

- **`services/chronicle.py`** (novo, puro): `CHRONICLE_EVENT_TYPES` (npc_killed,
  location_control_changed, quest_completed, secret_revealed — faction_relation_changed
  fica FORA por ruído), `CHRONICLE_TEMPLATES` voltados ao jogador, `render_milestone`
  (nome canônico via `context_builder._name`; `{by_player}` derivado de
  `actor_id == "player"`), `append_entry`/`open_chapter` puros,
  `default_chapter_title(region)`.
- **Schema:** `ChronicleEntry`/`ChronicleChapter` em `state.py`;
  `GameState.chronicle: List[ChronicleChapter]`; `CampaignPlan.arc_title`.
- **event_processor:** todo evento APLICADO (base + cascata da rules engine) de tipo
  crônica gera milestone determinístico com `event_id` auditável; chave `chronicle`
  só entra nos updates quando houve mudança.
- **archivist:** prosa (`chronicle_entry`) vira entrada `kind="prose"` appendada SOBRE
  o chronicle já atualizado pelos milestones (merge `{**event_updates, **updates}` —
  ordem invertida de propósito); prompt instrui a não repetir fatos secos.
- **campaign_manager:** `CampaignPlanModel.arc_title` (mesmo call do planner, zero
  request extra) com instrução de persistência; título novo → `open_chapter`; fallback
  mantém arco atual (não fragmenta por erro de LLM). MockLLM devolve
  `"A Verdade Enterrada"` estável.
- **Persistência:** backfill em `load_game_state` — `chronicle: List[str]` antigo vira
  capítulo único "Crônica da jornada" (entradas `prose`, turn 0).
- **API/frontend:** `GameResponse.chronicle` = capítulos (`_chronicle_block` filtra
  entradas vazias); `/game/new` e `game_engine.py` criam capítulo 1 no turno 0
  (`default_chapter_title`); `ChronicleTab` renderiza capítulos reversos com header
  (título + "desde o turno N"), milestone = ⚔ + `chron--milestone`, prosa = ❧.
- **Suíte:** 211 → **228 verdes** (+17 em `tests/test_fase31.py`). `npm run build` ok.
  Smoke API real ok (capítulo inicial + capítulo novo no primeiro replan). Falha do
  `smoke_api.sh` no /game/new é encoding de acento do curl do Git Bash (ambiente,
  não código — body ASCII passa).
- **Smoke com LLM real executado** (mesma sessão, 2 req gemini-pro direto em
  `_build_plan`): sem arco anterior o planner inventou "Fagulhas na Chuva Fria"
  (mapeamento do campo novo ok); com arco "A Sombra sobre Nova Arcádia" e mesma
  situação, MANTEVE o título (persistência ok). Ver spec §6.
- **Fix `scripts/smoke_api.sh`:** curl do Git Bash no Windows corrompe UTF-8 inline
  (`-d` com "Nova Arcádia" → bytes cp1252 → 422 "error parsing the body"); body do
  `/game/new` agora vai via `--data-binary @arquivo`. SMOKE OK completo.

---

## 2026-07-03 (2) — Faxina de código morto + auditoria de gameplay → Fase 4

- **Removidos** (zero importadores em produção, verificado por grep): `agents/ruler_completo.py`
  (CLAUDE.md alegava uso pelo storyteller — falso), `engine_utils.py` + `dice_system.py`
  (só testes importavam), `COMMON_LOOT_TABLE` (gamedata.py). 5 testes órfãos de
  `test_mvp.py` removidos junto. Suíte 216 → **211 verdes**.
- **Mantidos de propósito:** `XP_TABLE` (consumidor chega na 4.1), `party`/`CompanionState`
  (4.5), `frontend/` vanilla (fallback VIVO no api.py quando `web/dist` não existe).
- **Docs corrigidos:** CLAUDE.md (estrutura de pastas, storyteller sem "ruler",
  `world_lore.txt` fantasma, `world_map.json` → Valoria 30 nós), README.md, comentários
  mortos em `storyteller.py`/`mock_llm.py`.
- **Auditoria de jogabilidade** (achados-chave): `XP_TABLE` sem consumidor — xp nunca
  incrementa, NÃO existe progressão; buffs/passivas só texto (dano/AC não leem
  `active_conditions`; só DoT funciona); party só schema (combate é 1×N estrito);
  craft/shop/loot 100% LLM (sem receitas/estoque/drop tables); poção inutilizável em
  combate (parser só resolve habilidades); inventário inicial com nomes livres que o
  `ARTIFACTS_DB` não resolve; spawn narrativo sem teto de CR; campo `abilities` de
  inimigo decorativo; morte do player sem narrativa.
- **ROADMAP:** nova **Fase 4 — Gameplay Core** em 6 fatias `draft` (4.1 progressão/XP/
  árvore de habilidades · 4.2 buffs/passivas mecânicos · 4.3 inventário/equip/itens
  usáveis · 4.4 economia determinística · 4.5 party · 4.6 dificuldade/IA/morte).
  Fases antigas renumeradas (playtest 4→5 ... contract tests 10→11). Backlog consolidado:
  Party→4.5, Crafting→4.4, Lore Multi-Índice obsoleto (Codex 2.5 cobre), Mapa robusto
  reduzido ao restante (sub-locais, tempo de viagem variável, economy_tags).

## 2026-07-03 — Fase 2.8: Context builder com orçamento de tokens

Entregas (spec `specs/fase-2.8-context-builder.md`):
- `services/context_builder.py` — `estimate_tokens` (chars/4), `score_fact`
  (0.35 rel + 0.25 local + 0.20 entidade + 0.10 impacto + 0.10 recência), `render_event`
  (`EVENT_TEMPLATES`; nome canônico via `gr.get_entity`, não id cru), `collect_dynamic_facts`,
  `_assemble` (budget por seção + carry), `assemble_pack`, `build_context_pack`.
- Correções vs spec (aplicadas): evento usa `turn` (não `day`), `actor_id`/`target_id`;
  sem `visibility` no evento (lore filtra por `query_rag(max_visibility)`; `secret_revealed`
  só via `revealed_facts`); `location_summaries`/`revealed_facts` moram em `world_projection`;
  `build_context_pack` ganhou `game_id`/`npc_id` opcionais.
- Agentes: `agents/storyteller.py`, `agents/npc.py`, `agents/combat.py`,
  `agents/campaign_manager.py` — `query_rag`+`narrative_summary` manuais → pack.
- Suíte na época: 216 verdes (201 baseline + 15 da 2.8). Smoke LLM real pendente de quota.

## 2026-07-02 — Fase 2.7: Rules engine sistêmica

Entregas (spec `specs/fase-2.7-rules-engine.md`):
- `services/rule_engine.py` — `resolve_path` seguro (só literais/`event.`/`target.`/
  `component:`; dunder + expressão arbitrária → `RuleActionError`), `check_conditions`,
  `execute_action` (ops: set_entity_state, adjust_faction_stability, disable_controls_edges,
  create_dynamic_edge, emit_event), `run_rules` (dona da cascata + anti-loop depth 2).
- `data/graph/world_rules.json` (5 regras) + `data/graph/components.json` (overlay
  `power_vacuum_trigger` em 22 líderes/governantes). Overlay é **migration-safe**
  (`migrate_lore_nova.py` sobrescreve entities.json com `components:{}`), mergeado por
  `graph_resolver.load_entities`.
- Modelo HÍBRIDO: estrutura (líder/controle/rival) DERIVADA dos edges (`leads`/`controls`/
  `enemy_of`/`operates_in`); componente só carrega delta/sucessor/override + é o discriminador.
- `event_processor.process_pending_events` chama `run_rules` após cada `apply_event`.

## 2026-07-02 — Fase 2.6: Structured world changes

Entregas (spec `specs/fase-2.6-structured-events.md`):
- `services/structured_outputs.py` — `ProposedWorldEvent` / `WorldChangeProposal` (Pydantic).
- `services/world_validators.py` — `validate_proposal(dict, state)` → `ValidationResult(ok, reason)`;
  regras por tipo (npc_killed, secret_revealed, location_control_changed, quest_completed,
  faction_relation_changed) via `graph_resolver`; revalida do zero (dict malformado = rejeitado).
- `services/event_processor.py` — `process_pending_events` (valida→GameEvent→append→aplica→limpa fila)
  + `apply_event` puro (efeito direto na projection, SEM cascata — isso é a 2.7).
- `storyteller` propõe via `StoryUpdate.proposed_events` + bloco `<ENTIDADES_CANONICAS>` no prompt.
- `combat` gera `npc_killed` **determinístico** (`_kill_events`) p/ inimigo canônico — sem LLM.

## 2026-07-02 — DX: tooling do Claude Code (auditoria de fricção)

Auditoria de 20 sessões de transcripts achou: prefixo de PATH repetido 180×, ~36KB de
docs carregados toda sessão, leituras de lore de 30–56KB, 120 runs de pytest verbosos.
Entregas:

- **Docs de sessão em dieta:** `@REFERENCE.md` removido do auto-load do `CLAUDE.md`
  (leitura sob demanda); `ESTADO_ATUAL.md` de 13.3KB → ~5.5KB; histórico de sessões
  movido para este `CHANGELOG.md` (não carregado). Economia ~6-7K tokens/sessão.
- **Skills de projeto:** `/qa` (pytest token-lean, só falhas + resumo; `--lf` p/ iteração)
  e `/wrap-up` (ritual de fim de tarefa: suíte + docs + commit via caveman-commit).
- **`scripts/smoke_api.sh`:** smoke da API (health, options, map, /game/new, /game/state,
  /game/action + limpeza do save) — substitui loops de curl reescritos a cada sessão.
- **Hook `reindex-reminder.js`** (PostToolUse Edit|Write): editar `lore_nova/`,
  `data/codex/` ou `data/rules.txt` injeta lembrete de rodar `uv run python rag.py`
  (1x por sessão). Ativação junto com a allowlist em `.claude/settings.proposed.json`
  (renomear para `settings.json` após revisão — escrita direta bloqueada em auto mode).
- **Regra anti-leitura-gigante** no `CLAUDE.md`: lore/codex/JSONs grandes = Grep ou
  Read parcial, nunca Read inteiro.
- Pendente (ação manual, bloqueada em auto mode): PATH permanente do uv —
  `[Environment]::SetEnvironmentVariable('Path', "$env:APPDATA\Python\Python314\Scripts;" + [Environment]::GetEnvironmentVariable('Path','User'), 'User')`.

## 2026-07-02 — Fase 2.5b: Valoria nos dados mecânicos + combate com comportamento

- **Mapa** (`data/world_map.json`): 30 nós — 12 macro-regiões do grafo + 18 sublocais
  (anéis de Nova Arcádia, Fortaleza de Vorr, O Trono...). Grafo conexo (teste BFS),
  `region_id` em todo nó, 1 `start: true` por região. Start global: `nova_arcadia`.
- **Fações** (`data/factions.json`): 18 fações de Valoria (legiao_ferro, mao_sombria,
  filhos_chama_azul, tribos_devoradores_sol...) com goal/pace/ascension derivados do
  Codex; targets de ascensão apontam para o mapa novo.
- **Raças** (`data/origins.json`): 6 jogáveis (Humano, Elfo, Anão da Fuligem, Vrel,
  Cinzéu, Osshari) com **traits mecânicos** da lore — `apply_racial_traits()` em
  `character_creator.py` aplica bônus de atributo/recursos/defesa/ouro/itens em Python;
  `condition_resists` (ex.: Anão ignora veneno) e `racial_save_bonus` respeitados por
  `combat_mechanics`. Ficha ganha `racial_traits`/`condition_resists`/`racial_save_bonus`
  (`state.py`; saves antigos: campos ausentes = sem efeito, sem crash).
- **Bestiário** (`data/bestiary.json`): 84 entradas curadas com `regions` e `behavior`;
  criaturas do grafo usam `mon_<slug>`, combatentes de fação `enemy_<slug>` + campo
  `faction` (mapeia fação → soldado no encontro).
- **Combate com personalidade (R8):** perfis `tatico` (escolhe ataque por situação, foge
  por moral — `flee_below`/`pack_morale`), `feroz` (maior dano, frenesi +2 com HP<50%,
  NUNCA foge — urso-titã), `covarde` (foge cedo), `implacavel` (rotaciona ataques, nunca
  foge) — determinístico em `combat_mechanics.py` (`choose_enemy_attack`, `check_morale`,
  `get_behavior`). Status novo `"fugiu"`: não conta como vitória nem loot; combate sem
  mortos (todos fugiram) NÃO roteia para loot. Ataques de inimigo aplicam condições
  embutidas na string de dano ("+ veneno" → Condition no player, respeitando resist racial).
- **Fuga → alerta (R10):** `world["threat_alerts"]` (`world_utils.register_flee_alert`,
  chamado pelo combat_node); alerta ativo na REGIÃO dispara encontro de reforços 1x
  (validade 6 turnos, consumido ao disparar, expira sozinho). Backfill em `ensure_world`.
- **Encontro por região (R11):** `world_utils.pick_encounter_enemy()` sorteia criatura
  CONCRETA do bestiário por região/perigo/fação (BOSS nunca sai aleatório) —
  `check_encounter` devolve hint com o nome exato → spawn cai no cache (menos 1 LLM call).
- **Identidade:** `data/graph/entities_extra.json` (curadoria manual: sublocais +
  combatentes de fação; `migrate_lore_nova.py` NÃO o toca) mergeado em
  `graph_resolver.load_entities()` — canônico vence conflito. Teste de integridade
  cruzada cobre os 4 JSONs mecânicos.
- **Limpeza (R5):** `data/world_lore.txt` REMOVIDO; `mock_llm.py` agora usa `legiao_ferro`
  como fação simulada (era `selo_palido`).
- Testes: `tests/test_fase25b.py` (novo, 24 testes: integridade, mapa conexo, traits,
  moral/fuga/frenesi, alertas, sorteio regional) + repin de `test_fase0`/`test_fase2`/
  `test_world_sim` para os dados novos.

## 2026-07-02 — Limpeza de deps

Removidas do `pyproject.toml` deps sem nenhum `import` no código — `chromadb`, `graphviz`,
`kuzu`, `langchain-chroma`, `langchain-experimental`, `langsmith`, `streamlit` — leftovers
de planejamento anterior à 2.5 (o grafo de mundo virou JSON puro em
`services/graph_resolver.py`, não kuzu). `uv sync` + `uv run pytest` (116 verdes)
confirmaram nada quebrou. `stream_ctx.py` intocado — infra planejada pela spec 2.5b/2.8
(streaming futuro), não código morto.

## 2026-07-02 — Timeline de Valoria no Codex

`lore_nova/timeline_completa.txt` (Codex Omnia — 8 eras, da criação ao presente) ingerido
no Codex. Novo handler `parse_timeline()` em `scripts/migrate_lore_nova.py` gera
`data/codex/timeline/*.md` (1 doc por run de visibilidade, `type: timeline`, NÃO registra
entidade no grafo). Os 4 clusters de reveal que `secrets.txt` já protege (aprendiz→Arauto,
Rei Subterrâneo, pacto Valerius↔Daruun, Rede Carmesim) saem como `visibility: hidden` —
não vazam ao narrador público (`query_rag(max_visibility="public")`); o resto da história
é `public`. Curadoria explícita em `_TIMELINE_HIDDEN_CLUSTERS` (pares frase-inicial→
frase-final). 4 testes novos em `tests/test_fase25.py`. Codex reindexado (2579 chunks).

## 2026-07-02 — Fase 2.5: Codex + grafo de mundo

Lore REESCRITO em `lore_nova/` (universo **Valoria**, ~690KB), SUBSTITUI o lore antigo.
Spec `specs/fase-2.5-codex-world-state.md` → `done`:

- `scripts/migrate_lore_nova.py` → gera `data/codex/` (635 .md com frontmatter
  `id/type/name/tags/visibility`) + `data/graph/entities.json` (558 entidades: 12 regiões,
  28 fações, 141 NPCs, 10 raças, 340 monstros, 27 artefatos únicos).
  ⚠️ Re-rodar o script SOBRESCREVE curadoria manual no codex/entities.
- `data/graph/edges.json` (~70 edges curadas à mão) + `relation_types.json` (7 tipos).
  Estes o script NÃO toca.
- `services/graph_resolver.py` — edges efetivas = base − disabled + dynamic, com
  visibilidade; `get_current_controller`, `is_alive`. `services/codex_loader.py` —
  ingestão FAISS com metadados. `query_rag(..., max_visibility="public")` filtra
  `hidden`/`secret` do contexto do narrador (default preserva comportamento).
- `GameState` ganhou `event_log` / `world_projection` / `pending_world_events`
  (persistidos em `persistence.py`; saves antigos carregam com defaults vazios).
- Smoke real OK: reindex do Codex (2297 chunks), 1 turno real narrando lore de Valoria,
  chunks `secret` fora do contexto público.

## 2026-07-01 — Projeto vira spec-driven

`specs/` + convenção no `CLAUDE.md`; specs 2.5–2.8 criadas.

## 2026-06-26 — Multi-provider LLM + typewriter

- `get_llm()` suporta Gemini, Ollama, OpenAI e endpoints OpenAI-compatíveis (Qwen,
  LM Studio) via `LLM_PROVIDER` + vars no `.env`. Sem tocar nos agentes.
- Narrativa com efeito typewriter (palavra a palavra) no frontend React.
- `stream_ctx.py` criado com ContextVar SSE (infra para streaming real futuro).
- `MockLLM.stream()` adicionado para compatibilidade.

## 2026-06-26 — Otimização de turno

Turno reduzido de ~5-6 para ~2-3 LLM calls (commit `fcb14c0`).
