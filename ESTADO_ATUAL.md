# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Leia isto **primeiro** ao retomar o trabalho. Complementa `CLAUDE.md` (arquitetura).
> Decisões estruturais: `REFERENCE.md` (sob demanda). Histórico de sessões: `CHANGELOG.md`.
> Última atualização: 2026-07-03 (sessão 2: faxina + auditoria de gameplay)

---

## TL;DR — Em que pé está

**Sessão 2026-07-03 (2): FAXINA de código morto + auditoria de gameplay → Fase 4 no ROADMAP.**
Removidos (zero importadores em produção, verificado por grep): `agents/ruler_completo.py`,
`engine_utils.py`, `dice_system.py`, `COMMON_LOOT_TABLE`; testes órfãos de `test_mvp.py`
removidos junto. Suíte offline: **211 verdes** (era 216; −5 testes de código morto).
CLAUDE.md/README corrigidos (documentavam módulos mortos como vivos). Auditoria completa
de jogabilidade virou a **Fase 4 — Gameplay Core** no ROADMAP (6 fatias `draft`:
4.1 progressão/XP/árvore de habilidades · 4.2 buffs/passivas mecânicos · 4.3 inventário/
equip/itens usáveis · 4.4 economia determinística (craft/mercadores/loot tables) ·
4.5 party em combate · 4.6 dificuldade/IA/morte narrativa). Achados-chave da auditoria:
`XP_TABLE` nunca foi consumida (não existe progressão), buffs são só texto (dano/AC não
leem `active_conditions`), party só schema, craft/shop/loot 100% LLM, poção inutilizável
em combate. Fases antigas renumeradas no ROADMAP (playtest 4→5, conteúdo 5→6, ... 10→11).

**Fases 2.6, 2.7 e 2.8 DONE** (detalhes no `CHANGELOG.md`; specs em `specs/`):
2.6 = LLM propõe eventos estruturados, motor valida/aplica (`world_validators` +
`event_processor`; combate gera `npc_killed` determinístico). 2.7 = rules engine
(`services/rule_engine.py`, cascata determinística com anti-loop, `world_rules.json` +
overlay `components.json` migration-safe). 2.8 = context builder (`build_context_pack`
ranqueia fatos por relevância+local+recência com orçamento por seção; estado vivo entra
ANTES da lore base; 4 agentes integrados: storyteller/npc/combat/campaign_manager).
Smoke LLM real das 3 fases pendente de quota.

**Próximo passo:** Fase 3 (clareza de campanha, specs 3.1–3.4 em `draft`) e depois
Fase 4 — Gameplay Core (cada fatia vira spec antes de implementar; ver ROADMAP § Fase 4).

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
uv run pytest                        # 211 testes offline verdes (test_real_llm precisa de chave)
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
