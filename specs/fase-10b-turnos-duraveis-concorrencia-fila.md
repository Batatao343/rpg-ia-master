# SPEC — Fase 10b.3 — Turnos duráveis, idempotência distribuída e fila Postgres

> **Status:** `done` (2026-08-20)
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** [Postgres transacional](fase-10b-postgres-persistencia-transacional.md) `done`
> **Desbloqueia:** execução multiworker, geração assíncrona de assets e testes de caos

---

## 1. Contexto & Objetivo

O hardening atual garante idempotência apenas com `processed_action_ids` dentro
do save e `RLock` dentro de um processo. Dois workers podem carregar a mesma
versão, executar LLMs caros e confirmar resultados conflitantes. Segurar uma
transação/row lock durante 10–45 segundos de provider seria igualmente ruim.

Esta spec cria coordenação em duas fases: uma transação curta reclama a mutação
com lease; o grafo roda fora da transação; uma segunda transação verifica
lease+versão e confirma estado/eventos/memória/recibo. O cálculo é at-least-once
em falha, mas o commit é exactly-once por idempotency key.

## 2. Requisitos

- **R1 — idempotência de toda mutação:** `/game/new`, action POST/SSE, death,
  equip, levelup e delete aceitam `request_id` UUID; retry devolve o mesmo
  status/recibo sem reaplicar efeitos.
- **R2 — recibo fora do GameState:** ledger durável não depende do limite de 64
  IDs do save; o campo legado permanece só para compatibilidade/export.
- **R3 — lease sem transação longa:** claim e commit usam transações curtas. A
  chamada LangGraph/LLM nunca mantém conexão, advisory lock ou row lock aberto.
- **R4 — exclusão mútua distribuída:** uma campanha só tem uma mutação write em
  andamento. Segunda chave recebe `game_busy`; mesma chave recebe
  `operation_in_progress` ou o recibo concluído.
- **R5 — fencing:** cada lease tem token e versão base; worker atrasado não pode
  confirmar depois de lease expirado/adotado.
- **R6 — recovery:** lease expirado vira `abandoned`; a mesma `request_id` pode
  ser retomada/recomputada, sem permitir que ação posterior ultrapasse uma ação
  ambígua sem decisão registrada.
- **R7 — commit atômico:** estado, eventos, visual cue, checkpoint devido,
  intents de memória e recibo final confirmam/rollback juntos.
- **R8 — SSE resistente:** disconnect do consumidor não cancela o worker; retry
  POST/SSE com a mesma chave lê o recibo final. Pings não renovam lease; worker
  renova por heartbeat próprio com fencing token.
- **R9 — reads consistentes:** enquanto há mutação em andamento, GET retorna a
  última versão confirmada e sinaliza `operation_in_progress`, nunca estado parcial.
- **R10 — fila Postgres:** jobs usam leases, tentativas, backoff, dead-letter e
  dedupe; claim usa `FOR UPDATE SKIP LOCKED`. Nenhum Redis é exigido inicialmente.
- **R11 — rate limit distribuído:** substituir dict por limiter Postgres por
  owner/IP/rota no perfil local/hosted; headers e retry-after consistentes entre workers.
- **R12 — observabilidade:** toda operação/job registra correlation/request/game
  IDs, versões, timestamps e códigos fechados, sem salvar prompt/narrativa em log.
- **R13 — failpoints:** testes conseguem pausar/matar após claim, após grafo e
  antes/depois do commit, sem hooks de produção expostos ao cliente.

### Fora de escopo

- Executar gerador de imagem; apenas a fila/worker genérico.
- Garantir que uma LLM não seja cobrada duas vezes após crash antes do commit.
  O contrato garante efeito exactly-once, não computação exactly-once.
- Redis/Valkey, Kafka ou workflow SaaS.
- Processar vários turnos simultâneos da mesma campanha.

## 3. Design técnico

### Arquivos novos

- `services/turn_service.py` — orquestra claim→compute→commit sem FastAPI.
- `infrastructure/postgres_turns.py` — coordinator, receipts e limiter.
- `infrastructure/postgres_jobs.py` — fila/worker leases.
- `workers/job_worker.py` — loop síncrono, shutdown gracioso e heartbeat.
- `supabase/migrations/<ts>_operations_jobs.sql` — tabelas/indexes/functions mínimas.
- `tests/test_turn_service.py` — unidade/fakes/failpoints.
- `tests/test_turns_multiworker_local.py` — integração concorrente.
- `tests/test_postgres_jobs_local.py` — leases/retry/dead-letter.

### Schema

```sql
create table app.operations (
  id uuid primary key,
  owner_id uuid not null,
  game_id uuid references app.games(id) on delete cascade,
  kind text not null check (kind in ('new_game','turn','death','equip','levelup','delete')),
  status text not null check (status in ('running','completed','failed','abandoned')),
  base_game_version bigint,
  committed_game_version bigint,
  lease_token uuid,
  lease_until timestamptz,
  heartbeat_at timestamptz,
  request_sha256 text not null,
  receipt jsonb,
  error_code text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  unique (owner_id, id)
);

alter table app.games
  add column active_operation_id uuid,
  add column active_lease_token uuid,
  add column active_lease_until timestamptz;

create table app.turns (
  operation_id uuid primary key references app.operations(id) on delete cascade,
  game_id uuid not null references app.games(id) on delete cascade,
  owner_id uuid not null,
  sequence bigint not null,
  timeline_epoch integer not null,
  route text,
  input_sha256 text not null,
  state_version_before bigint not null,
  state_version_after bigint,
  latency_ms integer,
  llm_cost_usd numeric(12,6),
  unique (game_id, sequence)
);

create table app.jobs (
  id uuid primary key,
  owner_id uuid,
  game_id uuid references app.games(id) on delete cascade,
  kind text not null,
  dedupe_key text not null,
  status text not null check (status in ('queued','running','succeeded','retry','dead','cancelled')),
  payload jsonb not null,
  result jsonb,
  attempts integer not null default 0,
  max_attempts integer not null,
  available_at timestamptz not null default now(),
  lease_token uuid,
  lease_owner text,
  lease_until timestamptz,
  last_error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (kind, dedupe_key)
);
```

