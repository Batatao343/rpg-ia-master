# ROADMAP — RPG IA (Revisado 2026-07-03)

> **Objetivo central:** Mundo vivo persistente com estado consultável, antes de features novas.
> 
> **Princípio:** Lore base (Codex) ≠ Eventos confirmados (event_log) ≠ Estado atual (world_projection).  
> LLM propõe. Motor Python valida e aplica. Tudo persistente e auditável.
>
> Complementa `CLAUDE.md` (arquitetura) e `ESTADO_ATUAL.md` (status).
> **Desenvolvimento é spec-driven:** o detalhe técnico de cada fase vive em `specs/` — este arquivo só resume e aponta.

---

## O que já foi entregue

| Fase | Status |
|---|---|
| **Fase 0** | ✅ ENTREGUE — Motor fundacional (LangGraph, agentes, combate determinístico, RAG FAISS, memória de sessão, grafo de 9 locais, relógio, viagem, fog of war, gating) |
| **Fase 1** | ✅ ENTREGUE — Frontend React+Vite (Witcher tone), HUD em abas, mapa, modos combate/exploração, crônica, typewriter effect |
| **Fase 2** | ✅ PARCIAL — Fações com objetivos/reputação, ascensão de ameaça, encontros temáticos, memória de NPC, world_simulator básico, beats de campanha |
| **Polishes** | ✅ ENTREGUE — Multi-provider LLM (Gemini/Ollama/OpenAI/Qwen), otimização 5-6→2-3 calls/turno, combate determinístico profundo |
| **DX (2026-07-02)** | ✅ ENTREGUE — Tooling do Claude Code: skills `/qa` e `/wrap-up`, `scripts/smoke_api.sh`, hook de reindex FAISS, docs de sessão enxutos (histórico → `CHANGELOG.md`), allowlist proposta (`.claude/settings.proposed.json`) |
| **Faxina (2026-07-03)** | ✅ ENTREGUE — Código morto removido: `agents/ruler_completo.py`, `engine_utils.py`, `dice_system.py` (zero importadores em produção), `COMMON_LOOT_TABLE`; testes órfãos removidos (216→211); CLAUDE.md/README corrigidos (documentavam módulos mortos) |

---

## ✅ ENTREGUE — Fase 2.5 a 2.8: Mundo vivo v1

Fundação arquitetural: mundo não muda mais por narrativa textual livre — camadas
separadas (Codex ≠ event_log ≠ projection), motor de regras sistêmico, contexto
orçamentado, estado auditável. **Todas as 4 fases entregues** (2.5b pendente só de
smoke LLM real).

> **Specs completas (fonte da verdade técnica):** [specs/fase-2.5](specs/fase-2.5-codex-world-state.md) · [specs/fase-2.6](specs/fase-2.6-structured-events.md) · [specs/fase-2.7](specs/fase-2.7-rules-engine.md) · [specs/fase-2.8](specs/fase-2.8-context-builder.md)

### Fase 2.5 — Codex estruturado + World State Graph → [spec](specs/fase-2.5-codex-world-state.md) ✅ ENTREGUE (2026-07-02)

Universo REESCRITO (`lore_nova/` — Valoria) vira Codex Markdown com frontmatter
(`data/codex/`, 635 arquivos via `scripts/migrate_lore_nova.py`) + grafo estático autoral
(`data/graph/`: 558 entidades, ~70 edges curadas, relation_types) + estado dinâmico no
save (`event_log` append-only + `world_projection` calculada). `graph_resolver` combina
base + dynamic − disabled com visibilidade; `codex_loader` ingere com metadados no FAISS;
`query_rag(max_visibility=...)` filtra segredos do contexto do narrador.

**Aceite entregue:** `get_current_controller("brekmar", projection)` responde pelo estado atual; smoke real narrou Valoria e segurou chunks `secret`.

