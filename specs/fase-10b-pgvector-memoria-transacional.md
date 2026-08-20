# SPEC — Fase 10b.5 — Memória transacional em pgvector

> **Status:** `done` (2026-08-20)
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** [Postgres transacional](fase-10b-postgres-persistencia-transacional.md) `done` · [turnos duráveis](fase-10b-turnos-duraveis-concorrencia-fila.md) `done` · [Auth/RLS](fase-10b-auth-rls-isolamento.md) `done`
> **Desbloqueia:** checkpoint realmente atômico, runtime sem FAISS gravável e certificação serverless/container

---

## 1. Contexto & Objetivo

`rag.py` mantém três classes de índices: lore/regras globais, memória da sessão e
memória privada por NPC. Cada write FAISS substitui arquivos no disco e pode
acontecer dentro do grafo antes de o save JSON confirmar. O snapshot de checkpoint
copia a árvore inteira para tentar manter a timeline coerente.

Esta spec separa fato durável de embedding. O turno confirma o fato bruto e um
job de embedding na mesma transação; a vetorização pode ocorrer imediatamente ou
depois. Assim, indisponibilidade da Jina/Ollama não perde fato nem exige que o
turno finja persistência vetorial. pgvector substitui FAISS no perfil local/hosted,
enquanto `rag.py` preserva a interface e o adapter FAISS continua na suíte legacy.

## 2. Requisitos

- **R1 — três escopos equivalentes:** `lore|rules` globais, `session` por jogo e
  `npc` por jogo+NPC; filtros de visibility/proveniência mantêm a semântica atual.
- **R2 — fato atômico:** `MemoryWriteIntent` entra como row bruta junto do commit
  do turno, com `memory_id`, source, confidence, entity IDs, epoch e game version.
- **R3 — embedding desacoplado:** row começa `pending`; job idempotente grava o
  vetor e muda para `ready`. Falha fica `retry|failed`, nunca apaga texto.
- **R4 — leitura durante backlog:** busca combina vetores `ready` com FTS/exact
  match de fatos `pending`; falta de provider reduz recall, não causa amnésia total.
- **R5 — profile pinado:** um índice ativo usa provider/model/dimensão/métrica
  declarados. Default 1024 dimensões atende Jina v3 e Ollama `bge-m3`; vetor de
  dimensão diferente é recusado e exige reindex/profile novo.
- **R6 — dedupe/idempotência:** repetir o mesmo fato/job não cria row/vetor novo;
  mesmo ID com conteúdo/metadata divergente aborta e é auditado.
- **R7 — checkpoint/epoch:** restore marca como descartados fatos/jobs com commit
  posterior ao watermark do checkpoint e preserva histórico de continuidade;
  consulta nunca recupera timeline descartada.
- **R8 — isolamento/RLS:** session/NPC exigem owner+game; NPC secreto e fatos
  hidden/secret obedecem os gates atuais. Global não fica exposto ao browser.
- **R9 — ingest global reproduzível:** Codex/regras continuam fontes versionadas;
  reindex é Python, resumível, troca profile por cutover e nunca mistura dimensões.
- **R10 — migração FAISS segura:** global é reingerido da fonte; sessão/NPC pode
  extrair docstore local com preview/hash/metadata; diretório fonte não é removido.
- **R11 — paridade medida:** fixture PT-BR compara FAISS e pgvector em top-k,
  visibilidade, provenance/confidence, duplicatas e NPC namespace.
- **R12 — observabilidade:** query/write/embed emitem provider/profile, escopo,
  latência, candidatos, backlog e erro sanitizado; nunca texto do fato.
- **R13 — sem Vector Buckets alpha:** usar extensão pgvector/Postgres padrão;
  não depender de produto alpha cuja implementação local difere da hospedada.

### Fora de escopo

- Trocar os providers/rotas de embedding definidos em `rag.py`.
- Embeddings multimodais ou busca de imagem.
- Expor busca vetorial diretamente ao frontend.
- Apagar índices FAISS após migração.

## 3. Design técnico

### Arquivos novos

