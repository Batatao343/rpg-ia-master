# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Leia isto **primeiro** ao retomar o trabalho. Complementa `CLAUDE.md` (arquitetura).
> Decisões estruturais: `REFERENCE.md` (sob demanda). Histórico de sessões: `CHANGELOG.md`.
> Última atualização: 2026-07-03 (sessão 5: Fase 3.3 — Quest log)

---

## TL;DR — Em que pé está

**Sessão 2026-07-03 (5): Fase 3.3 DONE — Quest log (objetivos visíveis).**
`GameState.quests: List[Quest]` (side quests persistentes) somado à main quest, que
continua sendo VIEW pura do `campaign_plan` (zero estado novo). Criação: `StoryUpdate`/
`NPCResponse` ganham `proposed_quests` (campo novo, dentro dos trys existentes);
`services/quest_log.py::register_proposed_quests` valida/zera ids inválidos (location/
origin), deduplica por similaridade de título, aplica teto de 8 ativas. No `npc_actor`,
`origin_name`/`origin_entity_id` são SOBRESCRITOS em Python (match por nome no grafo
canônico) — não confiados ao LLM. **Conclusão reusa o pipeline 2.6**: nenhum campo
estruturado novo — o LLM propõe `ProposedWorldEvent(type="quest_completed",
target_id=quest_id, payload={"quest_id":...})` pelo MESMO canal de `npc_killed`;
`_v_quest_completed` ganhou branch de `quest_id` (modo beat antigo intacto como
fallback). Falha sistêmica (`quest_failed`) roda 100% em Python após `npc_killed`
aplicado — nunca passa pelo LLM. `render_milestone` usa `payload.quest_title` (embutido
pelo `event_processor` antes do milestone) em vez de resolver `target_id` no grafo —
`target_id` de quest é um uuid, não id canônico. Endpoint: `_quest_block` virou
`{main, side, markers}`; aba nova "Missões" no HUD (`QuestsTab.tsx`, greenfield — o
bloco antigo de "Objetivo Atual" nunca tinha componente algum) + selo no `WorldMap`
pro local de quest ativa. Suíte offline: 258 → **290 verdes** (+32
`tests/test_fase33.py`). `npm run build` + `smoke_api.sh` ok. **Smoke com LLM real
executado e verde**: NPC (Gemini SMART) propôs quest real com origem corretamente
sobrescrita pelo código; turno seguinte (Gemini) concluiu a quest via
`quest_completed`, milestone na crônica mostrou o TÍTULO (não o uuid). Detalhes/desvios
da spec: `CHANGELOG.md` e `specs/fase-3.3-quest-log.md` §8.

Sessão 2026-07-03 (4) — Fase 3.2 (Codex do jogador + bestiário progressivo) `done`; ver
`CHANGELOG.md`.

Sessão 2026-07-03 (3) — Fase 3.1 (crônica por capítulos) `done`; ver `CHANGELOG.md`.

Sessão 2026-07-03 (2) — faxina de código morto + auditoria de gameplay → **Fase 4 —
Gameplay Core** no ROADMAP (6 fatias `draft`): ver `CHANGELOG.md`. Achados-chave:
`XP_TABLE` sem consumidor (não existe progressão), buffs só texto, party só schema,
craft/shop/loot 100% LLM, poção inutilizável em combate.

**Fases 2.6, 2.7 e 2.8 DONE** (detalhes no `CHANGELOG.md`; specs em `specs/`):
2.6 = LLM propõe eventos estruturados, motor valida/aplica (`world_validators` +
`event_processor`; combate gera `npc_killed` determinístico). 2.7 = rules engine
(`services/rule_engine.py`, cascata determinística com anti-loop, `world_rules.json` +
overlay `components.json` migration-safe). 2.8 = context builder (`build_context_pack`
ranqueia fatos por relevância+local+recência com orçamento por seção; estado vivo entra
ANTES da lore base; 4 agentes integrados: storyteller/npc/combat/campaign_manager).
Smoke LLM real das 3 fases pendente de quota.

**Próximo passo:** Fase 3.4 (visualização de estado, spec `draft`) — fecha a Fase 3;
depois Fase 4 — Gameplay Core (cada fatia vira spec antes de implementar; ver ROADMAP
§ Fase 4).

Entregas da 2.5b (detalhes no `CHANGELOG.md`): mapa de Valoria 30 nós, 18 fações,
6 raças com traits mecânicos (`apply_racial_traits`), bestiário 84 entradas com
`regions`/`behavior`, combate com perfis (tatico/feroz/covarde/implacavel + moral/fuga/
frenesi), fuga → `threat_alerts` → reforços regionais, `pick_encounter_enemy()` por
região, `entities_extra.json` (curadoria manual que `migrate_lore_nova.py` NÃO toca).

**⚠️ Saves pré-2.5b:** carregam sem crash (backfill), mas locais/fações antigos não
existem mais no mapa — sessões antigas ficam narrativamente órfãs. Arquivar saves antigos.

---

## Como rodar (ambiente deste Windows)

`python` global é 3.14 (WindowsApps) — **errado** (projeto exige 3.13). Use sempre `uv`.

`uv` **não está no PATH** — fica em `%APPDATA%\Python\Python314\Scripts`. Em PowerShell:

```powershell
$env:Path = "$env:APPDATA\Python\Python314\Scripts;$env:Path"
uv sync                              # cria .venv com Python 3.13
copy .env.example .env               # cole GOOGLE_API_KEY no .env (NUNCA na .env.example)
uv run pytest                        # 290 testes offline verdes (test_real_llm precisa de chave)
uv run python game_engine.py         # CLI
uv run uvicorn api:app --port 8000   # API + frontend web (http://localhost:8000)
uv run python rag.py                 # reindexar lore (data/codex/) + regras (data/rules.txt)
uv run python scripts/migrate_lore_nova.py  # regerar Codex de lore_nova/ (SOBRESCREVE curadoria)
bash scripts/smoke_api.sh [porta]    # smoke da API (health, map, /game/new, /game/action)
```