**Adendo (2026-07-02):** `lore_nova/timeline_completa.txt` (Codex Omnia, 8 eras) ingerido em
`data/codex/timeline/` via handler `parse_timeline()`. Os 4 reveals que `secrets.txt` protege
(aprendiz→Arauto, Rei Subterrâneo, pacto Valerius↔Daruun, Rede Carmesim) ficam `hidden`; resto
`public`. Reindexado (2579 chunks). +4 testes (116 no total).

### Fase 2.5b — Valoria nos dados mecânicos + combate com comportamento → [spec](specs/fase-2.5b-valoria-dados-mecanicos.md) ✅ IMPLEMENTADA (2026-07-02; falta só o smoke real de LLM)

Dados mecânicos realinhados a Valoria com IDs do grafo: mapa (12 regiões + 18 sublocais,
grafo conexo), 18 fações com goal/ascension, 6 raças jogáveis com **traits mecânicos**
(bônus/resistências/saves aplicados em Python), bestiário curado (84 entradas com
`regions` + `behavior`) e `entities_extra.json` (curadoria que o migrate não sobrescreve).
**Combate com personalidade (R8-R10):** perfis `tatico/feroz/covarde/implacavel` — guardas
escolhem ataque e fogem por moral; urso-titã luta até a morte com frenesi; fugitivo gera
alerta de mundo que volta como reforço. Encontros sorteiam criatura concreta do bestiário
por região/fação (menos 1 chamada LLM). `world_lore.txt` removido.

### Fase 2.6 — Structured world changes → [spec](specs/fase-2.6-structured-events.md) ✅ ENTREGUE (2026-07-02)

LLM não altera mundo por narrativa livre: storyteller propõe eventos estruturados
(Pydantic), combate gera `npc_killed` determinístico; `world_validators` valida contra o
grafo e `event_processor` aplica na projection (via archivist, todo fim de turno).
`services/` ganhou `structured_outputs.py`, `world_validators.py`, `event_processor.py`.
177 testes offline. Smoke real Gemini ✅ (secret_revealed com id canônico validado; turno banal vazio).

**Aceite:** ✅ nenhuma mudança persistente sem validação; evento rejeitado não quebra o jogo.

### Fase 2.7 — Rules engine sistêmica → [spec](specs/fase-2.7-rules-engine.md) ✅ ENTREGUE (2026-07-02)

Entidades com componente `power_vacuum_trigger` (overlay `data/graph/components.json`,
migration-safe) disparam regras genéricas declarativas (`data/graph/world_rules.json`)
executadas sem eval (paths + ops whitelisted em `services/rule_engine.py`). Modelo HÍBRIDO:
estrutura (líder/controle/rival) derivada dos edges do grafo; componente só carrega
delta/sucessor/override. Cascata (líder morre → fação desestabiliza → controle do local
muda → rival ocupa) roda no `event_processor` após cada `apply_event`, auditável no
`event_log` com `source="rule_engine"` e profundidade limitada a 2 (anti-loop).



**Aceite:** ✅ matar qualquer chefe de fação destabiliza sistemicamente (2 líderes testados);
zero ifs por NPC em `services/`/`agents/`; op/regra malformada não quebra o turno.

### Fase 2.8 — Context builder com orçamento de tokens → [spec](specs/fase-2.8-context-builder.md) ✅ ENTREGUE (2026-07-03)

`build_context_pack(state, query, purpose, budget)` ranqueia fatos dinâmicos
(relevância/local/entidade/impacto/recência), respeita budget por seção e monta o bloco
`<ESTADO_ATUAL_DO_MUNDO>` (estado vivo ANTES de lore base). storyteller, npc_actor,
combat e campaign_manager consomem o builder. 100% determinístico (zero LLM extra).

**Aceite:** ✅ contexto nunca excede orçamento (teste 200 fatos); 50 eventos em 1 local →
só top relevantes no prompt; segredo não revelado não vaza; 216 testes offline verdes.
Smoke LLM real pendente de quota (fase determinística, sem `with_structured_output` novo).


---

## ✅ ENTREGUE — Fase 3: Clareza de campanha (Jogador entende o mundo)

