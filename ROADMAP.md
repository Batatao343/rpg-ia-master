# ROADMAP — RPG IA: de MVP para produto

> Visão de produto priorizada. Objetivo: deixar o jogo **divertido antes de escalar**.
> Status por fase abaixo. Complementa `CLAUDE.md` (arquitetura) e `ESTADO_ATUAL.md` (estado atual).

---

## Insight central

Quase todo pedido grande (mapa+fog, fações que se movem, itens regionais) depende de **um alicerce: o modelo de mundo estruturado** (locais como grafo + relógio + fações). Por isso a Fase 0 veio primeiro — ela destrava as demais. Construir features sem o alicerce = retrabalho.

## Decisões do dono

- Sequência: **Fase 0 primeiro** (feito), depois apresentação.
- Frontend: migrar para **React + Vite** na fase de apresentação (Fase 1).
- Arte: **híbrida** — packs pixel art CC0 curados (LPC/Kenney) para personagem/cenário + IA só para itens únicos.

---

## Pilares

- **P1 — Profundidade de simulação:** mundo estruturado, itens regionais, habilidades abertas com gating, memória de NPC vetorizada.
- **P2 — Apresentação:** React, mapa com fog of war, sprites pixel art, polish de HUD.
- **P3 — Mundo vivo:** simulador de eventos em descanso/viagem; fações/vilões com objetivos próprios.
- **P4 — Arte generativa:** IA gera a arte (pixel) do item a partir da descrição regional.

---

## Fases

### ★ Fase 0 — Fundação + ganhos baratos ✅ ENTREGUE
Branch `feat/fase0-mundo`. 26 testes verdes.
- [x] Modelo de mundo estruturado: `data/world_map.json` (grafo de 9 locais) + helpers em `gamedata.py`.
- [x] `state`: `current_location_id`, `visited` (fog of war), `world_clock` (dia+período).
- [x] `world_utils.py`: relógio, viagem entre locais conectados, descanso (cura+tempo).
- [x] Habilidades abertas com gating por personagem: `class_themes.py` revivido + Ruler em toda ação livre.
- [x] Itens cientes de região/local no `loot.py`.
- [x] API expõe `world` (location_id/day/period/visited/danger); front mostra Dia/Período.

> **Pendência de qualidade:** o gating de habilidade só fica afiado com `GOOGLE_API_KEY` (no modo simulado o juiz é permissivo).

### Fase 1 — Apresentação (tira o "simplista")
- [ ] Migrar frontend para **React + Vite** (canvas, sprites, estado de mapa).
- [ ] **Mapa com fog of war:** renderiza o grafo; revela nós conforme `world.visited` cresce. (Depende da Fase 0 — pronto.)
- [ ] **Sprites pixel art** (híbrido): packs CC0 para personagem/cenário; IA só nos itens.
- [ ] Polish de HUD.

### Fase 2 — Mundo vivo
- [ ] Nó `world_simulator` acionado em descanso/viagem (hook já marcado em `world_utils.apply_rest`): avança o relógio, simula eventos off-screen, grava no RAG da sessão, altera perigo/encontros.
- [ ] **Fações/vilões com objetivos próprios:** `state.factions[]` (name, goal, progress, location, disposition); avançam a cada tick de descanso/viagem; disparam eventos de mundo. Reputação por facção.
- [ ] **Memória de NPC vetorizada:** fatos no FAISS namespaceados por `game_id`+`npc_id`, recuperados por relevância. Reusa `add_memory_to_session`/`query_rag`.

### Fase 3 — Arte generativa de itens
- [ ] IA gera arte pixel do item a partir da descrição regional (Fase 0). Estilo travado, **cache por `item_id`**, geração assíncrona/lazy, fallback de silhueta no modo simulado.

---

## Backlog de diversão (oportunidades soltas)

- [ ] Objetivos/quests na UI — `campaign_plan.beats` já existem; falta exibir e avançar (avanço de beat hoje é no-op).
- [ ] Combate com profundidade: iniciativa, `active_conditions` (já existe, subusado), cooldowns.
- [ ] Tempo/clima com efeito real (campos existem).
- [ ] Codex/bestiário revelável (`bestiary.json` já existe).
- [ ] Economia regional (lojas com estoque por região).
- [ ] Permadeath / runs roguelike, aproveitando memória de mundo entre runs.
- [ ] Atmosfera sonora por região.
- [ ] Telemetria de balanceamento no playtest.

---

## Riscos e princípios

- **Custo & latência:** cada feature soma chamadas de IA/imagem → manter tiers, cache, geração assíncrona. **Estender o MockLLM a todo agente novo** (jogo segue jogável offline).
- **Consistência visual:** arte por IA deriva de estilo → travar paleta; assets curados no núcleo, IA só nos itens.
- **Crescimento de estado:** mundo vivo + memória vetorial incham save/FAISS → pruning/resumo.
- **Escopo:** produto vertical, não MVP. Fatiar **incrementos finos e jogar cada um** antes do próximo.

---

## Migração para escala (quando abrir multi-usuário)

Hoje persistência é local (JSON + FAISS). Ao escalar: Postgres + **pgvector** no Supabase, migrations versionadas no repo. `query_rag()` e `save_game_state()` são abstrações isoladas — trocar FAISS→pgvector e JSON→Postgres é reescrever só `rag.py` e `persistence.py`, sem tocar nos agentes.
