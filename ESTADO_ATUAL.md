# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Leia isto **primeiro** ao retomar o trabalho. Complementa `CLAUDE.md` (arquitetura).
> Decisões estruturais: `REFERENCE.md` (sob demanda). Histórico de sessões: `CHANGELOG.md`.
> Última atualização: 2026-07-02

---

## TL;DR — Em que pé está

**Fase 2.7 DONE — Rules engine sistêmica (cascata determinística, zero if por NPC).**
A morte de um líder/governante agora dispara consequência sistêmica: fação desestabiliza →
controle do local muda → rival ocupa. Genérico via componente `power_vacuum_trigger` + regras
declarativas (`world_rules.json`), executadas sem `eval` (paths + ops whitelisted). Roda no
`event_processor` logo após cada `apply_event`; derivados entram no `event_log` com
`source="rule_engine"`, cascata limitada a profundidade 2. Suíte **201 testes offline verdes**
(177 baseline + 24 da 2.7). Smoke offline: matar `npc_valerius` → `location_control_changed`
derivado, controller de nova_arcadia vira `mao_sombria`, stability +5 (ripple depth-2). Smoke
LLM real pendente de quota (fase é 100% determinística — MockLLM irrelevante aqui).

**Próximo passo:** Fase 2.8 (context builder com orçamento de tokens — `build_context_pack`).

Entregas da 2.7 (spec `specs/fase-2.7-rules-engine.md`):
- `services/rule_engine.py` — `resolve_path` seguro (só literais/`event.`/`target.`/
  `component:`; dunder + expressão arbitrária → `RuleActionError`), `check_conditions`,
  `execute_action` (ops: set_entity_state, adjust_faction_stability, disable_controls_edges,
  create_dynamic_edge, emit_event), `run_rules` (dona da cascata + anti-loop depth 2).
- `data/graph/world_rules.json` (5 regras) + `data/graph/components.json` (overlay
  `power_vacuum_trigger` em 22 líderes/governantes). Overlay é **migration-safe**
  (`migrate_lore_nova.py` sobrescreve entities.json com `components:{}`), mergeado por
  `graph_resolver.load_entities`.
- Modelo HÍBRIDO: estrutura (líder/controle/rival) DERIVADA dos edges (`leads`/`controls`/
  `enemy_of`/`operates_in`); componente só carrega delta/sucessor/override + é o discriminador.
- `event_processor.process_pending_events` chama `run_rules` após cada `apply_event`.

Entregas da 2.6 (spec `specs/fase-2.6-structured-events.md`):
- `services/structured_outputs.py` — `ProposedWorldEvent` / `WorldChangeProposal` (Pydantic).
- `services/world_validators.py` — `validate_proposal(dict, state)` → `ValidationResult(ok, reason)`;
  regras por tipo (npc_killed, secret_revealed, location_control_changed, quest_completed,
  faction_relation_changed) via `graph_resolver`; revalida do zero (dict malformado = rejeitado).
- `services/event_processor.py` — `process_pending_events` (valida→GameEvent→append→aplica→limpa fila)
  + `apply_event` puro (efeito direto na projection, SEM cascata — isso é a 2.7).
- `storyteller` propõe via `StoryUpdate.proposed_events` + bloco `<ENTIDADES_CANONICAS>` no prompt.
- `combat` gera `npc_killed` **determinístico** (`_kill_events`) p/ inimigo canônico — sem LLM.

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
uv run pytest                        # 177 testes offline verdes (test_real_llm precisa de chave)
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

| Bug | Local provável |
|---|---|
| Inventário: item narrado não entra no inventário | `agents/loot.py` ou `world_utils.add_to_inventory` |
| Capitalização estranha em itens | Grep `title()` / `capitalize()` nos agentes |
| NPC errado responde fala destinada a outro | `agents/router.py` — `active_npc_name` não filtra |
| Morte do player sem narrativa (só tela de morte) | Fluxo final de combate — adicionar death_narrative |

**Design:** campaign manager coloca plot twists com muita frequência — aumentar
intervalo de triggers de replan.

## Limitações conhecidas

- **Inventário inicial** usa nomes livres, não IDs — `ARTIFACTS_DB.get(item_id)` não acha
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