**Objetivo:** Transformar estado abstrato em interface legível. Jogador sabe onde está, o que descobriu, quem odeia ele, quais objetivos estão abertos.

**Fatiamento em 4 specs** (decidido 2026-07-03):

- [x] **3.1 — Diário + Crônica** → [spec](specs/fase-3.1-diario-cronica.md) `done` (2026-07-03) —
  milestones determinísticos do event_log + prosa de menestrel, capítulos por arco
  (`arc_title` no campaign_plan); trivial fica na memória, importante na crônica.
  Smoke com LLM real ok (planner mapeia e persiste `arc_title` no Gemini)
- [x] **3.2 — Conhecimento revelável** → [spec](specs/fase-3.2-conhecimento-revelavel.md) `done` (2026-07-03) —
  Codex do jogador como VIEW derivada do save (visited/intel/npcs/revealed_facts, zero
  estado novo) + bestiário progressivo com contadores determinísticos (4 graus: rumores →
  encontrada → estudada → dominada); docs `hidden`/`secret` nunca aparecem. Zero LLM.
- [x] **3.3 — Quest log** → [spec](specs/fase-3.3-quest-log.md) `done` (2026-07-03) —
  main quest = view do campaign_plan (arc_title); side quests propostas pelo LLM e
  validadas pelo motor; conclusão via pipeline 2.6 (reusa `quest_completed`, sem schema
  novo); NPC-origem canônico morto → quest falha sistemicamente; marker no mapa. Smoke
  com LLM real ok (criação + conclusão mapeadas corretamente nos dois agentes)
- [x] **3.4 — Visualização de estado** → [spec](specs/fase-3.4-visualizacao-estado.md) `done` (2026-07-03) —
  overlays do mapa derivados do event_log/projection (controle recente, ameaças,
  looming_threat, fog of war respeitado) + timeline de reputação por facção (evento novo
  `reputation_changed` no log, gerado 100% em Python — zero LLM; estabilidade só
  qualitativa, número interno nunca exposto)

**Fase 3 completa (2026-07-03).** Critério de aceite atingido: jogador sabe quem é, onde está, o que aconteceu, quem são aliados/inimigos, quais objetivos pode perseguir.

---

## 🎮 PRIORIDADE ALTA — Fase 4: Gameplay Core (sistemas de RPG)

> Origem: auditoria de jogabilidade de 2026-07-03. Constatações: `XP_TABLE` sem consumidor
> (xp nunca incrementa — **não existe progressão**), buffs/passivas são só texto (dano/AC
> nunca leem `active_conditions`), party só existe no schema, craft/shop/loot 100% na mão
> do LLM, poção inutilizável em combate, inventário inicial com nomes livres que o
> `ARTIFACTS_DB` não resolve, spawn narrativo sem teto de CR.
>
> **7 specs escritas (2026-07-03), todas `draft` aguardando aprovação** — links abaixo.
> Ordem: **4.1 → 4.1b (Fable) → 4.2 → 4.3 → 4.4 → 4.5 → 4.6** (4.2 e 4.3 podem paralelizar; 4.4 depende da 4.3; 4.5 da 4.2; 4.6 de 4.1+4.2+4.5).

Resumo por fatia (detalhe técnico SÓ nas specs — fonte única):

- **4.1 — Progressão** [✅ implementada 2026-07-04 → spec](specs/fase-4.1-progressao.md) —
  XP determinístico (kill por tier / beat / quest), level up com curvas por classe,
  árvore com ramos = subclasses mutuamente exclusivas, ids canônicos + backfill,
  `/game/levelup` + modal no frontend, `level_up` na crônica com gate anti-LLM.
  **Falta só smoke com LLM real** (quota) para `done`.
- **4.1b — Árvores de Valoria** [✅ `done` 2026-07-04 → spec](specs/fase-4.1b-arvores-valoria.md) —
  executada por Fable: 10 classes × 2 ramos ancorados nos pilares do mundo, 111
  habilidades (66 novas) com impacto mecânico, anti-spoiler ok, apêndice A preenchido.
