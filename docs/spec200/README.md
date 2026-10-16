# SPEC-200 — Baseline de latência percebida (ack, TTFMC, TTLT)

Evidência de execução. A spec só **mede**: nenhuma otimização, nenhuma mudança de comportamento
(mesma ordem de nós, mesmas chamadas LLM, mesmas mensagens SSE; campos novos só em logs/métricas).

## Definições (normativas)

| Medida | Definição |
|---|---|
| `ack_server_ms` | entrada do handler (`game_action_stream`, antes de `load_game_state`) → retomada do gerador logo após `yield accepted` (proxy de flush) |
| `ack_ui_ms` | submit no cliente → primeiro byte do corpo SSE. `accepted` isolado e `: ping` **não** são conteúdo |
| **TTFMC** | submit → primeiro `narrative` com `chunk.strip()` não vazio (cliente) / até o `yield` desse evento (servidor). `phase`, `route`, `visual`, `accepted`, ping não contam |
| **TTFT** | `TTFT ≡ TTFMC (pseudo_streaming)`: com `pseudo_streaming=true` não existe token real; os dois são o mesmo número |
| **TTLT** | submit → `narrative` com `done: true`; `state_ms` até o evento `state` |
| `pseudo_streaming` | `true` fixo enquanto `_stream_turn` fatiar uma mensagem JÁ pronta (o texto só existe depois do archivist) |

Estratificação de `input_size` (limiares fixos, em caracteres da ação do jogador): `short` ≤ 40,
`medium` ≤ 160, `long` > 160.

## O que mudou

* `observability/latency.py`: `TurnTimeline` (thread-safe, relógio injetável, fases **exclusivas** por pilha),
  `FakeClock`, `phase()`/`accumulate()` no-op sem timeline. Fases: `router`, `context`, `narrator`, `archivist`,
  `persistence`, `other` (soma == total ± 1 ms).
* `api.py`: timeline criada na entrada do handler e passada ao worker por **parâmetro** (não por ContextVar);
  campos aditivos na linha `rpg.turn`; linha `evt:"turn_delivery"` no fim do stream (ttfmc/ttlt/state só existem
  depois que o worker já logou o turno); `rpg_turn_duration_seconds` ganha `route="/game/action/stream"`;
  endpoint `POST /telemetry/client-latency` (desligado por default).
* `observability/metrics.py`: `rpg_sse_ack_seconds{route}`, `rpg_turn_phase_seconds{route,phase}`,
  `rpg_turn_first_content_seconds{route,source}`, `rpg_turn_last_content_seconds{route,source}`
  (`source ∈ {server,client}`; labels fechados).
* `agents/archivist.py`: `archivist_validate_ms` (sub-medida, só campo de log); `services/context_builder.py`:
  `build_context_pack` envolve a fase `context`.
* Cliente: `web/src/lib/turnLatency.ts` (`performance.mark/measure` `rpg:turn:<action_id>:submit|ack|first_phase|ttfmc|ttlt|state`),
  `sendActionStream` expõe `onAck`/`onEvent`; fallback POST registra `ttfmc = ttlt = state`.
* Baseline offline: `scripts/latency_baseline.py` (`run|report|compare|serve`), `scripts/latency_journeys.py`
  (J1–J6), `playtest/latency_llm.py` (LLM com latência injetada; **nunca** no runtime de produção).

## Métrica antiga deprecada (R7)

`rpg_sse_first_event_seconds` **continua registrada e observada** (nenhum buraco em séries), mas mede só o
enfileiramento do evento `accepted` (microssegundos), **não** a latência percebida. **Deprecada**; a medida
honesta é `rpg_sse_ack_seconds`. Remoção só em spec posterior, depois da SPEC-212.

## Campos novos da linha `rpg.turn` (R5/R17)

`action_ref` (pseudônimo), `transport`, `pseudo_streaming`, `ack_server_ms`, `ttfmc_server_ms`, `ttlt_server_ms`,
`state_server_ms`, `phase_ms`, `execution_mode`, `attribution:"interval"`, `llm_attempts`, `llm_fallbacks`,
`llm_failed_attempts`, `providers_used`, `cost_usd` + `cost_usd_basis` (`none|usage|partial|unavailable`; nunca zero
fabricado), `lock_wait_ms`, `llm_by_tier`, `llm_by_phase`, `cached_tokens`/`cache_hit_ratio` (`null` se nenhum provider
reportou), `input_chars`, `input_size`, `rag_cache:"not_instrumented"`, `archivist_validate_ms`, `route_next`.
Sem texto do jogador/narração e sem `game_id` cru (testado).

Trecho real (offline, MockLLM + perfil `typical` virtual; campos antigos preservados):

