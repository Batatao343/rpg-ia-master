# Fatia 04 — API, Frontend, Persistência e Experiência do Jogador

Projeto: `rpg-ia-master` (FastAPI + LangGraph + React/Vite/TS). Todos os caminhos são relativos à raiz do projeto, salvo indicação. Referências no formato `arquivo:linha`. Nada foi modificado; o relatório descreve o estado do código lido nesta sessão (working tree com muitas modificações não commitadas, branch `main`).

---

## 0. Visão geral em uma página

- **`api.py` (2.894 linhas)** é a única borda HTTP. Expõe ~30 rotas: auth, dados estáticos (`/data/*`), ciclo de jogo (`/game/new|action|action/stream|death|equip|levelup`), leitura (`/game/state|codex|history|saves|chronicle/*`), arte (`/game/art/*`, `/game/{id}/art/*`) e infra (`/health`, `/metrics`). No fim do arquivo monta `web/dist` (ou `frontend/`) na raiz `/` (`api.py:2877-2884`).
- **Dois modos de execução** controlados por `RPG_RUNTIME_PROFILE` (`api.py:83-85`, `infrastructure/runtime.py:58-66`): `legacy` (padrão: arquivos JSON + FAISS, sem login, loopback, locks em memória) e `local`/`portable`/`hosted` (Postgres + pgvector + auth cookie/CSRF + operações com *claim/lease/fencing* + rate-limit no Postgres). Quase todo endpoint tem dois ramos: `if _database_profile(): ... else: ...`.
- **Um turno** = `POST /game/action` ou `/game/action/stream` → `_execute_action` → lock por jogo (legacy) → `load_game_state` → idempotência por `action_id` → gates (memorial/arquivado/queda pendente) → `_run_turn` → `execute_graph(game_graph)` → resolução de cue visual → fila de arte (opcional) → `_mark_action_processed` → `_prepare_checkpoint` → `format_response` → `_commit_turn` (save atômico ou `commit_game` transacional) → log `rpg.turn`.
- **Persistência legacy**: `saves/{uuid}.json` (escrita atômica temp+fsync+replace), `saves/{uuid}.checkpoint.json` (1 slot), `saves/{uuid}.checkpoint.memory/` (cópia do FAISS da sessão), `data/saves_memory/{uuid}/`.
- **Frontend (`web/src`, ~4.700 linhas TS/TSX)** é um SPA sem router: `App.tsx` mantém uma máquina de telas `bootstrap → (auth) → saves | create → play | simulator`, e `PlayScreen` compõe `StoryLog` + `Hud` (8 abas) + dock tático de combate + modais (`DeathModal`, `LevelUpModal`).
- **Morte**: o combate (ou o descanso fatal no storyteller) marca `death_pending`; o grafo e a API recusam novos turnos; o cliente abre `DeathModal`; `POST /game/death` chama `services/checkpoints.resolve_death_choice` que restaura o checkpoint (incrementando `timeline_epoch`) ou aceita o fim (memorial `game_over`).

---

## 1. `api.py` — infraestrutura transversal

### 1.1 Middlewares (ordem de declaração; em Starlette o último registrado é o mais externo)

| Middleware | Onde | O que faz |
|---|---|---|
| CORS | `api.py:68-74` | `allow_origins` = `RPG_CORS_ORIGINS` (CSV; default `http://localhost:8000,http://localhost:5173`), `allow_credentials=True`, métodos/headers `*`. |
| `_session_boundary` | `api.py:87-121` | **Só** em perfis de banco e só para paths `/game*`. Verifica o cookie de acesso via `runtime.identity_verifier.verify`; para métodos mutáveis valida CSRF (cookie `CSRF_COOKIE` + header `x-csrf-token` + `Origin` na allowlist, token assinado por `RPG_SESSION_SECRET`). Seta o `principal` num ContextVar e abre `correlation_scope(owner_id=...)`. `Unauthorized`/`ValueError` → 401. |
| `_correlation_boundary` | `api.py:123-159` | `X-Request-ID` (gera ou herda), span `http.request`, métricas `rpg_http_requests_total` e `rpg_http_duration_seconds` com rota normalizada (UUIDs viram `{id}`), headers de segurança (`nosniff`, `Referrer-Policy: same-origin`, `Permissions-Policy` sem câmera/mic/geo). |
| `_rate_limit` | `api.py:437-478` | Limite por IP. Aplica-se a `/game/action`, `/game/action/stream`, `/game/new`, `/game/combat-simulator`, `/game/equip`, `/game/levelup`, `/game/prologue` e `DELETE /game/save/*`. `RPG_RATE_LIMIT` (default 30 req/min, 0 desliga). Legacy: janela deslizante de 60 s em `deque` por IP com limpeza quando passa de 1.000 chaves (`api.py:466-476`). Perfis de banco: `runtime.rate_limiter.consume(...)` (Postgres) com IP pseudonimizado e header `Retry-After`. Excedeu → 429 `"Muitas requisições — aguarde um instante."`. |

### 1.2 Locks por jogo, idempotência e operações

- **Legacy**: `_game_locks: Dict[str, RLock]` (`api.py:301-308`). `_game_lock(game_id)` serializa mutações do mesmo save no processo (action, death, equip, levelup, art confirm, delete). Nos perfis de banco o lock é `nullcontext()` — a exclusão vem do *claim* transacional (lease + fencing em `app.operations`).
- **`action_id` (UUID)**: validado no `ActionRequest` (`api.py:538-546`). No legacy vira um ledger de 64 ids em `state["processed_action_ids"]` (`_action_already_processed`/`_mark_action_processed`, `api.py:2018-2030`); repetir o mesmo id devolve `format_response(state)` sem rodar o grafo (`api.py:2478-2479`). Nos perfis de banco o `action_id` é **obrigatório** (400 se faltar, `api.py:2111-2112`) e vira `operation_id`; o hash do payload (`_operation_hash`, sem o `action_id`, `api.py:2089-2093`) detecta reuso com payload diferente → 409 `operation_request_mismatch` (`_validated_receipt`, `api.py:2096-2103`). Um recibo (`receipt.response`) já commitado é devolvido como `GameResponse` sem reexecutar.
- **Helpers de operação** (`api.py:2106-2252`): `_begin_turn_operation`, `_begin_state_mutation` (equip/levelup/death/art), `_begin_create_operation` (new_game/combat-simulator), `_commit_state_mutation`, `_fail_operation`. Em perfil legacy todos devolvem `(None, "", None)` e o commit cai no `save_game_state`.
- `operation_scope` (`services/turn_execution.py:11-26`) mantém o lease vivo com heartbeat (`keep_lease_alive`, intervalo = lease/4) e chama `coordinator.fail(...)` se qualquer exceção escapar.
- `GET /game/{game_id}/operations/{operation_id}` (`api.py:1572-1595`): diz ao cliente se uma ação pendente já foi concluída. Legacy: `completed` se o id está no ledger, senão `unknown`. Banco: lê `app.operations` filtrando por `owner_id` e `game_id`.

### 1.3 Log estruturado `rpg.turn` e telemetria de LLM

- Logger `rpg.turn` escreve **uma linha JSON por turno** em stderr (`api.py:281-288`; emissão em `_log_turn`, `api.py:2365-2383`). Campos: `evt:"turn"`, `game_id_ref` (pseudônimo, não o id real), correlação, `turn`, `route` (`state["next"]`), `latency_ms`, `events_applied`, `events_rejected`, `error` (nome da exceção, nunca a mensagem) e os campos de LLM de `_llm_log_fields`.
- Os campos de LLM vêm de dois hooks (`set_llm_telemetry_hook`, `set_llm_attempt_telemetry_hook`) que acumulam em `ContextVar`s (`_llm_turn_events`, `_llm_attempt_events`, `api.py:294-297`), inicializadas em `_run_turn_collected` (`api.py:2407-2408`) e resetadas no `finally`. Cada request roda em thread própria, então não há vazamento entre turnos. Custo real por turno usa `playtest.pricing.turn_cost` (`api.py:2287`) e também é gravado no banco (`llm_cost_usd`). Esses dados são "dev-only": nunca entram em `GameResponse`.
- Métricas Prometheus em `/metrics` (`api.py:1223`); `rpg_turn_duration_seconds` com labels `route/outcome/simulated`, `rpg_turn_commits_total`, `rpg_db_duration_seconds`, `rpg_sse_first_event_seconds`.

### 1.4 Gates de estado (HTTP 409)

- `_reject_memorial` (`api.py:406-411`): `game_over` → "Esta saga terminou…".
- `_reject_archived` (`api.py:414-421`): saves anteriores à migração de Virtudes (v3→v4) são órfãos e somente-leitura.
- Queda pendente: `action`, `equip`, `levelup` e `art confirm` retornam 409 se `death_pending` (ex.: `api.py:2481-2482`).
- Erros internos viram 500 genérico (`"Erro interno ao processar o turno."`, `api.py:2455`) — detalhe só no log do servidor (auditoria A6).

---

