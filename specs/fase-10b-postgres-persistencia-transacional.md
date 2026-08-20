# SPEC — Fase 10b.2 — Persistência Postgres híbrida e migração verificável

> **Status:** `done` (2026-08-20)
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** [fundação local e portas](fase-10b-fundacao-local-portas-adapters.md) `done`
> **Desbloqueia:** turnos multiworker, Auth/RLS, pgvector e backup transacional

---

## 1. Contexto & Objetivo

O save v7 é um documento grande, fortemente coeso e já possui migrations Python
confiáveis. Normalizar cada campo agora duplicaria `state.py`, aumentaria o risco
de drift e misturaria infraestrutura com mecânica. Por outro lado, guardar apenas
um blob sem versão/owner/controle otimista repetiria no banco os problemas do JSON.

Esta spec adota persistência híbrida: `GameState` permanece JSONB canônico;
identidade, versão, status, resumos operacionais, checkpoints, eventos e caches
que precisam de constraints ficam em colunas/tabelas próprias. O adapter usa
psycopg síncrono e SQL versionado, coerente com FastAPI/LangGraph síncronos.

## 2. Requisitos

- **R1 — GameState preservado:** o documento salvo é produzido/consumido pelas
  mesmas funções de serialização e `migrate_state`; Postgres não reimplementa
  defaults ou mecânicas em trigger.
- **R2 — ownership/version:** cada campanha tem `owner_id`, `version` monotônica,
  `schema_version`, hash e timestamps; update exige `expected_version`.
- **R3 — concorrência otimista:** versão divergente gera `StaleVersion`, sem
  sobrescrever estado novo; não existe last-write-wins silencioso.
- **R4 — leitura fechada:** `get/list/delete` sempre recebem `Principal`; jogo de
  outro owner é indistinguível de inexistente na borda HTTP.
- **R5 — checkpoint no banco:** cada jogo possui slot canônico com JSONB,
  versão/turno/epoch e watermark de memória; save e checkpoint não usam paths.
- **R6 — eventos deduplicados:** `event_log` continua no JSONB por compatibilidade,
  mas novos `GameEvent` também entram em tabela append-only com unique por jogo/id.
- **R7 — runtime catalog:** NPCs/inimigos/artefatos gerados e conhecimento
  persistente são documentos versionados com escopo `global|user|game` e
  constraints que impedem combinação de owners inválida.
- **R8 — summaries confiáveis:** listagem usa projeções calculadas em Python a
  partir do mesmo estado confirmado; inconsistência de projeção/hash falha o commit.
- **R9 — migração sem destruição:** importador de JSON oferece `scan`, `dry-run`,
  `import`, `verify` e relatório; nunca apaga fonte nem substitui row divergente.
- **R10 — export portátil:** exporta jogo/checkpoint/eventos/catálogo scoped em
  formato versionado, com hashes; não exige Supabase para restaurar em Postgres padrão.
- **R11 — cutover explícito:** `RPG_GAME_STORE=postgres` lê e escreve somente
  Postgres. Modo diagnóstico pode comparar reads, mas não confirmar dois writes.
- **R12 — falha segura:** indisponibilidade/commit abortado nunca retorna sucesso,
  nunca muta caches globais em memória e preserva a última versão confirmada.

### Fora de escopo

- Lease de turno, recibos idempotentes e jobs (spec seguinte).
- JWT/RLS e acesso do frontend.
- Vetores e rollback de memória após checkpoint.
- Limpar os diretórios JSON/FAISS depois do cutover.

## 3. Design técnico

### Arquivos novos

- `infrastructure/postgres.py` — pool psycopg, transações e `PostgresGameStore`.
- `infrastructure/postgres_catalog.py` — `PostgresRuntimeCatalogStore`.
- `services/game_serialization.py` — extrai de `persistence.py` a serialização
  pura estado↔dict, compartilhada pelos dois adapters.
- `supabase/migrations/<ts>_game_store.sql` — schema, constraints, indexes e grants.
- `scripts/migrate_file_saves.py` — importador/verificador seguro.
- `scripts/export_game_data.py` — export portátil por owner/jogo.
- `tests/test_postgres_game_store.py` — unit/contract tests.
- `tests/test_postgres_migration_local.py` — integração marcada `infra_local`.

