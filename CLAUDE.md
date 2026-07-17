# rpg-ia-master

RPG de texto com IA — motor LangGraph multi-agente com RAG híbrido e memória por sessão.
Stack: Python 3.13 · FastAPI · LangGraph · FAISS · Google Gemini · uv

> **AO RETOMAR:** leia `@ESTADO_ATUAL.md` primeiro — estado atual, como rodar,
> bugs já corrigidos, limitações conhecidas e convenção crítica de resiliência.
> Visão de produto e próximos passos: `ROADMAP.md` (Fase 0 entregue; Fases 1–3 mapeadas).

---

## Comandos essenciais

> Use sempre `uv run` (o `python` global deste Windows é 3.14 — errado; o projeto
> exige 3.13). `uv` fica fora do PATH: `$env:Path="$env:APPDATA\Python\Python314\Scripts;$env:Path"`.
> Detalhes do ambiente: `ESTADO_ATUAL.md`.

```bash
uv sync                                   # cria .venv (Python 3.13)
uv run python game_engine.py              # CLI — jogar no terminal
uv run uvicorn api:app --port 8000        # API REST + frontend web (http://localhost:8000)
uv run python rag.py                      # re-indexar lore (data/codex/) + regras (data/rules.txt)
uv run pytest                             # suíte offline (força MockLLM, não precisa de chave)
bash scripts/smoke_api.sh [porta]         # smoke da API (health, /data/map, /game/new, /game/action)
uv run python -m playtest run --all --turns 50   # Fase 5: harness — 12 perfis (MockLLM, offline)
uv run python -m playtest report <run_id>        # relatório agregado (per-perfil/violações/custo)
uv run python -m playtest transcript <run_id>    # transcrito ação→narração por turno (julgar prompt)
```

**Playtest agêntico (Fase 5):** `playtest/` roda campanhas longas sobre o MESMO
grafo (`app.invoke`) com 12 perfis determinísticos (`runner.py`/`profiles.py`);
invariantes de estado por turno (`invariants.py` — HP/ouro/unique/NPC morto/
fação/relógio/segredo/game_over); telemetria JSONL+summary por campanha
(`telemetry.py`) + relatório Markdown (`report.py`) + transcrito por turno.
Saves isolados em `saves_playtest/`, runs em `playtest_runs/` (ambos gitignored).
`--real` (opt-in, consciente de custo) mede provider/modelo/custo via
`set_llm_telemetry_hook`, com tetos `--max-requests`/`--max-cost`. **Suíte de
playtest REAL:** `uv run pytest -m llm_playtest -v -s` — os 4 perfis VITAIS
(explorador/combate/diplomatico/secret_rusher) jogam 30 turnos no LLM de verdade
(ROUTES; `RPG_PLAYTEST_TURNS` encurta) e assertam zero erro + zero violação
`error` + `mock=False`. FORA do `pytest` default (`addopts -m "not
llm_playtest"`), como os contratos da Fase 11.

**Skills do projeto:** `/qa` = pytest token-lean durante iteração (só falhas);
`/wrap-up` = ritual de fim de tarefa (suíte completa + docs + commit).

**Autoria de conteúdo (Fase 7.2):** adicionar/curar entidade do mundo segue
`docs/AUTORIA.md` — templates em `docs/templates/codex/`, lint via
`uv run python scripts/validate_content.py`, curadoria migration-safe em
`data/codex_overrides.yaml` + arquivos `curated: true`.

**Modo simulado / chave:** sem `GOOGLE_API_KEY`, `get_llm()` devolve um `MockLLM`
([mock_llm.py](mock_llm.py)) — jogo jogável e testável sem rede. Flags: `RPG_FORCE_MOCK=1`
força o mock mesmo com chave (usado pela suíte); `RPG_NO_MOCK=1` força o `FallbackLLM` de erro.