`rate_limit_buckets` usa chave hash, janela e contador com upsert transacional;
não armazena IP bruto além da retenção necessária.

### Fluxo de turno

```text
1. BEGIN: autenticar owner → buscar/criar operation → claim game lease + base version → COMMIT
2. carregar snapshot confirmado
3. executar grafo fora do DB; MemoryStore apenas acumula MemoryWriteIntent no UoW
4. BEGIN: SELECT game FOR UPDATE → conferir owner/version/lease token/freshness
5. persistir estado + events + checkpoint + memory intents + turn + receipt
6. limpar lease, marcar completed → COMMIT
7. responder/emitir state SSE a partir do receipt persistido
```

Falha antes de 6 não altera estado confirmado. Falha após 6 e antes da resposta
é resolvida pelo retry da mesma chave, que retorna `receipt`.

### Contrato HTTP

- Header preferido: `Idempotency-Key: <uuid>`; body legado `action_id` aceito e
  normalizado durante uma versão de compatibilidade.
- `409 game_busy|operation_in_progress|ambiguous_operation`, corpo com
  `operation_id` e `retry_after_ms`, sem detalhes internos.
- `GET /game/operations/{id}` retorna somente operação do owner.
- Recibo de action contém o `GameResponse` exato, inclusive visual cue.

### Worker/fila

O worker só conhece handlers registrados por `kind`. Payload e result têm
Pydantic schema por handler. Erro transitório usa backoff com jitter determinístico
por job; erro permanente vai a `dead`. Admin/replay é CLI local autenticada e
sempre cria audit row; não existe endpoint público de “rodar qualquer payload”.

## 4. Plano passo a passo

### Etapa 1 — Coordinator e recibos em fake

1. **Testes** (`test_turn_service.py`): retry concluído, duplicata em andamento,
   stale version, lease expirado, worker atrasado, crash nos quatro failpoints.
2. **Implementação:** serviço puro + UoW de intents.
3. **Verificação:** zero DB/LLM real.

### Etapa 2 — Postgres coordinator multiworker

1. **Testes** (`test_turns_multiworker_local.py`): dois processos/clients no
   mesmo game; uma confirmação; jogos diferentes paralelos; fencing token.
2. **Implementação:** tabelas e queries transacionais.
3. **Verificação:** nenhuma transação aberta durante barreira que simula LLM lenta.

### Etapa 3 — API POST/SSE e demais mutações

1. **Testes:** todos endpoints mutáveis aceitam chave; disconnect+retry; receipt
   exato; GET durante compute; compatibilidade de `action_id`.
2. **Implementação:** `api.py` delega ao `TurnService`; remover dependência do
   `_game_locks` no perfil Postgres.
3. **Verificação:** parity POST/SSE atual.

### Etapa 4 — Fila e rate limiter

1. **Testes** (`test_postgres_jobs_local.py`): SKIP LOCKED, lease expiry,
   heartbeat, retry/dead, dedupe, cancel, owner e shutdown; limiter entre workers.
2. **Implementação:** JobQueue/worker/limiter Postgres.
3. **Verificação:** worker kill não perde nem duplica efeito do handler fake.

### Etapa 5 — Recovery operacional

1. **Testes:** CLI lista/adota/abandona operações órfãs sem alterar completed;
   retry após restart confirma exatamente uma versão.
2. **Implementação:** `scripts/recover_operations.py` preview-first.
3. **Verificação:** cenário kill real em stack local.

## 5. Critérios de aceite

- [x] Toda rota mutável é idempotente fora do GameState.
- [x] Dois workers no mesmo jogo confirmam no máximo uma mutação.
- [x] Jogos distintos podem computar em paralelo.
- [x] Nenhum lock/conexão/transação fica aberto durante LLM/grafo.
- [x] Kill antes/depois do commit recupera sem estado parcial nem efeito duplo.
- [x] SSE desconectado conclui e retry retorna receipt persistido.
- [x] Estado/eventos/checkpoint/memória/visual/receipt confirmam atomicamente.
- [x] Fila Postgres passa leases/retry/dead-letter/dedupe multiworker.
- [x] Rate limit é consistente em dois workers.
- [x] `uv run pytest -m infra_local` e suíte offline completos verdes.
- [x] Guard de FallbackLLM permanece em todos os nós; nenhum schema LLM novo.
- [x] Cliente legado com `action_id` continua funcional no período documentado.

## 6. Smoke test com LLM real

Um turno real com barreira de observação confirma que não há transação DB aberta
durante o provider. Desconectar o stream, aguardar conclusão e repetir a mesma
idempotency key por POST deve devolver o mesmo texto/cue/versão sem nova chamada LLM.

## 7. Riscos & compatibilidade

- **Cobrança duplicada antes do commit:** inevitável em crash; telemetria marca
  recompute. Efeito mecânico continua exactly-once.
- **Lease curto/longo:** configurar acima do p99 observado, renovar por heartbeat
  com fencing e testar suspensão de máquina.
- **Receipt grande:** medir TOAST/retenção; não remover antes da janela de retry.
- **Fila no Postgres:** suficiente para volume inicial; medir locks/latência antes
  de introduzir outro sistema.