## 2. Catálogo completo de endpoints

### 2.1 Autenticação (apenas perfis de banco; no legacy retornam 404, exceto `/auth/config`)

| Método e rota | Linha | Payload / resposta |
|---|---|---|
| `GET /auth/config` | `api.py:168` | Resposta `{required, authenticated, user_id?}`. `required = _database_profile()`. O front usa para decidir se mostra `AuthScreen`. |
| `POST /auth/login` | `api.py:206` | Body `AuthRequest{email(3-320), password(8-256)}`. Seta cookies de acesso, refresh e CSRF; resposta `{authenticated, csrf_token}`. 401 em credencial inválida. |
| `POST /auth/signup` | `api.py:222` | Mesmo body; 400 em falha. |
| `POST /auth/refresh` | `api.py:249` | Exige CSRF; troca o cookie de refresh por novos tokens. |
| `POST /auth/logout` | `api.py:267` | 204; exige CSRF; revoga o token e apaga os 3 cookies (o de refresh só em `path=/auth/refresh`). |

Cookies: `_set_session_cookies` (`api.py:187-203`): acesso/refresh `httponly` via `cookie_settings(secure=RPG_COOKIE_SECURE=="1")`; CSRF legível por JS, `samesite=strict`.

### 2.2 Dados estáticos e infra

| Rota | Linha | Propósito |
|---|---|---|
| `GET /health` | `api.py:1214` | `{status:"online", engine, git_sha}`. Usado em smoke pós-deploy. |
| `GET /metrics` | `api.py:1223` | Prometheus text. |
| `GET /data/options` | `api.py:1492` | Listas de raças/classes/regiões, `races_full` (desc + traits) e `visuals` (capas de raça/classe de `creation_visuals()`). |
| `GET /data/onboarding` | `api.py:1504` | Serve `data/onboarding.json` (lore do wizard) sem LLM nem RAG; 404 se ausente. |
| `GET /data/map` | `api.py:1516` | `world_map.json` **sem** interiores (`kind=="interior"` filtrado). |
| `GET /data/combat-simulator` | `api.py:1462` | Catálogo do laboratório: classes, níveis `[1,3,5,10]`, quantidades `[1,2,3]`, inimigos agrupáveis por categoria (lacaio/padrão/elite/nomeado/chefe). |

### 2.3 Criação, prólogo e laboratório

| Rota | Linha | Payload / resposta |
|---|---|---|
| `POST /game/prologue` | `api.py:1598` | Body `CreateCharacterRequest` (a mesma ficha). Chama `build_start_scenario` (1 chamada SMART + guard → template determinístico, nunca 500) e devolve `{scenario, mock}`. Stateless: nada é salvo. Entra no rate-limit. |
| `POST /game/art/brief` | `api.py:1616` | `ArtBriefRequest`. Monta o brief e o prompt renderizado **sem chamar provedor** (`provider_called:false`). |
| `POST /game/new` | `api.py:1836` | `CreateCharacterRequest` (nome 1-80, raça/classe/região validadas contra catálogos, nível 1-20, backstory ≤2000, appearance ≤1000, visual_exclusions ≤500, `scenario: StartScenarioIn?`, `action_id`). Resposta `GameResponse`. |
| `POST /game/combat-simulator` | `api.py:1467` | `CombatSimulatorRequest` (classe, nível, `enemy_id`, quantidade). Cria arena isolada (`_build_combat_simulator_state`, `api.py:1338`); resposta `GameResponse`. |

### 2.4 Turno

| Rota | Linha | Payload / resposta |
|---|---|---|
| `POST /game/action` | `api.py:2486` | `ActionRequest`: `input_text` (≤2000), `game_id?`, `action_id?`, e seleção tática: `card_id`, `target_id`, `ruptura`, `reaction_card_id`, `action_kind` (`attack|maneuver|pass|flee`), `maneuver` (`engajar|desengajar|guardar|esconder|procurar`). Resposta `GameResponse`. |
| `POST /game/action/stream` | `api.py:2610` | Mesmo corpo; resposta `text/event-stream` (ver §3). |
| `POST /game/death` | `api.py:2497` | `DeathChoiceRequest{game_id?, choice: "continue"|"accept", action_id?}`. Resposta `GameResponse`. |
| `POST /game/equip` | `api.py:2630` | `{item_id? | unequip_slot?, game_id?, action_id?}`; validação 100% Python (`inventory.equip/unequip`). Resposta `{ok, equipment, inventory, derived:{ac,attack}}`. |
| `POST /game/levelup` | `api.py:2675` | `{choice_id, card_id?, evolve_card_id?, caminho?(A|B), virtude?, attr?, subclass_id?, virtue_card_id?, game_id?, action_id?}`; `progression.apply_choice`. Escolha de subclasse grava `subclass_chosen` no `event_log` e um milestone na crônica. Resposta `{ok, player_stats:{...}}`. |

### 2.5 Leitura e gestão de saves

| Rota | Linha | Propósito |
|---|---|---|
| `GET /game/state?game_id=` | `api.py:1530` | Carrega o jogo (sem `game_id` → o save mais recente). 404 se nada. Resposta `GameResponse`. |
| `GET /game/codex?game_id=` | `api.py:1549` | Codex do jogador sob demanda (`services.discovery.player_codex`), fora do `GameResponse` para não inchar. |
| `GET /game/history?game_id&cursor&limit` | `api.py:1560` | Histórico de apresentação paginado (`presentation_history.history_page`, limite 1-100); cursor `epoch:offset`; cursor de outra época → 409 `history_cursor_stale`. |
| `GET /game/saves` | `api.py:2765` | `List[SaveSummary]` `{game_id,name,class_name,level,location,day,game_over,combat_simulation,updated_at}` ordenada por mtime desc; arquivos corrompidos são pulados. |
| `DELETE /game/save/{game_id}` | `api.py:2772` | Legacy: apaga save + checkpoint + memória sob lock. Banco: exige header `Idempotency-Key` UUID, claim `delete`, `commit_delete`. 400 id inválido, 404 inexistente. |
| `POST /game/chronicle/search` | `api.py:2821` | `{game_id, query, top_k}`. Busca lexical; em banco com pgvector acrescenta candidatos semânticos. |
| `GET /game/chronicle/export?game_id=` | `api.py:2851` | Crônica em `.txt` (download) com capítulos separados por `====`. |

### 2.6 Arte dinâmica (Fase 8B)

| Rota | Linha | Propósito |
|---|---|---|
| `POST /game/{game_id}/art/player/confirm` | `api.py:1699` | `{action_id, reformulation}`. Se `RPG_DYNAMIC_ART_ENABLED` está desligado → `{status:"disabled", placeholder:true}`. Limite: 1 retrato + 1 reformulação (`409 "A reformulação visual já foi usada."`). Enfileira `generate_dynamic_art`. |
| `GET /game/{game_id}/art/{generation_id}` | `api.py:1740` | Status. Banco: lê `DynamicArtRepository`, devolve URLs assinadas (TTL 300 s) para `full`/`thumb`, mapeia `generating` com worker inativo para `reconcile_required`. Legacy: lê o ledger do save. |
| `POST /game/{game_id}/art/{generation_id}/quality` | `api.py:1802` | `{approved}` → `ready` / `rejected_quality`. |

---

## 3. O fluxo do turno e o SSE em detalhe

### 3.1 `_execute_action` (`api.py:2463-2483`)

1. `lock = _game_lock(req.game_id)` (legacy).
2. `state = load_game_state(_resolve_save_file(game_id))`. `_resolve_save_file` (`api.py:392-403`) valida UUID (400) via `persistence.save_path`.
3. `_begin_turn_operation` → claim/receipt (só banco).
4. Se o `action_id` já está no ledger → devolve estado atual (idempotente).
5. `_reject_memorial`, `_reject_archived`, `death_pending` → 409.
6. `_apply_action_options` (`api.py:2327-2362`): só em combate ativo; traduz `card_id/maneuver/action_kind/target_id/ruptura/reaction_card_id` para `state["combat_declaration"] = {actor_id:"player", acao:{...}}` e `player_reaction_card_id`. Alvo ausente → primeiro inimigo vivo. No laboratório, texto livre sem seleção vira `attack` básico (sem provedor).
7. `_run_turn` → `_run_turn_collected` (`api.py:2395-2460`):
   - `_append_player_input` (mantém só as últimas 20 mensagens, `api.py:2010-2014`);
   - `deepcopy` do estado anterior;
   - `execute_graph` (`services/turn_execution.py:29-39`): sem `progress` usa `graph.invoke`; com `progress` usa `graph.stream(stream_mode=["updates","values"])`, repassa cada chunk ao callback e guarda o último `values` como estado final;
   - `resolve_turn_visual_state` (cue de primeira aparição de NPC);
   - `_enqueue_turn_art` (só se `RPG_DYNAMIC_ART_ENABLED`);
   - `_mark_action_processed`;
   - `_prepare_checkpoint` (decide `should_checkpoint` e marca `continuity.last_checkpoint_turn`);
   - `_prepare_chronicle_derivatives` (legacy: digest extrativo local);
   - `format_response`;
   - `_commit_turn` → `record_history` (presentation_history), legacy: `save_game_state` + `checkpoints.maybe_write`; banco: `commit_game` transacional com `checkpoint=True/False`; depois `_schedule_chronicle_jobs`;
   - `_log_turn` e métricas.