- `infrastructure/pgvector_memory.py` — `PgVectorMemoryStore` e queries.
- `services/memory_intents.py` — collector/UoW e normalização idempotente.
- `workers/embedding_jobs.py` — handler do JobQueue.
- `supabase/migrations/<ts>_pgvector_memory.sql` — extension/tabelas/indexes/RLS.
- `scripts/reindex_pgvector.py` — Codex/regras por profile.
- `scripts/migrate_faiss_memory.py` — sessão/NPC preview/import/verify.
- `tests/test_pgvector_memory.py` — contrato unitário.
- `tests/test_pgvector_memory_local.py` — integração/recall/checkpoint/RLS.

### Arquivos alterados

- `rag.py` — facade e `FaissMemoryStore`; funções públicas mantidas.
- `agents/archivist.py`, `agents/npc.py`, `agents/world_simulator.py` — writes
  produzem intents no runtime pgvector; caminho legacy continua físico.
- `services/context_builder.py` — consome `MemoryDocument` normalizado.
- `services/checkpoints.py`, `services/memory_retry.py` — watermark/jobs em Postgres.
- `scripts/dev_stack.py`, `pyproject.toml`, `.env.example` — profile/dimensão/markers.

### Schema

```sql
create extension if not exists vector with schema extensions;

create table app.embedding_profiles (
  id text primary key,
  provider text not null,
  model text not null,
  dimensions integer not null check (dimensions > 0),
  metric text not null check (metric in ('cosine')),
  status text not null check (status in ('building','active','retired','failed')),
  corpus_sha256 text,
  created_at timestamptz not null default now(),
  activated_at timestamptz
);

create table app.memory_documents (
  id text primary key,
  owner_id uuid,
  game_id uuid references app.games(id) on delete cascade,
  npc_id text,
  scope text not null check (scope in ('lore','rules','session','npc')),
  content text not null,
  content_sha256 text not null,
  metadata jsonb not null default '{}'::jsonb,
  provenance text,
  confidence text,
  source_id text,
  source_turn integer,
  canonical_entity_ids text[] not null default '{}',
  visibility text not null default 'public',
  timeline_epoch integer,
  commit_version bigint,
  embedding_profile_id text references app.embedding_profiles(id),
  embedding extensions.vector(1024),
  embedding_status text not null check (embedding_status in ('pending','ready','failed','discarded')),
  search_text tsvector generated always as (to_tsvector('simple', content)) stored,
  discarded_at timestamptz,
  created_at timestamptz not null default now(),
  check (
    (scope in ('lore','rules') and owner_id is null and game_id is null and npc_id is null) or
    (scope='session' and owner_id is not null and game_id is not null and npc_id is null) or
    (scope='npc' and owner_id is not null and game_id is not null and npc_id is not null)
  )
);

create index memory_embedding_hnsw_idx on app.memory_documents
using hnsw (embedding extensions.vector_cosine_ops)
where embedding_status='ready' and discarded_at is null;
create index memory_scope_idx on app.memory_documents(owner_id, game_id, scope, npc_id)
where discarded_at is null;
create index memory_fts_idx on app.memory_documents using gin(search_text)
where discarded_at is null;
```

O nome/schema de operator class é validado contra a extensão local antes da
migration final. A dimensão é configuração de schema, não variável livre por row.

### Query

```python
@dataclass(frozen=True)
class MemoryQuery:
    text: str
    scope: Literal["lore", "rules", "session", "npc"]
    principal: Principal | None
    game_id: UUID | None
    npc_id: str | None
    max_visibility: Literal["public", "hidden", "secret"] = "public"
    k: int = 3
```

O adapter gera o embedding da query com o profile ativo, filtra owner/game/scope/
visibility/discarded no SQL e ordena por cosine. Resultados FTS pendentes são
mesclados sem elevar confidence/provenance. Overfetch/recall com filtro são medidos
antes de escolher parâmetros HNSW.

### Pipeline de write

