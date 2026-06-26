# ROADMAP — RPG IA

> Objetivo: deixar o jogo **divertido antes de escalar**.
> Complementa `CLAUDE.md` (arquitetura) e `ESTADO_ATUAL.md` (estado atual).

---

## O que já foi entregue

| Fase | O que é |
|---|---|
| **Fase 0** | Modelo de mundo estruturado (grafo de locais, relógio, viagem, descanso, fog of war, gating de ação por classe) |
| **Fase 1** | Frontend React + Vite (tom The Witcher), HUD em abas, mapa interativo, modo combate, crônica |
| **Fase 2** | Fações com objetivos, reputação, não-onisciência, ascensão que muda o mundo, encontros temáticos, memória de NPC vetorizada, world_simulator |
| **Polishes** | Combate profundo (IA identifica, Python resolve), beats de campanha na UI, typewriter effect, otimização ~5-6→2-3 chamadas/turno, multi-provider LLM (Gemini/Ollama/OpenAI/Qwen) |

---

## Próximas entregas prioritárias

### Bugs (sessão 2026-06-26)
- [ ] **Inventário:** storyteller narra item mas loot/inventory não commita — checar `agents/loot.py`
- [ ] **Capitalização:** itens do inventário com letra maiúscula em posição errada — grep `title()` / `capitalize()`
- [ ] **NPC routing:** NPC errado responde fala destinada a outro (active_npc_name não filtra)
- [ ] **Morte sem narrativa:** tela de morte aparece sem descrever a morte — adicionar death_narrative ao fluxo de combate

### Design (sessão 2026-06-26)
- [ ] **Campaign manager:** muitos plot twists seguidos — aumentar intervalo de triggers de replan, deixar história fluir mais

### Fase 3 — Arte generativa de itens
- [ ] IA gera arte pixel do item a partir da descrição regional — cache por `item_id`, fallback de silhueta no modo simulado

---

## Backlog de diversão

- [ ] **Agente autopilot** (TOP 2): persona+local configurável, loop autônomo que joga por um tempo, loga prompts/decisões/resultados para auditoria de qualidade
- [ ] **Objetivo do jogador via IA:** narrador devolve `player_objective` (meta em linguagem do jogador) separado dos beats internos
- [ ] Conhecimento de NPC profundo na aba Personagens (o que o jogador sabe vs. não sabe)
- [ ] Crônica/diário completo persistente para campanhas longas
- [ ] Tempo/clima com efeito real (campos já existem)
- [ ] Codex/bestiário revelável (`bestiary.json` já existe)
- [ ] Economia regional (lojas com estoque por região)
- [ ] Atmosfera sonora por região
- [ ] Dificuldade de encontro escalando com `danger_level` efetivo

### ★ Fase 4 (ÚLTIMA) — Sprites pixel art
> Exige sourcing pesado (curar packs CC0 LPC/Kenney). Só depois de tudo jogável e polido.
- [ ] Curadoria de packs CC0 — personagem e cenário
- [ ] Integração dos sprites no mapa e na cena

---

## Princípios

- **Mecânica é Python, não LLM.** IA identifica/narra; números resolvem em código determinístico.
- **MockLLM esconde bugs de mapeamento** — validar nós novos com chave real (respeitando quota).
- **Fatiar fino e jogar** cada incremento antes do próximo.
- **Multi-provider:** hoje Gemini/Ollama/OpenAI/Qwen via `LLM_PROVIDER` no `.env`. Adicionar provider = 1 função em `llm_setup.py`.

---

## Migração para escala (quando abrir multi-usuário)

`query_rag()` e `save_game_state()` são abstrações isoladas — trocar FAISS→pgvector e JSON→Postgres é reescrever só `rag.py` e `persistence.py`.