O grafo (`main.py:43-137`): `START` → (gate: `game_over|death_pending|archived` ⇒ `END`) → `action_guard` → `turn_prepare` → `campaign_manager` → `dm_router` → `dispatch` → {`storyteller`, `combat_agent`, `npc_actor`, `loot_agent`} → `archivist` → `turn_finalizer` → `END`. `RPG_TURN_EXECUTION=sequential` é o padrão; `concurrent` (campaign_manager e dm_router em paralelo) é experimental. Combate em simulação vai direto a `END` (sem loot nem archivist).

### 3.2 `/game/action/stream` (`api.py:2542-2627`)

- A rota (`api.py:2610`) só valida o `game_id` e abre `StreamingResponse(_stream_turn(...), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})`. Erros HTTP *depois* do início chegam como evento SSE `error`.
- `_stream_turn` emite primeiro `accepted {game_id}` e dispara uma **thread worker daemon** que chama `_execute_action(req, progress=lambda chunk: q.put(("chunk", chunk)))`. O worker é dono do lock, da execução e do save: se o consumidor desconectar, o turno ainda é gravado e o `action_id` torna seguro o fallback via POST (comentário `api.py:2547-2551`).
- O gerador lê a fila com `timeout=_SSE_PING_S=10 s`; sem nada, envia `: ping` (comentário SSE).
- Eventos:
  - `phase {node, status:"done"}` para cada nó que completa (excluindo `action_guard`, `turn_prepare`, `dispatch`, `turn_finalizer`) — vem do modo `updates` do LangGraph;
  - `route {route}` quando `dm_router` completa (`updates.next`);
  - depois da resposta final: `visual` (cue + cena), vários `narrative {chunk, done:false}` e um `narrative {chunk:"", done:true}`, e finalmente `state` (o `GameResponse` completo);
  - `error {detail, code}` em `HTTPException` (com o código HTTP) ou exceção genérica (sem `code` ⇒ o cliente assume 500).
- **Detalhe importante**: o texto **não é streaming de tokens do LLM**. O grafo roda inteiro; só depois que a `GameResponse` existe a narração é fatiada em chunks de 80 caracteres (`_NARRATIVE_CHUNK`, `api.py:2540`, loop em `api.py:2603-2608`). O que é "ao vivo" são as **fases** (`phase`/`route`) enquanto o grafo trabalha; a "digitação" é efeito cosmético do cliente (§5.4).

### 3.3 `format_response` e `GameResponse`

`format_response` (`api.py:687-778`) é a view pública do estado. `GameResponse` (`api.py:659-684`) tem: `timeline_epoch`, `portrait_generation_id`, `game_id`, `message`, `message_type` (`STORY|COMBAT|NPC|LOOT`), `player_stats` (Vitalidade/Ferimentos com aliases `hp`, Entropia, Carga do Abismo + `abyss_tier` (Médico oculto), cartas, Virtudes, `pending_choices`, `level_up`), `inventory`, `current_location`, `narrative_summary`, `last_turn_log` (últimas 5 mensagens), `simulated`, `world`, `quest`, `combat`, `npcs`, `chronicle`, `factions`, `party`, `death_pending`, `game_over`, `death`, `continuity`, `combat_simulation`, `visual`.

Blocos auxiliares: `_combat_block` (`api.py:1023`) devolve só informação **pública** do inimigo (via `bestiary_knowledge.public_panel`: Vitalidade, Esquiva, Proteção, Integridade, Cartas/resistências reveladas), zonas/posições da cena, trilha de perseguição `pressionado→afastado→quase_livre→escapou`, ferimentos do herói, cartas preparadas, `suggestions` e reações; `_world_block` (`api.py:1157`) traz relógio, fog of war, perigo, clima, luz, sobreposições de controle/ameaça, rotas bloqueadas e interiores; `_death_block` (`api.py:866`) alimenta o `DeathModal`.

---

## 4. Persistência

### 4.1 `persistence.py` (933 linhas)

- **Constantes**: `SAVES_DIR="saves"`, `SCHEMA_VERSION = 8` (`persistence.py:59`). Histórico: v2 camadas NPC; v3 5 Posturas + Entropia; v4 Virtudes/Vitalidade/Ferimentos; v5 Vitalidade canônica + aliases HP; v6 ledger visual; v7 metatempo (`continuity`); v8 crônica com IDs estáveis + progressão 1-20.
- **`save_path(game_id)`** (`persistence.py:73-88`): exige UUID e confina o caminho dentro de `saves/` (anti path-traversal). `_safe_save_path` (`persistence.py:500`) aceita legado não-UUID sanitizando o nome (fixtures/`autosave`), com `suffix=".checkpoint"` para o slot.
- **Escrita atômica** — `_atomic_write_json` (`persistence.py:514-531`): `tempfile.mkstemp` no mesmo diretório, `json.dump(indent=4, ensure_ascii=False)`, `flush()`, `os.fsync()`, `_replace_with_retry` (`os.replace` com até 6 tentativas e backoff exponencial para tolerar locks de OneDrive/antivírus, `persistence.py:40-56`); em qualquer exceção remove o temporário.
- **`_state_to_save_data`** (`persistence.py:535-633`) é a **fonte única** do dict serializado, reutilizada pelo save vivo, pelo checkpoint e por `services/game_serialization.py`. Normaliza Vitalidade de player/party/inimigos, trunca ledgers (`processed_action_ids` 64, `visual_cue_ledger` 64, etc.), serializa mensagens LangChain em dicts (`message_history`), compacta o resumo narrativo e coalesce NPCs de runtime.
- **`save_game_state`** (`persistence.py:636`): em perfil de banco usa `game_store.create/save` com versão otimista (`_storage_version`); no legacy escreve o JSON. Retorna `False` (não levanta) em falha; a API converte em `RuntimeError` → 500 (`_require_saved`, `api.py:2033-2035`).
- **`load_game_state`** (`persistence.py:683`): sem argumento carrega o save mais recente (`get_latest_save_file`); passa por `_raw_to_state` (`persistence.py:737`) que executa `migrate_state` e reconstrói as mensagens.
- **Migrações**: `migrate_state` (`persistence.py:234-247`) é pura e idempotente. Versão <4 ⇒ `_migrate_v3_to_v4` **arquiva** o save (`archived=True`, `archived_reason`) — não há conversão de atributos antigos; o save fica somente-leitura (409 em qualquer mutação). v4→v5 normaliza Vitalidade; v5→v6 cria ledger visual; v6→v7 normaliza `continuity`; v7→v8 normaliza progressão e dá IDs estáveis à crônica.
- **`list_saves`** (`persistence.py:302`) lê cada `saves/*.json` de forma tolerante (pula corrompidos), exclui checkpoints (`_iter_live_save_files`), e no perfil de banco consulta `game_store.list(principal)`.
- **`delete_save`** (`persistence.py:358`): remove save, checkpoint, memória da sessão e memória do checkpoint.
- **Checkpoint** — `save_checkpoint` (`persistence.py:842-900`): recusa se `transition_readiness` não está `ready`; reaplica `mark_checkpoint`; grava `*.checkpoint.json` com a mesma serialização; copia a memória FAISS da sessão (`save_checkpoint_memory`) e faz rollback do diretório de memória se algo falha. Em banco usa `store.save_checkpoint(principal, stored, state)`.
- **Memória do checkpoint**: `checkpoint_memory_path` (`persistence.py:396`), `restore_checkpoint_memory` (`persistence.py:440`), `capture_session_memory/restore_captured_session_memory` (`persistence.py:469/484`), usadas também pelo harness de playtest.

### 4.2 `services/checkpoints.py` (176 linhas)

Decisões D1-D8 (spec checkpoints-morte):

- `CHECKPOINT_EVERY = 10` turnos e `SAFE_DANGER = 1` (`checkpoints.py:25-26`).
- `should_checkpoint` (`:51`): grava a cada 10 turnos de mundo **ou** ao entrar numa zona segura (`danger_level <= 1` e mudou de local). Nunca se `transition_readiness` não está pronto (combate ativo ou ator em `LAST_STAND/TERMINAL/DEATH_PENDING/DEAD`, `services/actor_lifecycle.py:84-105`).
- `maybe_write` (`:79`): marca `continuity.last_checkpoint_turn` e chama `persistence.save_checkpoint`.
- Checkpoint inicial: `_create_game` grava um logo após `save_game_state` (`api.py:1998-2002`); falha apaga o save e aborta. Assim a morte sempre tem para onde voltar. Não se grava checkpoint no laboratório (`_prepare_checkpoint`, `api.py:2040-2041`).
- `resolve_death_choice(state, choice, ...)` (`:104`) — **não muta** o estado de entrada:
  - `accept`: `death_pending=False`, `game_over=True`, injeta (de forma idempotente por hash) um evento `player_died` e um milestone na crônica.
  - `continue`: obtém o checkpoint (parâmetro em memória p/ harness; ou `persistence.load_checkpoint`; ou `initial_state` — D7; ou o próprio estado), no legacy restaura também a memória FAISS do checkpoint (se o slot é anterior à spec e não tem memória, limpa o índice derivado e confia no ledger `memory_facts`), `_sanitize_legacy_combat_checkpoint` fecha cenas efêmeras, zera `death_pending/game_over` e atualiza `continuity` via `after_restore`.