### Arquivos alterados

- `persistence.py` — facade + `FileGameStore`; mantém nomes públicos.
- `api.py`, `game_engine.py`, `playtest/runner.py` — usam `GameStore` e principal.
- `pyproject.toml` — extra `postgres` com `psycopg[binary,pool]` pinado.
- `.env.example` — DSN/pool/timeouts sem credencial real.

### Schema SQL inicial

```sql
create schema if not exists app;

create table app.games (
  id uuid primary key,
  owner_id uuid not null,
  schema_version integer not null check (schema_version > 0),
  version bigint not null default 1 check (version > 0),
  state jsonb not null check (jsonb_typeof(state) = 'object'),
  state_sha256 text not null check (length(state_sha256) = 64),
  status text not null check (status in ('active','death_pending','memorial','archived','simulation')),
  player_name text not null,
  class_name text not null,
  player_level integer not null check (player_level > 0),
  location_name text not null,
  world_day integer not null check (world_day > 0),
  game_over boolean not null,
  combat_simulation boolean not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_action_at timestamptz,
  check ((state->>'game_id')::uuid = id),
  unique (owner_id, id)
);
create index games_owner_updated_idx on app.games(owner_id, updated_at desc);

create table app.game_checkpoints (
  game_id uuid primary key references app.games(id) on delete cascade,
  owner_id uuid not null,
  game_version bigint not null,
  canonical_turn integer not null,
  timeline_epoch integer not null,
  memory_commit_version bigint not null default 0,
  state jsonb not null,
  state_sha256 text not null check (length(state_sha256) = 64),
  created_at timestamptz not null default now(),
  foreign key (owner_id, game_id) references app.games(owner_id, id) on delete cascade
);

create table app.game_events (
  game_id uuid not null,
  owner_id uuid not null,
  event_id text not null,
  turn integer not null,
  event_type text not null,
  payload jsonb not null,
  source text not null,
  created_at timestamptz not null default now(),
  primary key (game_id, event_id),
  foreign key (owner_id, game_id) references app.games(owner_id, id) on delete cascade
);

create table app.runtime_catalog (
  id uuid primary key,
  namespace text not null,
  item_key text not null,
  scope text not null check (scope in ('global','user','game')),
  owner_id uuid,
  game_id uuid references app.games(id) on delete cascade,
  document jsonb not null,
  document_sha256 text not null,
  version bigint not null default 1,
  provenance text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (scope='global' and owner_id is null and game_id is null) or
    (scope='user' and owner_id is not null and game_id is null) or
    (scope='game' and owner_id is not null and game_id is not null)
  )
);

create unique index runtime_catalog_global_key
  on app.runtime_catalog(namespace, item_key) where scope='global';
create unique index runtime_catalog_user_key
  on app.runtime_catalog(namespace, item_key, owner_id) where scope='user';
create unique index runtime_catalog_game_key
  on app.runtime_catalog(namespace, item_key, owner_id, game_id) where scope='game';
```

`event_id` permanece `text`, não `uuid`: o schema vivo garante strings estáveis
e os saves/testes legados contêm IDs curtos (`e1`, `evt-1`) além de UUIDs hex.
Forçar cast apagaria compatibilidade sem ganho; a constraint exige 1–128 caracteres
e a deduplicação continua por `(game_id,event_id)` + hash do evento.

Os índices parciais dão a semântica correta para chaves nulas: um único documento
por namespace/key/escopo efetivo, sem tornar owner/game obrigatórios no escopo global.

### Semântica de save

```python
def save(self, principal: Principal, game_id: UUID, expected_version: int,
         state: dict[str, Any]) -> StoredGame:
    # serialize/migrate/validate/hash fora da transação
    # UPDATE ... SET state=?, version=version+1 ...
    # WHERE id=? AND owner_id=? AND version=? RETURNING ...
```

Dentro da mesma transação entram: row `games`, novos `game_events` com
`ON CONFLICT DO NOTHING` apenas quando payload/hash coincide, e checkpoint
quando solicitado. Conflito com mesmo `event_id` e payload diferente aborta.

