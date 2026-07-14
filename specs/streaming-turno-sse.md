# SPEC — Streaming do turno via SSE + custo por turno em produção

> **Status:** `done` (2026-07-13 — smoke real: `accepted` 0.09s, `route` 0.66s,
> `state` 20.2s num turno real de 20s; ver §8)
> **Criada:** 2026-07-13 · **Atualizada:** 2026-07-13
> **Depende de:** Fase 10 fatia local `done` (rate limit/log de turno); roteamento multi-provider `done`
> **Desbloqueia:** UX mobile (spec polish-sessao); qualquer demo pública

---

## 1. Contexto & Objetivo

Latência real medida na Fase 5: **p50 ≈ 15s, p95 33-46s por turno**. Hoje o
frontend espera o `POST /game/action` INTEIRO e só então roda o typewriter
(efeito 100% client-side — `web/src/components/StoryLog.tsx` via `useTypewriter`).
O jogador olha um spinner por 15-45s. Num jogo de TEXTO, isso é a maior dor de
produto do momento.

Streaming token-a-token de verdade é inviável sem reestruturar o motor: a
narração nasce DENTRO de `with_structured_output(StoryUpdate)` (campo
`narrative` de um schema Pydantic — parcial de JSON não é confiável entre 6
providers) e separar narração de eventos custaria +1 chamada LLM/turno,
desfazendo a otimização 5-6→2-3 calls. **Decisão desta spec: streaming honesto
de FASES do grafo** — LangGraph expõe `app.stream(state, stream_mode="updates")`
(síncrono), que emite o update de cada nó ao terminar. O jogador vê progresso
real em segundos ("o mestre decide a rota" → "⚔️ combate!" → narração
chegando em chunks), sem custo LLM extra e sem tocar nos agentes.

Carona da mesma spec (mesmo canal): o hook `set_llm_telemetry_hook` já mede
provider/modelo/latência/fallback por invoke (Fase 5.3) mas SÓ no playtest —
produção não registra. Plugar o hook no log de turno da API dá custo/latência
reais de produção de graça.

## 2. Requisitos

- **R1 — Endpoint SSE `POST /game/action/stream`.** Mesmo corpo do
  `/game/action` (`ActionRequest`). Resposta `text/event-stream` com eventos,
  nesta ordem garantida:
  - `accepted` — imediato (`{"game_id": ...}`); alvo: chega < 1s após o request;
  - `phase` — 1 por nó do grafo ao COMEÇAR/terminar (`{"node": "dm_router",
    "status": "done"}`), na ordem real de execução;
  - `route` — assim que o router decide (`{"route": "combat"}`) — a UI troca o
    indicador ("⚔️ O aço encontra o aço…");
  - `narrative` — texto final do turno em CHUNKS de ~80 chars
    (`{"chunk": "...", "done": false}`) — typewriter dirigido pelo servidor;
  - `state` — `GameResponse` completo serializado (idêntico ao POST clássico);
  - `error` — em falha (`{"detail": "..."}`, mesma sanitização A6), fecha o stream.
- **R2 — Resultado idêntico ao POST clássico.** O turno via stream produz o
  MESMO estado/save/GameResponse que `/game/action` (lógica compartilhada num
  helper único, não duplicada). `/game/action` continua existindo inalterado.
- **R3 — Guard-rails valem no endpoint novo.** Rate limit (mesma janela),
  `_reject_memorial` (evento `error` com 409 semântico), validação de game_id,
  teto de `input_text`, log JSON de turno — tudo reusado.
