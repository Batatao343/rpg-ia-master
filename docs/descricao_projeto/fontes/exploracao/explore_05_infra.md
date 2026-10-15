# Infraestrutura local-first / Fase 10b / Operação — como funciona

Escopo: `infrastructure/`, `workers/`, `supabase/`, `infra/`, `observability/`, serviços de turno durável, CI, backup/restore, concorrência e latência. Todos os caminhos são relativos à raiz `C:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master`. Nada foi modificado. Tudo abaixo foi lido no código; onde a afirmação vem só de docs/specs, está dito.

---

## 1. Visão geral e filosofia

A Fase 10b (specs SPEC-103..111, plano mestre SPEC-108) transforma um motor que gravava JSON + FAISS em disco, com `threading.RLock` por processo, num **data plane substituível**: o domínio fala com **portas** (Protocols Python), e adapters concretos implementam cada porta para dois mundos:

- **legacy** (CLI, testes, playtest, loopback): arquivos JSON, FAISS, fila inline, identidade fixa, lock em processo.
- **local / portable / hosted**: Postgres (+pgvector) como fonte de verdade de jogo, catálogo, fila, rate limit e memória; blobs em Supabase Storage ou S3; identidade por Supabase Auth ou OIDC.

Decisões estruturais registradas nas specs (SPEC-108, SPEC-111) e confirmadas no código:

1. `GameState` v7 continua um documento JSONB canônico (SPEC-109 R1); colunas próprias só para identidade/versão/projeções operacionais. Postgres não reimplementa o schema (`infrastructure/postgres.py:69-72` usa `serialize_game_state` de `services/game_serialization.py`).
2. **Nenhuma transação aberta durante chamada de LLM.** A mutação é em duas fases: `claim` (transação curta) → grafo roda fora de transação → `commit_game` (segunda transação curta que reverifica lease+versão). Comentário literal em `infrastructure/postgres_turns.py:127-130`.
3. Cálculo é at-least-once em falha; **commit é exactly-once por idempotency key** (SPEC-111 §1).
4. Memória de longo prazo vira **fato bruto durável + job de embedding** (outbox), não escrita direta no índice (SPEC-107).
5. Supabase Local é só ensaio zero-custo; o código não depende da SDK Supabase para o domínio (só dois adapters finos: `supabase_identity.py`, `supabase_blob.py`). O perfil `portable` troca por OIDC + S3.

---

## 2. Portas e contratos (`infrastructure/contracts.py`, 277 linhas)

O módulo é deliberadamente sem imports de psycopg/Supabase/S3/FAISS (docstring `contracts.py:3-4`).

**Erros de domínio** (`contracts.py:16-45`): `InfrastructureError` → `NotFound`, `Conflict` (→ `StaleVersion`, `LeaseHeld`), `Unauthorized`, `Forbidden`, `PersistenceUnavailable`. A API converte `Conflict/LeaseHeld/StaleVersion` em 409 (`operation_in_progress`, `stale_version`, `operation_conflict`; `api.py:2127-2160`).

**Valores**: `Principal` (user_id, issuer, subject, local; `:49`), `StoredGame` (game_id, owner_id, schema_version, `version`, state, updated_at; `:57`), `MemoryDocument/MemoryQuery/MemoryWriteIntent` (escopos `lore|rules|session|npc|chronicle`; `:67-95`), `BlobMetadata/BlobRef`, `JobRequest/LeasedJob`, `OperationClaim` (operation_id, `lease_token`, game_id, base_version, request_hash; `:134`), `RateLimitDecision`.

**Protocols** (`contracts.py:149-251`):

| Porta | Métodos | Observação |
|---|---|---|
| `GameStore` | create/get/list/save(expected_version)/delete | controle otimista por `version` |
| `RuntimeCatalogStore` | get/list/put com `scope ∈ global|user|game` | substitui os 4 overlays mutáveis (npc_database, bestiário runtime, custom_artifacts, bestiary_knowledge) |
| `MemoryStore` | query / stage | `stage` registra intenção; não escreve direto no turno |
| `BlobStore` | put/open/signed_url/delete | |
| `JobQueue` | enqueue/lease/complete/fail | tokens de fencing por job |
| `TurnCoordinator` | claim/complete/fail | núcleo de idempotência e lease |
| `RateLimiter` | consume | |
| `IdentityVerifier` | verify | |

Helpers de validação: `validate_scope` (`:260`, combinação coerente scope/owner/game), `require_unique_document_ids`.

Há ainda `infrastructure/ports.py` (27 linhas): porta separada `ImageGenerator` (`ImageGenerationInput`, `GeneratedImage`) para a Fase 8B, implementada por `infrastructure/openai_images.py`.

---

## 3. Perfis de runtime (`infrastructure/runtime.py`, 273 linhas)

`RuntimeConfig.from_env` (`runtime.py:56-86`) lê `RPG_RUNTIME_PROFILE` (default `legacy`) e uma tabela de defaults por perfil (`:59-64`):

| Perfil | game_store | memory | catálogo | blob | fila | rate limit | auth |
|---|---|---|---|---|---|---|---|
| legacy | file | faiss | file | file | inline | memory | disabled |
| local | postgres | pgvector | postgres | supabase | postgres | postgres | supabase |
| portable | postgres | pgvector | postgres | s3 | postgres | postgres | oidc |
| hosted | postgres | pgvector | postgres | s3 | postgres | postgres | oidc |

Cada slot pode ser sobrescrito por env (`RPG_GAME_STORE`, `RPG_MEMORY_STORE`, `RPG_BLOB_STORE`, ...), mas `validate()` (`:88-129`) é **fail-closed**:

- legacy exige tupla exata de adapters legados e bind em loopback (`:90-104`).
- local/portable/hosted exigem Postgres+pgvector, catálogo/fila/rate limit Postgres, auth ativa, blob != file, e `DATABASE_URL` (`:105-117`).
- hosted recusa bind em loopback (`:118-119`); portable/hosted exigem `auth_mode=oidc` com `RPG_OIDC_USERINFO_URL` e `RPG_OIDC_ISSUER` (`:120-126`).
- `SUPABASE_SERVICE_ROLE_KEY` com prefixo `VITE_` é rejeitado (service role nunca no namespace do bundle web, `:127-128`).

`InfrastructureRuntime` (`:132-142`) agrega todas as portas + `resources` (o pool, para `close`). Dois construtores:

