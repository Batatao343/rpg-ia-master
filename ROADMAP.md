# ROADMAP — RPG IA (Revisado 2026-07-06)

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

## ✅ ENTREGUE — Fase 4: Gameplay Core (sistemas de RPG)

> Origem: auditoria de jogabilidade de 2026-07-03. Constatações: `XP_TABLE` sem consumidor
> (xp nunca incrementa — **não existe progressão**), buffs/passivas são só texto (dano/AC
> nunca leem `active_conditions`), party só existe no schema, craft/shop/loot 100% na mão
> do LLM, poção inutilizável em combate, inventário inicial com nomes livres que o
> `ARTIFACTS_DB` não resolve, spawn narrativo sem teto de CR.
>
> **7 specs escritas (2026-07-03), todas `draft` aguardando aprovação** — links abaixo.
> Ordem: **4.1 → 4.1b (Fable) → 4.2 → 4.3 → 4.4 → 4.5 → 4.6** (4.2 e 4.3 podem paralelizar; 4.4 depende da 4.3; 4.5 da 4.2; 4.6 de 4.1+4.2+4.5).

Resumo por fatia (detalhe técnico SÓ nas specs — fonte única):

- **4.1 — Progressão** [✅ `done` → spec](specs/fase-4.1-progressao.md) —
  XP determinístico (kill por tier / beat / quest), level up com curvas por classe,
  árvore com ramos = subclasses mutuamente exclusivas, ids canônicos + backfill,
  `/game/levelup` + modal no frontend, `level_up` na crônica com gate anti-LLM.

- **4.1b — Árvores de Valoria** [✅ `done` 2026-07-04 → spec](specs/fase-4.1b-arvores-valoria.md) —
  executada por Fable: 10 classes × 2 ramos ancorados nos pilares do mundo, 111
  habilidades (66 novas) com impacto mecânico, anti-spoiler ok, apêndice A preenchido.
- **4.2 — Buffs mecânicos** [✅ `done` → spec](specs/fase-4.2-buffs-mecanicos.md) —
  condições tipadas lidas em dano/AC/acerto/save; stun/root/fear reais dos dois lados;
  9/10 passivas data-driven (Sapador declarativo, documentado).
- **4.3 — Inventário/equipamento** [✅ `done` → spec](specs/fase-4.3-inventario-equipamento.md) —
  inventário `{id, qty}` + slots (combate lê só slots); poção usável em combate;
  3 bugs fechados (arma inicial, item narrado, capitalização); `/game/equip` + HUD.
 
- **4.4 — Economia determinística** [✅ `done` → spec](specs/fase-4.4-economia-deterministica.md) —
  `services/economy.py`; preço = raridade × região × reputação em Python; mercadores
  persistentes com restock; craft com receita/local; drop tables; `TradeIntent` matou
  o `TransactionResult`.
- **4.5 — Party** [✅ `done` → spec](specs/fase-4.5-party-aliados.md) —
  recrutamento com gate determinístico (relationship ≥7, teto 3); N vs N no mesmo
  motor; alvo tático; morte de companion vira npc_killed; 4v5 sem crash testado.
 
- **4.6 — Dificuldade/IA/morte** [✅ `done` → spec](specs/fase-4.6-dificuldade-ia-morte.md) —
  clamp+piso por orçamento de pontos; 19 inimigos com habilidades mecânicas; 7 bosses
  com fases; morte com fecho de saga + save-memorial (409).

**Status da Fase 4 (2026-07-05): ✅ COMPLETA — 7 specs `done`** (313 → 461 testes
offline + smoke com LLM real executado; 4 bugs de integração achados e corrigidos
no smoke). Pendente só playtest de balanceamento. Próxima: **Fase 5**.

**Critério de aceite da Fase 4:** personagem sobe de nível e aprende habilidade nova; buff de habilidade muda número de dano observável; poção usada em combate cura; craft falha sem ingrediente; mercador de Skallgard vende coisa diferente do de Nova Arcádia; combate 4 (party) vs 5 (orcs) resolve sem crash; morte tem narrativa.

---

## 🎮 PRÓXIMA — Fase 5 — Agentic playtest + telemetria