**Frontend (Fase 1):** o cliente principal é um app **React + Vite + TypeScript** em `web/`
(tom dark medieval/The Witcher; `motion` p/ animações). A API serve `web/dist` na raiz quando
existe, senão cai no `frontend/` vanilla (legado). Build e dev:

```bash
cd web && npm install          # uma vez (Node ≥20)
npm run build                  # gera web/dist (servido por uvicorn na raiz)
npm run dev                    # dev server :5173 com proxy p/ a API :8000
```

---

## Arquitetura — grafo LangGraph

```
START
  ↓
campaign_manager      # planeja arcos narrativos (3–5 beats) com RAG de lore
  ↓
dm_router             # classifica intenção: STORY | COMBAT | NPC | LOOT
  ↓ (condicional)
storyteller           → archivist → END
combat_agent          → archivist → END
npc_actor             → archivist → END
loot_agent            → archivist → END
```

**archivist** roda em todo fim de turno: atualiza `narrative_summary` (curto prazo) e persiste fatos no FAISS da sessão (longo prazo).

---

## LLM — três tiers + roteamento multi-provider

`llm_setup.py` expõe `get_llm(temperature, tier)`. Sempre usar essa função — nunca instanciar provider direto.
Cada tier é uma **lista ordenada de candidatos `(provider, modelo)`** (`ROUTES`): o `get_llm`
devolve um `RoutedLLM` que tenta o preferido e cai pro próximo em qualquer falha
(429/500/timeout/dep faltando/sem key). Esgotou todos → `AIMessage` de erro (NUNCA levanta) —
o guard de `FallbackLLM` (`isinstance`/`try`) segue **obrigatório**.

| Tier | Uso | Candidatos default `ROUTES` (ordem = preferência → fallback) |
|---|---|---|
| `ModelTier.CLASSIFY` | router, combat (parse/spawn), loot (TradeIntent), librarian — classificação/parse temp 0 | **DeepSeek** → Groq `openai/gpt-oss-20b` → Gemini flash-lite |
| `ModelTier.FAST` | storyteller, combat (narração), npc_actor, loot (narração), world_simulator, bestiary | **DeepSeek** → MiniMax → Qwen → Groq llama-3.3-70b → Gemini flash |
| `ModelTier.SMART` | archivist, campaign_manager, character_creator | **DeepSeek** → Groq gpt-oss-120b → Anthropic → Gemini pro |

> **DeepSeek é o primário em TODOS os tiers** (2026-07-16, pós-playtest longo).
> Groq free segue de fallback vivo; sem key da DeepSeek o jogo continua rodando.

> **Structured output entre providers (achados do smoke real 2026-07-06):**
> - **Groq usa strict json_schema** e rejeita schema com dict aberto
>   (`StoryUpdate.payload`). Solução: `RoutedLLM._apply` injeta
>   **`method="function_calling"`** (tool calling) p/ todo provider OpenAI-compat
>   (`_OPENAI_COMPAT_PROVIDERS`) — com isso o Groq parseia QUALQUER schema. Logo há
>   um candidato **Groq grátis em todos os tiers**: o jogo roda 100% no free tier
>   do Groq (`llama-3.3-70b`/`gpt-oss-20b`/`gpt-oss-120b`) sem provider pago.
> - **Anthropic (Claude 5):** não aceita `temperature` (omitido no
>   `_build_anthropic`) nem **prefill** (falha se o prompt termina em `AIMessage`,
>   ex.: archivist → cai no fallback). OK em nós que terminam com humano.

Trocar modelo/provider = só mudar `ROUTES` (ou `RPG_ROUTES=<json>` sem deploy). Sem tocar nos agentes.

