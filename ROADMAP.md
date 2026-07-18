# ROADMAP — RPG IA (Revisado 2026-07-13)

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

## 🎮 Roteamento multi-provider + Fase 5 → ✅ AMBOS ENTREGUES (2026-07-06)

> Decisão 2026-07-06: **roteamento-multi-provider entrou ANTES da Fase 5** — o
> jogo vira produto pago (chave por provider), então o playtest/telemetria da
> Fase 5 rodou já sobre as rotas novas e mede provider/modelo/custo.
> Fase 5 concluída na sequência (ver seção "Fase 5 — Agentic playtest" acima).

- [x] **Roteamento multi-provider** ([spec](specs/roteamento-multi-provider.md),
  `done` 2026-07-06 — **smoke real OK**): 3 tiers (`CLASSIFY`/`FAST`/`SMART`) +
  `ROUTES` (tier → lista de candidatos `(provider, modelo)`) + fallback em tempo
  de invoke via `RoutedLLM`; providers OpenAI-compat (Groq/Qwen/MiniMax/DeepSeek)
  reusam `_build_openai`, Anthropic builder próprio (extra `--extra anthropic`).
  Hook `set_llm_telemetry_hook` alimenta a 5.3. Convenção CRÍTICA intacta.
  656 offline verdes; smoke real = turno vivo com narração + campanha + fallback
  + telemetria. ROUTES final: CLASSIFY `groq gpt-oss-20b→gemini-flash-lite`, FAST
  `minimax→qwen→groq llama-3.3-70b→gemini-flash`, SMART `deepseek→groq
  gpt-oss-120b→anthropic→gemini-pro` — **Groq grátis em TODOS os tiers** (o fix
  `method="function_calling"` p/ providers OpenAI-compat venceu o strict
  json_schema; ver ESTADO_ATUAL). Contas minimax/qwen pendentes de saldo/key do
  usuário — fallback cobre (deepseek respondeu vivo no playtest real de 2026-07-07).

## Fase 5 — Agentic playtest + telemetria → ✅ ENTREGUE (2026-07-06)

> 3 specs `done`. Ordem seguida: **5.1 → 5.2 → 5.3**. +43 testes
> (`test_fase51/52/53.py`) → **699 testes offline verdes** + smoke real executado.

**Objetivo (atingido):** Agentes testadores jogam campanhas automáticas offline
(MockLLM = custo zero). Detectam inconsistências, medem estado, embasam balanceamento.

**Fatias:**

- [x] **5.1 — Harness + 10 perfis** ([spec](specs/fase-5.1-playtest-harness.md)):
  `playtest/runner.py` (`run_campaign` via `app.invoke`, mesmo caminho da API) +
  10 perfis determinísticos em Python (`next_action(state, rng) -> str`, seed
  reproduz a campanha): agressivo, explorador, comerciante, diplomático, troll,
  mapa_breaker, combate, npc_only, loot_abuser, secret_rusher. `--real` opt-in.
  Saves isolados (`saves_playtest/`). Teste permanente na suíte (10 turnos).
- [x] **5.2 — Invariantes de estado** ([spec](specs/fase-5.2-invariantes.md)):
  `playtest/invariants.py` — `check_all(state, prev_state)` puro plugado no
  runner. HP válido, ouro ≥ 0, item único sem dupe, NPC morto não fala, fação
  derrotada não controla, relógio monotônico, segredo oculto não vaza
  (assinaturas curadas dos docs `hidden`). `assert_invariants` reusável.
- [x] **5.3 — Telemetria + relatório** ([spec](specs/fase-5.3-telemetria-relatorio.md)):
  `playtest/telemetry.py` (JSONL por turno + `summary.json`) + `playtest/report.py`
  (`aggregate` + `render_markdown` + `--baseline`) + `playtest/pricing.py` (custo
  estimado); grava provider/modelo/custo/`fell_back` por turno (hook do roteamento);
  tetos `--max-requests`/`--max-cost` protegem o `--real`.