> Decisão 2026-07-05: Fase 6 passou na frente (entregue) e a Fase 7 aproveitou o
> embalo do Codex (entregue). Com mundo robusto e conteúdo validado, a Fase 5 é
> a próxima — specs ainda não escritas (spec-driven: escrever antes de codar).

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

- [x] ~~**NPC errado responde** fala destinada a outro~~ → fechado por construção na
  spec **npcs-3-camadas** (gate `in_scene`: NPC fora de cena responde "não está aqui" sem LLM)
- [x] ~~Inventário / capitalização~~ → movidos para **Fase 4.3**
- [x] ~~Morte sem narrativa~~ → movido para **Fase 4.6**

### ✅ ENTREGUE — Melhorias de Personagens (NPCs) — Sistema de 3 camadas (2026-07-06)

> **Spec `done`:** [specs/npcs-3-camadas-traits.md](specs/npcs-3-camadas-traits.md)
> — 3 camadas (sessão → conhecidos → em cena), gate determinístico do
> npc_actor ("X não está aqui" sem LLM — fecha o bug "NPC errado responde"),
> `data/traits.json` (80 traits, sorteio seeded, DC modifiers em 6.4/4.4),
> revelação progressiva por interações, aba Personagens. Detalhe SÓ na spec.

Depende de Fase 2.5+ estar estável (world_projection, revealed_facts).

### ~~Encontros sistêmicos~~ → promovido para **Fase 6.4** ([spec](specs/fase-6.4-encontros-sistemicos.md))


### ~~Clima com efeito real~~ → promovido para **Fase 6.5** ([spec](specs/fase-6.5-clima-com-efeito.md))


### ~~Economia regional~~ → fundida na **Fase 6** (era duplicata; base determinística é a spec 4.4)

---

## ✅ ENTREGUE — Fase 6 — Conteúdo sistêmico (evolução da economia 4.4)

> **Priorizada antes da Fase 5** (decisão 2026-07-05).
> **STATUS 2026-07-05: ✅ FASE 6 COMPLETA — 6.1–6.5 `done`** (461 → 520 testes
> offline + smoke com LLM real; 3 fixes de robustez achados no smoke). Specs:
> [6.1 — Economia viva (rotas/escassez/eventos)](specs/fase-6.1-economia-viva.md) ·
> [6.2 — Itens únicos](specs/fase-6.2-itens-unicos.md) ·
> [6.3 — Migração de monstros](specs/fase-6.3-migracao-de-monstros.md) ·
> [6.4 — Encontros sistêmicos](specs/fase-6.4-encontros-sistemicos.md) ·
> [6.5 — Clima com efeito real](specs/fase-6.5-clima-com-efeito.md)
> (6.4/6.5 absorvem os itens homônimos do backlog — eram conteúdo sistêmico.)
> Ordem: **6.1 → 6.2 → 6.3 → 6.4 → 6.5** (6.3 usa rotas da 6.1; 6.4 usa sorteio
> da 6.3; 6.5 modifica a detecção da 6.4).

Depende da **Fase 4.4** (economia determinística) — Fase 6 é a evolução dela com
estado do mundo dinâmico. Absorve o item "Economia regional" do backlog (era duplicata).

> **Já coberto em outro lugar (não refazer aqui):**
> preço por controle de facção hostil + reputação → spec 4.4 (R4/R6);
> quest falha quando NPC-origem morre → ✅ entregue na 3.3;
> contexto muda quando facção perde local → ✅ entregue na 2.8;
> reforços/ameaça regional afetam encontros → ✅ parcial na 2.5b (`threat_alerts`).

**Entregas (o que sobrava de verdade — tudo feito):**

- [x] Rotas comerciais: fluxo de itens por conexões do mapa (bloqueio de rota corta oferta) — 6.1
- [x] Estoques reagem a EVENTOS do event_log (`route_blocked/cleared` no pipeline 2.6) — 6.1
- [x] `economy_tags` avançadas: produtor local ×0.6 / isolado ×1.8 por ALCANÇABILIDADE (BFS) — 6.1
- [x] Itens `unique` (um por mundo, claim engine no event_log, gates em loot/loja/craft/narrado) — 6.2
- [x] Migração real de monstros: pressão de caça com decay + fação no controle mudam a composição das tabelas — 6.3

