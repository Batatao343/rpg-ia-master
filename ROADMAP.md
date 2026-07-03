# ROADMAP — RPG IA (Revisado 2026-07-01)

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

---

## 🚨 PRIORIDADE CRÍTICA — Fase 2.5 a 2.8: Mundo vivo v1

Antes de adicionar mais features (economia, crafting, sprites, arte), o sistema precisa de **fundação arquitetural sólida**.

Problema atual: mundo muda via narrativa textual. Com campanhas longas, risco de contradição (NPC morto fala, local controlado muda sem evento, segredo vaza cedo).

Solução: Separar camadas → motor de regras sistêmico → contexto orçamentado → estado auditável.

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

### Fase 2.8 — Context builder com orçamento de tokens → [spec](specs/fase-2.8-context-builder.md)

`build_context_pack(state, query, purpose, budget)` ranqueia fatos dinâmicos
(relevância/local/entidade/impacto/recência), respeita budget por seção e monta o bloco
`<ESTADO_ATUAL_DO_MUNDO>` (estado vivo ANTES de lore base). storyteller, npc_actor,
combat e campaign_manager consomem o builder.

**Aceite:** contexto nunca excede orçamento; 50 eventos em 1 local → só top relevantes no prompt.


---

## Próximas entregas (após Fase 2.5-2.8)

### Fase 3 — Clareza de campanha (Jogador entende o mundo)

**Objetivo:** Transformar estado abstrato em interface legível. Jogador sabe onde está, o que descobriu, quem odeia ele, quais objetivos estão abertos.

**Entregas:**

- [ ] **Diário + Crônica melhorada:** separar eventos triviais (memória) de eventos importantes (crônica); chapters por arco
- [ ] **Codex revelável:** documentos sobre locais/facções/raças aparecem conforme jogador descobre (não spoiler)
- [ ] **Objetivos visíveis:** quest log com main/secondary, status, origem; mapa mostra objetivo próximo
- [ ] **Histórico de reputação:** timeline visual por facção (gráfico de estabilidade, mudanças recentes)
- [ ] **Mapa dinâmico:** destaque para local atual, controladores recentes, ameaças visíveis
- [ ] **Bestiário progressivo:** 4 graus (ouviu falar → 1 encontro → 3 vitórias → conhecimento profundo)

**Critério de aceite:** Após fechar e voltar dias depois, jogador sabe: quem é, onde está, o que aconteceu, quem são aliados/inimigos, quais objetivos pode perseguir.

### Fase 4 — Agentic playtest + telemetria

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

## Backlog — Features após Fase 4

### Bugs críticos (sessão 2026-06-26)

- [ ] **Inventário:** storyteller narra item mas loot/inventory não commita — checar `agents/loot.py`
- [ ] **Capitalização:** itens com letra maiúscula errada — grep `title()` / `capitalize()`
- [ ] **Morte sem narrativa:** tela de morte sem death_narrative — adicionar ao combate

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

Depende de Fase 2.8 (context builder) estar estável.

Hoje: storyteller detecta encontro → combate sempre (1 inimigo, sem contexto).  
Novo: `encounter_agent` centraliza lógica (detecção, tipo, composição).

**Fluxo:**
```
storyteller (viagem)
  → check_encounter() [Python: d20 + wis vs DC]
  → encontro_agent (tipo: story/trap/combat + composição)
  → combate | storyteller (condicional)
```

**Tarefas:**

- [ ] `agents/encounter.py` — detection check, encounter type por danger, composição de inimigos
- [ ] `world_utils.py` — ENCOUNTER_BUDGET, generate_encounter_spec(), detection_check()
- [ ] `main.py` — nó + arestas condicionais (encounter_agent → combat_agent | storyteller)
- [ ] `storyteller.py` — parar de short-circuit; emitir next="encounter_agent"

### Clima com efeito real

Depende de context builder estável.

**Cadeias de clima por local:** cada local tem sequência (limpo → nublado → chuva). Fenômenos globais (Tempestade de Mana) sobrepõem.

**Efeitos mecânicos:** penalidades de percepção, HP, saves, viagem, combate.

**Tarefas:**

- [ ] `world_utils.py` — WEATHER_CHAINS (por local), WEATHER_EFFECTS (dataclass), advance_weather()
- [ ] `storyteller`, `combat`, `encounter_agent` — aplicar efeitos
- [ ] `campaign_manager` — emitir fenômenos globais em beats específicos
- [ ] Frontend — ícone de clima com tooltip

### Economia regional

Depende de Mapa robusto (Fase 5 prerequisites).

**Regra:** item com economy_tags só aparece em locais com tags correspondentes; preço = abundante (×0.6) ou escasso (×1.8).

**Tarefas:**