- **R4 — Frontend consome o stream.** Ao enviar ação: entrada aparece no log
  na hora; indicador de fase com textos curados por nó (dict estático:
  `campaign_manager` → "O mestre consulta os arcanos…", `combat_agent` → "⚔️ O
  aço encontra o aço…", `archivist` → "O escriba registra…"); `narrative` chunks
  alimentam o `useTypewriter` (flag `streaming` já existe). Se SSE falhar
  (proxy/browser), fallback AUTOMÁTICO e silencioso para o POST clássico.
- **R5 — Telemetria de LLM em produção.** *(Confirmado no refinamento
  2026-07-13: dev-only via log — SEM endpoint /game/stats e SEM HUD; promover
  depois só se sentir falta.)* `api.py` registra
  `set_llm_telemetry_hook` que acumula invokes do turno corrente; o log
  `rpg.turn` ganha `llm_calls` (n), `llm_providers` (contagem por provider),
  `fell_back` (bool), `cost_usd_est` (estimativa via `playtest/pricing.py` —
  mesma heurística de tokens fixos/invoke). Dev-only: NADA disso vai no
  GameResponse. MockLLM → custo 0 (como na Fase 5.3).

### Fora de escopo

- Streaming token-a-token de dentro do structured output (frágil entre providers).
- Separar narração de eventos em 2 chamadas LLM (mudaria custo/arquitetura 2.6).
- WebSocket (SSE basta: unidirecional, HTTP puro, passa em proxy).
- Refactor async do grafo (LangGraph segue síncrono; o stream roda em thread).
- Cancelamento de turno no meio (fechar a aba não desfaz o turno — save é atômico no fim).

## 3. Design técnico

**Arquivos alterados**
- `api.py` —
  - refatorar o miolo de `game_action` num helper `_run_turn(state, req) ->
    GameResponse` (carga/validações ficam no endpoint; helper roda grafo + save
    + log — usado pelos DOIS endpoints);
  - novo `POST /game/action/stream`: generator SÍNCRONO (Starlette roda em
    threadpool) que consome `game_graph.stream(state, stream_mode="updates")`,
    emite eventos SSE e salva ao final; keepalive `: ping\n\n` a cada 10s;
  - hook de telemetria (R5): `llm_setup.set_llm_telemetry_hook(_acumula)` no
    import; acumulador por turno em `contextvars.ContextVar` (grafo roda numa
    thread só por turno — ContextVar copiado pro generator; zero estado global
    entre requests concorrentes).
- `web/src/App.tsx` + `web/src/api.ts` — `sendActionStream()` com
  `fetch` + `ReadableStream` parser de SSE (POST não funciona com
  `EventSource` nativo — parser manual de `event:`/`data:`); fallback pro
  `sendAction()` existente em qualquer erro de stream ANTES do evento `state`.
- `web/src/components/StoryLog.tsx` — entrada "streaming" com fase + chunks.
- `playtest/pricing.py` — nenhuma mudança (reuso; função já é pura).

**Formato SSE (exemplo real de turno de combate)**
```
event: accepted
data: {"game_id": "3f2a..."}

event: phase
data: {"node": "campaign_manager", "status": "done"}

event: route
data: {"route": "combat"}

event: phase
data: {"node": "combat_agent", "status": "done"}

event: narrative
data: {"chunk": "O Sapo-Boi salta da lama, mandíbula aberta — sua lâmina o encontra no ar. ", "done": false}

event: narrative
data: {"chunk": "", "done": true}

event: state
data: {"game_id": "3f2a...", "message": "...", "player_stats": {...}, ...}
```

**Assinaturas**
```python
# api.py
def _run_turn(state: dict, input_text: str) -> "GameResponse": ...   # POST clássico
def _stream_turn(state: dict, input_text: str) -> Iterator[str]: ... # gerador SSE

# telemetria (R5)
def _telemetry_hook(provider: str, model: str, tier: str,
                    latency_ms: int, fell_back: bool) -> None: ...
```

**Nota LangGraph:** `stream_mode="updates"` devolve `{node_name: partial_state}`
por nó concluído — a narrativa final sai do update do nó narrador (última
`messages`); o estado COMPLETO final é o acumulado (usar `stream_mode=
["updates","values"]` ou reconstruir com o último `values`). Validar na Etapa 1
com o grafo real (MockLLM).

## 4. Plano passo a passo

### Etapa 1 — Prova do canal (grafo real, MockLLM)
1. **Testes** (`tests/test_streaming.py`): `test_graph_stream_emite_updates_por_no`
   (MockLLM; `app.stream` devolve nós na ordem campaign_manager → dm_router →
   <rota> → archivist); `test_estado_final_do_stream_igual_ao_invoke` (mesmo
   seed → mesmo estado).
2. **Implementação:** nenhuma — é caracterização do LangGraph atual.
3. **Verificação:** verde; qualquer surpresa aqui muda o design ANTES de codar.

### Etapa 2 — Refactor sem comportamento novo (R2 parcial)
1. **Testes:** suíte existente da API continua verde (garantia do refactor).
2. **Implementação:** extrair `_run_turn`; `game_action` usa o helper.
3. **Verificação:** `uv run pytest` verde; diff de comportamento zero.

### Etapa 3 — Endpoint SSE (R1, R3)
1. **Testes:** `test_stream_ordem_de_eventos` (TestClient com `stream=True`:
   accepted → phase(s) → route → narrative(done) → state);
   `test_stream_memorial_devolve_error`; `test_stream_respeita_rate_limit`;
   `test_stream_state_igual_ao_post` (mesmo save/GameResponse);
   `test_stream_erro_no_meio_emite_error_sanitizado`.
2. **Implementação:** `_stream_turn` + endpoint.
3. **Verificação:** suíte verde.

### Etapa 4 — Telemetria de produção (R5)
1. **Testes:** `test_log_de_turno_tem_custo_e_providers` (caplog: campos
   `llm_calls`/`cost_usd_est` presentes; MockLLM → custo 0);
   `test_hook_nao_vaza_entre_turnos`.
2. **Implementação:** hook + acumulador ContextVar + campos no log.
3. **Verificação:** verde; log continua 1 linha JSON válida.

### Etapa 5 — Frontend (R4)
1. **Testes:** build (`npm run build`); parser SSE com teste unitário se houver
   infra de teste no web/ (senão smoke manual).
2. **Implementação:** `sendActionStream` + fases + chunks + fallback.
3. **Verificação:** `npm run build` ok + smoke manual local (MockLLM: fases
   passam rápido mas visíveis; forçar erro de rede → fallback POST funciona).

## 5. Critérios de aceite

- [x] Evento `accepted` chega < 1s após o request (real: 0.09s; MockLLM: 0.03s)
- [x] Ordem de eventos garantida e testada; `state` final idêntico ao POST clássico
- [x] `/game/action` clássico intocado (fallback vivo — testado)
- [x] Rate limit + memorial + sanitização A6 valem no endpoint novo
- [x] Log `rpg.turn` com `llm_calls`/`providers`/`fell_back`/`cost_usd_est`; zero exposição ao jogador
- [x] Frontend: fase visível durante a espera; typewriter consome chunks; fallback automático
- [x] `uv run pytest` verde (769) + `npm run build` ok
- [x] Guard de FallbackLLM: nenhum `with_structured_output` novo (só reuso)
- [x] Saves antigos continuam carregando (nenhuma mudança de schema)
- [x] ESTADO_ATUAL.md + ROADMAP.md atualizados

## 6. Smoke test com LLM real

1. Turno vivo via `/game/action/stream` (curl -N ou frontend): cronometrar
   request→`accepted` (< 1s), request→primeiro `phase`, request→`state`
   (deve empatar com o POST clássico).
2. Turno de COMBATE real: evento `route` correto, indicador de fase certo na UI.
3. Derrubar a rede no meio do stream → frontend cai no POST clássico sem erro visível.
4. Conferir stderr: linha `rpg.turn` com custo estimado e providers do turno.

## 7. Riscos & compatibilidade

- **MockLLM/FallbackLLM:** fases passam em ms — stream funciona igual (suíte
  usa TestClient sobre MockLLM). FallbackLLM: turno degrada como hoje; o evento
  `state` carrega a resposta degradada normal.
- **Proxy dev (Vite :5173):** SSE passa por HTTP normal; confirmar que o proxy
  não bufferiza (`proxy` do Vite com `configure` p/ desligar buffering se
  necessário) — faz parte da Etapa 5.
- **Concorrência:** acumulador de telemetria por ContextVar; teste explícito de
  não-vazamento entre turnos.
- **Custo:** zero chamada LLM extra por design (só reorganiza o transporte).
- **Compatibilidade de API:** endpoint novo aditivo; clientes antigos (CLI,
  scripts, smoke_api.sh) intocados.

## 8. Registro de execução (2026-07-13)

- **Etapa 1 (caracterização):** `app.stream(state, stream_mode=["updates","values"])`
  emite `(mode, payload)`; nós na ordem campaign_manager → dm_router → rota →
  archivist; estado final == `invoke` com mesmo seed (2 testes).
- **Implementação:** `_run_turn` compartilhado; `_stream_turn` roda o grafo em
  thread própria com `queue.Queue` (keepalive `: ping` a cada 10s entre nós);
  memorial vira evento `error` com `code: 409`; telemetria por
  `contextvars.ContextVar` (hook global registrado no import do api.py).
- **Smoke real (Groq/Gemini vivos):** turno de 20.2s → `accepted` 0.09s,
  primeiro `phase` 0.11s, `route` 0.66s ("npc_actor"). Log `rpg.turn` real:
  `llm_calls=5, llm_providers={groq:3, gemini:2}, cost_usd_est=0.0036,
  fell_back=true` (minimax 402/qwen 401 — contas sem saldo, fallback ok).
- **Frontend:** parser SSE manual (fetch+ReadableStream), fases com textos
  curados, chunks alimentam `useTypewriter` (que agora CONTINUA quando o texto
  cresce), fallback silencioso pro POST em qualquer erro antes de `state`
  (entrada parcial órfã é removida do log). 9 testes em `tests/test_streaming.py`.