- `build_legacy_runtime` (`:145-161`): `FileGameStore`, `InMemoryMemoryStore`, `LegacyRuntimeCatalogStore` (aponta para `data/runtime` via `RPG_RUNTIME_CACHE_DIR`), `FileBlobStore`, `InProcessTurnCoordinator`, `InlineJobQueue`, `MemoryRateLimiter`, `FixedIdentityVerifier` (principal fixo `LOCAL_PRINCIPAL_ID`, `:34`).
- `build_database_runtime` (`:164-236`): **um único `PostgresPool` compartilhado** por GameStore, MemoryStore pgvector, catálogo, coordenador de turnos, fila e rate limiter. Escolhe `SupabaseBlobStore` (exige URL + service role no backend) ou `S3BlobStore` (boto3 opcional, `RPG_S3_BUCKET/ENDPOINT/REGION`); identidade `SupabaseIdentityProvider` ou `OidcIdentityProvider`. O embedder do pgvector é fixado em **1024 dimensões** e usa `rag.get_embeddings()` (Jina/…) com falha explícita se indisponível (`:211-221`). Qualquer exceção fecha o pool antes de propagar (`:234-236`) — "falha antes de servir".

Singleton com `RLock`: `get_runtime/set_runtime/reset_runtime` (`:246-273`); testes injetam runtime com `set_runtime`.

A API decide o modo por `_database_profile()` (`api.py:83-84`): qualquer perfil != legacy. Nesse modo, `action_id` UUID passa a ser obrigatório (`api.py:2113-2114` área, 400 se faltar) e o `_game_lock` em processo vira `nullcontext()` (`api.py:1704, 2466, 2502`...), ficando a serialização por conta do banco.

---

## 4. Adapters locais/legacy (`infrastructure/local_adapters.py`, 583 linhas)

- `FileGameStore` (`:76`): JSON atômico (`_atomic_json`, `:59`, com `_replace_with_retry` `:43` para o `WinError 5` do OneDrive/Windows).
- `JsonRuntimeCatalogStore` (`:181`) e `LegacyRuntimeCatalogStore` (`:245`): overlays de `data/runtime/` (isolados desde a spec isolar-cache-runtime).
- `InMemoryMemoryStore` (`:336`), `FileBlobStore` (`:366`, com `_safe_blob_key` `:357` contra path traversal).
- `InlineJobQueue` (`:437`): executa jobs no mesmo processo (semântica de teste/CLI).
- `MemoryRateLimiter` (`:496`), `FixedIdentityVerifier` (`:518`).
- `InProcessTurnCoordinator` (`:528-583`): claim em memória (`_active_games` por game_id, `_claims` por operation_id). Reuso de operation_id com outro principal/hash → `Conflict`; mesmo hash → devolve o mesmo claim; jogo já ativo → `LeaseHeld("campanha já possui mutação ativa")`. `complete/fail` conferem `lease_token` (fencing em memória). Não tem heartbeat nem persistência — por isso `operation_scope` usa `getattr(coordinator,'heartbeat',None)`.

`infrastructure/testing.py` (27 linhas) fornece utilitários para suítes.

---

## 5. Adapters Postgres

### 5.1 Pool (`infrastructure/postgres.py:31-51`)
`PostgresPool` embrulha `psycopg_pool.ConnectionPool` (extra opcional `postgres`; erro acionável se ausente, `:33-34`). Defaults: `min_size=0, max_size=4, timeout=5s`, `row_factory=dict_row`, `connect_timeout=5` e `options="-c statement_timeout=15000 -c lock_timeout=5000"` (`:40-41`). Esses timeouts são o motivo pelo qual `lease_heartbeat.py:56` diz "DB adapters have bounded connect/query timeouts".

### 5.2 GameStore (`postgres.py:65-232`)
- `_prepare(state)` → `(document, sha256, projection)` via `game_serialization`. `projection` preenche colunas operacionais (status, player_name, class_name, player_level, location_name, world_day, game_over, combat_simulation).
- `create` trata `23505` como `Conflict("game_id já existe")` (`:125-127`); `_insert_events` grava `event_log` na tabela `app.game_events` com `on conflict (game_id,event_id) do nothing` e, se conflitar, **compara `event_sha256`** — divergência vira `Conflict` (eventos imutáveis, `:75-101`).
- `save` usa `where version=expected_version` + `version=version+1` (`:156-172`); sem linha: `StaleVersion` se o jogo existe, `NotFound` caso contrário (`:173-180`).
- `save_checkpoint`/`get_checkpoint` (`:192-232`): upsert 1:1 por game_id em `app.game_checkpoints`, exigindo que a versão do checkpoint = versão confirmada.

### 5.3 Catálogo (`postgres_catalog.py`, 74 linhas) → tabela `app.runtime_catalog` (namespace/item_key/scope).

### 5.4 Fila (`postgres_jobs.py`, 143 linhas)
- `enqueue` (`:25-43`): `insert ... on conflict (kind,dedupe_key) do update set dedupe_key=excluded.dedupe_key returning id` → **dedupe determinístico** (o no-op update permite o `returning`). Aceita uma `connection` externa para enfileirar **na mesma transação** do commit do turno.
- `lease` (`:45-85`): CTE `picked` com `for update skip locked`, aceita `queued/retry` com `available_at<=now()` **ou** `running` com `lease_until<now()` (reclaim de worker morto), incrementa `attempts`, grava `lease_token` novo e `lease_owner`, `lease_until=now()+lease_seconds(90)`.
- `_require_running` (`:87-96`): `select ... for update` e checa `status='running'` e `lease_token` igual — é o **fencing** do job. `heartbeat/complete/fail` chamam isso.
- `fail` (`:118-132`): backoff exponencial `min(300, 2**attempts)` + jitter 0..3 s derivado do hash do job_id; vira `dead` quando `attempts>=max_attempts` (dead-letter), senão `retry`.
- `cancel` (`:134`): só `queued/retry`.

### 5.5 Coordenador de turnos (`postgres_turns.py`, 477 linhas) — o coração da concorrência
Detalhado na seção 8.

---

## 6. Schema Supabase/Postgres (`supabase/`)

### 6.1 Config e seed
`supabase/config.toml`: projeto `rpg-ia-master-local`; API 55321, DB 55322 (Postgres 17, shadow 55320), Studio 55323 (desligado), SMTP local 55324, Storage ligado com limite 20 MiB, Auth ligado (`jwt_expiry=3600`, signup aberto, anônimo desligado, senha mínima 8, `site_url` 127.0.0.1:5173), Realtime/Edge/Analytics desligados. Portas 553xx evitam colisão com o Supabase default. `seed.sql` é só `select 1;` com o comentário "Nunca inserir campanha real" (`seed.sql:1-2`): dados técnicos vão em migrations/testes.

### 6.2 Migrations (ordem cronológica, 8 arquivos)