### 4.3 `services/continuity.py` (metatempo)

`normalize` mantém quatro campos: `session_action_count` (ações do jogador, nunca retrocede), `timeline_epoch` (incrementa a cada restore), `last_checkpoint_turn`, `death_history` (≤32). `after_restore` (`continuity.py:40-65`) registra um `record` com `epoch`, `death_turn`, `restored_turn`, `lost_canonical_turns`, local, causa, "retained/reverted" e então `timeline_epoch += 1`. O turno canônico do mundo (`world.turn_count`) **retrocede** ao restaurar; a contagem de ações da sessão não.

### 4.4 `services/game_serialization.py`, `game_transfer.py`, `restore_effects.py`

- **`game_serialization.py`** (77 linhas): fachada comum aos stores File e Postgres. `serialize_game_state` e `deserialize_game_state` delegam (import tardio) a `persistence._state_to_save_data` / `_raw_to_state`; `canonical_json_bytes` (JSON ordenado e compacto) e `document_sha256` dão hash estável.
- **`game_transfer.py`** (161 linhas): import/export *preview-first* entre saves JSON legados e Postgres. `scan_saves` (sem escrita) classifica cada arquivo (`SavePreview{status, sha256, archived}`); `import_saves` é insert-only (reexecução idêntica pula; colisão divergente falha); `export_game` gera bundle portátil por dono com hashes independentes (eventos, itens de namespace); `verify_export` valida.
- **`restore_effects.py`** (44 linhas): executado **dentro da transação de restore** no perfil Postgres. Lê `app.game_checkpoints` e: marca como descartados (`discarded_at`, `embedding_status='discarded'`) os documentos de memória de épocas/versões posteriores ao checkpoint; cancela jobs `queued/retry/running` de compressão de crônica, de memória descartada e de arte pertencente à linha do tempo abandonada; marca `art_generations` fora do ledger restaurado como `superseded`; apaga `chronicle_digests` (reconstruíveis da crônica restaurada).

### 4.5 Perfis de runtime (`infrastructure/runtime.py:58-125`)

Tupla (game_store, memória, catálogo, blob, fila, rate-limit, auth):

- `legacy`: file, faiss, file, file, inline, memory, disabled. Só escuta em loopback (`RPG_HOST` default 127.0.0.1, `api.py:2893`).
- `local`: postgres, pgvector, postgres, **supabase** (blob), postgres, postgres, **supabase** (auth). Para desenvolvimento com Supabase Local.
- `portable`/`hosted`: postgres, pgvector, postgres, **s3**, postgres, postgres, **oidc**. `hosted` exige bind explícito (não loopback). Validações em `runtime.py:105-125` recusam combinações inválidas (ex.: blob em filesystem, sem `DATABASE_URL`, auth OIDC ausente).
- Efeitos no código: lock em memória ↔ claim/lease; sem login ↔ cookies+CSRF; `action_id` opcional ↔ obrigatório; salvar JSON ↔ `commit_game` transacional (jogo + evento + recibo + custo + job de arte na mesma transação via `effect_scope()/effects.defer(publish)`).

### 4.6 Histórico de apresentação (`services/presentation_history.py`)

`record_history` grava linhas `{id=sha256(game:epoch:turn:role)[:24], turn, epoch, role, text, type}` para a ação do jogador e a narração (idempotente: não duplica ids). `history_page` pagina 1-100 itens por cursor `epoch:offset`; save antigo sem histórico gera entradas `legacy:*` a partir das mensagens e sinaliza `partial_history:true` (o front mostra aviso).

---

## 5. Frontend (`web/src`)

### 5.1 Estrutura

```
web/src/
  main.tsx, App.tsx (595)      máquina de telas + toda a orquestração de rede/estado
  api.ts (229)                 cliente tipado da API
  http.ts (48)                 fetch com cookies, CSRF, refresh de 401
  pendingOperation.ts (42)     ação pendente em localStorage (retomada)
  lib.ts (47)                  mdLite (markdown mínimo escapado), pct, roleLabel, looksDegraded
  types.ts (700)               espelho dos DTOs do backend
  hooks/useTypewriter.ts       efeito de digitação
  components/ (25 arquivos, ~2.970 linhas)
    AuthScreen, SaveScreen, CreateScreen (519), CombatSimulatorScreen,
    PlayScreen (255), StoryLog, Hud (628, 8 abas), WorldMap, QuestsTab, CodexTab,
    CardHand, ReactionPrompt, SceneZones, WoundTrack,
    DeathModal, LevelUpModal, OnboardingHint, Banner,
    SceneArtwork, VisualArtwork, GeneratedPortrait, ArtworkDialog,
    EmberField (canvas de brasas), ornaments (Frame/Divider/Medallion)
  styles.css                   tema único, tokens OKLCH
web/tests/    http.test.mjs, pending.test.mjs (node --test), artwork.fixture.tsx
web/e2e/      critical-journeys.spec.ts (+ .yaml F01–F16), visual-surfaces.spec.ts (Playwright + axe)
```

Dependências: React 18, Vite 5, TypeScript, `motion` (animações). `npm run build` = `tsc -b && vite build`; `npm run dev` roda o servidor :5173 com proxy para :8000 (CLAUDE.md).

### 5.2 Cliente HTTP e autenticação (`http.ts`, `api.ts`)

- `http()` usa `credentials:'include'`, `Content-Type: application/json` por padrão e, em métodos mutáveis, copia o cookie `rpg_csrf` para o header `X-CSRF-Token` (`http.ts:9-18`).
- Em 401 (fora de `/auth/*`) faz **single-flight refresh**: uma promessa `refreshing` compartilhada chama `/auth/refresh`; se falha, dispara `window` event `rpg:auth-expired` (o `App` volta para a tela de login, invalida a sessão e limpa estado). Depois reexecuta a requisição original uma vez (`http.ts:21-47`). `authVersion` evita refresh redundante quando outra requisição já renovou.
- `api.ts` gera `crypto.randomUUID()` como `action_id` em `newGame`, `newCombatSimulator`, `resolveDeath`, `postEquip`, `postLevelUp`; `deleteSave` envia `Idempotency-Key`. Para turnos o `action_id` vem do `pendingOperation` (§5.3).

### 5.3 Operação pendente e retomada (`pendingOperation.ts`)

Antes de enviar uma ação, `preparePending` grava em `localStorage` (`valoria:pending:v1:{owner}:{game}`) o payload completo, o `operation_id` (UUID), um SHA-256 do payload ordenado (sem `action_id`) e timestamp. Se um pendente já existe para o jogo, devolve **o mesmo** (o usuário precisa resolvê-lo antes de mandar outra ação). Se a gravação falha, a ação não é enviada. Após sucesso, `clearPending`; após logout/troca de dono, `clearOwner`. Validação estrita ao carregar (formato do UUID, hex de 64 chars, tipos). É o que permite reiniciar a aba no meio de um turno e reconciliar via `GET /game/{id}/operations/{op}` sem duplicar o turno.

### 5.4 `App.tsx` — telas e fluxo

Estado: `screen ∈ {"bootstrap","auth","saves","create","simulator","play"}` (`App.tsx:41`), `data` (último `GameResponse`), `log` (entradas da narrativa), `busy/thinking/phaseLabel`, `banner`, `saves`, refs `gameId` (também em `localStorage["cronicas_game_id"]`), `session` (contador de geração para descartar respostas atrasadas), `owner`.