**Critério de aceite:** ✅ Bloquear um porto → peixe some de lojas, preço explode — rastreável no event_log (validado no smoke real da sessão 8).

---

## ✅ ENTREGUE — Fase 7 — Pipeline de autoria + validação

Depende de Codex estruturado (Fase 2.5) estar estável.

**Objetivo:** Evitar inconsistência conforme conteúdo cresce. Documentos, IDs, relacionamentos validados automaticamente. Paga os 3 débitos técnicos da Fase 2.5 (encoding, curadoria sobrescrita, NPC público+segredo).

> **FASE 7 COMPLETA (2026-07-05)** — 7.1/7.2/7.3 `done`, 581 testes offline,
> lint verde no repo, reindex feito, smoke real de não-vazamento executado.

**Fatias:**

- [x] **7.1 — Validadores de conteúdo + CI** ([spec](specs/fase-7.1-validadores-conteudo.md)):
  `services/content_validator.py` puro — frontmatter (id/type/name/tags/visibility, id = nome do arquivo),
  ids únicos (codex + entities_extra + components), referências (edges → entidade existente, constraints
  de `relation_types.json`, `related_entities` órfão), aliases sem duplicação (normalizado sem acento),
  visibilidade (secret não vaza em doc public), encoding UTF-8 (débito 2.5). CLI
  `scripts/validate_content.py` (exit 1 com erro) + teste-gate sobre os dados reais do repo +
  GitHub Action rodando `uv run pytest` em PR (fecha "CI hook antes de merge").
- [x] **7.2 — Pipeline de autoria: curadoria preservada, templates, reindex com gate**
  ([spec](specs/fase-7.2-autoria-curadoria.md)): `data/codex_overrides.yaml` — patches de frontmatter
  por id aplicados pelo `migrate_lore_nova.py` no fim da geração (curadoria sobrevive à regeração —
  débito 2.5); arquivos manuais com `curated: true` não são apagados pelo script (entidade em
  `entities_extra.json`, padrão 2.5b); templates Markdown por tipo em `docs/templates/codex/`
  (local, facção, raça, NPC, monstro, artefato); `rag.py` roda o lint 7.1 ANTES de reindexar e
  aborta com erro (fecha "comando para reindexar"); workflow documentado em `docs/AUTORIA.md`.
- [x] **7.3 — Separação público/segredo nos NPCs** ([spec](specs/fase-7.3-npc-segredos.md)):
  migrate divide cada NPC por rótulo de parágrafo (lista curada: "História real", "Motivação real",
  "O pacto e seus efeitos"...) → doc paralelo `npcs/segredos/{npc_id}_segredo.md` com
  `visibility: hidden` (débito 2.5 — hoje `codex_body`/RAG entregam o pacto de Valerius ao narrador);
  lint anti-regressão (rótulo secreto em doc public = ERRO); regeneração + auditoria manual + reindex.

**Critério de aceite:** Adicionar NPC novo segue template, é validado automaticamente, entra em entities.json com IDs únicos — e segredo de NPC não chega ao narrador público. ✅ **Validado em smoke real 2026-07-05** (NPC de teste via template sobreviveu ao migrate e passou no lint; narrador Gemini descreveu Valerius só pela persona pública, zero Daruun/pacto; `query_rag` public não devolve chunks de segredo).

**Pendência de curadoria (fora do escopo 7.3):** alguns NPCs públicos citam a Rede Carmesim como ameaça conhecida (Kess, Volkar, Oráculo de Ferro) enquanto a timeline da era 7 marca o despertar como `hidden` — revisar na próxima passada de lore se isso é conhecimento comum do norte ou spoiler.

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

## Fase 10 — Hardening técnico e escala — fatia local ✅ ENTREGUE (2026-07-06)

> **Spec `done`:** [specs/fase-10-hardening-tecnico.md](specs/fase-10-hardening-tecnico.md)
> — game_id UUID anti-traversal (`persistence.save_path`), `schema_version` +
> pipeline de migrations (v0→v1 consolida backfills 3.1/4.1/4.3/4.5; v1→v2 =
> camadas de NPC), CORS por env, rate limit mínimo, log JSON por turno.
> Postgres/pgvector/auth/fila = **Fase 10b** (só com usuários externos).