- **4.2 — Buffs mecânicos** [✅ implementada 2026-07-04 → spec](specs/fase-4.2-buffs-mecanicos.md) —
  condições tipadas lidas em dano/AC/acerto/save; stun/root/fear reais dos dois lados;
  9/10 passivas data-driven (Sapador declarativo, documentado). Falta só smoke LLM real.
- **4.3 — Inventário/equipamento** [✅ implementada 2026-07-04 → spec](specs/fase-4.3-inventario-equipamento.md) —
  inventário `{id, qty}` + slots (combate lê só slots); poção usável em combate;
  3 bugs fechados (arma inicial, item narrado, capitalização); `/game/equip` + HUD.
  Falta só smoke LLM real.
- **4.4 — Economia determinística** [✅ implementada 2026-07-04 → spec](specs/fase-4.4-economia-deterministica.md) —
  `services/economy.py`; preço = raridade × região × reputação em Python; mercadores
  persistentes com restock; craft com receita/local; drop tables; `TradeIntent` matou
  o `TransactionResult`. Falta só smoke LLM real.
- **4.5 — Party** [`draft` → spec](specs/fase-4.5-party-aliados.md) — recrutamento com
  gate de relationship; combate N vs N no mesmo motor (perfis 2.5b p/ aliados); alvo
  tático dos inimigos; morte de companion alimenta o mundo (npc_killed).
- **4.6 — Dificuldade/IA/morte** [`draft` → spec](specs/fase-4.6-dificuldade-ia-morte.md) —
  clamp+piso do spawn por orçamento de pontos; inimigos usam habilidades; boss com
  fases; morte do player com fecho narrativo e save-memorial.

**Critério de aceite da Fase 4:** personagem sobe de nível e aprende habilidade nova; buff de habilidade muda número de dano observável; poção usada em combate cura; craft falha sem ingrediente; mercador de Skallgard vende coisa diferente do de Nova Arcádia; combate 4 (party) vs 5 (orcs) resolve sem crash; morte tem narrativa.

---

## Fase 5 — Agentic playtest + telemetria

**Objetivo:** Agentes testadores jogam campanhas automáticas. Detectam inconsistências, medem qualidade, reduzem custo de API.

**Perfis:** agressivo, explorador, comerciante, diplomático, troll, mapa-breaker, combate, NPC-only, loot-abuser, secret-rushed.

**Invariantes:** HP válido, inventário sem dupe, ouro não nega, NPC morto não fala, facção derrotada não controla, relação dinâmica > lore base, segredo oculto não vaza.

**Métricas:** turnos/campanha, erros/turno, latência, custo, contexto size, eventos gerados, mudanças rejeitadas, fatos prioritários.

**Entrega:**

- [ ] `agents/test_player.py` — 10 perfis com estratégias diferentes
- [ ] Invariant checks ao fim de cada turno
- [ ] Logger estruturado (eventos, mudanças, erros) para análise
- [ ] Dashboard simples: turnos, erros encontrados, custo acumulado

**Critério de aceite:** Campanha de 50 turnos não quebra invariantes. Agente consegue jogar até nível 10 autonomamente.

---

## Backlog — Features após Fase 5

### Bugs críticos (sessão 2026-06-26)

- [ ] **NPC errado responde** fala destinada a outro — `agents/router.py` (`active_npc_name` não filtra)
- [x] ~~Inventário / capitalização~~ → movidos para **Fase 4.3**
- [x] ~~Morte sem narrativa~~ → movido para **Fase 4.6**

### Melhorias de Personagens (NPCs) — Sistema de 3 camadas

Depende de Fase 2.5+ estar estável (world_projection, revealed_facts).

**Camada 1:** Todos os NPCs da sessão (dedup interno, jogador não vê).  
**Camada 2:** NPCs conhecidos pelo jogador (aba Personagens, conhecimento revelado progressivamente).  
**Camada 3:** NPCs em cena (visíveis para npc_actor; ausentes retornam "X não está aqui").