**Overrides (`llm_setup.get_llm`):** `RPG_FORCE_MOCK=1` → MockLLM (suíte); `LLM_PROVIDER=gemini|
ollama|openai` força TODOS os tiers a um provider único (ignora `ROUTES` — use p/ jogo só-Gemini
ou 100% local); sem key nenhuma → MockLLM (zero-config) ou `FallbackLLM` (`RPG_NO_MOCK`);
default → `ROUTES`. Telemetria: `set_llm_telemetry_hook(fn)` recebe `(provider, model, tier,
latency_ms, fell_back)` por invoke (consumido pela Fase 5.3). Cada provider lê sua env key
(`GROQ_API_KEY`/`QWEN_API_KEY`/`MINIMAX_API_KEY`/`DEEPSEEK_API_KEY`/`ANTHROPIC_API_KEY`/
`GOOGLE_API_KEY`; GLM/Kimi seguem no registro p/ uso via `RPG_ROUTES` — ver `.env.example`).

`max_retries=0` (fail-fast) por candidato: `429` de quota não é transitório; o fallback é trocar
de PROVIDER, não fazer retry no mesmo. Anthropic exige `uv sync --extra anthropic` (ausência da
dep = candidato pulado). Gemini free tier = **20 req/dia por modelo** — ver `ESTADO_ATUAL.md`.

---

## RAG — sistema híbrido

`rag.py` — `query_rag(query, index_name, game_id)` busca em dois índices:

1. **Global** (`faiss_lore_index/`, `faiss_rules_index/`) — imutável durante o jogo; lore
   vem do **Codex** (`data/codex/**/*.md` via `services/codex_loader.ingest_codex`, metadados
   `id/type/tags/visibility` por chunk; Fase 2.5), regras de `data/rules.txt`.
   `query_rag(..., max_visibility="public")` filtra chunks `hidden`/`secret` do narrador
2. **Sessão** (`data/saves_memory/{game_id}/`) — dinâmico, criado pelo archivist via `add_memory_to_session()`

Embeddings: `models/text-embedding-004` (Google). Chunks: 500 tokens, overlap 50.

Para re-indexar lore global: `python rag.py` (ou chamar `ingest_file()` diretamente).

---

## Persistência

- Saves em `saves/{game_id}.json` — serializa mensagens LangChain para dicts simples
- `persistence.py` — `save_game_state()` / `load_game_state()`
- Memória vetorial por sessão em `data/saves_memory/{game_id}/`
- `load_game_state()` sem argumento carrega o save mais recente (por `ctime`)

---

## Estado do jogo (GameState)

Definido em `state.py` como TypedDict. Campos principais:

```
game_id             str          — UUID da sessão, isola memória RAG
narrative_summary   str          — resumo comprimido (short-term memory)
archivist_last_run  int          — turno da última execução do arquivista
chronicle           List[ChronicleChapter] — capítulos (arc_title): milestones do event_log + prosa (persistido)
player              PlayerStats  — name, class_name, race, hp/max_hp, mana/max_mana, stamina/max_stamina,
                                   gold, level, xp, attributes (chaves curtas str/dex/...), inventory,
                                   known_abilities, defense, attack_bonus, active_conditions, ability_cooldowns
world               WorldState   — current_location(+_id), visited[] (fog of war), world_clock{day,period},
                                   time_of_day, turn_count, danger_level, weather, quest_plan
messages            List[BaseMessage]  — histórico LangChain (operator.add)
campaign_plan       CampaignPlan — location, beats[{description,status}], climax, current_step, last_planned_turn, arc_title
needs_replan        bool         — força replanejamento no próximo campaign_manager
enemies             List[EnemyStats]
npcs                Dict[str, Dict]
active_npc_name     Optional[str]   — alvo da rota NPC (setado pelo router)
combat              Optional[Dict]  — {round, active, order[]} do combate determinístico
combat_target       Optional[str]
loot_source         Optional[str]   — "TREASURE" | "SHOP" | "CRAFT"
```

`state.py` é a fonte da verdade do schema. Atributos usam **chaves curtas** (`str/dex/con/int/wis/cha`)
em runtime; `combat_mechanics.normalize_attr` converte nomes longos/PT que o LLM possa devolver.