Antes de abrir para usuários externos.

**Problemas atuais:**

- Saves locais em JSON (sem versionamento, sem migrations)
- Sem autenticação
- Sem isolamento por usuário
- Sem controle de concorrência
- CORS aberto

**Entregas:**

- [x] Validar `game_id` como UUID (prevenir path traversal) — 2026-07-06
- [x] Adicionar `schema_version` em saves (migrations para antigas) — 2026-07-06
- [x] Adicionar rate limiting (mínimo, por IP em memória) — 2026-07-06
- [x] Logs estruturados (JSON por turno, base da observabilidade) — 2026-07-06
- [ ] (10b) Migrar para Postgres (quando multiusuário)
- [ ] (10b) Migrar FAISS para pgvector/Qdrant
- [ ] (10b) Adicionar autenticação
- [ ] (10b) Storage para imagens geradas
- [ ] (10b) Fila para geração de assets
- [ ] (10b) Observabilidade completa (latência, custo)

**Critério de aceite:** Máximo 1 game_id per usuário. Migração entre providers transparente. Zero path traversal risks.

---

## ✅ ENTREGUE — Fase 11 — LLM contract tests (2026-07-06)

> **Spec `done`:** [specs/fase-11-llm-contract-tests.md](specs/fase-11-llm-contract-tests.md)
> — `uv run pytest -m llm_contract -v -s`: 9 contratos (router×2, StoryUpdate
> banal sem alucinação, combate, NPC não-onisciente, TradeIntent, e2e+archivist,
> loot, fallback offline), todos VERDES contra Gemini real em 2026-07-06;
> `tests/test_real_llm.py` migrado/removido; fora do CI padrão (addopts).

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

### ✅ ENTREGUE — Mapa robusto — restante (2026-07-06)

> **Spec `done`:** [specs/mapa-sublocais-viagem-variavel.md](specs/mapa-sublocais-viagem-variavel.md)
> — `travel_times` por conexão (default 1; intra-cidade 0 sem virar relógio),
> nós `kind: interior` (masmorras/tavernas com danger próprio, abrigo de
> clima, fora do mapa-mundi), 4-6 interiores curados. Detalhe SÓ na spec.

Mapa de Valoria (35 nós: 30 + 5 interiores). Entregue pela spec acima:

- [x] Sub-locais (interiores: masmorras/tavernas com danger próprio, abrigo de clima)
- [x] Tempo de viagem variável por conexão (intra-cidade 0, travessias longas 2-3)
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
3. **Fase 4** ✅ COMPLETA (2026-07-05, 7 specs `done` + smoke real): Gameplay Core.
4. **Fase 6** ✅ COMPLETA (2026-07-05, specs `done` com smoke real): economia viva, 20 itens únicos, migração de monstros, encontros sistêmicos, clima mecânico.
5. **Fase 7** ✅ COMPLETA (2026-07-05, 3 specs `done` + smoke real): lint de conteúdo + CI, curadoria migration-safe + templates, segredos de NPC separados.
6. **Fase 5** 🎮 PRÓXIMA: agentic playtest + telemetria (specs a escrever).
7. **Fases 8+** (depois): arte, sprites/som, hardening, contract tests.

Sem 2.5-2.8, as features de economia/craft/encontros ficariam acopladas, contraditórias e não-testáveis — fundação entregue; Fases 4/6/7 construíram gameplay, conteúdo sistêmico e pipeline de autoria em cima dela.

### Métrica de sucesso

- ✅ Fase 2.8: campanha 50 turnos sem contradição; event log rastreável; contexto nunca explode.
- ✅ Fase 4: progressão + buff observável + poção em combate + craft com receita + mercadores distintos + 4v5 + morte com narrativa (smoke real 2026-07-05).
- ✅ Fase 6: porto bloqueado → escassez rastreável no event_log (smoke real 2026-07-05).
- ✅ Fase 7: NPC novo via template validado automaticamente; segredo de NPC não chega ao narrador (smoke real 2026-07-05).
- **Fase 5 (próxima):** campanha de 50 turnos automatizada sem quebrar invariantes; agente joga até nível 10 autonomamente.