**CLI:** `uv run python -m playtest run --all --turns 50` · `... report <run_id>`.

**Achados (mock — NÃO produção; report marca `mock: true`) da rodada `--all
--turns 50 --seed 42`:** 10/10 perfis com `erros=0` e `violações=0/0` (motor
sólido); `agressivo` morre no nível 1 (letal cedo sob combate mock); `explorador`
visita 13 locais / nível 3; `loot_abuser` acumula 297 ouro; **nenhum perfil
completa quest** (created=1/completed=0 em todos).

**Achados investigados a fundo → CORRIGIDOS (2026-07-07):**
- **Quests nunca fechavam.** Pipeline de conclusão está SÃO (já testado). Causa:
  nenhum perfil perseguia quest + o MockLLM só CRIAVA, nunca completava. Fix: perfil
  **`quester`** (11º perfil) + **MockLLM propõe `quest_completed`** ~50% quando há
  quest ativa no prompt → harness fecha quest offline (`test_quester_fecha_quest...`).
- **Letalidade viagem×combate.** Sem assimetria estrutural (mesmo `encounter_budget`;
  surpresa = ±5 init). Causa: a base de perigo do budget ignorava sub-nível
  (nível-1 @danger-4 = budget 11 ≈ 2 elites = one-shot vs 1 minion no perigo certo).
  Fix: **teto de sobrevivência** `cap = 5 + 3×nível + 2×aliados` — perigo alto segue
  duro mas não é sentença de morte no sub-nível; bosses ignoram budget.
- **Bugs de conteúdo/motor achados pelo playtest REAL e corrigidos:** rota `NONE →
  KeyError` no troll (router normaliza NONE→STORY); **vazamento do Verme-Primordial**
  (bug de parse do migrate dumpava o bestiário inteiro num doc público de 1613 linhas
  + doc de fação nomeava o segredo + Legião afirmava o pacto Valerius↔Daruun) — tudo
  curado na fonte + Verme `hidden` + reindex; RAG público verificado limpo.

**Suíte:** 43 → +4 → **703 testes offline verdes** (após os fixes acima).

**Ciclo `fix-playtest-achados` ([spec](specs/fix-playtest-achados.md) `done`, 2026-07-13):**
o novo `playtest transcript <run_id>` (ação→narração por turno) expôs 6 defeitos que o
mock escondia, todos corrigidos + smoke real: R1 beats em INGLÊS → força pt-BR; R2 NPC
repetia fala verbatim → `<SUA_ULTIMA_FALA>`+anti-repetição; R3 perfil `quester` colava
prosa do beat → objetivo curto; R4 morto continuava jogando (só a API barrava) → gate de
`game_over` no grafo + invariante; R5 nível-1 one-shot por elite em viagem → perigo
efetivo por nível (`forced_encounter_danger`, 5 zonas `apex` não escalam) + **fuga do
jogador (estava vestigial) implementada de verdade** (perfis `fujao`/`quester`). **715
testes offline verdes.**

---

## ✅ ENTREGUE — Ciclo de produto (2026-07-13) — 3 specs `done`

> Decisão da sessão 14 (pós-auditoria): antes de Fase 8 (arte) ou 10b (público),
> atacar **retenção e experiência**. **Executado na sessão 15 — as 3 specs
> viraram `done` (769 testes offline verdes; registro de execução no §8 de cada spec).**

1. ✅ **Balanceamento do early game + pacing** → [spec](specs/balanceamento-early-game.md) —
   baseline mock+real gravado ANTES do tuning; knobs: máx 1 elite no nível 1 +
   piso de HP nas classes frágeis (cap novo de budget pulado — dados não pediam);
   **derrota narrada "O Saque"** entregue (1ª queda fora de apex/boss = acorda
   1 dia depois saqueado, únicos voltam ao pool, 2ª queda = memorial; invariante
   5.2 nova vigia downed ilegal); **replan só quando o ARCO muda** (região nova
   + beat concluído; intervalo 10→15): replans do explorador **50 → 4 (−92%)**.
   Bônus: `secret_rusher` 30t REAL confirmou o fix do Verme (0 vazamentos).
