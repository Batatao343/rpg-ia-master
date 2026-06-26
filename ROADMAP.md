# ROADMAP — RPG IA: de MVP para produto

> Visão de produto priorizada. Objetivo: deixar o jogo **divertido antes de escalar**.
> Status por fase abaixo. Complementa `CLAUDE.md` (arquitetura) e `ESTADO_ATUAL.md` (estado atual).

---

## Insight central

Quase todo pedido grande (mapa+fog, fações que se movem, itens regionais) depende de **um alicerce: o modelo de mundo estruturado** (locais como grafo + relógio + fações). Por isso a Fase 0 veio primeiro — ela destrava as demais. Construir features sem o alicerce = retrabalho.

## Decisões do dono

- Sequência: **Fase 0 primeiro** (feito), depois apresentação.
- Frontend: migrar para **React + Vite** na fase de apresentação (Fase 1).
- Arte: **híbrida** — packs pixel art CC0 curados (LPC/Kenney) para personagem/cenário + IA só para itens únicos. **Sprites são a ÚLTIMA entrega** (sourcing pesado) — só depois de tudo jogável.

---

## Pilares

- **P1 — Profundidade de simulação:** mundo estruturado, itens regionais, habilidades abertas com gating, memória de NPC vetorizada.
- **P2 — Apresentação:** React, mapa com fog of war, polish de HUD. (Sprites pixel art ficam para o fim — ver última fase.)
- **P3 — Mundo vivo:** simulador de eventos em descanso/viagem; fações/vilões com objetivos próprios.
- **P4 — Arte generativa:** IA gera a arte (pixel) do item a partir da descrição regional.

---

## Fases

### ★ Fase 0 — Fundação + ganhos baratos ✅ ENTREGUE
Branch `feat/fase0-mundo`. 39 testes verdes (offline). Fluxo de IA auditado + hardening em 2026-06-25 (ver `ESTADO_ATUAL.md`).
- [x] Modelo de mundo estruturado: `data/world_map.json` (grafo de 9 locais) + helpers em `gamedata.py`.
- [x] `state`: `current_location_id`, `visited` (fog of war), `world_clock` (dia+período).
- [x] `world_utils.py`: relógio, viagem entre locais conectados, descanso (cura+tempo).
- [x] Habilidades abertas com gating por personagem: `class_themes.py` revivido + Ruler em toda ação livre.
- [x] Itens cientes de região/local no `loot.py`.
- [x] API expõe `world` (location_id/day/period/visited/danger); front mostra Dia/Período.

> **Pendência de qualidade:** o gating de habilidade só fica afiado com `GOOGLE_API_KEY` (no modo simulado o juiz é permissivo).

### Fase 1 — Apresentação (tira o "simplista")
- [ ] Migrar frontend para **React + Vite** (TypeScript; app em `web/`, vanilla `frontend/` como fallback até paridade).
- [ ] **Mapa com fog of war:** renderiza o grafo (`coords` já no `world_map.json`); revela nós conforme `world.visited` cresce. (Depende da Fase 0 — pronto.)
- [ ] Polish de HUD.

> Sprites pixel art **não** entram aqui — viraram a última fase (sourcing pesado).

### Fase 2 — Mundo vivo
- [x] **Fações/vilões com objetivos próprios** (núcleo determinístico): `state.factions[]` (id, name, goal, region, progress 0-100, pace, disposition, reputation, completed); avançam a cada tick de descanso (2 períodos)/viagem (1); ao concluir, emitem evento que o storyteller tece na narração. Seed em `data/factions.json` (5 fações por região). Aba "Fações" no HUD. Testes: `tests/test_fase2.py`. **Reputação por ação do jogador entregue:** o storyteller identifica (IA) qual fação a ação ajuda/prejudica → `world_utils.apply_reputation` aplica delta FIXO em Python (`REP_STEP=12`, clamp ±100, disposição derivada por limiar ±40); id inválido = no-op. **Não-onisciência entregue (conhecimento em camadas):** `state.faction_intel` (por fação: known/knows_goal/progress_seen snapshot/intel_turn) começa vazio; só um **NPC** revela (IA sinaliza `faction_reveals`, `world_utils.apply_faction_reveal` grava); narrador/HUD só citam fações conhecidas; HUD mostra **snapshot** de progresso (nunca o ao vivo) + hint de intel defasada. **Ascensão entregue (consequências concretas):** ao concluir objetivo, a fação muda o mundo via `world_utils.resolve_faction_completions` (determinístico, autorado em `data/factions.json#ascension`): dominar local (`world.controlled`), expandir região (reseta → cadeia), elevar perigo (`world.danger_overrides`), invocar entidade (`world.looming_threat`), eliminar fação rival (`defeated`). Nota nomeia a fação só se conhecida; mapa mostra domínio/perigo elevado. **Encontros entregues:** viajar/descansar chama `world_utils.check_encounter` (determinístico) — perigo≥4, local dominado por fação hostil, ou `looming_threat`+perigo≥3 disparam combate temático (curto-circuito no storyteller → COMBAT START + `combat_target`; aresta condicional `storyteller→combat|archivist`). Cooldown 2 turnos; dica respeita não-onisciência. O estado de mundo da Etapa B agora afeta a jogabilidade. **Pendente:** dificuldade do inimigo escalando com o perigo efetivo.
- [ ] Nó `world_simulator` acionado em descanso/viagem (hook em `world_utils.apply_rest`): avança o relógio, simula eventos off-screen narrados (LLM), grava no RAG da sessão, altera perigo/encontros. (Tick determinístico de fações já existe; falta a camada narrada.)
- [ ] **Memória de NPC vetorizada:** fatos no FAISS namespaceados por `game_id`+`npc_id`, recuperados por relevância. Reusa `add_memory_to_session`/`query_rag`.