**Frontend:** `cd web && npm install && npm run build` → gera `web/dist` (servido na
raiz). Dev: `npm run dev` (:5173 com proxy para :8000).

**LLM providers:** `LLM_PROVIDER=gemini|ollama|openai|openai_compat` no `.env`
(ver `.env.example`). Sem chave (ou provider sem chave), `get_llm()` devolve `MockLLM` —
jogo jogável sem rede.

**Quota Gemini:** free tier = **20 req/dia por modelo** (flash e pro têm buckets
separados). E2e em lote inviável. `get_llm()` é fail-fast (`max_retries=0`): `429` falha
em ~3s. **MockLLM esconde bugs de mapeamento** — validar nós novos com a chave real.

---

## O que funciona

- Criação de personagem (CLI + `/game/new`) — resiliente sem chave
- Loop completo: `campaign_manager → dm_router → (storyteller|combat|npc|loot) → archivist → save`
- **Combate:** IA identifica/narra; Python resolve tudo (`combat_mechanics.py`) —
  iniciativa, DoT/condições, custos, cooldowns, saves + perfis de comportamento (2.5b)
- **Mundo:** mapa de Valoria 30 nós, relógio, viagem (fog of war), descanso, gating por
  classe; raças com traits mecânicos (2.5b)
- **Fase 2:** fações com objetivos, reputação, não-onisciência, ascensão, encontros
  temáticos, memória de NPC vetorizada, world_simulator off-screen
- **Fase 2.5:** Codex Valoria + grafo de mundo (558 entidades) + `event_log`/
  `world_projection` no save + RAG com visibilidade (`secret`/`hidden` não vaza ao
  narrador); timeline por era em `data/codex/timeline/`
- Beats de campanha avançam via `StoryUpdate.beat_completed`; HUD mostra objetivo
- **Fase 3.1:** crônica por capítulos (`arc_title` do planner) — milestones
  determinísticos do event_log (auditáveis por `event_id`) + prosa de menestrel;
  backfill de saves antigos; HUD distingue ⚔ milestone de ❧ prosa
- **Fase 3.2:** Codex do jogador (`GET /game/codex`, aba `CodexTab`) — locais/fações/
  NPCs/segredos derivados do save (zero estado novo); bestiário progressivo com 4 graus
  (`bestiary_knowledge`, 100% Python) revelando ficha crescente da criatura
- **Fase 3.3:** quest log (aba "Missões") — main quest deriva do `campaign_plan`; side
  quests (`GameState.quests`) propostas por NPC/narrador, concluídas via pipeline 2.6
  (`quest_completed`), falha sistêmica automática se a origem canônica morre
- Multi-provider LLM + typewriter effect no frontend React
- Loot/Craft/Shop/Treasure + economia (sinal do ouro forçado em Python)
- Memória híbrida (resumo + RAG por sessão) + persistência JSON por `game_id`

---

## Convenção CRÍTICA de resiliência

`FallbackLLM.with_structured_output(X).invoke()` devolve `AIMessage`, **não** instância
de `X`. Acessar `resultado.campo` **estoura** sem guard.

**Regra obrigatória em todo nó com `with_structured_output`:**
1. `try/except` no acesso aos campos, **ou**
2. `isinstance(resultado, SeuModelo)` antes de usar.

Já blindados: `router.py`, `character_creator.py`, `combat.py` (isinstance). Demais
agentes: dentro de `try`.

---

## Bugs conhecidos (sessão 2026-06-26)

| Bug | Local provável / destino |
|---|---|
| Inventário: item narrado não entra no inventário | `agents/loot.py` — mapeado na **Fase 4.3** |
| Capitalização estranha em itens | Grep `title()` / `capitalize()` — mapeado na **Fase 4.3** |
| NPC errado responde fala destinada a outro | `agents/router.py` — `active_npc_name` não filtra |
| Morte do player sem narrativa (só tela de morte) | Fluxo final de combate — mapeado na **Fase 4.6** |

**Design:** campaign manager coloca plot twists com muita frequência — aumentar
intervalo de triggers de replan.

## Limitações conhecidas

- **Inventário inicial** usa nomes livres, não IDs — `ARTIFACTS_DB.get(item_id)` não acha
  (arma inicial não dá bônus de combate) — mapeado na **Fase 4.3**
- **API stateless por save** — sem sessão concorrente; migrar p/ Postgres+pgvector ao escalar
- **Saves antigos** (schema `class`/`abilities`) carregam mas campos novos ficam ausentes

---

## Checklist ao começar a próxima tarefa

0. Feature/fase nova? **Spec primeiro** — `specs/` (CLAUDE.md § spec-driven)
1. `/qa` verde antes de mexer
2. Nó novo com `with_structured_output`? Guard de fallback (seção CRÍTICA)
3. Mudou schema do player/estado? Atualizar `state.py` + `game_engine.py` + `api.py` + creator
4. Novo agente no grafo? Conectar ao `archivist` no fim (REFERENCE.md)
5. Editou `lore_nova/`, `data/codex/` ou `data/rules.txt`? Rodar `uv run python rag.py`
6. Mecânica nova (números)? Python determinístico, não LLM
7. **Ao finalizar:** `/wrap-up` — suíte completa verde + ESTADO_ATUAL.md + ROADMAP.md + commit