**Traits ocultos** (Python): gerados na criação, aplicam DC modifiers, revelados progressivamente após 5 interações.

**Tarefas:**

- [ ] `traits.py` — 80 traits com modificadores de DC e dificuldade de revelação
- [ ] `state.py` — campos de NPC (home_location_id, hidden_traits, revealed_traits, interaction_count, known_by_player, knowledge_source, in_scene)
- [ ] `storyteller` — gerenciar in_scene ao entrar/sair; criar layer 2 quando NPC menciona outro
- [ ] `npc_actor` — validar layer 3; aplicar trait modifiers; revelação progressiva; incrementar interaction_count
- [ ] Frontend — aba Personagens com layer 2 + source + revealed_traits

### Encontros sistêmicos (A+B+D)

Depende da Fase 4.6.

> **Orçamento/composição de encontro por danger+nível → absorvido pela spec 4.6**
> (`encounter_budget.py`, clamp/fill do spawn). O que sobra aqui é a parte de
> DETECÇÃO e VARIEDADE de encontro (nem todo encontro é combate).

**Tarefas restantes:**

- [ ] `check_encounter()` em Python: d20 + wis vs DC (detecção/surpresa)
- [ ] Tipos de encontro além de combate: story/trap/social por danger e região
- [ ] `agents/encounter.py` + nó no grafo com arestas condicionais (encounter → combat_agent | storyteller); storyteller para de short-circuit

### Clima com efeito real

Depende de context builder estável.

**Cadeias de clima por local:** cada local tem sequência (limpo → nublado → chuva). Fenômenos globais (Tempestade de Mana) sobrepõem.

**Efeitos mecânicos:** penalidades de percepção, HP, saves, viagem, combate.

**Tarefas:**

- [ ] `world_utils.py` — WEATHER_CHAINS (por local), WEATHER_EFFECTS (dataclass), advance_weather()
- [ ] `storyteller`, `combat`, `encounter_agent` — aplicar efeitos
- [ ] `campaign_manager` — emitir fenômenos globais em beats específicos
- [ ] Frontend — ícone de clima com tooltip

### ~~Economia regional~~ → fundida na **Fase 6** (era duplicata; base determinística é a spec 4.4)

---

## Fase 6 — Conteúdo sistêmico (evolução da economia 4.4)

Depende da **Fase 4.4** (economia determinística) — Fase 6 é a evolução dela com
estado do mundo dinâmico. Absorve o item "Economia regional" do backlog (era duplicata).

> **Já coberto em outro lugar (não refazer aqui):**
> preço por controle de facção hostil + reputação → spec 4.4 (R4/R6);
> quest falha quando NPC-origem morre → ✅ entregue na 3.3;
> contexto muda quando facção perde local → ✅ entregue na 2.8;
> reforços/ameaça regional afetam encontros → ✅ parcial na 2.5b (`threat_alerts`).

**Entregas (o que sobra de verdade):**

- [ ] Rotas comerciais: fluxo de itens por conexões do mapa (bloqueio de rota corta oferta)
- [ ] Estoques reagem a EVENTOS do event_log (bloquear porto → peixe some da loja e preço explode — hoje o estoque 4.4 só reage a controle/relógio)
- [ ] `economy_tags` avançadas: item abundante (×0.6) / escasso (×1.8) por região (multiplicadores finos sobre a base da 4.4)
- [ ] Itens `unique` (um por mundo, rastreados no event_log)
- [ ] Migração real de monstros: danger/ameaça muda a COMPOSIÇÃO das loot/encounter tables com o tempo (2.5b só adiciona reforço pontual)

**Critério de aceite:** Bloquear um porto → peixe some de lojas, preço explode — rastreável no event_log.

---

## Fase 7 — Pipeline de autoria + validação

Depende de Codex estruturado (Fase 2.5) estar estável.

**Objetivo:** Evitar inconsistência conforme conteúdo cresce. Documentos, IDs, relacionamentos validados automaticamente.

**Entregas:**