**1. `20260819001305_game_store.sql`** — schema `app` (revoga tudo de public/anon/authenticated, `:1-3`).
- `app.games` (`:5-27`): `id`, `owner_id`, `schema_version`, `version bigint` (controle otimista), `state jsonb` (object), `state_sha256` (len 64), `status` ∈ active/death_pending/memorial/archived/simulation, colunas de projeção, timestamps; `check (state->>'game_id')::uuid = id` amarra documento à linha; `unique(owner_id,id)` para FKs compostas.
- `app.game_checkpoints` (`:31-42`): PK `game_id`, FK composta `(owner_id,game_id)` → um checkpoint por jogo (replace), com `memory_commit_version`, `timeline_epoch`, `canonical_turn`.
- `app.game_events` (`:46-58`): PK `(game_id,event_id)`, `event_sha256`.
- `app.runtime_catalog` (`:63-81`): constraint de coerência scope/owner/game e três índices únicos parciais (global/user/game, `:83-88`).

**2. `20260819001850_operations_jobs.sql`**
- `app.operations` (`:1-20`): `id` PK, `kind` ∈ new_game/turn/death/equip/levelup/delete/account_delete (depois + `art`), `status` ∈ running/completed/failed/abandoned, `base_game_version`, `committed_game_version`, `lease_token`, `lease_until`, `heartbeat_at`, `request_sha256`, `receipt jsonb`, `error_code`. É o **livro de idempotência e recibos**.
- `app.games` ganha `active_operation_id`, `active_lease_token`, `active_lease_until` (`:25-28`): o "mutex" por jogo vive na própria linha do jogo.
- `app.turns` (`:33-46`): PK `operation_id`, `unique(game_id,sequence)`, rota, `input_sha256`, versões antes/depois, `latency_ms`, `llm_cost_usd` (telemetria durável por turno; não guarda texto da ação, só hash).
- `app.jobs` (`:51-72`): `unique(kind,dedupe_key)`, status queued/running/succeeded/retry/dead/cancelled, `attempts/max_attempts`, `available_at`, lease_*; índice parcial `jobs_claim_idx`.
- `app.rate_limit_buckets` (`:79-85`): janela fixa por `bucket_key`.

**3. `20260819002358_auth_rls.sql`**
- Cria role `rpg_api` `NOLOGIN NOSUPERUSER NOBYPASSRLS` (`:3-7`); `grant rpg_api to postgres` (`:11`): a conexão do backend assume `rpg_api` somente depois de validar o JWT; a role nunca é usada diretamente.
- `app.current_owner_id()` (`:13-21`): lê `request.jwt.claim.sub` via `current_setting`, `stable`, `security invoker`, `search_path=''`.
- RLS **enable + force** em games, game_checkpoints, game_events, runtime_catalog, operations, turns, jobs (`:31-83`), com policies `owner_id = app.current_owner_id()`. Policies de games separadas por comando; as demais usam `for all`.
- `runtime_catalog`: leitura vê `global` ou próprio; escrita nunca em `global` (`:57-65`) — catálogo global é imutável para tenants.
- `rate_limit_buckets`: `revoke all from rpg_api` (`:87`) — buckets podem conter IP/owner e só a role de manutenção os toca.

Nota importante para entender o runtime: o `PostgresTurnCoordinator` usa o pool com a role de conexão do backend (não aplica `set role rpg_api` neste código); filtra explicitamente por `owner_id=%s` em todas as queries. A RLS é "defesa em profundidade" (OPERACAO_LOCAL.md: "O gameplay usa FastAPI; RLS é defesa em profundidade"), e os testes `security_local` validam o isolamento A/B.

**4. `20260819002401_pgvector_memory.sql`**
- `create extension vector with schema extensions`.
- `app.embedding_profiles` (`:3-13`): id, provider, model, dimensions, `metric='cosine'`, status building/active/retired/failed; semente `local-1024` / `deterministic-test` (`:15-17`).
- `app.memory_documents` (`:19-48`): `id text` PK, `owner_id/game_id/npc_id`, `scope`, `content`, `content_sha256`, `metadata`, proveniência (`provenance, confidence, source_id, source_turn, canonical_entity_ids`), `visibility` public/hidden/secret, `timeline_epoch`, `commit_version`, `embedding_profile_id`, `embedding vector(1024)`, `embedding_status` ∈ pending/ready/failed/discarded, `search_text tsvector` **generated stored** (`to_tsvector('simple', content)`), `discarded_at`. CHECK de escopo (`:43-47`): lore/rules sem owner/game/npc; session/chronicle com owner+game; npc com owner+game+npc_id.
- Índices: HNSW cosseno parcial (`embedding_status='ready' and discarded_at is null`), btree por escopo, GIN para FTS (`:50-57`).
- RLS: leitura de lore/rules para qualquer um, privados só do dono; escrita só em session/npc/chronicle do dono (`:61-74`).

**5. `20260819002404_blob_assets_chronicle.sql`**
- `app.assets` (`:1-25`): kinds player/npc/location/item/monster/epic; variants full/thumb; status pending_upload/processing/ready/rejected/delete_pending/deleted/orphaned; `bucket`, `object_key` único, mime, bytes, dimensões, sha256, proveniência (`source_provider/model`, `prompt_sha256`), `moderation`.
- `app.chronicle_digests` (`:40-52`): resumo comprimido por capítulo, `unique(game_id,timeline_epoch,chapter_id,source_hash,profile_version)` → idempotente por conteúdo.
- `app.art_generations` (`:60-84`): máquina de estados da geração de arte (pending → generating → ready/failed_retryable/failed/refused/rejected_quality/superseded), `trigger_kind` ∈ player_portrait/npc_first_appearance/arc_epic_moment, unique `(game_id,timeline_epoch,trigger_kind,trigger_instance_id,profile_version)` (impede cobrança dupla), `attempt_count<=3`, `cost_usd`.
- RLS ligada e forçada nas três.

**6. `20260820113242_dynamic_storage_bucket_rls.sql`** — cria bucket privado `rpg-dynamic` (20 MiB, só `image/webp`, `:4-15`) e 4 policies em `storage.objects` (select/insert/update/delete) para `authenticated`, restritas a chaves `users/<auth.uid()>/...` (`:17-52`). O backend usa service role; as policies são defesa em profundidade para uploads assinados futuros.

**7. `20260828163000_drop_redundant_operations_unique.sql`** — remove `operations_owner_id_id_key`. Motivo no comentário: `id` já é PK; ter um segundo árbitro de unicidade fazia o `ON CONFLICT` depender de qual índice o Postgres reportasse primeiro (corrida de idempotência).

**8. `20260926132501_audit_art_operation_kind.sql`** — recria o CHECK de `operations.kind` adicionando `'art'` (aditivo; veio com o bug "CHECK de operações sem `art`" do ESTADO_ATUAL).