2. ✅ **Streaming do turno (SSE) + custo em produção** → [spec](specs/streaming-turno-sse.md) —
   `POST /game/action/stream` (fases reais do grafo + narrativa em chunks +
   keepalive); smoke real: **`accepted` 0.09s / `route` 0.66s num turno de 20s**;
   frontend com indicador de fase + typewriter dirigido pelo servidor + fallback
   automático pro POST; log `rpg.turn` agora tem custo/providers reais (dev-only).
3. ✅ **Polish de sessão** → [spec](specs/polish-sessao.md) — tela "Continuar
   jornada" (lista/continua/exclui com confirmação; memorial em modo leitura),
   **chips de COMBATE 100% mecânicos** (`combat_suggestions` pura; smoke real
   confirmou name→id), export .txt + busca local da crônica, onboarding do 1º
   turno, passe mobile 390px (smoke Playwright 14/14, overflow-x 0).

**Decisões de refinamento (2026-07-13, com o usuário):**
- **Pós-ciclo (arte Fase 8 vs público 10b): DECIDIR DEPOIS**, com dados do
  playtest do ciclo — nenhum compromisso agora.
- **Backlog v2 enxugado (YAGNI):** sobrevive só **Crônica avançada** (compressão
  de capítulo + busca RAG — ver Backlog § Melhorias da Crônica). DESCARTADOS de
  vez: chips de exploração via LLM, dificuldade configurável. (O "prólogo
  guiado" foi REVIVIDO em 2026-07-16 por decisão do usuário — virou a spec
  `inicio-personalizado`, ver seção abaixo.)

---

## Achados do playtest longo REAL (2026-07-14) — insumo pra decisão pós-ciclo

> 3 perfis × 100 turnos no DeepSeek (agora principal no SMART + 1º fallback do
> FAST). ~$0.25, zero erro de turno. Análise completa + recomendações
> priorizadas: **[docs/playtest-longrun-2026-07-14.md](docs/playtest-longrun-2026-07-14.md)**.

- **Prosa/imersão do DeepSeek: salto claro** (arco da Thrace no quester = ponto
  alto; 7/7 quests, level 5). Custo ~$0.001/turno.
- Defeitos priorizados — **8 specs `approved` (2026-07-17) com ordem de dev
  cravada** (embeddings + métricas primeiro):
  1. [embeddings-provider](specs/embeddings-provider.md) — cadeia
     jina → openai → ollama → **gemini (último fallback; caro demais p/
     primário)**; provider fixado por índice via meta.
     **✅ `done` (2026-07-17): 804 verdes; re-index real com Jina + smoke §6
     3/3; RAG vivo.**
  2. [playtest-stop-gameover](specs/playtest-stop-gameover.md) — harness para
     na morte + telemetria de rota fiel (achados A+I).
     **✅ `done` (2026-07-18): 812 verdes; 552 turnos mock 0 rota vazia; smoke
     real 3/3 (combate parou no t14, combat_agent contado, p50=14s).**
  3. [combate-lifecycle](specs/combate-lifecycle.md) — viagem=fuga, combate
     órfão expira (achado C).
     **✅ `done` (2026-07-18): 822 verdes; 492 turnos mock 0 combat.zombie
     (combate ativo ≤4t vs 59); smoke real (viagem=fuga narrada, nunca teleporte).**
  4. [pos-saque-recuperacao](specs/pos-saque-recuperacao.md) — poção + carência
     + beat de recuperação (achado B).
     **✅ `done` (2026-07-18): 835 verdes; 3 seeds 0 violações de recuperação;
     smoke real (poção+beat+narração).**
  5. [npc-fallback-sem-alvo](specs/npc-fallback-sem-alvo.md) — fim do "Ninguém
     responde."; party em cena (achado E).
     **✅ `done` (2026-07-18): 844 verdes; quester/npc_only mock 0 "Ninguém
     responde"; smoke real (aliado cita objetivo, sozinho → gancho).**
  6. [beats-visibilidade-ptbr](specs/beats-visibilidade-ptbr.md) — sanitizador
     de segredo + PT-BR nos beats (achados D+F).
     **✅ `done` (2026-07-18): 855 verdes; módulo secret_signatures compartilhado;
     achado F era o fallback template em inglês (traduzido); smoke real 3 planos
     pt-BR sem segredo.**
  7. [encontros-dedupe](specs/encontros-dedupe.md) — NPC gerado com vínculo de
     local + cooldown (achado G).
     **✅ `done` (2026-07-18): 862 verdes; contexto filtrado por local; smoke real
     (NPC gerado não vaza p/ outro local).**
  8. [polish-prosa](specs/polish-prosa.md) — anti-repetição, 2ª pessoa na
     morte, menu de opções (achado H).
     **✅ `done` (2026-07-18): 870 verdes; smoke real (aberturas distintas + menu;
     downed em 2ª pessoa).**