- **Bootstrap** (`App.tsx:66-101`): `getAuthConfig()`. Se `required && !authenticated` → tela `auth`. Senão `getSaves()`; com saves → `saves`, sem → `create`. Se `/game/saves` falha (API antiga) cai no modo clássico: tenta `getState` do último `game_id` em `localStorage` e oferece "Continuar jornada anterior".
- **Sessão/expiração**: `rpg:auth-expired` incrementa `session`, zera estado e vai para `auth` (`App.tsx:53-62`). `session.current` é comparado após cada `await` (`active()`) para ignorar respostas de jogos/sessões que já não são os atuais (jornada F15 `game_switch_inflight`).
- **`handleAction`** (`App.tsx:291-353`) — o turno:
  1. valida `busy`, texto e `gameId`;
  2. se há pendente com texto diferente → erro "Resolva a ação pendente antes de enviar outra.";
  3. `preparePending`;
  4. consulta `GET operations`; `completed` ⇒ não reenvia, recarrega `getState` e `loadHistory`; `running` ⇒ erro "ainda está sendo processada";
  5. empurra a fala do jogador no log e mostra o rótulo de fase inicial;
  6. `sendActionStream(...)` com `onPhase`/`onRoute` (rótulos temáticos em `PHASE_TEXTS`/`ROUTE_TEXTS`, `App.tsx:20-33`), `onVisual` (anexa a arte da primeira aparição de NPC) e `onChunk` (alimenta **uma** entrada de log em streaming);
  7. ao receber `state`: `clearPending`; se houve chunks, `finishStreamEntry` + `setData(r)`; senão `onTurn(r)`;
  8. **Fallback**: erro 4xx ⇒ relança (400/422 também limpam o pendente para o usuário editar; 409 exige resolução); qualquer outro erro (inclui falha do stream ou `error` sem código) ⇒ remove a entrada órfã e chama `POST /game/action` com o **mesmo `action_id`**. A idempotência do backend garante que o turno não rode duas vezes.
- **`onTurn`** (`App.tsx:149-180`): cria entrada `streaming:true` (ativa o typewriter), em 300 ms marca `streaming:false`, atualiza `data`, e mostra banners de "Modo simulado" (`r.simulated`) ou "Modo degradado" (`looksDegraded`) uma vez.
- **`handleContinueSave`** (`App.tsx:373-396`): `getState`, `screen="play"`, restaura pendente, concilia com `getOperation`, `loadHistory` (pagina `GET /game/history` até acabar; `partial_history` ⇒ banner).
- **`handleDeathChoice`** (`App.tsx:467-480`): `resolveDeath` → `setData(r)` → `loadHistory`; erro vira banner "A Roda hesitou: …".
- **`handleLevelUp`/`handleEquip`**: chamam a rota e fazem *merge* parcial de `player_stats` ou recarregam o estado completo (porque AC/ataque derivam do equipamento).
- **`handleDeleteSave`**: exclui, limpa `localStorage` se era o jogo ativo, recarrega a lista; sem saves ⇒ `create`.
- Render: `MotionConfig reducedMotion="user"`, `atmosphere` + `EmberField` (canvas de brasas, escondido sob `prefers-reduced-motion`), `Banner`, botão flutuante "Consultar / retomar ação pendente" quando há pendente, botão "Encerrar sessão" (apenas se auth exigida) e `DeathModal` condicional (`death_pending && !game_over && !combat_simulation.enabled`, `App.tsx:526-533`). A troca de tela usa `AnimatePresence mode="wait"` com `scale/opacity` 0.45-0.55 s.

### 5.5 Typewriter e streaming visual (`useTypewriter.ts`, `StoryLog.tsx`)

`useTypewriter(text, enabled)` avança 1-8 caracteres a cada 30 ms; aceita texto que **cresce** (chunks): preserva o prefixo já exibido e continua de onde parou. `StoryLog` renderiza cada entrada como `motion.article` (fade+blur), mostra o cursor `msg__cursor` enquanto `streaming`, aplica `mdLite` (escape HTML + `**negrito**`/`*itálico*`) via `dangerouslySetInnerHTML` (seguro porque escapa antes), separa narrações consecutivas com "❧" e rotula só falas do jogador ou tipos não-STORY (`Diálogo`, `Combate`, `Espólio`). Enquanto `thinking`, mostra três pontos e o rótulo de fase atual. Como o servidor só envia a narração depois de pronta (§3.2), a sensação de "digitação" é do cliente.

### 5.6 `PlayScreen` e o HUD

`PlayScreen.tsx` compõe:
- **Topbar**: local, relógio (`Dia N · período · clima`, chips de luz 🌑/🔦), flags `Laboratório`/`⚔ Combate`, botão `⬆ Nível!` se há escolhas pendentes, `☰ Ficha` (abre a gaveta do HUD no mobile), `Nova`/`Reiniciar`, `Sair`.
- **Placesbar**: chips "Entrar em {interior}" / "Sair para {pai}" (viram `onAction("Entro em …")`).
- **Stage**: `SceneArtwork` (capa do local) + `StoryLog` + `Hud`.
- **Dock tático** (só em combate e sem bloqueio): `CardHand`, `ReactionPrompt`, `WoundTrack`, `SceneZones`, além de `actionchips` (Engajar/Guardar/Esconder-se/Procurar/Fugir; "Ataque básico" no laboratório).
- **Barra de ação**: input + botão "Agir"/"Lutar"; desabilitada em memorial, laboratório encerrado ou queda pendente, com placeholders contextuais.
- **Modais**: `LevelUpModal` (reabre quando muda a primeira escolha pendente), resultado do laboratório, e a tela "VOCÊ MORREU" do memorial (`game_over`) com "Começar de novo"/"Ler a crônica".
- **Onboarding**: `OnboardingHint` no turno ≤1, dispensável por jogo (`localStorage cronicas_onboard_{id}`), lista exemplos de comandos.

`Hud.tsx` tem 8 abas (`Tab`, `Hud.tsx:13`): `ficha` (barras de Vitalidade/Entropia, chip de Carga do Abismo por patamar, Virtudes, equipamento/inventário com equipar/desequipar, retrato gerado), `combate` (auto-seleciona ao entrar na luta e volta a `ficha` ao sair, `Hud.tsx:30-34`), `personagens` (NPCs conhecidos/camadas), `mapa` (`WorldMap` com fog of war, selos de facção/quest/ameaça, clique para viajar), `faccoes` (reputação com sparkline), `missoes` (`QuestsTab`), `cronica` (capítulos, busca, export `.txt`) e `codex` (`CodexTab`, carregado sob demanda). Dano à Vitalidade dispara ênfase visual (`vitalityHit`).

### 5.7 Combate tático de Cartas (UI)

- **`CardHand`**: lista só cartas `type==="ativa"` preparadas; cada carta mostra custo (`{n}E`), frequência (`livre`, `1× turno`, `1× cena`, descansos), descrição, estado (Gasta/Disponível/Sem Entropia, caminho evoluído A/B), botão "Declarar Ruptura" (se `has_rupture` e `rupture_ready`) e "Jogar Carta". Alvo: `<select>` quando há >1 inimigo. O clique chama `onAction("Uso {nome}.", {card_id, target_id, ruptura, reaction_card_id})` — ou seja, **o texto é cosmético; o servidor usa o `card_id` estruturado** (`_apply_action_options`).
- **`ReactionPrompt`**: escolhe *uma* carta de Reação (ou "Passar") para a rodada; fica em estado `reactionCardId` do `PlayScreen` e viaja em todas as ações; se a carta deixa de estar pronta, o estado é limpo (`useEffect`, `PlayScreen.tsx:74-77`). O servidor só a usa se o gatilho casar.
- **`WoundTrack`** (Ferimentos leve/grave/crítico + espaços), **`SceneZones`** (zonas, distância, postura, ocultação, engajamento e trilha de perseguição).
- **Laboratório**: `CombatSimulatorScreen` escolhe classe, nível (1/3/5/10), inimigo (agrupado por categoria) e quantidade; `POST /game/combat-simulator` cria o jogo isolado (`combat_simulation.enabled`: sem planejamento de campanha, RAG, archivist, loot, XP nem checkpoints). A UI e o motor são os de produção; texto livre vira ataque básico. O resultado (VITÓRIA/DERROTA) aparece em overlay e **nunca** abre `DeathModal`.

### 5.8 Responsividade, tema e acessibilidade

- Tema dark medieval via tokens `oklch` (`styles.css:11-56`): `--bg`, `--surface` bronzeado, `--accent` dourado, `--danger` rubro, fontes Cinzel/Cinzel Decorative (títulos) e EB Garamond (corpo), `--z-hud:40`, `--z-banner:50`, `--z-overlay:60`.
- `@media (max-width: 900px)`: o `.hud` vira gaveta fixa (360px/90vw) com `translateX(100%)` que desliza ao abrir (`styles.css:804-815`). `@media (max-width: 480px)`: topbar quebra em linhas, `.hud` ocupa 100vw, botão fechar `×` visível, texto da meta do relógio escondido, `overflow-x: hidden` (`styles.css:995-1010`). Spec polish-sessao validou 390 px.
- `prefers-reduced-motion`: desliga animações/transições e o canvas de brasas (`styles.css:817-820`) e `MotionConfig reducedMotion="user"`.
- Testes: `web/tests/*.test.mjs` (HTTP refresh e pendente) e Playwright `web/e2e` com as 16 jornadas F01-F16 (auth, criação, retomada, stream, replay idempotente, mapa, NPC, combate, quest, **F10 death_recovery**, level-up, retrato, expiração de sessão, falha de rede, troca de jogo em voo, navegação responsiva) com axe-core e viewports 320/390/768/1440.

### 5.9 `frontend/` legado

`frontend/{index.html, app.js (394 linhas), styles.css}` é um cliente vanilla de zero build, sem auth/CSRF/SSE/pendentes. A API só o serve se `web/dist` não existir (`api.py:2880`).