### 6.3 Testes pgTAP (`supabase/tests/valoria_rls_test.sql`, 85 linhas, `plan(14)`)
Roda dentro de `begin; ... rollback;` com `pgtap`. Os 14 asserts: `rpg_api` existe sem BYPASSRLS; sem `CREATE` no DB; bucket `rpg-dynamic` privado; limite 20971520; RLS enable+force em `games`, `memory_documents`, `assets`; 4 policies `rpg_dynamic_%` em `storage.objects`; `rpg_api` sem SELECT em `rate_limit_buckets`; policies de UPDATE de games/assets/memory com `USING` **e** `WITH CHECK` não nulos; `anon` e `authenticated` sem `USAGE` no schema `app`. Resultado registrado: pgTAP 14/14 (`docs/operacao/readiness/readiness-local.md`, G1).

---

## 7. Identidade, sessão e CSRF

- `services/auth_sessions.py` (98 linhas): cookies HttpOnly `rpg_access`, `rpg_refresh`, `rpg_csrf` (`:21-23`) — o browser **não guarda bearer token**. `CsrfSigner` (HMAC-SHA256, segredo ≥ 32 chars `RPG_SESSION_SECRET`, `:41-57`) emite `nonce.assinatura`. `validate_mutation_request` (`:60-76`) exige `Origin` presente e na allowlist, cookie CSRF == header `X-CSRF-Token` (compare_digest) e assinatura válida. `cookie_settings` (`:79-85`): refresh com `SameSite=Strict` e `path=/auth/refresh`. `principal_from_session` confere `user_id == UUID(subject)` (`:88-94`).
- `infrastructure/supabase_identity.py` (82 linhas): HTTP direto ao GoTrue (`/auth/v1/token?grant_type=password`, signup, refresh, logout, verify) com chave publishable; sem SDK no browser. `oidc_identity.py` (67 linhas) valida via userinfo OIDC para o perfil portátil. Password grant do Supabase "não faz parte" do perfil portable (OPERACAO_LOCAL.md).
- Middleware HTTP `_session_boundary` (`api.py:87-121`): só ativo em perfis Postgres e só para paths `/game*`; verifica o cookie de acesso via `identity_verifier.verify`, exige CSRF+Origin em métodos mutáveis, e injeta `Principal` em ContextVar (`infrastructure/request_context.py`, `current_principal`/`principal_scope`) e no `correlation_scope(owner_id=...)` para telemetria. Falha → 401. Rotas de auth: `/auth/config`, `/auth/login`, `/auth/signup`, `/auth/refresh`, `/auth/logout` (`api.py:168-267`).
- Rate limit Postgres: `PostgresRateLimiter.consume` (`postgres_turns.py:446-477`) faz **upsert atômico de janela fixa**: um `INSERT ... ON CONFLICT DO UPDATE` reinicia a janela se expirou, senão incrementa; devolve `allowed = count<=limit`, `remaining`, `retry_after`. Sem race (um statement só).

---

## 8. Turnos duráveis, idempotência, lease e fencing

### 8.1 Fluxo de uma mutação no perfil durável (`api.py`)
1. `_begin_turn_operation` (`api.py:2106-2160`): exige `action_id` UUID; calcula `request_hash` (`_operation_hash`); **primeiro consulta recibo** (`coordinator.receipt`, `postgres_turns.py:348-364`) — se já completou, devolve a resposta gravada sem rodar o grafo (retry exactly-once). Senão `claim`. Se `claim` falhar com `Conflict`, **relê o recibo** (corrida: outro request pode ter acabado de commitar) antes de traduzir em 409.
2. `operation_scope` + `effect_scope` abrem o contexto (heartbeat + outbox).
3. O grafo roda (`execute_graph`).
4. `_commit_turn` / `_commit_state_mutation` (`api.py:2215-2260`) → `commit_game`. Qualquer exceção chama `coordinator.fail(claim, ...)`.

### 8.2 `claim` (`postgres_turns.py:28-112`)
Uma transação:
1. **Ordem de locks fixa: game → operation** (comentário `:42-45`: inserir a operação primeiro tomaria um FK lock compartilhado em `games` em dois contendores, que depois deadlockariam ao subir para `FOR UPDATE`). `select * from app.games where id and owner_id for update`; `NotFound` se não é do dono.
2. `base_version` ≠ `version` atual → `StaleVersion` (cliente com estado velho).
3. Se `active_operation_id` é outra operação e `active_lease_until > now()` → `LeaseHeld("game_busy")` (**single-flight por jogo**). Lease expirado é tomável.
4. `insert into app.operations ... on conflict do nothing returning id`; depois `select ... for update` da operação. Se `owner_id` difere → `Conflict("idempotency key indisponível")` (não vaza existência).
5. Se não inseriu (retry): hash diferente → `Conflict` (chave reutilizada com request divergente); game/kind/base_version diferentes → `Conflict`; `completed` → `Conflict("operation_completed")` (a API converte em recibo); `running` com lease fresca → `LeaseHeld("operation_in_progress")`; senão **retoma**: atualiza com novo `lease_token` e `lease_until` (takeover pós-crash).
6. Grava `active_operation_id/active_lease_token/active_lease_until` na linha do jogo.

Lease padrão 180 s (`__init__`, `:24`).

### 8.3 `commit_game` (`:114-245`)
Uma transação, todo fora de LLM:
1. Lock do jogo e da operação; **fencing**: `status='running'` e `lease_token` igual ao do claim, senão `LeaseHeld("fencing token inválido")` (`:149-151`) — um worker "atrasado" cujo lease foi tomado não consegue publicar.
2. Se `timeline_epoch` do novo documento > antigo (restauração de checkpoint/morte) → `restore_effects` (`services/restore_effects.py`) **na mesma transação**.
3. `update app.games set version=version+1, state=..., ... where id and owner_id and version=%s(base) and active_operation_id=%s and active_lease_token=%s` — **dupla barreira**: versão otimista e token de fencing. 0 linhas → `StaleVersion`.
4. `effects.flush(...)`: escreve as intenções de memória acumuladas (outbox) e writes diferidos, marcados com `commit_version` e `epoch`.
5. `_insert_events`, checkpoint opcional (upsert), linha em `app.turns` (`sequence=committed_version`), operação `completed` com `receipt` (+`committed_version`) e `lease_token=null`, limpa `active_*` do jogo.

Variantes: `commit_create` (`:247-315`, cria jogo+eventos+checkpoint inicial+recibo; operação "desacoplada" de game_id), `commit_delete` (`:317-346`, operação sem game_id para preservar o recibo depois que o jogo some via cascade).

