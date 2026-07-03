# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Leia isto **primeiro** ao retomar o trabalho. Complementa `CLAUDE.md` (arquitetura).
> Decisões estruturais: `REFERENCE.md` (sob demanda). Histórico de sessões: `CHANGELOG.md`.
> Última atualização: 2026-07-03 (sessão 4: Fase 3.2 — Codex do jogador + bestiário progressivo)

---

## TL;DR — Em que pé está

**Sessão 2026-07-03 (4): Fase 3.2 DONE — Codex do jogador + bestiário progressivo.**
`GameState.bestiary_knowledge: Dict[str, BestiaryKnowledge]` (contadores `seen/fought/
defeated`, 100% Python) alimenta `services/discovery.py::knowledge_tier` (4 graus:
Rumores/Encontrada/Estudada/Dominada) e `bestiary_view` (revela mais ficha por grau).
`player_codex(state)` agrega — SEM estado novo além do bestiário — locais visitados,
fações conhecidas (`goal` só se `knows_goal`, mesma regra do HUD), NPCs (match por nome
em `load_entities()`) e segredos revelados; corpo vem do Codex (`data/codex/`) só se
`visibility: public` (`services/codex_loader.py::codex_index`/`codex_body`, cache
módulo-level). Hooks: spawn de combate → `record_encounter` (1x/combate, não por round);
morte de instância → `record_kills`; `check_encounter` (emboscada) nomeia criatura ANTES
do combate → `agents/storyteller.py` registra `record_rumor` (seen sem fought) —
ajuste em relação à spec original: o rumor não nasce no `threat_alert` em si (a criatura
que fugiu já teria `fought≥1`), nasce quando o hint nomeia a criatura pro jogador antes
da luta. Endpoint `GET /game/codex` on-demand (fora do `GameResponse`, não incha o
turno); frontend `CodexTab` com fetch próprio (novo padrão — `ChronicleTab` só usa
props) + refetch quando `world.turn_count` muda com a aba aberta. Suíte offline:
228 → **258 verdes** (+30 `tests/test_fase32.py`, ids reais de `data/bestiary.json`/
`data/codex/`, zero fixture inventada). `npm run build` + `smoke_api.sh` (com
`/game/codex` novo) ok. Zero LLM na fase — sem guard de `FallbackLLM`. Detalhes/desvios
da spec: `CHANGELOG.md` e `specs/fase-3.2-conhecimento-revelavel.md` §8.

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

**Próximo passo:** Fase 3.3 (quest log — usa o `arc_title` da 3.1, spec `draft`), depois
3.4 (visualização de estado); depois Fase 4 — Gameplay Core (cada fatia vira spec antes
de implementar; ver ROADMAP § Fase 4).

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
uv run pytest                        # 258 testes offline verdes (test_real_llm precisa de chave)
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