---

## Estrutura de pastas

```
# --- raiz: núcleo do motor ---
main.py               # grafo LangGraph (build_game_graph, app) + setup UTF-8
state.py              # GameState e TypedDicts — FONTE DA VERDADE do schema
llm_setup.py          # get_llm(tier) + MockLLM/FallbackLLM (NUNCA instanciar Gemini direto)
mock_llm.py           # MockLLM — dados fictícios por agente (modo simulado sem chave)
rag.py                # query_rag / add_memory_to_session / ingest_file (FAISS + embeddings)
persistence.py        # save_game_state / load_game_state (serializa mensagens)
gamedata.py           # carrega data/*.json; ARTIFACTS_DB, CLASSES, ABILITIES, XP_TABLE, helpers de world_map
combat_mechanics.py   # NÚCLEO DETERMINÍSTICO do combate (iniciativa, DoT, custos, cooldowns, normalize_attr)
world_utils.py        # Fase 0: relógio, viagem (fog of war), descanso — determinístico, sem LLM
character_creator.py  # cria ficha do player (IA + JSON oficial); guard de fallback
game_engine.py        # CLI interativo (wizard + loop)
api.py                # FastAPI REST (/game/new, /game/action, /game/state, /data/map) + serve web/dist|frontend/
web/                  # FRONTEND PRINCIPAL — React+Vite+TS (src/, build em web/dist; tom Witcher; motion)
frontend/             # web vanilla legado (zero build) — fallback se web/dist não existir
# --- agentes (nós do grafo) ---
agents/
  router.py           # dm_router_node — classifica intenção + seta NPC/loot/combat
  storyteller.py      # storyteller_node — narração + viagem/descanso + avanço de beat
  combat.py           # combat_node — IA identifica ação/inimigos + narra; resolve via combat_mechanics
  npc.py              # npc_actor_node + generate_new_npc()
  loot.py             # loot_node — loot/craft/shop/treasure
  archivist.py        # archive_node — memória curto (resumo) / longo prazo (RAG)
  campaign_manager.py # campaign_manager_node — planejamento de arcos + incrementa turn_count
  bestiary.py         # generate_new_enemy + cache de bestiário
  class_themes.py     # temas/gating narrativo por classe (allowed/forbidden)
  librarian.py        # find_existing_entity — dedupe semântico de entidades
services/             # serviços determinísticos (Fases 2.5–3.1)
  graph_resolver.py   # consultas ao grafo de mundo (base − disabled + dynamic, visibility)
  codex_loader.py     # parse/split/ingest do Codex no FAISS (metadados por chunk)
  world_validators.py # valida propostas de evento do LLM contra grafo/projection (2.6)
  event_processor.py  # proposta válida → GameEvent → projection + milestones da crônica (2.6/3.1)
  rule_engine.py      # cascata sistêmica determinística pós-evento, anti-loop (2.7)
  context_builder.py  # build_context_pack — contexto ranqueado com orçamento de tokens (2.8)
  npc_layers.py       # NPCs 3 camadas: traits seeded, gate in_scene, view da API (spec npcs-3-camadas)
  chronicle.py        # crônica por capítulos: templates de milestone + append/open puros (3.1)
scripts/
  migrate_lore_nova.py # gera data/codex/ (inclui timeline/) + entities.json de lore_nova/ (SOBRESCREVE curadoria)
lore_nova/            # FONTE do lore Valoria (11 .txt, inclui timeline_completa.txt) — editar aqui e re-rodar o script
data/
  codex/              # Codex Valoria gerado — .md com frontmatter id/type/tags/visibility
                      #   timeline/ = história do mundo por era (reveals de secrets.txt ficam visibility:hidden)
  graph/              # entities.json (gerado) + edges.json/relation_types.json (curados à mão)
  rules.txt           # regras indexadas para FAISS
  world_map.json      # grafo de locais — mapa de Valoria, 30 nós (Fase 2.5b)
  bestiary.json       # criaturas
  classes.json        # classes jogáveis (base_stats, passive)
  class_themes.json   # allowed/forbidden por classe (gating)
  origins.json        # raças e regiões
  artifacts.json      # artefatos
  player_abilities.json
  npc_database.json   # cache de NPCs gerados (runtime)
specs/
  TEMPLATE.md         # template de spec (desenvolvimento spec-driven — ver seção acima)
  fase-2.5*.md ...    # specs das fases 2.5–2.8 (Mundo Vivo v1)
tests/
  test_mvp.py         # suíte offline do MVP (dados, persistência, router, combate, beats)
  test_fase0.py       # suíte da Fase 0 (mapa, relógio, viagem, descanso, gating, e2e)
  test_fase25.py      # suíte da Fase 2.5 (event_log/projection, grafo, resolver, codex)
  conftest.py         # força RPG_FORCE_MOCK=1 (suíte determinística e offline)
conftest.py           # (raiz) injeta pythonpath
faiss_lore_index/     # índice FAISS gerado — não editar à mão
faiss_rules_index/    # índice FAISS gerado — não editar à mão
saves/                # saves JSON por game_id
data/saves_memory/    # índices FAISS por sessão (gerado em runtime)
```