### 8.4 `heartbeat`, `complete`, `fail`
`heartbeat` (`:366-389`) renova `lease_until` na operação e em `games.active_lease_until`, travando a linha do jogo antes; `rowcount != 1` → `LeaseHeld`. `complete/fail` (`:391-443`) idem com o mesmo token. Todas as operações de fim travam o jogo primeiro (mesma ordem de locks).

### 8.5 `services/turn_execution.py` (40 linhas)
- `operation_scope(coordinator, claim)` (`:11-26`): context manager que, se o coordenador tem `heartbeat`, abre `keep_lease_alive` com intervalo `lease_seconds/4` (45 s para lease de 180 s). Em qualquer `BaseException` chama `coordinator.fail(claim, type(exc).__name__)` engolindo falha de fence ("Fence may already belong to another worker") e re-lança.
- `execute_graph(graph, state, progress=None)` (`:29-40`): sem callback usa `graph.invoke`; com callback usa `graph.stream(stream_mode=['updates','values'])` (SSE) e retorna o último `values`.

### 8.6 `services/lease_heartbeat.py` (56 linhas)
`keep_lease_alive(renew, interval_seconds)`: faz um tick síncrono inicial (`:47-48`), sobe uma thread daemon `lease-heartbeat` que renova a cada intervalo. Se `renew` lança, marca `LeaseWatch.lost` e **para** (`:34-37`); incrementa `rpg_lease_renewals_total{outcome=ok|lost}`. Na saída do bloco chama `watch.check()` (`:52`) → `LeaseHeld("lease_lost")`: **um turno que perdeu o lease durante o LLM não deve commitar**. O banco continua sendo a autoridade final (docstring). `thread.join()` no `finally` é seguro por causa dos timeouts do pool.

### 8.7 `services/job_fence.py` (29 linhas)
ContextVar com o `LeasedJob` corrente. `job_scope(job)` (usado em `JobWorker._run`) o define; `require_job_fence(connection)` (`:23-29`) é chamado por escritas derivadas (ex.: persistir embedding, resumo de crônica, arte) para **travar a linha do job (`_require_running`) dentro da mesma transação da escrita**. Resultado: um worker que perdeu o lease não consegue publicar efeitos derivados. Chamadas diretas de manutenção (sem job) são permitidas.

### 8.8 `services/operation_recovery.py` (48 linhas) e `scripts/recover_operations.py`
`orphan_operations` lista `status='running' and lease_until < now()` (opcional por owner). `abandon_expired(pool, operation_id)` marca **uma** operação expirada como `abandoned` (`error_code='operator_abandoned'`) e libera `games.active_*` se ainda for a ativa (`:29-47`); recibos completos são imutáveis (só atua em `running` expirado). CLI é **preview-first**: sem `--apply` só imprime; `--abandon <uuid> --apply` age (`recover_operations.py:22-30`). O runbook diz para abandonar só leases expirados.

### 8.9 Outbox / memória (`services/turn_effects.py`, 65 linhas; `services/memory_intents.py`; `infrastructure/pgvector_memory.py`)
- `TurnEffects` é um ContextVar por request (`effect_scope`, `:48-65`). Durante o turno, o archivist/NPC chama `PgVectorMemoryStore.stage(intent)`: se há `current_effects()`, **apenas acumula** (`pgvector_memory.py:60-66`); fora de escopo escreve imediatamente em transação própria.
- No `commit_game`, `flush` (`turn_effects.py:25-45`) valida que `game_id` e `principal` batem (`effect_scope_mismatch`), carimba `commit_version` e `timeline_epoch`, sufixa o `document_id` com `:epoch:N` e chama `stage_on(connection, ...)`. Portanto **o fato de memória só existe se o turno commitou** (sem fato órfão de turno revertido).
- `stage_on` (`pgvector_memory.py:68-130`): `insert ... on conflict (id) do nothing`; se já existia, compara identidade (`intent_sha256`) e levanta `Conflict("memory_id reutilizado com conteúdo divergente")` se diferir; se novo, **enfileira job `embed_memory`** (`dedupe_key = document_id`, `max_attempts=5`) na mesma transação.
- O vetor entra depois: `workers/embedding_jobs.py` carrega o texto, chama o embedder e `set_embedding` (`:104-120`) que só atualiza se `content_sha256` e `embedding_profile_id` ainda conferem e o doc não foi descartado. Se Jina/Ollama cai, o fato fica `pending`, o turno permanece canônico e o job tenta de novo / vai a `dead`.
- `query` (`:166-200`) é **híbrido**: vetorial (cosseno HNSW, só `embedding_status='ready'`) + lexical (`websearch_to_tsquery('simple')` com `ts_rank`), mesclados por id e ordenados por score. Se o embedder falha na consulta, cai só no lexical (graceful). Filtro de visibilidade `public<hidden<secret` por `max_visibility` (`:150-157`). Escopo privado exige principal+game_id.
- `discard_after` (`:202-211`) e `restore_effects`: ao restaurar checkpoint, descartam memória pós-corte (`discarded_at`, `embedding_status='discarded'`), cancelam jobs `compress_chronicle`, de commit_version posterior ou de memória descartada, marcam `art_generations` fora do ledger como `superseded`, cancelam jobs de arte não retidos e apagam `chronicle_digests` (recomputáveis) — tudo na transação do commit (`restore_effects.py:5-44`).
- **`services/memory_retry.py` (60 linhas) é outra coisa**: fila persistida *no próprio save* (`pending_npc_memory`) de escritas `add_npc_memory` de NPC, para o perfil legacy/FAISS. Normaliza, deduplica por `(npc_id, fato)`, limita a 50 entradas, trunca npc_id a 120 e fato a 480 chars, tolera saves adulterados (`:20-48`). Ela garante retry quando a escrita RAG do NPC falha sem perder o fato, e é independente do outbox Postgres.

---

## 9. Workers (`workers/`)