```json
{"evt": "turn", "game_id_ref": "bb43ce60d0f1089a", "turn": 4, "route": "storyteller", "latency_ms": 117,
 "action_ref": "2b5379437c60f39f", "transport": "stream", "pseudo_streaming": true,
 "ack_server_ms": 0, "ttfmc_server_ms": null, "ttlt_server_ms": null,
 "phase_ms": {"archivist": 3743, "context": 0, "narrator": 2936, "other": 0, "persistence": 0, "router": 0},
 "execution_mode": "sequential", "attribution": "interval", "llm_attempts": 3, "llm_fallbacks": 0,
 "llm_failed_attempts": 0, "providers_used": ["deepseek"], "cost_usd": null, "cost_usd_basis": "unavailable",
 "lock_wait_ms": 0, "cached_tokens": null, "cache_hit_ratio": null, "input_chars": 130, "input_size": "medium",
 "rag_cache": "not_instrumented", "llm_by_phase": {"archivist": 1, "narrator": 1, "router": 1}}
{"evt": "turn_delivery", "action_ref": "2b5379437c60f39f", "transport": "stream", "pseudo_streaming": true,
 "ack_server_ms": 0, "ttfmc_server_ms": 6695, "ttlt_server_ms": 6695, "state_server_ms": 6695, "outcome": "ok"}
```

(`ttfmc/ttlt` ficam `null` na linha `turn` do stream porque o worker loga antes da entrega; saem em `turn_delivery`.)

## Baseline offline — como reproduzir

```
uv run python scripts/latency_baseline.py run --journeys all --reps 30 --seed 200 --profile typical --mode virtual
uv run python scripts/latency_baseline.py report <run_id>
uv run python scripts/latency_baseline.py compare <run_a> <run_b>   # recusa fingerprints incompatíveis
```

Saída em `latency_runs/<run_id>/{records.jsonl,summary.json,report.md}` (gitignored).

**Honestidade do modo offline.** `mode=offline-virtual` usa MockLLM com latência **injetada** e relógio virtual:
mede a *estrutura* do turno (decomposição, ordem, contagens, fallbacks), **não** latência de rede. Por isso
`persistence`, `context` e `other` aparecem como 0 (nada avança o relógio virtual fora das chamadas LLM) e
`ack = 0`. O p95 absoluto só é interpretável no modo `real`.

### Determinismo (mesma seed ⇒ `summary.json` idêntico)

`typical`, 6 jornadas × 30 reps, seed 200, duas execuções independentes:

```
f791fec9f763b8a8fa40a8299f9c4ab6af9bd22a4fd4a02ccf61a4cda3d18e35  summary-typical-a.json
f791fec9f763b8a8fa40a8299f9c4ab6af9bd22a4fd4a02ccf61a4cda3d18e35  summary-typical-b.json
```

### Resultados (ms; relatórios completos em `report-*.md`)

`pseudo_streaming=true` ⇒ **TTFT = TTFMC (pseudo_streaming)**; TTLT − TTFMC ≈ 0 (blocos de 80 chars são
drenados de uma vez, depois do archivist).

| Perfil | TTFMC p50 | TTFMC p95 | router p50/p95 | narrator p50/p95 | archivist p50/p95 | fallbacks |
|---|---|---|---|---|---|---|
| `typical` (330 turnos) | 6417 | 7964 | 289 / 355 | 2658 / 5996 | 3589 / 4709 | 0 |
| `slow-tail` | 6728 | 18946 | 292 / 1086 | 2704 / 10621 | 3643 / 15758 | 0 |
| `fallback-once` | 9681 | 11432 | 435 / 517 | 3878 / 7416 | 5521 / 6752 | 849 |

`llm_fallbacks > 0` somente em `fallback-once` (conferido). Por jornada (`typical`, TTFMC p50/p95): J1 6247/7661,
J2 5782/13064, J3 6761/8780, J4 7043/7964, J5 6573/7707, J6 2978/7882. Leitura estrutural (offline): o **archivist
(~45%)** e o **narrator (~51%)** dominam o caminho até o primeiro conteúdo, porque a mensagem só existe depois do
archivist — insumo direto das SPEC-213/214. Nenhuma conclusão sobre rede/provedor real.

## Cliente (Chromium)

`web/e2e/latency.spec.ts` (390 e 1440 px, API determinística das fixtures): marcas por turno na ordem
`ack ≤ first_phase ≤ ttfmc ≤ ttlt ≤ state`, um `action_id` por turno, nenhuma chamada a `/telemetry` com o beacon
desligado, zero erro de console. JSON de `performance.getEntriesByType('measure')`:
`performance-measures-390.json`, `performance-measures-1440.json`.