- [ ] ⚠️ **TECHNICAL DEBT (da Fase 2.5):**
  - **Encoding:** Lore em PT-BR (acentos). Script e loaders explicitam `encoding="utf-8"` (Windows default cp1252). Validar em CI que arquivos .md entram como UTF-8.
  - **Script sobrescreve curadoria:** `migrate_lore_nova.py` regera `data/codex/` + `entities.json` do zero. Curadoria manual (aliases, `related_entities`, overrides de visibility) é PERDIDA. Docstring avisa, mas documentar workflow pós-script ou versionar curadoria separadamente (ex.: `entities-curated.json` que merge com gerado).
  - **NPC miscel público+segredo:** Arquivos de NPC mesclam "Descrição pública" com "História real" (motivação/segredos) no mesmo `.md` `public`. Separar em seções `visibility: hidden` ou criar NPCs_secrets.md paralelos. Hoje: contexto público vê motivação real (não é erro crítico, mas compromete revelação controlada de segredos).
- [ ] Templates Markdown para: local, facção, raça, NPC, monstro, artefato
- [ ] Validador de frontmatter (id, type, name, tags, visibility obrigatórios)
- [ ] Validador de referências (edges apontam para entidade que existe)
- [ ] Validador de alias (sem duplicação entre entidades)
- [ ] Validador de visibilidade (segredo não marcado como público)
- [ ] Comando para reindexar Codex
- [ ] CI hook: validar novo conteúdo antes de merge

**Critério de aceite:** Adicionar NPC novo segue template, é validado automaticamente, entra em entities.json com IDs únicos.

---

## Fase 8 — Arte de itens, monstros e personagens

Depende de: entidades estáveis, Codex revelável funcional.

**Objetivo:** Gerar e cachear arte apenas para entidades já confirmadas.

**Entregas:**

- [ ] Gerador de arte por item_id (cache por ID)
- [ ] Gerador de arte por monster_id
- [ ] Gerador de arte por NPC importante
- [ ] Estilo visual travado (prompt consistente)
- [ ] Lazy generation: só gerar quando jogador descobre
- [ ] Fallback: sem arte = silhueta + cor
- [ ] Não gerar arte de segredo não revelado

**Critério de aceite:** Jogador encontra novo monstro → arte gerada em 2s, cacheada, reutilizada.

---

## Fase 9 — Sprites, som e polish audiovisual

Depende de: arte de itens pronta, Fase 6+ estável.

**Entregas:**

- [ ] Sprites por bioma (sourcear/gerar)
- [ ] Sprites por tipo de local
- [ ] Música por região
- [ ] Efeitos de combate
- [ ] Paleta visual consistente
- [ ] Transições smooth entre cenas

**Nota:** Som/sprite melhoram imersão, mas não corrigem consistência. Prioridade baixa até mundo estar sólido.

---

## Fase 10 — Hardening técnico e escala

Antes de abrir para usuários externos.

**Problemas atuais:**

- Saves locais em JSON (sem versionamento, sem migrations)
- Sem autenticação
- Sem isolamento por usuário
- Sem controle de concorrência
- CORS aberto

**Entregas:**

- [ ] Validar `game_id` como UUID (prevenir path traversal)
- [ ] Adicionar `schema_version` em saves (migrations para antigas)
- [ ] Migrar para Postgres (quando multiusuário)
- [ ] Migrar FAISS para pgvector/Qdrant
- [ ] Adicionar autenticação
- [ ] Adicionar rate limiting
- [ ] Storage para imagens geradas
- [ ] Fila para geração de assets
- [ ] Logs estruturados
- [ ] Observabilidade (latência, custo)

**Critério de aceite:** Máximo 1 game_id per usuário. Migração entre providers transparente. Zero path traversal risks.

---

## Fase 11 — LLM contract tests

Depende de: Fases 2.5-5 estáveis.

**Objetivo:** Validar providers reais (não apenas MockLLM) respeitam contratos (structured output, fallback, schemas).

**Casos mínimos:**