---

## Desenvolvimento spec-driven

Toda feature/fase nova segue o fluxo de `specs/`:

1. **Spec antes de código.** Feature nova começa como `specs/<nome>.md` (copiar
   `specs/TEMPLATE.md`), status `draft`. Nada de implementar direto do ROADMAP.
2. **Aprovação.** O usuário revisa; spec vira `approved`. Só então implementar.
3. **Implementação segue o plano da spec** (etapas ordenadas, testes primeiro).
   Desvio necessário durante a implementação? Atualizar a spec no mesmo commit.
4. **Conclusão:** critérios de aceite todos marcados + `uv run pytest` verde +
   smoke test real da spec executado → status `done` + atualizar ROADMAP/ESTADO_ATUAL.
5. **ROADMAP.md é resumo + link;** o detalhe técnico mora SÓ na spec (fonte única).

Specs: 2.5 `done`; 2.5b (dados mecânicos Valoria) `done` (smoke real 2026-07-14); 2.6 (structured events) `done`;
2.7 (rules engine) `done`; 2.8 (context builder) `done`; 3.1–3.4 `done` — **Fase 3 completa**;
4.1–4.6 + 4.1b `done` — **Fase 4 completa**; 6.1–6.5 `done` — **Fase 6 completa**;
7.1 (validadores+CI) · 7.2 (autoria/curadoria) · 7.3 (segredos de NPC) `done` —
**Fase 7 completa** (lint `services/content_validator.py` + CLI
`scripts/validate_content.py`; gate no `rag.py`; autoria em `docs/AUTORIA.md`).
2026-07-06: fase 10 fatia local (hardening: `save_path` UUID, `schema_version`+
migrations, CORS/rate-limit/log) · fase 11 (contratos `-m llm_contract`, 9 verdes
no Gemini real) · mapa (interiores + `travel_times`) · NPCs 3 camadas
(`services/npc_layers.py` + `data/traits.json`) — todas `done`. Roteamento
multi-provider `done`. **Fase 5 (5.1 harness + 5.2 invariantes + 5.3 telemetria)
`done`** — `playtest/`. 2026-07-13: **ciclo de produto `done`** —
balanceamento-early-game ("O Saque" + tuning nível 1 + replan por região) ·
streaming-turno-sse (`POST /game/action/stream` + custo real no log `rpg.turn`) ·
polish-sessao (`GET /game/saves` + DELETE + chips mecânicos de combate +
export/busca da crônica + onboarding + mobile 390px).
2026-07-16: **8 specs `draft`** do playtest longo real (3×100 turnos, análise em
`docs/playtest-longrun-2026-07-14.md`): playtest-stop-gameover ·
combate-lifecycle · pos-saque-recuperacao · npc-fallback-sem-alvo ·
beats-visibilidade-ptbr · encontros-dedupe · polish-prosa · embeddings-provider
— aguardando aprovação. 2026-07-17: **criação imersiva `done`** —
onboarding-valoria (wizard 5 passos + `data/onboarding.json` +
`GET /data/onboarding`) · inicio-personalizado (`POST /game/prologue` + seed de
arco pessoal/NPCs/cena no `/game/new`; limites de schema viraram truncagem em
Python + `StartScenarioIn` estrito na borda). **792 testes offline.** Próxima:
aprovar/implementar as 8 specs do playtest; Fase 8 (arte) vs 10b (público)
segue adiada.

