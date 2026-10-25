# SPEC-317 — Latência: CLASSIFY mais rápido, contexto em paralelo, caches e ordem do prompt

> **Status:** `approved` (dono 25/10: "boa, aprovo" — decisões nos padrões recomendados em negrito)
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-25
> **Depende de:** nenhuma (independente da SPEC-316); insumos `done`: SPEC-032 (ROUTES), SPEC-143 (NO-GO do fan-out), SPEC-214 (NO-GO do cache de cena), SPEC-217/229 (pré-classificação determinística)
> **Desbloqueia:** reavaliação de `RPG_TURN_EXECUTION=concurrent` (SPEC-143) sem contenção de provider
> **Origem:** investigação de latência 2026-10-25 (oportunidades #3, #4, #7, #10)
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_REQUIRED:** `true` (roteamento toca eval do router — só produto, nunca dataset)
> **EVAL_AUTHORING_REQUIRED:** `false` — rodar `evals compare` nos datasets existentes; nenhum expected/dataset editado

---

## 1. Contexto & Objetivo

Fora do narrador e do arquivista, ~2 s por turno vão para trabalho barato que está em série ou repetido:

- **Router CLASSIFY no DeepSeek: 1 530 ms p50 / 1 689 p95** quando não há fast path
  (`playtest_runs/20261023-103617-864024/report.md:44`), para devolver ~30 tokens. Groq `openai/gpt-oss-20b`
  já é o 2º candidato do tier (`llm_setup.py:346-350`) e funciona com `function_calling`. Além disso, a
  pré-classificação já calcula `addressed_in_scene` (`services/interlocutor.py:409-432`, `:496`) mas só o usa
  para suprimir o teste de meta — endereçar um NPC presente ainda paga o CLASSIFY. Em loot, `TradeIntent`
  roda mesmo quando o regex já decidiu SHOP/CRAFT (`agents/loot.py:81-106`). O router manda `messages[-3:]`
  (`router.py:420-423`), com a narração anterior inteira (~600 tokens) para classificar uma frase.
- **Contexto/RAG em série depois do router**: `build_context_pack(purpose="story")` (`storyteller.py:1444`)
  depende só de local/estado/input — podia começar junto com o router. SPEC-214 mediu context p95 762 ms,
  3,9 % do TTLT (teto ~0,4 s p50): ganho pequeno, mas gratuito.
- **Sem cache de índice**: `FAISS.load_local` a cada consulta (`rag.py:836,1023,1069,1104,1191,1354,1514,1605`);
  `faiss_lore_index/` tem 9,9 MB e é imutável durante o jogo. `npc_database.json` é lido do disco sem cache
  (`npc.py:315-355`). Em combate, `_prepare_scene` e a narração montam pack com lore (embedding Jina +
  FAISS) e usam só `world_state_block` (`combat.py:479-481`, `:1492-1494`).
- **Cache de prefixo nunca bate**: os prompts começam pelo cabeçalho dinâmico (`storyteller.py:1602-1612`:
  Local/Momento/NPCs/Objetivo; `npc.py:1181`; router `:395-397`) e as instruções estáticas (~2 k chars) vêm
  depois. O DeepSeek cacheia prefixos em blocos de 64 tokens; `llm_setup.py:264-269` já extrai
  `prompt_cache_hit_tokens`, e `cache_hit_ratio` sai `null` nos registros (`docs/spec200/README.md:63`).
- **Cold start Vercel 6–10 s** (import de langgraph/langchain; bundle 314,5 MB; `docs/spec192/README.md:26-30,95-97`)
  explica o ack p95 de 19,3 s no staging (`docs/spec213/staging-measure-2026-10-18.md`).

Alvo somado: −1,0 a −1,8 s p50 em STORY/NPC/LOOT; ack p95 < 3 s; custo por turno menor (cache + menos
embeddings). Mecânica e evals intocados; só o produto muda.

## 2. Requisitos

**A. CLASSIFY**

- **R1 — A/B de provider do tier CLASSIFY sem código:** medir no staging `RPG_ROUTES` com Groq
  `openai/gpt-oss-20b` em 1º no CLASSIFY (DeepSeek 2º) vs default, 30 turnos cada, usando `llm_by_tier` da
  linha `rpg.turn`. Promover a ordem em `ROUTES` só se latência CLASSIFY p50 cair ≥ 40 % **e** a concordância de
  rota com o DeepSeek nos mesmos inputs for ≥ 95 % (replay offline do dataset do router existente, sem editá-lo).
- **R2 — Rota NPC determinística:** `interlocutor.pre_classify` devolve `NPC` (target = NPC endereçado) quando
  `addressed_in_scene` acha vocativo/endereçamento inequívoco a um NPC **presente na cena**, o texto não casa
  com verbos de combate/saque (`_EXPLICIT_*` do router) e não há combate ativo. `social_approach` default
  `conversar`. Flag `RPG_ROUTER_DETERMINISTIC_NPC=off|shadow|on`; em `shadow` roda o CLASSIFY e loga
  `router.deterministic_shadow {agree: bool}`. Default **`shadow`**; `on` após concordância ≥ 97 % em 200 decisões.
- **R3 — Loot sem CLASSIFY redundante:** quando o regex já deu SHOP/CRAFT e o `item_ref` resolve contra o
  catálogo do mercado/receitas por nome normalizado (único), `TradeIntent` não é chamado. Ambíguo ⇒ CLASSIFY
  como hoje.
- **R4 — Entrada do router enxuta:** `messages[-3:]` vira [última fala do jogador + até 400 chars do fim da
  narração anterior + fala anterior do jogador]. Decisão idêntica nos testes do router existentes.

**B. Contexto em paralelo e caches**

- **R5 — Vetor de consulta pré-computado:** `turn_prepare` dispara em thread (`ThreadPoolExecutor(1)`) o
  `prepare_shared_query_vector` (`rag.py:926`) para a consulta de story (`compose_lore_query`), guardado num
  cache por turno `(game_id, turn_count, query)` em `services/context_sources.py`; `embed_context_query`
  reaproveita quando a consulta é igual. Falha/timeout ⇒ caminho atual. Limites por processo da SPEC-143 §2.4
  respeitados.
- **R6 — Cache de índice em processo:** `rag._load_index(path)` com cache `{path: (mtime(index.faiss),
  FAISS)}`; invalida por mtime (escrita de sessão/NPC atualiza mtime). Lore e regras ficam residentes; índices
  de sessão também, invalidados a cada `_save_index`. Flag `RPG_INDEX_CACHE=on|off`, default **`on`**.
  Testes xdist seguem isolados (paths em `tmp_path`).
- **R7 — Catálogos em cache:** `npc_database.json` e `bestiary.json` lidos uma vez por mtime.
- **R8 — Combate sem retrieval inútil:** `build_context_pack(..., include_lore=False)` quando o consumidor usa
  só `world_state_block` (`combat.py:479`, `:1492`); `_prepare_scene` só monta pack dentro do ramo
  `_wants_prepared_scene`. Zero chamadas de embedding por rodada de combate comum.

**C. Ordem do prompt**

- **R9 — Estático primeiro:** storyteller, npc e router passam a ter o bloco de instruções/regras (texto
  constante por campanha) **no início** do `SystemMessage` e o estado (Local/Momento/NPCs/EVENTOS/blocos
  dinâmicos) no fim. Conteúdo idêntico (só ordem); flag `RPG_PROMPT_STATIC_FIRST=on|off`, default **`off`**
  até R10.
- **R10 — Medir cache:** `rpg.turn.cache_hit_ratio` não nulo com DeepSeek; promover para `on` se
  `cache_hit_ratio` p50 ≥ 0,3 e `evals compare` dos datasets de grounding/regressão sem piora nos hard gates.

**D. Vercel**

- **R11 — Lazy import:** SDKs de provider (`langchain_anthropic`, `langchain_google_genai`, `ollama`),
  `PIL`, `faiss` só importados dentro dos builders/funções que os usam; `api.py` não importa módulos de arte/STT
  no topo. Meta: tempo de import de `vercel_app` −30 % (medido por `python -X importtime`).
- **R12 — `excludeFiles` e warm-up:** `vercel.json` exclui `lore_nova/**`, `data/codex/**` se o índice FAISS já
  cobre (confirmar que `codex_loader` não lê em runtime; senão manter), `evals/**` inteiro, `handoffs/**`,
  `project_index/**`; `/staging-deploy` faz 1 `GET /health` + 1 turno sintético após o deploy.

### Fora de escopo

- Entrega antecipada/stream de tokens (316/319). Tirar trabalho do nó narrador (318). Mudar `ROUTES` de FAST/SMART.
- Fan-out router ∥ planner (`RPG_TURN_EXECUTION=concurrent`) — reavaliar em spec própria depois de R1.
- Editar datasets/expected do router (SPEC-178/180) ou de grounding; mudar conteúdo dos prompts.

## 3. Design técnico

- **Alterado** `services/interlocutor.py`: `pre_classify` ganha ramo R2 após `addressed_in_scene`
  (`:496`), devolvendo `_resolution(NPC, target_key, "addressed_in_scene", approach="conversar")`;
  `agents/router.py` consome como já faz com as outras resoluções (`:330-345`) e registra `route_source="deterministic_npc"`.
- **Alterado** `agents/loot.py:81-106`: `_resolve_item_ref(text, catalog) -> str | None` (puro) antes do CLASSIFY.
- **Alterado** `agents/router.py:420-423`: `_router_window(messages) -> list[BaseMessage]` (puro).
- **Novo** `services/context_prefetch.py`: `start_prefetch(state) -> None`, `take_vector(game_id, turn, query)
  -> list[float] | None`; cache `dict` com teto 8 entradas; thread daemon única.
- **Alterado** `rag.py`: `_load_index(path, embeddings) -> FAISS` central (substitui os 8 `load_local`), cache
  por mtime; `_save_index` invalida. `services/context_builder.build_context_pack(..., include_lore: bool = True)`.
- **Alterado** `agents/storyteller.py:1601-1678`, `agents/npc.py:1180-1247`, `agents/router.py:395-410`:
  montagem do system prompt em duas partes `static_block` + `dynamic_block`; ordem pela flag R9.
- **Alterado** `llm_setup.py:396-503`: imports dentro de `_build_*`; `api.py` topo: mover imports de arte/STT
  para as funções.
- **Alterado** `vercel.json` (`excludeFiles`), skill `/staging-deploy` (warm-up).
- Sem schema novo; sem campo novo em `GameState`.

## 4. Plano passo a passo

### Etapa 1 — Roteamento determinístico e loot (A)
1. **Testes** (`tests/test_router_interlocutor.py`, estender): `test_vocative_to_present_npc_routes_npc_without_llm`
   (MockLLM com contador: 0 invocações); `test_vocative_with_attack_verb_goes_to_classify`;
   `test_absent_npc_name_goes_to_classify`; `test_shadow_mode_calls_classify_and_logs_agreement`;
   `test_router_window_trims_previous_narration` (R4). `tests/test_loot_trade_intent.py`:
   `test_regex_shop_with_unique_catalog_item_skips_classify`; `test_ambiguous_item_calls_classify`.
2. **Implementação:** §3 (interlocutor, router, loot).
3. **Verificação:** `uv run pytest tests/test_router_interlocutor.py tests/test_loot*.py tests/test_jev_router_port.py -n 2`
   e `python -m evals ... run --dataset <router dataset existente> --run-id spec317-router` + `compare`.

### Etapa 2 — Caches e prefetch (B)
1. **Testes** (`tests/test_rag_index_cache.py`): `test_load_index_hits_cache_same_mtime` (2 consultas = 1
   `load_local`, via monkeypatch contador); `test_save_invalidates_cache`; `test_cache_off_flag_loads_every_time`.
   `tests/test_context_prefetch.py`: `test_take_vector_returns_prefetched_for_same_query`;
   `test_prefetch_failure_falls_back_to_inline_embedding`; `test_embedding_called_once_per_turn` (contador no
   provider fake). `tests/test_combat_context.py`: `test_combat_round_makes_zero_embedding_calls`.
2. **Implementação:** `rag._load_index`, `context_prefetch`, `include_lore`, combate.

### Etapa 3 — Ordem do prompt (C)
1. **Testes** (`tests/test_prompt_order.py`): `test_static_first_keeps_same_token_set` (multiset de linhas
   não vazias igual nas duas ordens); `test_dynamic_header_is_last_when_flag_on`; `test_flag_off_byte_identical`.
2. **Implementação:** split static/dynamic nos 3 prompts.

### Etapa 4 — Vercel (D)
1. **Testes** (`tests/test_lazy_imports.py`): `importlib.import_module("api")` não carrega
   `langchain_anthropic`/`PIL` em `sys.modules`; `tests/test_vercel_config.py` valida `excludeFiles` JSON.
2. **Implementação:** lazy imports, `vercel.json`, warm-up na skill.

## 5. Critérios de aceite

- [ ] R1 medido no staging com tabela p50/p95 por tier e concordância; decisão registrada (promovido ou não).
- [ ] R2 em `shadow` ≥ 200 decisões com concordância ≥ 97 % antes de `on`; `evals compare` do router sem piora.
- [ ] R5–R8: embedding por turno STORY = 1; por rodada de combate = 0 (asserts com contador).
- [ ] R10: `cache_hit_ratio` registrado; promoção só com `evals compare` sem piora.
- [ ] Import de `vercel_app` −30 % (`-X importtime` antes/depois anexado); cold start medido (`scripts/staging/measure.py`).
- [ ] `uv run pytest` verde; nenhum `with_structured_output` novo; saves antigos carregam.

## 6. Smoke test com LLM real

Staging, DeepSeek + Groq, teto **US$ 0,20** total:
1. R1: `vercel_env.py` com `RPG_ROUTES` (CLASSIFY Groq-first) → `projection_measure.py --label classify_groq
   --turns 15` ×2; depois rollback e `--label classify_deepseek` ×2. Comparar `llm_by_tier.classify` p50/p95 e
   `route_next` por input (mesmo roteiro).
2. R9/R10: 15 turnos com `RPG_PROMPT_STATIC_FIRST=on`; conferir `cache_hit_ratio` > 0 na linha `rpg.turn`.
3. R11/R12: `scripts/staging/measure.py` para cold start/bundle antes e depois do deploy.
Alvos: CLASSIFY p50 ≤ 0,8 s; TTLT p50 −1 s vs baseline do dia; ack p95 ≤ 3 s em função morna.

## 7. Riscos & compatibilidade

- **Qualidade do roteamento (R1/R2):** classificador menor pode errar NPC×STORY; por isso `shadow` +
  concordância + `evals compare` (dataset do router não é editado). Kill switches independentes por item.
- **SPEC-143:** a contenção que derrubou o fan-out era SMART e CLASSIFY no mesmo provider; com CLASSIFY no Groq
  a hipótese muda — mas a promoção de `concurrent` fica para spec própria.
- **Cache de índice:** processo multi-worker (uvicorn) tem um cache por processo; mtime no OneDrive/Windows pode
  ter granularidade de 1–2 s — invalidação explícita em `_save_index` cobre o caso quente.
- **Prompt reordenado:** mesmo conteúdo, ordem diferente — modelos podem reagir; por isso `off` até R10.
- **MockLLM/FallbackLLM:** rotas determinísticas reduzem chamadas; guards existentes mantidos.
- **Regra de ouro / mecânica:** inalteradas (nenhum filtro de contexto muda; só ordem e cache).

## 8. Decisões do dono

- **D1 — CLASSIFY Groq-first:** **fazer o A/B no staging (R1) e promover em `ROUTES` se passar nos dois gates**
  (alternativa: só via `RPG_ROUTES` no staging — mantém a main em DeepSeek; aceitável se o dono preferir um só provider pago).
- **D2 — Rota NPC determinística:** **`shadow` por default; `on` após 200 decisões com ≥ 97 % de concordância**.
- **D3 — Ordem do prompt:** **`off` até medir `cache_hit_ratio` e rodar `evals compare`**; promover se ≥ 0,3.
- **D4 — Caches de índice/catálogo:** **`on` por default** (baixo risco, invalidação por mtime + save).
- **D5 — `excludeFiles` de `data/codex`:** **só se confirmado que o runtime não lê o codex fora do índice**.