- `JobWorker` (`job_worker.py`, 59 linhas): `run_once` faz `queue.lease(worker_id, kinds, 1)` (um job por vez, `:27`). `_run` abre `keep_lease_alive` (heartbeat da fila a cada `lease_seconds/4`), `job_scope` (fence) e `span("job.run")`; depois de `handler(payload)` chama `lease.check()` e só então `queue.complete`. `LeaseHeld` → retorna silenciosamente (o novo dono manda; nunca "falha" o job alheio). Outra exceção → `queue.fail(code)`, onde `code = exc.error_code` ou `handler_error`. `request_stop` para o loop (shutdown gracioso).
- `run_worker.py` (106 linhas): CLI `--worker-id`, `--once`. Registra SIGINT/SIGTERM → `request_stop`. Exige runtime Postgres e `PgVectorMemoryStore`. Três handlers:
  - `embed_memory` → `embed_memory_job` (checa `missing/discarded/already_ready`, valida 1024 dims).
  - `compress_chronicle` → `compress_chronicle_job` (`chronicle_jobs.py`, delega a `services/chronicle_compression.compress_chapter`) e `ChronicleRepository.complete`.
  - `generate_dynamic_art` → proteção contra **cobrança dupla**: `repository.begin(generation_id)` só permite uma tentativa; em exceção marca `external_result_uncertain` com `retryable=False` e re-lança (`:46-60`) — jamais transforma resultado externo incerto em outra geração paga. O job (`dynamic_art_jobs.py`) chama o `ImageGenerator`, processa variantes WebP (`process_image`), grava no `BlobStore` com chave canônica `users/<owner>/games/<game>/...` e devolve manifesto com hash do `provider_request_id`.
- Procfile: `web: uvicorn api:app --host 0.0.0.0 --port $PORT`. **Só existe processo `web`**; não há linha `worker`, não existe Dockerfile no repositório. A topologia Railway "api-web + worker com mesma imagem e outro comando" é decisão registrada na SPEC-104 (`draft`), ainda sem artefato de deploy.
- Em `local`, o worker é rodado à mão: `uv run python -m workers.run_worker` (o `__main__` do arquivo faz `sys.path.insert`).

---

## 10. Blob storage

`FileBlobStore` (local/legacy, `local_adapters.py:366`), `SupabaseBlobStore` (`supabase_blob.py`, 94 linhas, service role no backend), `S3BlobStore` (`s3_blob.py`, 65 linhas, boto3 com endpoint configurável para MinIO/R2). Todos implementam `put/open/signed_url/delete` e `put` recebe `BlobMetadata` com sha256 e `purpose`. `infrastructure/file_blob.py` é só um shim de 5 linhas. A chave de objeto sempre começa com `users/<owner>/` para casar com as policies de `storage.objects`. A arte curada (90 WebPs em `web/public/art/v1`) **não** passa pelo storage (SPEC-110 R1).

---

## 11. Observabilidade (`observability/`, `infra/observability.compose.yml`)

### 11.1 Código
- `observability/metrics.py` (121 linhas): registry em processo com **nomes e labels fechados** (`LABELS`, `:12-30`, 17 métricas). Cardinalidade controlada por construção: `rpg_turn_commits_total{outcome}`, `rpg_turn_duration_seconds{route,outcome,simulated}`, `rpg_operation_lease_age_seconds{kind}`, `rpg_lease_renewals_total{outcome}`, `rpg_db_duration_seconds`, `rpg_db_pool{state}`, `rpg_llm_attempts_total/duration/cost_usd_total{provider,tier,...}`, `rpg_rag_duration_seconds{scope,outcome}`, `rpg_memory_embedding_backlog{status}`, `rpg_jobs{kind,status}`, `rpg_job_oldest_age_seconds{kind}`, `rpg_blob_operations_total`, `rpg_backup_age_seconds{component}`, HTTP e SSE first-event. Métodos `increment/observe/set_gauge/snapshot/render_prometheus`.
- `observability/telemetry.py` (142 linhas): `new_request_id` (aceita `X-Request-Id` seguro, senão uuid4), `pseudonym` (HMAC-SHA256 truncado 16 hex com `RPG_TELEMETRY_SECRET`), **`redact`** (chaves sensíveis → `[REDACTED]`; strings: Bearer token, e-mail, URL assinada; corta em 2000 chars), `safe_json`, `correlation_scope` (ContextVar com request_id/owner/game/operation), `span()` que usa OpenTelemetry **se** o extra `observability` estiver instalado e `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` definido; exporter opcional "nunca derruba o domínio" (docstring `:124`).
- API: middleware `_correlation_boundary` (`api.py:124+`) normaliza o path trocando UUIDs por `/{id}` (evita cardinalidade) e abre `span("http.request")`; `GET /metrics` (`api.py:1223`) renderiza Prometheus e, em perfil de banco, consulta `app.jobs` para publicar gauges de backlog; `GET /health` devolve `git_sha` (usado pelo smoke pós-deploy para checar SHA).

### 11.2 Stack Docker opcional (`infra/observability.compose.yml`, 50 linhas)
Quatro serviços, todos publicando só em `127.0.0.1`, com limites de memória/CPU:
- Tempo 2.10.7 (`53200`; retenção de blocos 1 h em `tempo.yml:51`), backend local de traces.
- OTel Collector contrib 0.159.0 (`54317` gRPC, `54318` HTTP) → exporta OTLP/HTTP para o Tempo (`otel-collector.yml`).
- Prometheus v3.13.2 (`59090`), scrape a cada 5 s de `host.docker.internal:8000/metrics` (`prometheus.yml:1-9`), carregando `alerts/*.yml`.
- Grafana 13.0.2 (`53000`), acesso anônimo Viewer, provisionamento e dashboard `observability/dashboards/valoria-local.json`.
Volumes dedicados `valoria-prometheus/grafana/tempo`. Uso: `uv sync --extra observability`, `docker compose -f infra/observability.compose.yml up -d` e `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:54318/v1/traces`.

### 11.3 Alertas (`observability/alerts/local.yml`)
Sete regras: `TurnErrorRate` (`rate(rpg_turn_commits_total{outcome="error"}[5m])>0`), `TurnP95High` (`>2` s só para `simulated="true"` — SLO do modo mock), `OperationLeaseExpired` (`>90`), `JobBacklogOld` (`>60` s), `RagFailure`, `DbPoolWaiting`, `BackupStale` (`>86400` s). `local.test.yml` (promtool) tem dois cenários: todos disparam com séries ruins e todos resolvem com séries boas. Validação: `promtool check rules` / `promtool test rules` dentro do container (OPERACAO_LOCAL.md). Certificação registrada: 7 alertas verdes (G7).

---

## 12. Backup, restore, RPO/RTO