---

## 6. Onboarding, prólogo e criação

- **`data/onboarding.json`** tem 4 chaves: `world_intro{title, paragraphs}`, `regions` (12 ids: `nova_arcadia`, `pantano_melancolia`, `deserto_zhur`, `floresta_sussurros`, `selva_xylos`, `skallgard`, `aethelgard`, `ophidia`, …), `classes` (5 Posturas) e `races` (`race_humanos`, `race_elfos`, `race_anoes_fuligem`, `race_vrel`, `race_cinzeus`, `race_osshari`). Os campos `name/bonus` das regiões espelham `origins.json` (teste anti-drift). Autoria: `docs/guias/AUTORIA.md` § Fluxo D.
- **`CreateScreen`** (`web/src/components/CreateScreen.tsx`, 5 passos + prólogo): `STEPS = ["O Mundo","Origem","Vocação","Região","Identidade"]` (`:23`).
  1. *O Mundo* (`step 0`): `world_intro` + "Começar"/"Pular introdução".
  2. *Origem* (`step 1`): cards de raça (traits mecânicos em chips via `traitEffectChips`, capa de `opts.visuals`).
  3. *Vocação* (`step 2`): cards das 5 classes.
  4. *Região* (`step 3`): cards das regiões com bônus.
  5. *Identidade* (`step 4`): nome (≤40 no input), nível, história, aparência e exclusões visuais; botão "Revisar brief visual (sem gerar/cobrar)" chama `/game/art/brief` e, se o usuário marca o checkbox de confirmação, `generate_portrait=true`.
  6. *Prólogo* (`step 5`, `requestPrologue` `:117`): "Tecer o prólogo" chama `POST /game/prologue`; mostra título do arco, texto, NPCs semente em chips; "Começar a jornada" faz `onCreate({...payload, scenario})`; "Refinar história" volta ao passo 5. Falha do prólogo volta ao passo anterior com banner (nunca trava).
  - *Fallback*: se `GET /data/onboarding` falha, `wizard=false` e a tela vira o formulário clássico de um passo (selects de raça/classe/região) que chama `onCreate` direto, sem prólogo.
  - O stepper permite navegação livre; o estado dos passos é preservado ao voltar (smoke de UI 15/15 relatado no ESTADO_ATUAL).
- **Back-end do prólogo**: `services/prologue.py` — `StartScenario{prologue, arc_title, beats(3-5), climax, opening_scene_brief, seed_npcs(0-2)}` (`prologue.py:35-52`). Os limites de tamanho **não** estão no schema enviado ao LLM (DeepSeek/Anthropic/Groq o rejeitavam e o guard caía sempre no template): o LLM recebe só descrições, `_normalize` (`:130`) trunca/normaliza em Python, e `StartScenarioIn` (`:55-68`) re-valida estritamente na borda (excesso ⇒ 422). `build_start_scenario` (`:159`) devolve `(scenario, mock)` e cai em `fallback_scenario` (`:101`) se a cadeia falhar.
- **`/game/new` com `scenario`** (`api.py:1966-1978`): `scenario_to_state_seed` (`prologue.py:214`) semeia `campaign_plan` pessoal (que sobrevive ao primeiro `campaign_manager`), título do capítulo 1, NPCs `in_scene`/`known_by_player` (alvos válidos da rota NPC no turno 1), troca a `HumanMessage` inicial pelo brief da cena de abertura e acrescenta contexto ao `narrative_summary`. Sem `scenario`, o fluxo clássico fica idêntico (CLI intacta).
- Estado inicial (`api.py:1862-1953`): ficha do `create_player_character` + `gamedata.sync_vitality`, `game_id=uuid4()`, ouro `50×nível`, Cartas conhecidas/preparadas, traits raciais, `starting_world(região, nível)`, fações semeadas (`seed_factions`), `faction_intel={}` (jogador começa sem saber de nenhuma fação), `continuity` zerado, ledgers de arte vazios e a primeira rodada do grafo (`game_graph.invoke`) que gera a cena de abertura. Depois: `mark_checkpoint` (ações da sessão = 0), `resolve_turn_visual_state` (`new:{id}`), `format_response`, `record_history(include_input=False)`, persistência e checkpoint inicial.

---

## 7. Arte (Fase 8A estática + 8B dinâmica)

### 7.1 Fase 8A — catálogo curado (`services/visual_catalog.py`, 158 linhas)

- **Fonte**: `data/visual_assets.json` (schema_version 1) carregado com `lru_cache` (`:29-38`). Cada ativo: `asset_id` (ex. `VAL-P4-CLS-ARCANISTA_CINZENTO-001`), `subject_type` (`race|class|location|npc`), `subject_id`, `title`, `alt`, `visibility`, `source{bundle,relative_path,sha256}`, `variants.thumbnail/display{url,width,height,bytes,sha256}` e `placeholder_color`. Os WebPs ficam em `web/public/art/v1/...` e levam o hash curto da fonte no nome. O catálogo importado cobre **45 ativos / 90 WebPs**: 6 raças, 5 classes, 22 locais, 12 NPCs (`docs/guias/ARTE_VISUAL.md`).
- **`_public_asset`** só devolve ativos com `visibility=="public"` e sem o campo `source` (nunca vaza caminho/hash da fonte). NPCs secretos (Thessavar, Víbora) foram excluídos na origem.
- **`creation_visuals()`** alimenta `GET /data/options.visuals` (capas de raça/classe do wizard).
- **`scene_visual(world)`** (`:73-86`): resolve a arte do local atual — `scope:"exact"` se há ativo do `location_id`; `scope:"regional"` se usa o fallback regional de `catalog.location_fallbacks` (13 locais); senão `scope:"placeholder"` (`asset:null`). O front rotula "· visão regional" quando aplicável (`SceneArtwork.tsx`).
- **Cue de NPC** — `resolve_turn_visual_state(previous, current, action_key)` (`:116-138`): entre os NPCs elegíveis (`known_by_player`, `in_scene`) e ainda não vistos (`visual_seen_entity_ids`), escolhe o NPC ativo (`active_npc_name`) ou o que acabou de entrar na cena, ordenado deterministicamente; grava no `visual_cue_ledger` (64 entradas) por `action_key` e adiciona o token em `visual_seen_entity_ids`. A identidade vem de `services/entity_identity.resolve_npc_entity_id` (IDs canônicos e aliases); NPC de runtime sem ID canônico usa o token `runtime_npc:{slug}` e fica sem arte (monograma CSS, **nunca empresta o rosto de outro**).
- **`visual_response`** (`:141-158`) reaplica o cue pelo `action_key` — por isso o retry com o mesmo `action_id` devolve o mesmo cue e há paridade POST/SSE (o SSE manda o evento `visual` antes da narração).
- **Frontend**: `SceneArtwork` (imagem `display` do local com véu, legenda do local, botão "Ampliar" → `ArtworkDialog`, fallback "Arte indisponível" em `onError`), `VisualArtwork` (retratos/capas: `srcSet` thumb+display, `sizes` por variante, `width/height` explícitos, `loading="lazy"`, monograma quando não há ativo ou a imagem falha) e `StoryLog` mostra o cue de NPC como `msg__visual` antes do texto.
- **Importador**: `scripts/import_visual_assets.py` (valida `approved + public + SHA-256`, orientação e confinamento de path; remove metadados; gera thumb/display; limites 120 KiB thumb, 300 KiB retrato, 400 KiB cena; `--check` reconstrói em temporário; `--prune` remove derivados desconhecidos). `scripts/validate_content.py` verifica identidade, visibilidade, hash, bytes e cobertura. Os PNGs originais e o ZIP do handoff **não** entram no Git nem são servidos.
- **Placeholder de sistema**: `assets/visual/system/aguardando-arte-source.png` (1024×1536) existe como composição neutra para futura lacuna de raça/classe; hoje não é publicado (o handoff cobre todas as raças/classes). Estado: Fase 8A `done` (sessão 37).

### 7.2 Fase 8B — arte dinâmica rara (opt-in, `RPG_DYNAMIC_ART_ENABLED`)

Pipeline completo, desligado por padrão (`api.py:1683-1684`, `api.py:1710`):