- Router classifica corretamente
- Storyteller respeita contexto
- Combat action é válido
- NPC conversation respeita fatos ocultos
- World change é estruturado e validável
- Archivist resume sem perder crítico
- Fallback funciona quando provider falha

**Nota:** Opcional no CI padrão, mas importante antes de releases.

---

## Backlog adicional — Features menores (ordem livre)

### ~~Sistema de Aliados (Party)~~ → promovido para **Fase 4.5**

### Melhorias da Crônica

- [x] ~~**Arcos:** arc_title + chapters~~ → ✅ entregue na **Fase 3.1**
- [ ] **Compressão:** capítulo antigo > 20 entradas → archivist comprime
- [ ] **Busca:** endpoint `POST /game/chronicle/search` via RAG
- [ ] **Frontend restante:** search + download .txt (separadores por capítulo já existem, 3.1)

### ~~Lore Multi-Índice~~ → OBSOLETO

Superado pela Fase 2.5: Codex em `data/codex/` com metadados `type`/`tags`/`visibility`
por chunk (timeline separada, secrets como `hidden`). `world_lore.txt` não existe mais.

### Mapa robusto — restante

Mapa de Valoria com 30 nós já entregue (2.5b). Sobra:

- [ ] Sub-locais (distritos, masmorras internas)
- [ ] Tempo de viagem variável por conexão (hoje: sempre 1 período)
- [x] ~~`economy_tags` por local~~ → absorvido pela **spec 4.4** (R2: `craft_tags` + `economy_tags` nos 30 nós)

### ~~Sistema de crafting~~ → promovido para **Fase 4.4**

### Atmosfera sonora

Depende de sourcing CC0. **Defer até tudo jogável.**

- [ ] Áudio por região e período
- [ ] Efeitos de combate
- [ ] Sourcing de packs CC0

---

## Princípios de desenvolvimento

- **Estado antes de features.** Mundo vivo e auditável > mais features.
- **Lore base ≠ Estado vivo.** Codex é canônico. Campanha muda via events + rules, não sobrescrita de lore.
- **LLM propõe, motor aplica.** Nunca confiar em sinal/valor do LLM sem validar. Tudo estruturado ou rejeitado.
- **Mecânica é Python.** IA narra; números resolvem determinístico (combate, economia, mundo).
- **Regras genéricas, não hardcode.** Morte de qualquer líder dispara mesma regra. Tags + componentes = zero ifs por NPC.
- **MockLLM esconde bugs.** Validar nós novos com chave real (respeitando quota Gemini).
- **Fatiar fino.** Cada fase é testável, jogável, com invariantes claros.

---

## Resumo executivo

### Mudança de direção

Antes: "mais features, sprites depois".  
**Agora:** "estado sólido, depois tudo mais cresce nele".

### Ordem crítica

1. **Fases 2.5-2.8** ✅ ENTREGUES: Codex, event_log, world_projection, rules engine, context builder.
2. **Fase 3** ✅ ENTREGUE (2026-07-03): Clareza de campanha — diário/crônica, codex do jogador, quest log, visualização de estado.
3. **Fase 4** (AGORA — 7 specs `draft` escritas): Gameplay Core — progressão + árvores lore-driven (4.1/4.1b), buffs mecânicos, inventário/equip, economia determinística, party, dificuldade/morte.
4. **Fase 5** (na sequência): agentic playtest + telemetria (depende da progressão 4.1 p/ "jogar até nível 10").
5. **Fase 6+** (depois): conteúdo sistêmico (evolução da 4.4), autoria, arte, sprites.

Sem 2.5-2.8, as features de economia/craft/encontros ficariam acopladas, contraditórias e não-testáveis — fundação entregue; Fase 4 constrói gameplay em cima dela.

### Métrica de sucesso

- ✅ Fase 2.8: campanha 50 turnos sem contradição; event log rastreável; contexto nunca explode.
- **Fase 4 (atual):** critério de aceite da seção Fase 4 (progressão + buff observável + poção em combate + craft com receita + mercadores distintos + 4v5 + morte com narrativa).
