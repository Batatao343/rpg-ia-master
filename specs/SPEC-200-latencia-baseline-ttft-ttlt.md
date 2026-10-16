# SPEC-200 — Baseline de latência percebida (ack, TTFMC, TTLT) e decomposição por fase

> **Status:** `draft`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** nenhuma · SPEC-116 `done`, SPEC-143 `done` NO-GO e SPEC-182 `done` são insumos. Recomendado (não bloqueia): medir após a SPEC-235 para não instrumentar o pending antigo (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-207, SPEC-212, SPEC-213, SPEC-214, SPEC-217 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 09
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` (contextvars entre thread SSE e worker, métricas Prometheus, endpoint novo)
> **EVAL_AUTHORING_REQUIRED:** `false` — o baseline é harness de medição, não evaluator/dataset protegido de `evals/`. Vira `true` somente se o dono quiser gate com limiar numérico em `evals/` (ver seção 8, P4).

Rótulos: **[F]** fato observado no source do HEAD `6b94f66` · **[D]** decisão de produto fechada · **[H]** hipótese técnica · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**Problema.** O jogador espera segundos sem sinal de vida e ninguém sabe medir "quanto tempo até o texto começar" nem onde o tempo vai. O pacote pede medir antes de otimizar (paralelismo, memória hierárquica, Jev). Hoje as medições existem espalhadas e uma delas engana.

**Fatos auditados.**

- **[F]** `api.py::_stream_turn` (≈L3402) roda `_execute_action` inteiro numa thread (`_worker`), drena `progress` em fila e só depois do `response` fatia `resp.message` em blocos de `_NARRATIVE_CHUNK = 80` chars, emitidos de uma vez como eventos `narrative`. Não há streaming de tokens do LLM: o primeiro `narrative` sai **depois** de grafo + archivist + persistência. O texto só existe após `archivist` porque `validate_narrative` roda dentro do archivist (hot path, [D] D5).
- **[F]** `rpg_sse_first_event_seconds` (`observability/metrics.py` L16, observada em `api.py` ≈L3410) é observada **antes** de `yield _sse("accepted", ...)`, com `stream_started` capturado na linha anterior: mede microssegundos, não o tempo até o primeiro byte, nem até conteúdo. Enganosa. Nenhum alerta/dashboard do repo a consome (grep: só `observability/metrics.py`, `api.py`, SPEC-106 e docs); `observability/alerts/local.yml` usa apenas `rpg_turn_duration_seconds_p95{simulated="true"}`.
- **[F]** `rpg_turn_duration_seconds` (`api.py` ≈L3275-3290) usa `route="/game/action"` fixo, inclusive para o turno executado via `/game/action/stream`; não separa transporte.
- **[F]** `_telemetry_hook` (`api.py` L646) e `_attempt_telemetry_hook` (L664) acumulam por turno em ContextVars (`_llm_turn_events`, `_llm_attempt_events`, `_embedding_attempt_events`) criados em `_run_turn_collected` (L3247-3249), isto é, **na thread do worker**. `LLMAttemptEvent` (`llm_setup.py` L97) traz provider/model/tier/attempt_index/latency_ms/fell_back/outcome/usage. A linha `rpg.turn` (`_log_turn`, L3206) leva latência total, rota, eventos e campos de `_llm_log_fields`.
- **[F]** `playtest/telemetry.py` e `playtest/runner.py` agregam `node_latency_ms` por nó (count/média/p50/p95/max) desde a SPEC-116, atribuindo o intervalo entre updates do `graph.stream` ao primeiro nó do chunk. Não há decomposição de contexto/RAG nem persistência, nem medição cliente.
- **[F]** `services/turn_execution.py::execute_graph` consome `graph.stream(..., stream_mode=['updates','values'])` e chama `progress(chunk)`; `main.py` define o grafo `turn_prepare → campaign_manager/dm_router (sequencial por default) → dispatch → {storyteller|combat_agent|npc_actor|loot_agent} → archivist → turn_finalizer → END`. `RPG_TURN_EXECUTION` default `sequential` (L76); fan-out foi NO-GO na SPEC-143 (piorou p95 no R29).
- **[F]** Cliente: `web/src/api.ts::sendActionStream` parseia `event:`/`data:` manualmente sobre `fetch`; `handleEvent` ignora `accepted`; `web/src/App.tsx` (≈L521) consome `onPhase/onRoute/onVisual/onChunk`. Não há `performance.mark` em `web/src` para turnos.
- **[F]** `mock_llm.py::MockLLM.invoke` devolve narrativa por `random.choice` sem latência; `_StructuredMock.invoke` é instantâneo. Logo toda medição MockLLM atual só mede overhead do grafo.
- **[F]** SPEC-182: `app.usage_events` + `normalize_attempts` registram tentativas, usage e custo (`cost_basis`) por operação; `rpg_llm_cost_usd_total{provider,tier,basis}` já existe.
- **[F]** `scripts/benchmark_turn_pipeline_real.py` é o precedente de benchmark real com teto (`max_requests`, `max_cost`); fica fora deste escopo exceto como padrão de CLI.

**Objetivo.** Entregar (a) definições canônicas e instrumentação servidor+cliente de ack, primeiro conteúdo narrativo significativo (TTFMC) e último conteúdo (TTLT) por `action_id`, com decomposição por fase; (b) correção honesta da métrica enganosa sem quebrar consumidores; (c) baseline **offline, repetível e determinístico** (MockLLM com latência injetada + jornadas fixas) com relatório p50/p95; (d) protocolo separado, opt-in e com teto para medir provider real. **Nenhuma otimização.**

**[D] D3:** esta spec só mede, incluindo o pseudo-streaming atual. Streaming real de tokens fica como hipótese a avaliar após o baseline, fora de escopo. **[D] D5:** `validate_narrative` permanece síncrona; a spec apenas a mede.

## 2. Requisitos

**Definições (normativas)**

- **ACK servidor** `ack_server_ms`: da entrada do handler (`game_action_stream`, antes de `load_game_state`) até a retomada do gerador logo após `yield accepted` (proxy de flush).
- **ACK UI** `ack_ui_ms`: no cliente, do clique/submit (`performance.now()` ao chamar `sendActionStream`) até o primeiro byte do corpo SSE lido. Evento `accepted` isolado e `: ping` NÃO contam como conteúdo.
- **TTFMC** (`time_to_first_meaningful_content`): do submit até o primeiro evento `narrative` com `chunk` não vazio após `strip()` (no cliente) / até o `yield` desse evento (no servidor). `phase`, `route`, `visual`, `accepted`, ping não contam.
- **TTFT** (nome do prompt 09): primeiro token **narrativo** percebido. Com `pseudo_streaming=true`, TTFT ≡ TTFMC por definição e o relatório imprime ambos com essa nota; se um dia houver streaming real de tokens (fora de escopo), TTFT passa a ser o primeiro token narrativo e TTFMC o primeiro bloco com conteúdo significativo, sem renomear campos já gravados.
- **TTLT**: do submit até o evento `narrative` com `done: true` (último conteúdo visível); `state_ms` até o evento `state`.
- **Duração do turno**: do início de `_run_turn_collected` até o fim do commit (`rpg_turn_duration_seconds`, inalterada).
- **pseudo_streaming**: booleano fixo `true` enquanto `_stream_turn` fatiar mensagem pronta; todo relatório o declara. [H] Com o código atual TTFMC ≈ duração do turno + overhead de transporte e TTLT − TTFMC ≈ custo de drenar blocos (≈0).

**Requisitos**

- **R1** — `observability/latency.py` define `TurnTimeline` (dataclass thread-safe, relógio injetável `clock: Callable[[], float]`, default `time.monotonic`) com marcas `accepted`, `first_phase`, `ttfmc`, `ttlt`, `state` e acumulador de fases exclusivas (pilha: tempo de fase interna é subtraído da externa; sem dupla contagem).
- **R2** — Fases fechadas (enum `TurnPhase`): `router`, `context`, `narrator`, `archivist`, `persistence`, `other`. Mapeamento: nós `dm_router`/`campaign_manager` → `router`; `storyteller|combat_agent|npc_actor|loot_agent` → `narrator`; `archivist` → `archivist`; `build_context_pack`/RAG de contexto (chamada de `services/context_builder.py` dentro do nó) → `context` via `with timeline.phase(TurnPhase.CONTEXT)`; `resolve_turn_visual_state`…`_commit_turn` em `_run_turn_collected` → `persistence`; resto (`turn_prepare`, `action_guard`, `dispatch`, `turn_finalizer`, carga do save) → `other`. Invariante: `sum(phase_ms) == turn_total_ms ± 1 ms`.
- **R3** — Atribuição por nó reutiliza o intervalo entre updates do `progress` (mesmo critério da SPEC-116) **dentro da thread do worker**. Sob `RPG_TURN_EXECUTION != sequential` a atribuição é ambígua: o registro grava `execution_mode` e `attribution: "interval"`; o baseline oficial roda só `sequential`.
- **R4** — Sub-medida opcional `archivist_validate_ms` (tempo de `validate_narrative`/guard dentro do archivist) gravada como campo do registro, **não** como label de métrica (insumo da SPEC-213).
- **R5** — O registro por turno é gravado **aditivamente** na linha `rpg.turn` existente: `action_ref` (`pseudonym(action_id)`), `transport` (`stream`|`post`), `pseudo_streaming`, `ack_server_ms`, `ttfmc_server_ms`, `ttlt_server_ms` (nulos no POST), `phase_ms` (objeto com as 6 fases), `execution_mode`, `llm_attempts` (n), `llm_fallbacks` (n), `llm_failed_attempts` (n), `providers_used` (lista), `cost_usd` e `cost_basis` (soma via `normalize_attempts`, nunca estimativa silenciosa: `unavailable` quando o provider não devolve usage). Nenhum texto do jogador/narração, nenhum `game_id` cru. Campos existentes não mudam de nome nem tipo.
- **R6** — Métricas Prometheus novas (nomes e labels registrados em `LABELS`, cardinalidade fechada, sem ids): `rpg_sse_ack_seconds{route}`, `rpg_turn_phase_seconds{route,phase}`, `rpg_turn_first_content_seconds{route,source}`, `rpg_turn_last_content_seconds{route,source}` com `source ∈ {server,client}`.
- **R7** — Correção da métrica enganosa **sem quebra**: `rpg_sse_first_event_seconds` permanece registrada, com a semântica documentada ("enfileiramento do evento `accepted`, não latência percebida") e marcada `deprecated` em comentário e em `docs/spec200/README.md`; continua sendo observada para não criar buraco em séries. A observação honesta passa a ser `rpg_sse_ack_seconds` (R1/definição ACK servidor). Remoção da antiga só em spec posterior, após SPEC-212.
- **R8** — `rpg_turn_duration_seconds` ganha `route="/game/action/stream"` para turnos do stream (hoje `/game/action` fixo). Alerta `TurnP95High` e `local.test.yml` continuam válidos; o teste promtool existente permanece verde. (Ver P3 na seção 8 sobre o efeito de partição da série.)
- **R9** — Cliente: `web/src/lib/turnLatency.ts` cria marcas `performance.mark("rpg:turn:<action_id>:submit|ack|first_phase|ttfmc|ttlt|state")` e `performance.measure` correspondentes; `sendActionStream` passa a expor `onAck` e `onEvent` (todos os eventos incluindo `accepted`), sem alterar o contrato dos handlers atuais. Fallback POST registra `transport: "post"` com `ttfmc = ttlt = state`.
- **R10** — Reporte cliente→servidor: `POST /telemetry/client-latency` com corpo fechado `{action_id: uuid, transport, ack_ms, first_phase_ms, ttfmc_ms, ttlt_ms, state_ms, outcome}`; valores inteiros clampados a `[0, 600000]`; exige a mesma sessão/CSRF das demais mutações e o rate limit do middleware; não aceita `game_id` nem texto; responde 204. O servidor loga `evt:"client_latency"` com `action_ref` e observa as métricas `source=client`. Desligado por default (`RPG_CLIENT_LATENCY_REPORT=0`); o cliente só envia se `GET /health`/bootstrap sinalizar habilitado. Sem efeito em estado, saves ou saldo.
- **R11** — Baseline offline: `scripts/latency_baseline.py run --journeys all --reps N --seed S --profile <nome>` usa **MockLLM com latência injetada determinística** (R12) e jornadas fixas (R13), roda in-process (`TestClient`/ASGI, stream real) com relógio virtual e grava `latency_runs/<run_id>/{records.jsonl,summary.json}`; `report <run_id>` gera Markdown com p50/p95/max por jornada e por fase.
- **R12** — Injeção de latência: wrapper `LatencyInjectingLLM` (apenas em `playtest/`/`scripts/`, nunca no runtime de produção) aplicado em torno de `get_llm` com perfil `{tier: {base_ms, jitter_ms}}` e jitter por PRNG semeado `(seed, jornada, rep, chamada)`. Modo `virtual` avança o `FakeClock` sem `sleep` (testes, zero espera); modo `scaled-real` usa `sleep` real de `ms * escala` (smoke de browser). Perfis versionados: `flat-fast`, `typical` (CLASSIFY 300/FAST 2500/SMART 4000 ms, jitter ±20%), `slow-tail` (cauda longa para exercitar p95), `fallback-once` (1ª tentativa de cada tier falha e cai para o próximo candidato com latência própria).
- **R13** — Jornadas fixas e versionadas em `scripts/latency_journeys.py`, cada uma com save/fixture e entradas imutáveis: `J1_story_simple`, `J2_combat_start`, `J3_npc_dialogue`, `J4_loot_shop`, `J5_travel_replan`, `J6_first_turn_new_game`. Cada jornada declara nº de turnos, ação, rota esperada e tamanho de entrada (curto/médio/longo) para estratificar percentis.
- **R14** — Relatório obrigatório inclui cabeçalho de **fingerprint de ambiente** (`git_sha`, `mode=offline-virtual|offline-scaled|real`, perfil de latência, `RPG_TURN_EXECUTION`, versão Python, `pseudo_streaming`). O comando `compare` recusa comparar runs com fingerprints incompatíveis e exige flag explícita `--allow-env-mismatch`, que imprime a ressalva no topo.
- **R15** — Experimento com provider real **separado**: `scripts/latency_baseline.py run --real` só executa com `RPG_LATENCY_REAL_AUTHORIZED=1` **e** `--max-requests` **e** `--max-cost` explícitos (sem default); aborta ao tocar qualquer teto; reusa `set_llm_attempt_telemetry_hook`; não roda em CI nem em `uv run pytest`; resultado tem `mode=real` e nunca é misturado com offline no mesmo relatório.
- **R17** — Campos complementares exigidos pelo prompt 09, gravados aditivamente no mesmo registro `rpg.turn` (nunca como label Prometheus): `lock_wait_ms` (tempo esperando `_game_lock(game_id)` em `api.py` ≈L640 e, nos perfis hosted, a espera de lease/operação — a "fila" do turno); `llm_by_tier` (`{tier: {attempts, failed, fallbacks, latency_ms, cost_usd}}`); `llm_by_phase` (`{phase: attempts}`, atribuído pela fase corrente da `TurnTimeline` no momento do `_attempt_telemetry_hook`, isto é, custo/chamadas por agente); `cached_tokens` e `cache_hit_ratio` (soma de `usage.cached_tokens` já capturado por `llm_setup._usage_snapshot` ≈L138 — cache de prompt do provider; `null` se nenhum provider reportou); `input_chars` (tamanho da ação do jogador) e `input_size` (`short|medium|long`, limiares fixos documentados em `docs/spec200/README.md`) para estratificar p50/p95 por tamanho de entrada. Cache de RAG/embeddings não tem contador hoje: registrar `rag_cache: "not_instrumented"` em vez de inventar hit/miss.
- **R18** — Regra de decisão herdada do prompt 09 (vale para SPEC-214/217): nenhuma spec posterior pode aprovar **chamada LLM extra só para decidir qual memória consultar** sem demonstrar, com este baseline (mesmo fingerprint) em A/B, redução de busca/contexto **e** p95 de TTFMC não pior. Esta spec não implementa tal chamada.
- **R16** — Nenhuma mudança de comportamento: mesma ordem de nós, mesma quantidade de chamadas LLM, mesmas mensagens SSE (campos novos só em logs/métricas), mesmo estado final. Teste de equivalência compara estado final com/sem instrumentação.

### Fora de escopo

- Streaming real de tokens ([D] D3), qualquer otimização, paralelismo, cache, memória hierárquica, Jev, mover `validate_narrative`. Mudar thresholds/alertas de SLO (apenas medir; metas vêm após baseline).
- Persistir latência em tabela Postgres/`usage_events` (sem migration). Export de sessão (SPEC-207 consome esta spec).
- Medir mobile/Capacitor; medir rede real do usuário além do que `performance` do navegador expõe.
- Editar `evals/`, datasets ou baselines protegidos; editar SPEC-197/198.

## 3. Design técnico

**Arquivos novos**

- `observability/latency.py` — `TurnPhase`, `TurnTimeline`, `phase()` context manager (pilha por timeline), `FakeClock`, `summarize_phases()`. Puro, sem I/O.
- `scripts/latency_baseline.py` — CLI `run|report|compare`; `scripts/latency_journeys.py` — definição das jornadas.
- `playtest/latency_llm.py` — `LatencyInjectingLLM` + perfis (R12); reutiliza `llm_setup.get_llm` por composição.
- `web/src/lib/turnLatency.ts` — marcas/medidas e reporter opcional; `web/e2e/latency.spec.ts` — leitura de `performance.getEntriesByType('measure')` no Chromium.
- `tests/test_latency_timeline.py`, `tests/test_latency_metrics_compat.py`, `tests/test_latency_baseline_offline.py`, `tests/test_latency_client_endpoint.py`.
- `docs/spec200/README.md` — definições, fingerprint, relatório de evidência. Adicionar `latency_runs/` ao `.gitignore`.

**Arquivos alterados**

- `api.py` — criar `TurnTimeline` em `game_action_stream`/`game_action` (capturar o `t0` de entrada), passar ao worker por **closure/parâmetro** (não por ContextVar: `_stream_turn` gera na thread do servidor e o grafo roda em outra; ContextVars criados em `_run_turn_collected` continuam sendo o canal de eventos LLM). Marcar `accepted` após o `yield`, `ttfmc` no `yield` do primeiro `narrative` não vazio, `ttlt` no `done:true`, `state` no `yield` de `state`. `progress` (thread do worker) alimenta fases por intervalo. Envolver o trecho `resolve_turn_visual_state → _commit_turn` em `phase(PERSISTENCE)`. Estender `_log_turn` aditivamente. Novo endpoint R10.
- `observability/metrics.py` — registrar as 4 métricas novas em `LABELS`; manter `rpg_sse_first_event_seconds`.
- `services/context_builder.py` (apenas o ponto de entrada `build_context_pack`) e call sites de RAG de contexto nos agentes — envolver em `phase(CONTEXT)` via helper `current_timeline()` que devolve um no-op quando não há timeline (CLI/playtest sem API).
- `web/src/api.ts`, `web/src/App.tsx` — `onAck/onEvent`, chamada às marcas; sem mudança visual.
- `playtest/telemetry.py` — ler `phase_ms` quando presente (aditivo); relatório existente intacto.

**Contratos de dados**

Linha `rpg.turn` (exemplo, campos novos em negrito conceitual):

```json
{"evt":"turn","game_id_ref":"…","turn":12,"route":"storyteller","latency_ms":9120,
 "action_ref":"a1b2c3","transport":"stream","pseudo_streaming":true,
 "ack_server_ms":4,"ttfmc_server_ms":9190,"ttlt_server_ms":9191,
 "phase_ms":{"router":410,"context":380,"narrator":6100,"archivist":1900,"persistence":240,"other":90},
 "execution_mode":"sequential","llm_attempts":6,"llm_fallbacks":1,"llm_failed_attempts":1,
 "providers_used":["deepseek","groq"],"cost_usd":"0.00081","cost_basis":"usage"}
```

`records.jsonl` do baseline: o mesmo conteúdo + `journey`, `rep`, `seed`, `profile`, `input_size`, `mode`. `summary.json`: `{fingerprint, journeys:{J1:{n, ack:{p50,p95}, ttfmc:{…}, ttlt:{…}, total:{…}, phases:{router:{p50,p95,share},…}}}}`. Percentil: método nearest-rank reusando `playtest.telemetry._percentile` (inteiros em ms); com n < 20 o relatório imprime "p95 indicativo".

**State ownership.** Nenhum campo novo em `GameState`/save/projeção. `TurnTimeline` é efêmera, dono = request atual (handler cria, worker escreve fases, gerador escreve marcas de entrega); lock interno para as duas threads. Cliente: marcas vivem em `performance`; reporter envia no máximo 1 beacon por `action_id`.

**Degradação/fallback.** Falha ao registrar métrica/marca/log **nunca** quebra o turno (try/except estreito, como `_log_turn`); timeline ausente → helpers no-op; endpoint R10 desligado → 404/204 silencioso no cliente, que desiste após a primeira falha; sem `performance.measure` → no-op. Provider sem usage → `cost_basis="unavailable"`, nunca zero fabricado.

**Concorrência [H].** Risco central: `TurnTimeline` tocada por thread do gerador (marcas) e do worker (fases). Mitigação: `threading.Lock` por instância, relógio lido sob lock, `phase()` usa pilha local à thread do worker. Desconexão do consumidor: o worker termina o save (comportamento atual); a timeline registra `ttfmc/ttlt = null` e `outcome="client_gone"` sem exceção.

## 4. Plano passo a passo

### Etapa 1 — Núcleo de timeline e fases
1. **Testes** (`tests/test_latency_timeline.py`): `test_phases_exclusive_no_double_count` (fase `context` aninhada em `narrator` subtrai); `test_sum_phases_equals_total` com `FakeClock`; `test_noop_when_no_timeline`; `test_marks_thread_safe` (gerador e worker simulados); `test_client_gone_leaves_nulls`.
2. **Implementação:** `observability/latency.py`.
3. **Verificação:** `uv run pytest tests/test_latency_timeline.py`.

### Etapa 2 — Métricas e compatibilidade
1. **Testes** (`tests/test_latency_metrics_compat.py`): `test_old_sse_metric_still_registered_and_observed`; `test_ack_metric_measures_after_yield` (clock controlado: atraso injetado em `load_game_state` aparece em `rpg_sse_ack_seconds` e não na antiga); `test_labels_closed_for_new_metrics` (label extra levanta `ValueError`); `test_turn_duration_route_stream`; `test_promtool_alert_fixture_unchanged` (reexecuta `local.test.yml` se promtool disponível, senão pula com marca explícita).
2. **Implementação:** `metrics.py`, `api.py` (R6–R8).
3. **Verificação:** testes do arquivo + `tests/test_fase10.py`, `tests/test_api_attempt_telemetry.py`, `tests/test_hardening_persistencia_sse.py` verdes.

### Etapa 3 — Instrumentação do turno e linha `rpg.turn`
1. **Testes**: `test_rpg_turn_line_additive_fields` (campos antigos preservados, novos presentes, sem texto do jogador nem `game_id` cru); `test_cost_unavailable_not_zero`; `test_fallback_counts_from_attempts`; `test_instrumentation_equivalence` (estado final idêntico com/sem timeline, R16); `test_disconnect_mid_stream_single_turn` (reaproveitar fixture de `test_hardening_persistencia_sse.py`).
   Mais `test_lock_wait_measured`, `test_llm_attempt_attributed_to_phase`, `test_cached_tokens_null_when_unreported` (R17).
2. **Implementação:** `api.py` + `context_builder`/nós (R2–R5, R17).
3. **Verificação:** suíte focada + `uv run python -m playtest run --profile normal --turns 5` sem erro/violação.

### Etapa 4 — Cliente e endpoint de reporte
1. **Testes**: Node (`web/tests/turnLatency.test.ts`): ordem `submit<ack<ttfmc<=ttlt<=state`, `accepted` e ping não definem TTFMC, fallback POST; Python (`tests/test_latency_client_endpoint.py`): `test_requires_csrf`, `test_rejects_extra_fields_and_text`, `test_clamps_values`, `test_disabled_by_default`, `test_rate_limited`.
2. **Implementação:** `turnLatency.ts`, `api.ts`, `App.tsx`, endpoint.
3. **Verificação:** `cd web && npm run build` e testes Node; `uv run pytest tests/test_latency_client_endpoint.py`.

### Etapa 5 — Baseline offline repetível
1. **Testes** (`tests/test_latency_baseline_offline.py`): `test_injected_latency_recovered_in_phases` (perfil `typical` virtual: narrator p50 ≈ valor injetado ± tolerância declarada); `test_same_seed_same_summary` (dois runs idênticos byte a byte no `summary.json` virtual); `test_fallback_once_profile_counts_fallbacks`; `test_compare_refuses_env_mismatch`; `test_real_mode_refuses_without_caps` (sem env/teto sai com erro antes de construir qualquer LLM).
2. **Implementação:** `playtest/latency_llm.py`, `scripts/latency_baseline.py`, `scripts/latency_journeys.py`.
3. **Verificação:** `uv run python scripts/latency_baseline.py run --journeys all --reps 30 --seed 200 --profile typical --mode virtual` duas vezes; `report` gera Markdown; diff de `summary.json` vazio.

### Etapa 6 — Browser smoke e evidência
1. **Testes** (`web/e2e/latency.spec.ts`, Chromium 390/1440, API com MockLLM `scaled-real`): marcas presentes por turno; `ttfmc` posterior ao último `phase`; sem erro de console.
2. **Implementação:** nenhuma além de ajustes; gerar `docs/spec200/README.md` com o relatório offline (perfil `typical` e `slow-tail`).
3. **Verificação:** `uv run pytest` completo verde.

## 5. Critérios de aceite

- [ ] `TurnTimeline` produz fases exclusivas com soma igual ao total (±1 ms) em teste com `FakeClock`.
- [ ] `rpg.turn` contém os campos de R5, sem PII/texto/ids crus; campos antigos intactos.
- [ ] `rpg_sse_ack_seconds` reflete atraso injetado antes do primeiro byte; `rpg_sse_first_event_seconds` segue registrada e documentada como deprecada; `local.yml`/`local.test.yml` inalterados e verdes.
- [ ] Marcas `performance` no cliente seguem a ordem definida; TTFMC ignora `accepted`/ping/`phase`.
- [ ] Endpoint de reporte exige sessão/CSRF, rejeita campos extras, clampa valores, está desligado por default.
- [ ] Baseline offline: 6 jornadas × N reps, mesma seed ⇒ `summary.json` idêntico; relatório p50/p95 por jornada e por fase; fingerprint presente; `compare` recusa ambientes incompatíveis.
- [ ] Modo `--real` não roda sem autorização + `--max-requests` + `--max-cost`; nenhuma chamada paga foi feita para fechar a spec (a menos que o dono autorize, P5).
- [ ] `rpg.turn` contém `lock_wait_ms`, `llm_by_tier`, `llm_by_phase`, `cached_tokens`/`cache_hit_ratio` (ou `null`), `input_size`; teste `test_lock_wait_measured` (segundo turno concorrente no mesmo `game_id` registra espera > 0 com `FakeClock`) e `test_llm_attempt_attributed_to_phase` verdes (R17).
- [ ] Relatório imprime TTFT com a nota `TTFT ≡ TTFMC (pseudo_streaming)` e percentis estratificados por `input_size` (R17).
- [ ] Teste de equivalência R16 verde; ordem de nós e nº de chamadas LLM inalterados.
- [ ] `uv run pytest` verde (suíte completa offline); `npm run build` e testes Node verdes; Ruff verde nos arquivos tocados.
- [ ] Guard de FallbackLLM: nenhum `with_structured_output` novo (a spec não adiciona nós LLM).
- [ ] Saves antigos continuam carregando (nenhum campo de save alterado).

## 6. Smoke test

**Offline (padrão, sem custo):**

1. `uv run python scripts/latency_baseline.py run --journeys all --reps 30 --seed 200 --profile typical --mode virtual` e repetir; comparar `summary.json`.
2. Idem com `slow-tail` e `fallback-once`; conferir `llm_fallbacks > 0` só no último.
3. `uv run uvicorn api:app` com perfil `scaled-real` + Playwright (`web/e2e/latency.spec.ts`): ler `performance.getEntriesByType('measure')` por turno.
4. `uv run python -m playtest run --all --turns 3` sem erro nem violação `error`.

**Provider real (opt-in, fora desta aprovação):** ver P5. Sequência prevista: `RPG_LATENCY_REAL_AUTHORIZED=1 uv run python scripts/latency_baseline.py run --real --journeys J1,J2,J3 --reps 5 --max-requests <teto> --max-cost <teto>`; aceite = zero erro de turno e relatório com `mode=real` em arquivo separado. MockLLM esconde bugs de mapeamento, mas esta spec não altera caminhos de structured output, portanto o smoke real é medição, não validação de contrato.

## 7. Riscos & compatibilidade

- **Saves:** nenhuma mudança de schema; sem migração. Teste round-trip não aplicável além de "save antigo carrega e turno roda com instrumentação".
- **Dashboards/alertas (SPEC-196, SPEC-106):** nomes antigos preservados; adição de novas séries e de `route="/game/action/stream"` em `rpg_turn_duration_seconds` pode partir a série do alerta `TurnP95High` em duas (a expressão atual não filtra `route`). Coberto por P3.
- **Cardinalidade:** labels fechados, valores truncados em 60 chars pelo registro; `action_ref` só em log, nunca em label.
- **Privacidade:** pseudônimo por `observability.telemetry.pseudonym`; nada de texto do jogador; beacon sem `game_id`.
- **Overhead:** marcas e acumuladores são O(1) por evento; teste de equivalência R16 + microbenchmark informativo (não gate).
- **Ambiguidade de atribuição:** modo paralelo não é suportado pelo baseline oficial (R3); intervalo entre updates inclui overhead do grafo (aceito na SPEC-116).
- **Honestidade das métricas:** offline `virtual` mede estrutura (decomposição, ordem, contagens), não latência de rede; o relatório rotula isso. [H] O valor de p95 absoluto só é interpretável no modo `real`.
- **MockLLM/FallbackLLM:** o wrapper de latência fica fora do runtime de produção; `RPG_FORCE_MOCK=1` continua forçando mock na suíte.
- **Interação com outras specs:** SPEC-213 usa `phase_ms.archivist` e `archivist_validate_ms` para decidir o que vai a segundo plano; SPEC-214 usa `context`; SPEC-217 só reavalia Jev com este baseline; SPEC-207 exporta `rpg.turn`/`client_latency` redigidos; SPEC-212 consome o relatório como evidência de gate.

## 8. Pontos de decisão do dono

- **P1 — Meta numérica de TTFMC/TTLT.** Default recomendado [R]: **sem meta nesta spec**; metas só após o baseline real (SPEC-212), para não inventar alvo. Alternativa: fixar orçamento provisório (ex.: ack < 300 ms, TTFMC p95 < 20 s).
- **P2 — Beacon cliente→servidor.** Default [R]: implementar R10 **desligado**, ligar só em beta com consentimento (texto legal via SPEC-197 por handoff, sem editá-la). Alternativa: medir cliente apenas em Playwright local e não ter endpoint.
- **P3 — Partição de `rpg_turn_duration_seconds` por rota.** Default [R]: adicionar `route=/game/action/stream` e ajustar o alerta para agregar `sum by (simulated)` em spec/PR de observabilidade futuro. Alternativa: manter rota fixa e discriminar transporte em métrica nova (zero risco para o alerta, menos clareza).
- **P4 — Gate numérico em `evals/`.** Default [R]: não; relatório informativo. Se o dono quiser limiar que quebre CI, abrir tarefa separada com `EVAL_AUTHORING_REQUIRED: true`.
- **P5 — Experimento com provider real.** Default [R]: autorizar **após** a implementação, com teto proposto de 40 requests e US$ 0,20 (precedente de `benchmark_turn_pipeline_real.py`), jornadas J1–J3, 5 reps, `RPG_TURN_EXECUTION=sequential`. Esta spec, por si, não executa nada pago.

## 9. Evidência requerida

- Saída dos comandos de teste das Etapas 1–6 e `uv run pytest` completo (contagem passed/skipped).
- `docs/spec200/README.md` com: definições, fingerprint, tabela p50/p95 por jornada e fase (perfis `typical`, `slow-tail`, `fallback-once`), declaração `pseudo_streaming=true`, e nota sobre a métrica deprecada.
- Dois `summary.json` idênticos (mesma seed) e hash de ambos.
- Trecho de linha `rpg.turn` real do servidor (offline) mostrando campos novos redigidos.
- Captura do JSON de `performance.getEntriesByType('measure')` do Chromium para ao menos um turno em 390 e 1440.
- Diff de `observability/alerts/*` vazio (ou justificado por P3).
- Para o experimento real, se autorizado: run id, nº de requests, custo normalizado com `cost_basis`, e relatório separado `mode=real`.
- Parecer da revisão Sol independente (concorrência da `TurnTimeline`, cardinalidade, endpoint novo).