### Migração de arquivos

```text
scan     → inventário: válido/corrompido/checkpoint/arquivado/sem memória
dry-run  → deserialize + migrate_state + hash, zero write
import   → insert-only por padrão; --resume por journal
verify   → reexport + comparação semântica e hashes
report   → JSON + Markdown; origem nunca removida
```

O owner de importação é obrigatório. Arquivos corrompidos e IDs duplicados são
reportados; nunca “ganham” silenciosamente pelo mtime.

## 4. Plano passo a passo

### Etapa 1 — Serialização pura e parity

1. **Testes:** fixtures v4–v7 e estado atual produzem o mesmo documento no
   `FileGameStore`; messages, continuidade, visual ledger e memória pendente sobrevivem.
2. **Implementação:** extrair `game_serialization` sem alterar formato JSON.
3. **Verificação:** suíte de persistência atual verde.

### Etapa 2 — Migration SQL e adapter Postgres

1. **Testes** (`test_postgres_game_store.py`): create/get/list/save/delete,
   owner, stale version, hash, status/projeções, event dedupe e rollback.
2. **Implementação:** schema + pool + adapter psycopg síncrono.
3. **Verificação:** contracts rodam em File e Postgres local.

### Etapa 3 — Checkpoint e runtime catalog

1. **Testes:** checkpoint replace/restore, evento divergente aborta, catálogo
   global/user/game não cruza escopo, conhecimento de bestiário não vaza.
2. **Implementação:** tabelas/adapters e fachadas atuais.
3. **Verificação:** fluxo de morte/checkpoint passa sem filesystem no perfil local.

### Etapa 4 — Import/export

1. **Testes:** dry-run zero write; corrupto isolado; rerun idempotente; colisão
   divergente recusada; export→import conserva hash/estado/checkpoint/eventos.
2. **Implementação:** CLIs Python com journal e relatório.
3. **Verificação:** cópia descartável do inventário histórico, nunca os diretórios reais.

### Etapa 5 — Cutover do GameStore

1. **Testes:** API/CLI/playtest selecionam adapter; `postgres` não chama
   `save_path`/glob/os.remove; falha DB retorna erro sanitizado.
2. **Implementação:** injeção nos entrypoints.
3. **Verificação:** campanha MockLLM, restart e continuação em Postgres local.

## 5. Critérios de aceite

- [x] GameState v7 mantém round-trip semântico nos dois adapters.
- [x] Save concorrente com versão velha falha sem perder estado confirmado.
- [x] Owner B não lê/lista/altera/exclui dados de A pelo GameStore.
- [x] Checkpoint/eventos/runtime catalog participam da transação correta.
- [x] Conhecimento mutável tem escopo explícito e zero vazamento entre campanhas.
- [x] Importador é preview-first, resumível e não destrutivo.
- [x] Export→restore em Postgres limpo conserva hashes e estado jogável.
- [x] Perfil Postgres não escreve save/checkpoint/runtime JSON no disco.
- [x] `uv run pytest -m infra_local` verde além da suíte completa offline.
- [x] Guard de FallbackLLM — N/A; nenhum invoke novo.
- [x] Saves antigos continuam carregando/exportáveis pelo adapter legado.

## 6. Smoke test com LLM real

Não há contrato LLM novo. Criar campanha MockLLM em Postgres local, jogar cinco
turnos, reiniciar API, continuar, criar checkpoint e restaurar. Como confirmação
final, um único turno real verifica que a latência do provider não mantém
transação aberta e que o estado final persiste uma vez.

## 7. Riscos & compatibilidade

- **JSONB grande:** medir tamanho/TOAST e tempo de update; normalizar apenas com
  evidência, preservando o documento como fonte.
- **Pool/serverless:** pool pequeno, timeout e conexão por invocação configuráveis;
  certificação cloud mede o alvo real.
- **Schema `auth`:** `owner_id` não depende de FK Supabase para manter
  portabilidade; Auth/RLS garante ciclo de vida.
- **Migrations Python x SQL:** SQL versiona storage; `migrate_state` continua
  sendo a única evolução mecânica do documento.