Smoke com latência injetada **em tempo real** (API local, MockLLM, perfil `typical`, escala 0,2, `web/dist`
servido pelo FastAPI): `performance-measures-scaled-390.json` (ack 14 ms, first_phase 24, ttfmc 525, ttlt 529,
state 529) e `...-scaled-1440.json` (ack 17, first_phase 22, ttfmc 1366, ttlt 1369, state 1370), zero erro de
console. Comando: `uv run python scripts/latency_baseline.py serve --profile typical --scale 0.2 --port 8765`.

## Beacon cliente → servidor (R10) — DESLIGADO por default (P2)

`POST /telemetry/client-latency`, corpo fechado `{action_id, transport, ack_ms, first_phase_ms, ttfmc_ms, ttlt_ms,
state_ms, outcome}` (campos extras → 422; inteiros clampados em [0, 600000]; sem `game_id`/texto), mesma sessão/CSRF
das mutações nos perfis com banco (o prefixo `/telemetry` entrou no boundary de sessão), balde de rate limit
**próprio** (não consome o das ações), responde 204. `RPG_CLIENT_LATENCY_REPORT=1` liga; o servidor sinaliza em
`/auth/config` (`client_latency_report: true`, ausente quando desligado) — o cliente só envia se esse flag vier
(nenhuma requisição extra) e desiste após a primeira falha. Sem efeito em estado, saves ou saldo.
Texto de consentimento/legal para ligar em beta: handoff para a SPEC-197 (não editada aqui).

## Alertas (P3)

`observability/alerts/local.yml` e `local.test.yml` **inalterados** (diff vazio). `TurnP95High`
(`rpg_turn_duration_seconds_p95{simulated="true"} > 2`) não filtra `route`: a nova série
`route="/game/action/stream"` dispara por conta própria, então o alerta segue válido sem agregação nova.
`promtool` não está instalado neste ambiente; o teste correspondente verifica a expressão e pula a execução do
`promtool test rules` com marca explícita.

## Experimento com provider real (P5) — NÃO executado

Nenhuma chamada paga foi feita. Comando previsto (precisa de autorização do dono; tetos propostos 40 requests / US$ 0,20):

```
RPG_LATENCY_REAL_AUTHORIZED=1 uv run python scripts/latency_baseline.py run --real \
  --journeys J1,J2,J3 --reps 5 --max-requests 40 --max-cost 0.20
```

`--real` recusa sem `RPG_LATENCY_REAL_AUTHORIZED=1` **e** `--max-requests` **e** `--max-cost` (antes de construir qualquer
LLM); o resultado tem `mode=real`, nunca é misturado com offline, e a checagem de teto ocorre entre turnos
(estouro máximo de um turno). Não roda em CI nem em `uv run pytest`.

## Desvios e decisões (defaults da seção 8)

* **P1** sem meta numérica · **P2** beacon implementado e desligado · **P3** série do alerta mantida (sem mudança) ·
  **P4** sem gate numérico em `evals/` · **P5** real não executado.
* `cost_basis` já existia na linha `rpg.turn` (`estimated|normalized`); para não mudar campo existente, o novo é
  `cost_usd` + `cost_usd_basis`. `llm_attempts` já existia com o mesmo significado.
* `ttfmc_server_ms`/`ttlt_server_ms` saem na linha `turn_delivery` (o worker loga antes da entrega); o registro final
  publicado aos sinks (baseline) junta tudo.
* A flag do beacon viaja em `/auth/config` (não em `/health`): o cliente já faz essa requisição no bootstrap, e as
  fixtures e2e não interceptam `/health`.
* POST (`/game/action`) agora executa o grafo via `stream` quando o grafo suporta (mesmo estado final, testado), para
  decompor por fase; grafos sem `stream` caem em `invoke` (tudo em `other`).
* RAG de contexto nos agentes: só `build_context_pack` ganhou a fase `context`; chamadas diretas a `query_rag` fora dele
  continuam atribuídas ao nó que as faz.
* Browser e2e usa a API determinística das fixtures (CI-friendly); o smoke em tempo real fica no comando `serve` acima.
* `EVAL_AUTHORING_REQUIRED: false` mantido: nada em `evals/` foi tocado.

## Revisão (2026-10-16)

Revisão Sol independente: APPROVED_WITH_FOLLOWUPS — `stream` equivale ao `invoke` (o `Pregel.invoke` da versão
instalada é o próprio stream em modo values); testes de equivalência de estado final e de falha no meio do stream
adicionados; teste intermitente de desconexão SSE estabilizado. Coordenador: o cliente limpa marcas/medidas de turnos
além dos 3 mais recentes. Follow-up: o label `route` de `rpg_turn_duration_seconds` agora separa `/game/action/stream`.
Experimento `--real` não executado (exige autorização e tetos).