1. Nós produzem `MemoryWriteIntent` normalizado e não fazem I/O físico.
2. Commit do turno insere `memory_documents(pending)` e `jobs(embed_memory)`.
3. Worker gera embedding pelo provider pinado e faz update por ID/hash/profile.
4. Retry usa a mesma dedupe key; dimensão/hash divergente nunca sobrescreve.

Global Codex/regras podem ser vetorizados em lote pelo script porque são build
artifacts; sessão/NPC seguem jobs duráveis.

## 4. Plano passo a passo

### Etapa 1 — Contrato e intents

1. **Testes** (`test_pgvector_memory.py`): scopes, normalization, dedupe,
   provenance/visibility, pending fallback e erro de dimensão.
2. **Implementação:** dataclasses/collector + facade `rag.py`.
3. **Verificação:** adapter FAISS preserva testes atuais.

### Etapa 2 — Schema/queries/RLS

1. **Testes** (`test_pgvector_memory_local.py`): insert/query cosine+FTS, filtros,
   A/B isolation, hidden/secret, NPC, HNSW plan/recall.
2. **Implementação:** migration e adapter psycopg.
3. **Verificação:** nenhum acesso direto do frontend.

### Etapa 3 — Commit de turno e worker

1. **Testes:** fato/job commitam com estado; rollback deixa zero row; provider
   down mantém pending; retry completa; ID divergente falha.
2. **Implementação:** UoW no TurnService + embedding handler.
3. **Verificação:** turno continua jogável com provider de embedding desligado.

### Etapa 4 — Checkpoint e timeline

1. **Testes:** checkpoint watermark, fatos root/NPC posteriores descartados,
   jobs cancelados e death history preservado; restore repetido idempotente.
2. **Implementação:** restore transacional por commit_version/epoch.
3. **Verificação:** regressões de `checkpoint-transacional-memoria` passam nos dois adapters.

### Etapa 5 — Ingest/migração/paridade

1. **Testes:** dry-run, resume, corpus hash, profile cutover, FAISS extraction,
   metadata e top-k fixture PT-BR.
2. **Implementação:** scripts Python preview-first.
3. **Verificação:** lore/regras/session/NPC em base local limpa e relatório de recall.

## 5. Critérios de aceite

- [x] Lore, rules, session e NPC preservam filtros/formatos do contexto atual.
- [x] Turno confirma fato bruto+job atomicamente sem depender do provider de embedding.
- [x] Backlog pending continua recuperável por FTS e observável.
- [x] Worker é idempotente e recusa dimensão/profile/hash incompatível.
- [x] Restore não recupera nenhum fato da timeline descartada.
- [x] A/B e NPC secreto não vazam via query, RLS ou fallback FTS.
- [x] Reindex global é resumível e faz cutover de profile sem mistura.
- [x] Paridade top-3 FAISS↔pgvector atinge limiar documentado ≥80% no corpus fixo,
  com 100% nos casos obrigatórios de visibility/provenance/namespace.
- [x] Perfil pgvector não grava em `data/saves_memory/`.
- [x] `uv run pytest -m infra_local` e suíte offline completos verdes.
- [x] Guard de FallbackLLM — N/A; nenhum invoke LLM novo.
- [x] Índices FAISS históricos permanecem intactos/exportáveis.

## 6. Smoke test com LLM real

Um diálogo real com NPC deve criar fato `npc_claim/reported` bruto; parar o
worker antes do embedding comprova `pending`; reiniciar completa o vetor; turno
seguinte recupera somente para o mesmo game/NPC. Restaurar checkpoint elimina o
fato da timeline ativa. Máximo de duas interações reais; restante MockLLM.

## 7. Riscos & compatibilidade

- **Provider indisponível:** raw fact+job evita perda; backlog/SLO alerta degradação.
- **Dimensão fixa:** profile 1024 é deliberado; trocar dimensão exige migration/
  tabela nova e reindex, nunca cast silencioso.
- **HNSW com filtros:** medir recall/plan e ajustar overfetch/indexes; não declarar
  ganho sem benchmark local.
- **Dados secretos:** filtros ficam no SQL e no context builder; testes usam
  assinaturas secretas reais do projeto sem expor conteúdo em logs.