- `services/local_backup.py` (98 linhas): backup como **diretório com `manifest.json`** (versão 1) listando cada arquivo com `size` e `sha256` (`build_manifest`, `:124-138`); `write_manifest` é atômico (tmp + `fsync` + `os.replace`, `:141-153`); `verify_manifest` falha se o conjunto de arquivos mudou ou algum hash/tamanho diverge (`:156-168`); `copy_sources` e `restore_files` recusam destino não vazio (`:171-196`).
- `scripts/backup_local.py` (78 linhas): antes de tudo `_assert_local_container` inspeciona o label `com.supabase.cli.project == rpg-ia-master-local` dos containers de DB e Storage — **recusa operar fora do laboratório**. Produz: `config/migrations` + `dynamic_art_profiles.json`, `database_app.dump` (`pg_dump -Fc --schema app`), `database_platform_data.dump` (só dados de `auth` e `storage`, excluindo tabelas de migrations, audit log e buckets), `objects/` (docker cp de `/mnt` do storage), e o manifesto.
- `scripts/restore_local.py` (91 linhas): exige `--confirm-local-empty-target`, verifica o manifesto, restaura os dumps (tolera dois erros conhecidos de permissão em `buckets_vectors`/`vector_indexes`, `:55-67`, qualquer outro erro aborta; e-mails são mascarados nas mensagens), limpa e recopia os objetos do Storage. `scripts/verify_restore.py` conta linhas das tabelas-chave e confere que nenhum `state_sha256` tem tamanho != 64.
- `scripts/dev_stack.py` (208 linhas): `doctor/start/status/stop/reset --confirm-local`; usa o CLI `supabase` global ou `npx supabase@<versão>`; `_assert_unlinked` impede rodar contra projeto remoto linkado (`:76`); `status` mascara segredos (`_redact_status`).
- Metas e medição (readiness): **RPO 0** para turnos confirmados (porque o dump é do Postgres que commita atomicamente) e **RTO ≤ 30 min** como objetivo; medido **RTO 36,19 s** com DB + Auth + Storage restaurados após reset e login verificado (G6). OPERACAO_LOCAL.md afirma "RTO menor ou igual a 30 minutos".
- Ressalva: o gauge `rpg_backup_age_seconds{component=...}` existe nas métricas e há alerta, mas o código de backup lido não o alimenta automaticamente; ele depende de quem rode o processo registrar a idade.

---

## 13. Caos, carga e prontidão (G0–G7)

- `scripts/chaos_test.py` (148 linhas): cria jogo/usuário de teste e simula **expiração de lease** (força `lease_until` no passado em operação e jogo), um segundo claim que toma o jogo, e tenta commitar com o token antigo (deve falhar por fencing), além de atomicidade e jobs. Resultado registrado: 5/5 cenários convergiram (G3).
- `scripts/load_test.py` (249 linhas): N workers/processos, commits concorrentes, idempotência com a mesma chave, `JobWorker`s; falha se `commit p95 >= 250 ms` (`:193`). Registrado: 12 commits, dedupe de uma linha, 12 jobs, commit p95 32,257 ms (G4).
- Testes por marker (`pyproject.toml:70-77`): `addopts = -m "not llm_contract and not llm_playtest"` e markers `infra_local`, `security_local`, `chaos_local`, `browser_local` são **opt-in** (precisam do Docker/Supabase). `uv run pytest -m infra_local` = 13 passed (G1).
- `scripts/readiness_report.py` (130 linhas): `record_gate` grava evidência por gate (G0..G7: suíte offline, integração local, segurança local, caos, carga multiworker, soak 1.000 turnos, backup/restore, browser/build/lint/audits), com `redact` do telemetry, e `build` produz `docs/operacao/readiness/readiness-local.json` e `.md`. O relatório atual: **READY**, commit `eccb65d`, gerado 2026-08-20; G0: 1564 passed/16 skipped/14 deselected; G5: 1000/1000 turnos, 0 erros/violações, 38 transações; G7: Vite 457 módulos, browser desktop/390 px, 0 vulnerabilidades, 0 secrets, Prometheus/Grafana/Collector/Tempo e 7 alertas.

---

## 14. CI (`.github/workflows/`)

| Workflow | Gatilho | O que faz |
|---|---|---|
| `validate.yml` | push em `main`, PR | `uv sync --extra openai --extra anthropic --extra postgres`, `ruff check`, `scripts/validate_content.py`, `pytest -q`, depois Node 20 em `web/`: `npm ci`, `npm test`, `npm run build`. É o gate de merge base (extras instalados porque testes de roteamento exercitam os providers). |
| `audit-local.yml` | dispatch, push `main`, PR `main` | Job `infra-browser` (35 min): instala extras postgres/browser, Playwright Chromium, build web, **sobe a stack Supabase local (`dev_stack.py start`)**, roda `scripts/audit_local_gate.py` (infra_local + browser em stack real), sobe artifacts, `stop` com `if: always()`. Comentário: certificado remotamente em 2026-09-26 (run 36263717580, 3m27s); sem conta cloud, sem segredos de provider, sem modelo pago. |
| `eval-gates.yml` | push `main`, PR, dispatch | Job `scope` (`scripts/ci_eval_scope.py` classifica o diff em backend/frontend/protected); `protected-evaluator-review` roda no **Environment `eval-governance`** (aprovação humana) quando a régua/datasets mudam; `deterministic-evals` (governança, Project Index check, testes de eval); `backend-selective` (`playtest run --all --turns 3`); `frontend-selective` (Playwright F01–F16, `npm run test:e2e`). |
| `eval-protected.yml` | só `workflow_dispatch` | `real-provider-short` (Environment `eval-provider`, exige `GOOGLE_API_KEY`; contrato real manual com teto de requests/custo conforme ESTADO_ATUAL: 20 requests/US$ 0,20) e `private-holdout` (Environment `eval-holdout`, clona repo privado de holdout; só agregados). |
| `post-deploy-smoke.yml` | só dispatch | Environment `post-deploy-smoke`; `scripts/post_deploy_smoke.py` read-only, verifica o SHA de `/health`. |

Observações verificáveis:
- **O scanner de segredos, `pip-audit` e `npm audit` NÃO estão em nenhum workflow nem script versionado** (grep por `pip-audit|npm audit|gitleaks|detect-secrets` em `.github`, `scripts`, `docs/*.md` e `pyproject.toml` não achou nada). Os resultados "0 vulnerabilidades / 0 secrets" aparecem só como evidência textual do G7 em `docs/operacao/readiness/readiness-local.md`, ou seja, foram rodados manualmente. Se o objetivo for gate contínuo, falta automatizar.
- Não existe `Dockerfile` nem `Procfile` com processo `worker`; CI não constrói imagem.
- `validate.yml` não roda os marcadores `infra_local/security_local/chaos_local` (só o `audit-local.yml`, via o gate de auditoria).

---

## 15. Segurança — resumo dos controles reais