- [ ] `data/artifacts.json` — adicionar economy_tags + unique flag
- [ ] `data/world_map.json` — adicionar economy_tags por local
- [ ] `gamedata.py` — PRICE_MODIFIERS (item_id + tag → multiplicador)
- [ ] `agents/loot.py` — filtrar pool por tags, aplicar preço modificado

---

## Fase 5 — Conteúdo sistêmico

Depende de Fases 2.5-3 estáveis (world_projection, context builder, clareza de campanha).

**Objetivo:** Economia, loot e encontros afetados visivamente pelo estado do mundo.

**Entregas:**

- [ ] Economia regional: preços afetados por controle de facção, bloqueio de rotas, guerra
- [ ] Rotas comerciais: fluxo de itens por conexões de mapa
- [ ] Estoques em lojas: variam por acesso regional e eventos (bloquei porto → peixe suma)
- [ ] Quests dinâmicas: ajustadas por mudanças de mundo (aliado morreu? quest falha; facção perdeu local? contexto muda)
- [ ] NPCs reagem a histórico: preço sobe se traiu, desconto se salvou
- [ ] Monstros migram por ameaça: danger regional afeta composição de encontros

**Critério de aceite:** Bloquear um porto → peixe some de lojas, preço explode. NPC que salvou paga menos.

---

## Fase 6 — Pipeline de autoria + validação

Depende de Codex estruturado (Fase 2.5) estar estável.

**Objetivo:** Evitar inconsistência conforme conteúdo cresce. Documentos, IDs, relacionamentos validados automaticamente.

**Entregas:**

- [ ] ⚠️ **TECHNICAL DEBT (Fase 2.5):**
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

## Fase 7 — Arte de itens, monstros e personagens

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

## Fase 8 — Sprites, som e polish audiovisual

Depende de: arte de itens pronta, Fase 5+ estável.

**Entregas:**

- [ ] Sprites por bioma (sourcear/gerar)
- [ ] Sprites por tipo de local
- [ ] Música por região
- [ ] Efeitos de combate
- [ ] Paleta visual consistente
- [ ] Transições smooth entre cenas

**Nota:** Som/sprite melhoram imersão, mas não corrigem consistência. Prioridade baixa até mundo estar sólido.

---

## Fase 9 — Hardening técnico e escala

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

## Fase 10 — LLM contract tests

Depende de: Fases 2.5-4 estáveis.

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

### Sistema de Aliados (Party)

`CompanionState` já existe. Zero lógica.

- [ ] **Recrutamento** — após N interações, trait HELPFUL desbloqueia opção
- [ ] **Combate** — roll_initiative inclui aliados; resolve_ally_action baseado em occupation
- [ ] **Morte** — HP ≤ 0 → narrativa de morte, sem loot
- [ ] **Frontend** — HP bars na aba Personagens

### Melhorias da Crônica

- [ ] **Arcos:** arc_title + chapters (mudança de título = quebra de capítulo)
- [ ] **Compressão:** capítulo antigo > 20 entradas → archivist comprime
- [ ] **Busca:** endpoint `POST /game/chronicle/search` via RAG
- [ ] **Frontend:** separadores, search, download .txt

### Lore Multi-Índice

Migrar de `world_lore.txt` único para 5 índices: rumors, daily_life, faction_perspectives, timeline, secrets.

**Tarefas:**

- [ ] Gerar 5 arquivos de lore a partir do existente
- [ ] `rag.py` — ingest cada arquivo em índice próprio
- [ ] `storyteller` — query rumors + daily_life
- [ ] `npc_actor` — query faction_perspectives + rumors

### Mapa robusto

Expandir de 9 para ~25 locais com sub-locais, tempo de viagem variável, danger granular.

**Geração:** Claude extrai de `world_lore.txt`, monta `world_map.json` completo com adjacências, sub-locais, danger, tags, economy_tags.

**Desbloqueia:** crafting situacional, danger dinâmico, economia mais profunda.

### Sistema de crafting

Depende de mapa robusto + economy_tags.

- Locais de craft (forja, laboratório, altar)
- Skills por classe/background
- `recipes.json` (materiais + local + skill → resultado)
- Materiais de economia regional

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

1. **Fases 2.5-2.8** (próximas 4 semanas): Codex, event_log, world_projection, rules engine, context builder.
2. **Fase 3-4** (mês 2): Clareza de campanha, agentic playtest, telemetria.
3. **Fase 5+** (depois): economia, craft, arte, sprites.

Sem 2.5-2.8, as features de economia/craft/encontros ficam acopladas, contraditórias e não-testáveis.

### Métrica de sucesso

Fim de Fase 2.8: Campanha 50 turnos roda sem contradição. Event log rastreável. Estado auditável. Context nunca explode.