### Fase 3 — Arte generativa de itens
- [ ] IA gera arte pixel do item a partir da descrição regional (Fase 0). Estilo travado, **cache por `item_id`**, geração assíncrona/lazy, fallback de silhueta no modo simulado.

### ★ Fase 4 (ÚLTIMA) — Sprites pixel art de personagem/cenário
> Deliberadamente por último: exige **trabalho pesado de sourcing** (curar packs CC0 LPC/Kenney,
> padronizar paleta/escala) antes de qualquer código. Só faz sentido com o jogo já jogável e bonito
> no resto. Híbrido: assets curados no núcleo, IA só nos itens (Fase 3).
- [ ] Sourcing/curadoria de packs CC0 (LPC/Kenney) — personagem e cenário.
- [ ] Integração dos sprites no mapa e na cena (paleta/escala travadas).

---

## Backlog de diversão (oportunidades soltas)

- [x] Objetivos/quests na UI — HUD mostra objetivo atual + beats (pendente/atual/feito) com progresso; storyteller sinaliza `beat_completed` e avança `current_step` (replaneja ao esgotar). Mock avança ~30%/turno no modo simulado.
- [x] Combate com profundidade: **IA identifica + Python resolve**. Iniciativa (d20+dex), condições/DoT estruturadas, custos (stamina/mana) + cooldowns de habilidade, save por atributo real do inimigo, painel de combate na UI. Núcleo determinístico em `combat_mechanics.py` (testável offline).
- [ ] **Objetivo do jogador** via IA: o narrador devolve `player_objective` (meta em linguagem de jogador) no `StoryUpdate`, separado dos beats internos do `campaign_manager`. Hoje o HUD não mostra objetivo (removido por ser direção do narrador).
- [ ] **Conhecimento de NPC profundo** (aba Personagens): o que o jogador sabe vs. não sabe; fatos revelados por interação. Hoje a aba mostra só o básico (nome/papel/local/relação/última lembrança).
- [ ] **Crônica/diário persistente completo**: hoje a Crônica usa o histórico mantido no save (~últimos 20 turnos). Persistir o diário inteiro à parte para campanhas longas.
- [ ] Tempo/clima com efeito real (campos existem).
- [ ] Codex/bestiário revelável (`bestiary.json` já existe).
- [ ] Gerar arte dos monstros e personagens
- [ ] Economia regional (lojas com estoque por região).
- [ ] Permadeath / runs roguelike, aproveitando memória de mundo entre runs.
- [ ] Atmosfera sonora por região.
- [ ] Telemetria de balanceamento no playtest.

---

## Riscos e princípios

- **Custo & latência:** cada feature soma chamadas de IA/imagem → manter tiers, cache, geração assíncrona. **Estender o MockLLM a todo agente novo** (jogo segue jogável offline).
- **Quota:** free tier do Gemini = 20 req/dia por modelo → testar IA real em lote exige billing. Validar caminhos novos de structured output com a chave real (o MockLLM esconde bugs de mapeamento de campo).
- **Consistência visual:** arte por IA deriva de estilo → travar paleta; assets curados no núcleo, IA só nos itens.
- **Crescimento de estado:** mundo vivo + memória vetorial incham save/FAISS → pruning/resumo.
- **Escopo:** produto vertical, não MVP. Fatiar **incrementos finos e jogar cada um** antes do próximo.

---

## Migração para escala (quando abrir multi-usuário)

Hoje persistência é local (JSON + FAISS). Ao escalar: Postgres + **pgvector** no Supabase, migrations versionadas no repo. `query_rag()` e `save_game_state()` são abstrações isoladas — trocar FAISS→pgvector e JSON→Postgres é reescrever só `rag.py` e `persistence.py`, sem tocar nos agentes.