> **🏁 As 8 specs do playtest longo estão `done` (2026-07-18).** Todos os 7
> defeitos do playtest 2026-07-14 fechados, cada um com smoke LLM real.
- Faltas de gameplay sentidas: quests não puxam pro mundo (quester: 1 local em
  100 turnos), exploração sem recompensa mecânica (23 locais, 0 quests, 0 ouro),
  economia invisível, aliados sem presença mecânica.
- ✅ Embeddings: resolvido pela spec embeddings-provider (Jina primário; RAG
  vivo). Google (429) virou último fallback.

## Criação de personagem imersiva — ✅ ENTREGUE 2026-07-17 (2 specs `done`)

> Pedido do usuário: jogador precisa de **afinidade com o personagem**. Hoje a
> criação é form seco; a backstory não influencia nada além de atributos. Meta:
> overview curado de Valoria + descrição livre → início de campanha sob medida
> (cena, missão pessoal e NPCs da história). Detalhe técnico SÓ nas specs.

1. [onboarding-valoria](specs/onboarding-valoria.md) `done` — wizard rico de 5
   passos com lore curado (`data/onboarding.json`: intro do mundo + 12 regiões
   + 10 classes + 6 raças) + `GET /data/onboarding`. Zero LLM, cobertura
   testada; smoke de UI 15/15 (Playwright, incl. 390px).
2. [inicio-personalizado](specs/inicio-personalizado.md) `done` —
   `POST /game/prologue` (1 chamada SMART + guard) gera prólogo confirmável;
   `/game/new` com `scenario` semeia `campaign_plan` pessoal + crônica + NPCs
   `in_scene` + cena de abertura. Sem scenario = fluxo atual intacto (CLI
   incluso). Smoke real §6 no DeepSeek executado — achado importante na spec:
   limites duros no schema do LLM derrubavam todos os providers (fix:
   truncagem em Python + `StartScenarioIn` estrito só na borda).

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
> `data/traits.json` (40 traits — lote 1; lote 2 até 80 pendente; sorteio
> seeded, DC modifiers em 6.4/4.4),
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