1. **Isolamento por dono**: toda query durável filtra `owner_id`; RLS forçada em 11 tabelas; `rpg_api` NOLOGIN/NOBYPASSRLS; `anon/authenticated` sem `USAGE` em `app`; pgTAP prova isso.
2. **Sessão**: tokens só em cookies HttpOnly, CSRF assinado + Origin allowlist em mutações, refresh restrito a `/auth/refresh` com SameSite=Strict.
3. **Service role** só no backend; guard contra `VITE_`.
4. **Idempotência sem vazamento**: chave de outro dono retorna "indisponível", não "pertence a outrem".
5. **Redaction** em logs/relatórios: JWT, e-mail, URL assinada, prompt/narrativa não vão para telemetria; turnos guardam só `input_sha256`.
6. **Backup/restore**: recusa containers fora do label local, destino vazio, manifesto SHA-256.
7. **Rate limit** por bucket em Postgres, tabela inacessível ao tenant.
8. Limite: o coordenador não executa `SET ROLE rpg_api` por request neste código; a proteção primária é o filtro explícito `owner_id` + `Principal` vindo do middleware; a RLS é a segunda camada exercida nos testes de segurança.

---

## 16. Concorrência de turnos e latência (SPEC-143)

**Entre requests** (mesmo jogo): no perfil legacy, `_game_lock(game_id)` (`api.py:305`, RLock por game_id) serializa; no durável, o mutex é `games.active_operation_id/active_lease_*` + `FOR UPDATE` (single-flight por jogo, 409 `operation_in_progress`/`game_busy` ao concorrente). Jogos distintos rodam em paralelo; um teste de carga multiprocesso confirma. A SPEC-143 diz que concorrência E2E de muitos jogos fica para uma spec de go-live futura.

**Dentro do turno** (SPEC-143, `done` com **no-go**): `main.py:76-86` lê `RPG_TURN_EXECUTION` (default `sequential`).
- `sequential`: `turn_prepare → campaign_manager → dm_router → dispatch`.
- `concurrent` (experimental): fan-out de `campaign_manager` e `dm_router` a partir de `turn_prepare`, com join em `dispatch` (`add_edge([...], "dispatch")`).
O gate R28/R29 (2026-08-28) mostrou overlap em benchmark controlado, mas **o DeepSeek real piorou** (contenção do provider quando planejamento SMART e roteamento CLASSIFY batem na mesma rota). O arquivista continua inline (resumo, fatos e memória antes da resposta); não há worker de derivação para ele. `turn_prepare` incrementa turno/continuidade uma vez; plano e rota escrevem canais disjuntos. `ainvoke` usa `to_thread`, sem cancelamento nativo de HTTP.

**SSE**: `POST /game/action/stream` usa `execute_graph(progress=...)` (`stream_mode=['updates','values']`) e o worker SSE é dono do lock e conclui mesmo se o cliente desconectar (ESTADO_ATUAL, sessão 35). `action_id` compartilhado com o POST permite replay sem duplicar turno (smoke: SSE → replay POST → mesmo recibo; payload divergente → 409).

**Single-flight de playtest** (outro mecanismo, não de jogo): `playtest/matrix_lock.py` cria `.matrix-suite.lock` atômico para impedir duas matrizes longrun simultâneas, com checagem de PID vivo (Windows via `OpenProcess`/`GetExitCodeProcess`), e `playtest/__main__.py` entra em `matrix_single_flight()`.

---

## 17. Documentação operacional e specs

- `docs/operacao/OPERACAO_LOCAL.md`: bootstrap (`dev_stack.py doctor/start/status`), `reset --confirm-local` (apaga só DB/Storage locais; nunca `supabase link`/`--linked`), gates (`pytest`, `-m infra_local`, `-m security_local`, `-m chaos_local`, `load_test.py`, `playtest run --all --turns 77`), backup/restore, observabilidade opcional, tabela de incidentes (API caiu antes do commit → repetir o mesmo `action_id`; worker morto → outro assume após lease, fencing; operação presa → `recover_operations.py` em preview; embedding/blob fora → turno continua canônico, job converge ou dead-letter; banco reiniciado → reiniciar API/worker e repetir a chave; nunca remover receipts à mão; backup inválido → não restaurar), segurança e perfil portátil (`RPG_OIDC_*`, `RPG_S3_*`).
- Specs (cabeçalhos): SPEC-108 plano mestre `done`; 105 fundação/portas `done`; 109 Postgres híbrido `done`; 111 turnos duráveis/fila `done`; 103 Auth/RLS `done`; 107 pgvector `done`; 110 storage `done`; 106 observabilidade/backup/caos `done` (todas 2026-08-20); **104 certificação cloud `draft`** — Railway alvo primário (api-web serve `web/dist`+FastAPI na mesma origem; worker privado com a mesma imagem), Render contingência, Vercel só benchmark (Services em Private Beta em 2026-08-16); R1 proíbe qualquer deploy/projeto/domínio/banco pago sem aprovação e orçamento; R4 staging descartável; R8 testes cloud-only (TLS/CORS/cookies, JWKS, e-mail, CDN/signed URL, cold start, SSE, quotas); R11 beta externo só após G0–G7 local + gates cloud. SPEC-143: ver seção 16.

---

## 18. Pontos de atenção / lacunas observadas

1. **Procfile sem worker e sem Dockerfile**: o repositório não tem artefato de deploy do worker; só está descrito na SPEC-104 (`draft`).
2. **Segurança contínua**: pip-audit/npm audit/scanner de segredos aparecem só como evidência manual; nenhum workflow os executa.
3. **Alimentação do gauge de backup**: alerta `BackupStale` existe, mas o produtor da métrica não está ligado aos scripts de backup lidos.
4. **Worker processa um job por vez** (`lease(..., 1)`, `job_worker.py:27`) — simples, mas limita throughput de embeddings; `run_once(limit)` ignora o `limit` além de zero.
5. **Dois "outbox"** diferentes: `pending_npc_memory` no save (legacy/FAISS) e `TurnEffects`+`embed_memory` jobs (Postgres). Convivem porque os perfis divergem.
6. **Coordenador não usa `SET ROLE`**: a RLS não é a barreira primária no caminho FastAPI→Postgres; depende dos filtros `owner_id` explícitos (testados).
7. **Cloud não certificada** (ESTADO_ATUAL "Limitações conhecidas"): Auth/RLS/OIDC/S3 foram provados só localmente; rede, proxy, limites e restore em Railway/Supabase remoto não foram medidos.
8. **Estado do repositório**: o git status mostra dezenas de arquivos modificados (inclui `.github/workflows/validate.yml`, `llm_setup.py`, `evals/`, etc.) e existem cópias `.tmp/spec176-*` dentro do projeto; os números de CI/readiness acima refletem o que está no working tree e nos docs, não necessariamente o último commit (`1beefc4`). A linha de readiness (commit `eccb65d`, 2026-08-20) é anterior aos blocos de ESTADO_ATUAL de setembro/outubro (SPEC-164..176, gate completo 1.898 passed) que tratam de evals, não de infra.