1. **Brief** — `services/art_brief.py`: `build_player_art_brief` (âncoras de estilo global, raça e classe de `data/dynamic_art_profiles.json`, aparência declarada pelo jogador, exclusões, restrições de pose/anatomia; reformulação inclui âncoras da subclasse), `build_npc_art_brief`, `build_epic_art_brief` (pose do catálogo curado `epic_poses`, referência ao retrato aprovado). `sanitize_visual_text` remove marcadores de papel/prompt-injection (`system:`, `ignore previous`...), blocos de código e limita tamanhos. `render_image_prompt` monta o prompt final marcando o conteúdo do jogador como "descritivo, nunca instruções".
2. **Gatilhos e orçamento** — `services/art_triggers.py`: `resolve_art_triggers` detecta (a) **primeira aparição de NPC sem arte curada** (cue com `fallback:true`, NPC conhecido e em cena) e (b) **momento épico**: novo conflito com chefe. `reserve_request` aplica: dedupe por (tipo, instância, arco), **orçamento por arco** (`NPC_LIMIT_PER_ARC=4`, **1** épica por arco) e cooldown de 15 turnos entre NPCs (`NPC_COOLDOWN_TURNS`); `subclass_chosen` nunca gera job (zero custo). `generation_id` é um UUID5 determinístico.
3. **Enfileiramento** — `_enqueue_art_generation` (`api.py:1624-1678`): reserva no ledger do estado; no perfil legacy enfileira imediatamente; em perfil de banco **adia** (`effects.defer(publish)`) para a mesma transação do turno (reserva em `app.art_generations` + job `generate_dynamic_art`, `max_attempts=3`).
4. **Worker** — `workers/dynamic_art_jobs.py::generate_dynamic_art_job`: chama o `ImageGenerator` **uma vez** (modelo pinado `gpt-image-2-2026-04-21`, `infrastructure/openai_images.py`), roda `process_image`, grava no `BlobStore` privado e devolve metadados (apenas hash do request id do provedor).
5. **Pipeline Python** — `services/asset_pipeline.py`: valida PNG/JPEG/WEBP, ≤20 MiB e ≤24 Mpx, descarta EXIF, converte para RGB e gera `full` (≤1536²) e `thumb` (≤384²) em WebP q=88; `object_key` = `users/{owner}/games/{game}/{kind}/{entity}/{asset}.{variant}.{sha12}.webp`; `can_serve` só serve `public` ou revelado.
6. **Repositório** — `services/dynamic_art.py::DynamicArtRepository` (`reserve`, `begin`, `complete`, `fail`, `set_quality`, `get`, `assets`): máquina de estados `pending → generating → ready | failed_retryable | failed | rejected_quality | superseded | refused | reconcile_required`. `begin` só reclama `pending|failed_retryable`; resultado externo incerto nunca é regenerado automaticamente.
7. **Cliente** — `CreateScreen` pede o brief revisável e uma confirmação explícita (custo possível); após `newGame`, `App.handleCreate` chama `confirmPlayerArt` (assíncrono) e injeta `portrait_generation_id`; `GeneratedPortrait` (aba Ficha) faz *polling* com backoff (2 s × 1,3^n, teto 15 s, até 30 tentativas) e renova URLs assinadas a cada 240 s; mostra rótulos de status em português. Restore na morte invalida jobs/gerações da linha do tempo abandonada (`restore_effects.py`).

---

## 8. A jornada completa do jogador, tela por tela

> Convenção: **[UI]** é o que o jogador vê; **[Rede]** a chamada; **[Back]** o que o servidor faz.

### Tela 0 — Bootstrap ("Abrindo as Crônicas…")
- **[UI]** `<main className="create" aria-busy>` com mensagem de status (`App.tsx:501-505`), fundo `atmosphere` + brasas.
- **[Rede]** `GET /auth/config`; se autenticação não é exigida (legacy), `GET /game/saves`.
- **[Back]** `auth_config` informa `required` conforme o perfil. A API legacy não tem login: `saves/` local.
- **Decisão**: sem saves ⇒ Tela 2 (criação); com saves ⇒ Tela 1b; auth exigida e sem sessão ⇒ Tela 1a.

### Tela 1a — Login/Signup (`AuthScreen`, só perfis de banco)
- **[UI]** formulário e-mail/senha (≥8 caracteres), alternância entre entrar e criar conta, mensagem de erro.
- **[Rede]** `POST /auth/login` ou `/auth/signup`; cookies HttpOnly + CSRF; depois `GET /auth/config` (para `user_id` e limpeza de pendentes do dono anterior) e `GET /game/saves`.
- **[Back]** `identity_verifier` (Supabase/OIDC) emite tokens; `_session_boundary` protege `/game*`. Expiração no meio do jogo ⇒ evento `rpg:auth-expired` ⇒ volta aqui.

### Tela 1b — "Continuar jornada" (`SaveScreen`)
- **[UI]** lista de cartões: nome, selos `⚰ memorial` e `⚔ laboratório`, classe · nível, local — dia N, botão ✕ de excluir (modal "Apagar esta saga?" com o nome do herói), "Nova jornada" e "Simular combate".
- **[Rede]** `GET /game/saves`; ao clicar: `GET /game/state?game_id=`, `GET /game/{id}/operations/{pendente}` se há ação pendente, `GET /game/history` (paginado); ao excluir: `DELETE /game/save/{id}`.
- **[Back]** `list_saves` ordenado por mtime; `history_page` reconstrói o log; saves arquivados (pré-v4) abrem em modo leitura (qualquer ação ⇒ 409).

### Tela 2 — Criação de personagem (wizard, `CreateScreen`)
- **Passo 1 "O Mundo"**: introdução de Valoria (`world_intro`), botões "Começar" e "Pular introdução".
- **Passo 2 "Origem"**: 6 cartões de raça com arte de capa e traits (ex.: bônus/resistências como chips).
- **Passo 3 "Vocação"**: 5 cartões das Posturas diante do Abismo (Devoto do Abismo, Sangromante, Corruptor, Arcanista Cinzento, Médico de Campo).
- **Passo 4 "Região"**: cartões das regiões com bônus.
- **Passo 5 "Identidade"**: nome, nível (1-20, normalmente 1), história, aparência visual, exclusões, brief de arte opcional e checkbox de confirmação do retrato dinâmico.
- **Chamadas**: `GET /data/options` + `GET /data/onboarding` (ao montar), opcionalmente `POST /game/art/brief`.
- Botão alternativo "Simular combate" leva à Tela 2b; botão "Continuar jornada anterior" quando `continueData` existe.

### Tela 2b — Prólogo (passo 6 do wizard)
- **[UI]** estado de carregamento ("tecendo…"), depois título do arco, parágrafos do prólogo, chips dos NPCs semente (tooltip com a persona), botões "Começar a jornada" e "Refinar história".
- **[Rede]** `POST /game/prologue` (rate-limited).
- **[Back]** `build_start_scenario`: 1 chamada SMART com contexto de região/classe, `_normalize` (truncagem em Python) e fallback determinístico. Nada é persistido. Cada "Refinar" que reenvia custa uma nova chamada.

### Tela 3 — Entrada no jogo: "Forjando…" → `PlayScreen`
- **[UI]** `handleCreate` muda para `play`, limpa o log e mostra `thinking` (pontos animados); falha ⇒ volta à criação com banner "Falha ao criar personagem".
- **[Rede]** `POST /game/new` (com `action_id` e `scenario`). Em seguida, se marcado, `POST /game/{id}/art/player/confirm` (assíncrono, sem bloquear).
- **[Back]** `_create_game`: cria ficha, estado inicial, semeia o cenário, roda o grafo (campaign_manager planeja o arco, dm_router/storyteller narram a abertura, archivist), grava save v8 + **checkpoint inicial**, devolve `GameResponse` (a primeira narração aparece com typewriter).

### Tela 4 — Exploração/narrativa (`PlayScreen`, estado normal)
- **[UI]**: topbar (local, `Dia 1 · Amanhecer`, clima), `SceneArtwork` com a ilustração do local (exata/regional/ausente), log narrativo com capa de NPC na primeira aparição, `OnboardingHint` no 1º turno, barra de ação "O que você faz?", HUD lateral (desktop) ou gaveta (≤900 px) na aba Ficha.
- **Ação do jogador**: texto livre (ou chips de interiores, clique no mapa "Viajo para X").
- **[Rede]** `GET /game/{id}/operations/{op}` (consulta de segurança) → `POST /game/action/stream` → eventos `accepted`, `phase`/`route` (texto temático: "O mestre consulta os arcanos…", "O narrador tece o destino…"), `visual`, `narrative`×N, `state`. Falha ⇒ `POST /game/action` com o mesmo `action_id`.
- **[Back]** grafo completo; viagem, descanso e clima são determinísticos (`world_utils`); o storyteller pode disparar um encontro; o archivist atualiza resumo e memória FAISS; checkpoint a cada 10 turnos ou ao entrar em zona segura; log `rpg.turn`.

### Tela 5 — HUD: Ficha, Mapa, Pessoas, Missões, Crônica, Codex, Fações
- **Mapa** (`GET /data/map`): nós visitados nomeados, demais "???"; clique em local conhecido envia "Viajo para {nome}"; selos de facção controladora, ameaça regional, quest ativa, rota comercial bloqueada pontilhada.
- **Crônica**: capítulos com marcos (•) e prosa (—); busca (`POST /game/chronicle/search`); exportar `.txt` (`GET /game/chronicle/export`).
- **Codex**: `GET /game/codex` apenas quando a aba está aberta e o turno mudou.
- **Equipar**: clique no item ⇒ `POST /game/equip` ⇒ recarrega o estado (AC/ataque derivados).