---

## Convenções de código

- Python 3.13+ com type hints em tudo
- Pydantic v2 para structured output do LLM (`llm.with_structured_output(Model)`)
- Async não usado — LangGraph roda síncrono neste projeto
- `httpx` se precisar HTTP externo (nunca `requests`)
- Prefixo `test_` em todos os arquivos e funções de teste
- Cada agente retorna dict parcial do GameState — nunca retornar o estado completo
- **Guard de resiliência (CRÍTICO):** `FallbackLLM.with_structured_output(X).invoke()` devolve um
  `AIMessage`, **não** uma instância de `X`. Acessar `resultado.campo` fora de `try/except` ou sem
  `isinstance(resultado, X)` estoura. Todo nó novo com structured output precisa desse guard.
- **Mecânica é Python, não LLM.** A IA só identifica/narra; números (combate, dados, economia)
  resolvem em código determinístico (`combat_mechanics.py`, `world_utils.py`).
  Não confiar em sinal/valor vindo do LLM sem validar (ex.: sinal do ouro em `loot.py`).
- **MockLLM esconde bugs de mapeamento:** ele devolve instâncias Pydantic válidas, então acesso a
  campo nunca quebra no mock. Bug de nome/tipo de campo só aparece no Gemini real. Validar caminhos
  novos de structured output com a chave real (ver harness/quota em `ESTADO_ATUAL.md`).
- **Ao FINALIZAR qualquer tarefa (SEMPRE, sem exceção):**
  1. Rodar `uv run pytest` e garantir verde antes de declarar a tarefa concluída — nunca afirmar
     que funcionou sem a saída dos testes.
  2. Atualizar **`ESTADO_ATUAL.md`** (TL;DR, contagem de testes, o que funciona, correções) **e**
     **`ROADMAP.md`** (marcar item entregue/pendência) refletindo a mudança. Os dois, sempre.

---

## O que NÃO fazer

- Não instanciar `ChatGoogleGenerativeAI` direto — usar sempre `get_llm()`
- Não ler FAISS com `allow_dangerous_deserialization=False` — vai quebrar load
- Não commitar `.env` ou `saves/` com dados reais
- Não adicionar agentes ao grafo sem conectar ao `archivist` no final
- Não usar `requests` — projeto usa `httpx` se necessário
- Não editar os arquivos `faiss_*_index/` à mão — sempre re-gerar via `rag.py`
- **Não fazer `Read` inteiro de arquivos de lore** (`lore_nova/*.txt`, `data/codex/**`) — têm
  30–100KB cada e estouram o contexto. Usar `Grep` primeiro, `Read` com offset/limit no trecho,
  ou delegar a um subagent (Explore) e trazer só a conclusão. Vale também para `data/*.json`
  grandes (bestiary, npc_database): Grep pelo id/campo, não Read completo.

> **REFERENCE.md** (decisões arquiteturais e seus porquês) NÃO é carregado automaticamente —
> ler sob demanda quando a tarefa envolver decisão estrutural (novo agente, troca de provider,
> persistência, RAG). **CHANGELOG.md** = histórico de sessões antigas, também sob demanda.

@ESTADO_ATUAL.md