**Vazamento achado pelo playtest real e CORRIGIDO (Fase 5, 2026-07-07):** perguntar
direto "conte sobre o Rei Subterrâneo" fez o narrador surfacear o **Verme-Primordial
das Raízes do Mundo** (segredo `hidden`, turno 13 do `secret_rusher`). Raiz =
curadoria, NÃO motor: o doc de fação `data/codex/factions/ultimos_anoes_reino.md`
(`visibility: public`) NOMEAVA o Verme-Primordial na linha "Conhecimento:" → RAG
público surfaceia e o narrador repete. **Fix aplicado:** suavizada a linha na FONTE
`lore_nova/factions.txt` (Durgrim só SUSPEITA que o Rei teme "algo que dorme mais
fundo", sem nomear o Verme) + `migrate` (idempotente, 2 arquivos) + `rag.py`
reindexado (2587 chunks). Verificado: `query_rag(public)` p/ "Rei Subterrâneo" NÃO
retorna mais assinatura do Verme. Confirmação final = re-rodar `secret_rusher --real`
30 turnos (deferido — Groq esgotado hoje; a cerca já está no índice).

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
- [x] **Auditoria 2026-07-13 (achados A1–A8) — TODOS corrigidos na mesma data**
  (+14 testes `tests/test_audit_fixes.py`; detalhe em ESTADO_ATUAL § Bugs conhecidos):
  `level` validado no `/game/new` (fechava ouro negativo); gate `game_over` + rate
  limit em `/game/equip`+`/game/levelup`; `save_game_state` via `save_path()`/
  sanitização; flag `simulated` = `llm_setup.is_simulated()` (todas as keys);
  bind default `127.0.0.1` (`RPG_HOST` p/ expor); 500 sem `str(e)`; teto em
  `input_text`; poda do dict do rate limit
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

> Refinamento 2026-07-13: único item de backlog v2 MANTIDO (os demais foram
> descartados — ver § Próximo ciclo). Search local + download .txt saem na
> spec polish-sessao; ficam aqui os avançados:

- [x] ~~**Arcos:** arc_title + chapters~~ → ✅ entregue na **Fase 3.1**
- [ ] **Compressão:** capítulo antigo > 20 entradas → archivist comprime
- [ ] **Busca semântica:** endpoint `POST /game/chronicle/search` via RAG
- [x] ~~**Frontend restante:** search + download .txt~~ → na spec **polish-sessao** (busca local + export)

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
6. **Roteamento multi-provider** ✅ ENTREGUE (2026-07-06, smoke real): 3 tiers + rotas com fallback (produto pago).
7. **Fase 5** ✅ ENTREGUE (2026-07-06, 3 specs `done` + smoke real): agentic playtest + invariantes + telemetria (699 testes).
8. **Fase 11** ✅ ENTREGUE (2026-07-06): 9 contratos LLM verdes contra Gemini real (`-m llm_contract`).
9. **Ciclo fix-playtest-achados** ✅ ENTREGUE (2026-07-13): 6 defeitos do transcrito real + fuga do jogador (715 testes).
10. **Auditoria de segurança** ✅ ENTREGUE (2026-07-13): 8 achados A1–A8 corrigidos + regressão (729 testes).
11. **Fases 8+** (próximas): arte, sprites/som, Fase 10b (Postgres/auth).

Sem 2.5-2.8, as features de economia/craft/encontros ficariam acopladas, contraditórias e não-testáveis — fundação entregue; Fases 4/6/7 construíram gameplay, conteúdo sistêmico e pipeline de autoria em cima dela.

### Métrica de sucesso

- ✅ Fase 2.8: campanha 50 turnos sem contradição; event log rastreável; contexto nunca explode.
- ✅ Fase 4: progressão + buff observável + poção em combate + craft com receita + mercadores distintos + 4v5 + morte com narrativa (smoke real 2026-07-05).
- ✅ Fase 6: porto bloqueado → escassez rastreável no event_log (smoke real 2026-07-05).
- ✅ Fase 7: NPC novo via template validado automaticamente; segredo de NPC não chega ao narrador (smoke real 2026-07-05).
- ✅ Fase 5: 10 perfis × 50 turnos automatizados sem quebrar invariantes (`erros=0`, `violações=0`);
  telemetria por turno com provider/custo; relatório agregado + baseline (smoke real 2026-07-06).