### Tela 6 — Combate (`PlayScreen` com `is-combat`)
- **[UI]**: véu de combate, flag `⚔ Combate`, a aba Combate do HUD assume foco (inimigos com Vitalidade/Esquiva/Proteção/Integridade públicas e Cartas reveladas, iniciativa por lado, condições), dock com `CardHand` (Cartas preparadas), `ReactionPrompt`, `WoundTrack`, `SceneZones` (e trilha de perseguição se houver fuga), chips de manobra (Engajar, Guardar, Esconder-se, Procurar, Fugir). Os botões enviam ação estruturada.
- **[Rede]** mesmo `POST /game/action/stream` com `card_id/target_id/ruptura/reaction_card_id/action_kind/maneuver`.
- **[Back]** `_apply_action_options` ⇒ `combat_declaration`; `combat_agent` resolve tudo em Python (`services/conflict_orchestrator`: 2d10 + Virtude contra Esquiva, Cartas, Reações, Ferimentos, IA tática dos inimigos, Entropia/Carga) e só a narração usa LLM. Ao vencer: `next="loot"`, XP, possível `pending_choices` de level-up. Fugir usa a trilha de perseguição.

### Tela 7 — Level-up (`LevelUpModal`)
- **[UI]** quando `pending_choices` aparece (fora de combate): título dinâmico — "Escolha sua subclasse" (nível 3, irreversível), "Expanda seu Acervo" (Carta + evolução A/B), "Fortaleça uma Virtude" ou "Aprofunde uma Carta de Virtude" (Maestria). Pode adiar com "Depois" (reabre via `⬆ Nível!`).
- **[Rede]** `POST /game/levelup`.
- **[Back]** `progression.apply_choice` (validação total); subclasse grava evento e marco de crônica; resposta traz `player_stats` atualizado, mesclado no cliente.

### Tela 8 — A queda (`DeathModal`)
- **Gatilho no back**: `combat.py:1025` (`result["death_pending"] = True`, com `combat.death_context` = última ação, entrada em Estado Terminal, estabilização, matador) após o fluxo rico de morte (Última Ação → Terminal → até 2 estabilizações) em `death_flow`; ou `storyteller.py:963` quando um descanso/ambiente mata (`rested_player.dead`). O combate é encerrado, `enemies=[]`, `next=None` (sem loot). Registra evento `player_downed`. **Não** há `game_over` ainda.
- **Efeito imediato**: o grafo recusa novos turnos (gate de `START` em `main.py:63-67`) e a API devolve 409 em action/equip/levelup/art ("Você tombou. Resolva a tela de morte.").
- **[UI]** `App` renderiza `DeathModal` (overlay com sigilo ☠, título "Você tombou", resumo): Última ação (ex.: "Carta X"), Estado Terminal (atravessado/não), Estabilização, "Queda diante de {killer}", **Retorno: turno N**, **Progresso revertido: M turno(s)**, e as listas "Mantém" (histórico de mortes, contagem de ações da sessão) e "Reverte" (mundo, inventário, posição e memória após o checkpoint). Dois botões: **"Continuar do checkpoint"** e **"Aceitar a morte"**. Não aparece no laboratório nem em memorial.
- Os números de "Retorno/Progresso" vêm de `_death_block` (`api.py:866-896`): `will_restore_turn = continuity.last_checkpoint_turn`, `will_lose_turns = max(0, turno_canônico − checkpoint)`.

### Tela 9 — Restore (continuar)
- **[Rede]** `POST /game/death {choice:"continue", action_id}`; depois `GET /game/history` para reconstruir o log.
- **[Back]** `game_death` (`api.py:2497`): lock, claim (`kind="death"`), `_reject_archived`, 409 se não há `death_pending`, `checkpoints.resolve_death_choice(state,"continue")` ⇒ carrega `saves/{id}.checkpoint.json`, restaura a memória FAISS do checkpoint, sanitiza, zera `death_pending`/`game_over`, `continuity.after_restore` (`timeline_epoch+1`, `death_history` ganha o registro), `format_response`, `_commit_state_mutation` (save; em banco também executa `restore_effects`: descarta memória/jobs/arte da linha do tempo abandonada).
- **[UI]** o modal fecha, `data` é substituído, o log é recarregado do histórico (cursor de época anterior fica obsoleto, 409 `history_cursor_stale`); o jogador volta ao ponto do checkpoint (a cada 10 turnos ou ao entrar numa zona segura; sem nenhum — o checkpoint inicial).
- **Efeitos persistidos**: `timeline_epoch` sobe, o contador de ações da sessão não retrocede, `world.turn_count` volta, e o histórico de mortes permanece.

### Tela 10 — Aceitar a morte (memorial)
- **[Rede]** `POST /game/death {choice:"accept"}`.
- **[Back]** `game_over=True`, `death_pending=False`, evento `player_died` + milestone "o fim foi aceito" na crônica.
- **[UI]** overlay "VOCÊ MORREU" com "Começar de novo" e "Ler a crônica" (abre o HUD na crônica). O save fica como **memorial** (selo ⚰ na lista de saves, qualquer mutação ⇒ 409).

### Tela 11 — Sessão e nova jornada
- "Nova" (`handleNew`) incrementa `session`, limpa pendente e volta à criação (ou ao laboratório se era simulação). Excluir saves, "Encerrar sessão" e expiração de autenticação retornam às telas 1a/1b/2.

---

## 9. Pontos de atenção e observações do código

1. **Streaming "falso" por design**: a latência real do LLM só é mascarada por `phase`/`route`; a narração é fatiada depois (`api.py:2603-2608`). Se o objetivo futuro for token streaming, o grafo precisaria emitir tokens via `stream_mode="messages"`/callbacks — hoje não faz.
2. **`game_death` repete `_reject_archived`** (`api.py:2514` e `2517`) e um `try/except` que só serve para `_fail_operation`; é inofensivo, mas é código duplicado.
3. **Fallback do stream** (`App.tsx:333-345`): erros 4xx *não* caem para o POST; se o servidor devolver `error` sem `code` (exceção genérica) vira 500 no cliente e o POST de fallback é disparado — seguro por causa do `action_id`, mas no perfil legacy o ledger só marca o id **depois** do save bem-sucedido, então uma queda no meio pode reexecutar o turno (a idempotência é por commit, não por início).
4. **Rate limit legacy é por IP em memória** (não compartilhado entre workers) — os perfis de banco usam Postgres.
5. **`list_saves` no legacy** lê todos os JSONs a cada chamada (O(n) em disco); com muitos saves da suíte/fixtures históricas (`ESTADO_ATUAL`: 1.390 arquivos preservados) isso pode ficar lento; a suíte atual isola `saves/` em `tmp_path`.
6. **Arte dinâmica depende de `RPG_DYNAMIC_ART_ENABLED`** e de infraestrutura de fila/blob; no legacy `inline` queue, o fluxo existe, mas a validação real ponta a ponta de geração paga foi deliberadamente não executada (ESTADO_ATUAL).
7. **`GET /game/state` sem `game_id`** carrega o save mais recente (por mtime/ctime) — útil para CLI, mas ambíguo em multiusuário; os perfis de banco filtram pelo principal.
8. **Mock/degradado**: o front avisa uma vez com banners quando `simulated` ou quando a narração parece vir do fallback (`looksDegraded`: "erro ai", "indisponível"...).

## 10. Mapa rápido de arquivos citados

- API: `api.py` (`:68` CORS, `:87` sessão, `:437` rate-limit, `:687` format_response, `:1836` /game/new, `:2463` _execute_action, `:2497` /game/death, `:2546` _stream_turn, `:2765` saves).
- Persistência: `persistence.py` (`:59` schema, `:73` save_path, `:234` migrate_state, `:514` atomic, `:535` serialização, `:842` checkpoint), `services/checkpoints.py`, `services/continuity.py`, `services/game_serialization.py`, `services/game_transfer.py`, `services/restore_effects.py`, `services/presentation_history.py`, `services/turn_execution.py`, `services/actor_lifecycle.py`.
- Infra: `infrastructure/runtime.py`, `infrastructure/postgres*.py`, `workers/dynamic_art_jobs.py`.
- Arte: `services/visual_catalog.py`, `services/art_brief.py`, `services/art_triggers.py`, `services/asset_pipeline.py`, `services/dynamic_art.py`, `data/visual_assets.json`, `data/dynamic_art_profiles.json`, `web/public/art/v1/`, `assets/visual/system/`, `scripts/import_visual_assets.py`, `docs/guias/ARTE_VISUAL.md`.
- Onboarding/prólogo: `data/onboarding.json`, `services/prologue.py`, `web/src/components/CreateScreen.tsx`.
- Frontend: `web/src/App.tsx`, `api.ts`, `http.ts`, `pendingOperation.ts`, `components/{PlayScreen,StoryLog,Hud,CardHand,ReactionPrompt,DeathModal,LevelUpModal,SaveScreen,CombatSimulatorScreen,SceneArtwork,VisualArtwork,GeneratedPortrait}.tsx`, `styles.css`, `web/e2e/critical-journeys.yaml`.
- Legado: `frontend/app.js`.
