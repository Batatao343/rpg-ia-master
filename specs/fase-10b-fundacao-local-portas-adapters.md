# SPEC — Fase 10b.1 — Fundação local reproduzível e portas de infraestrutura

> **Status:** `done` (2026-08-20)
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** [plano mestre local-first](fase-10b-plano-mestre-local-first.md) `approved`
> **Desbloqueia:** Postgres, turnos distribuídos, Auth/RLS, pgvector, BlobStore e operação local

---

## 1. Contexto & Objetivo

O projeto escolhe implementações diretamente por imports globais: `api.py` chama
funções de `persistence.py`, agentes chamam `rag.py`, e caches gerados escrevem em
`data/runtime/`. Trocar apenas o diretório por uma URL Supabase não resolve o
acoplamento nem garante que CLI, playtest e API usem a mesma semântica.

Esta fatia cria o laboratório local e as portas Python, mantendo o comportamento
atual como adapters de referência. Ela não migra um único save ainda. O objetivo
é permitir que cada fatia seguinte seja implementada e testada sem alterar
agentes, mecânicas ou o grafo.

## 2. Requisitos

- **R1 — bootstrap reproduzível:** um comando Python oferece `doctor`, `start`,
  `status`, `stop` e `reset --confirm-local` para a stack local; comandos
  destrutivos mostram alvo/ports e recusam qualquer projeto remoto/linkado.
- **R2 — Supabase local mínimo:** migrations/config versionados sob `supabase/`;
  serviços necessários são Database, Auth, REST, Storage e caixa de e-mail local.
  Realtime, Functions e analytics ficam desligados quando o CLI suportar.
- **R3 — descoberta, não suposição:** o script consulta `docker`, `supabase
  --version` e `supabase <cmd> --help`; versão/feature incompatível produz erro
  acionável, nunca tenta flags inventadas.
- **R4 — doctor de recursos:** verifica Docker ativo, espaço, portas, memória e
  arquivos de env. Abaixo do mínimo configurado, avisa/falha antes de baixar ou
  iniciar containers.
- **R5 — contratos:** definir `GameStore`, `MemoryStore`, `RuntimeCatalogStore`,
  `BlobStore`, `TurnCoordinator`, `JobQueue`, `RateLimiter` e `IdentityVerifier`
  como `Protocol` síncronos, com dataclasses de entrada/saída e erros tipados.
- **R6 — adapters legados:** JSON/FAISS/runtime JSON/arquivo/fila inline continuam
  passando a suíte atual; `persistence.py`, `rag.py` e APIs públicas permanecem
  fachadas, evitando alteração massiva de callsites.
- **R7 — seleção central:** somente `infrastructure/runtime.py` lê env e monta
  adapters; módulos de domínio recebem runtime explícito ou usam accessor
  controlado e resetável nos testes.
- **R8 — validação de perfil:** combinações inválidas falham no startup. `hosted`
  exige auth, storage remoto, GameStore Postgres, MemoryStore pgvector e runtime
  cache remoto; `legacy` só pode ficar exposto em loopback.
- **R9 — sem segredos versionados:** config local usa env; chaves admin/service
  nunca entram no frontend, em logs ou no repositório.
- **R10 — isolamento da suíte:** `uv run pytest` continua sem Docker, rede ou
  mudança nos diretórios reais; testes de infra recebem markers opt-in.
- **R11 — filesystem auditável:** um guard de teste registra writes em execução
  de API `local/hosted` e falha se ocorrerem fora de diretórios temporários
  explicitamente permitidos.
- **R12 — caches classificados:** templates gerados de NPC/inimigo/artefato usam
  `RuntimeCatalogStore`; conhecimento revelado usa escopo `user`/`game`, nunca
  namespace global implícito.

### Fora de escopo

- Criar tabelas finais, migrar dados ou ligar a API ao Postgres.
- Login no frontend e políticas RLS.
- Migrar vetores ou assets.
- Subir containers em CI padrão ou publicar a stack local na rede.

## 3. Design técnico

### Arquivos novos

- `infrastructure/contracts.py` — Protocols, dataclasses e erros estáveis.
- `infrastructure/runtime.py` — `RuntimeConfig`, validação e factory única.
- `infrastructure/local_adapters.py` — wrappers sobre JSON/FAISS/runtime atual.
- `infrastructure/testing.py` — fakes e recorder de writes.
- `scripts/dev_stack.py` — orquestrador Python da stack local.
- `supabase/config.toml` — stack local somente desenvolvimento.
- `supabase/seed.sql` — dados técnicos de teste; nunca campanhas reais.
- `supabase/migrations/.gitkeep` — diretório inicial; SQL entra nas specs seguintes.
- `tests/test_infrastructure_contracts.py` — contrato dos adapters locais.
- `tests/test_runtime_profiles.py` — matriz de configuração/fail-closed.
- `tests/test_dev_stack.py` — subprocessos simulados, sem Docker real.

### Arquivos alterados

- `persistence.py` e `rag.py` — passam a delegar às portas sem mudar assinaturas públicas.
- `gamedata.py`, `agents/npc.py`, `agents/bestiary.py`,
  `services/bestiary_knowledge.py` — cache mutável pela porta classificada.
- `api.py`, `game_engine.py`, `playtest/runner.py` — selecionam perfil explícito.
- `tests/conftest.py` — instala runtime `legacy` temporário por teste.
- `.env.example`, `pyproject.toml`, `.gitignore`, `README.md` — perfis/comandos/marker.

### Contratos públicos

```python
@dataclass(frozen=True)
class Principal:
    user_id: UUID
    issuer: str
    subject: str
    local: bool = False

@dataclass(frozen=True)
class StoredGame:
    game_id: UUID
    owner_id: UUID
    schema_version: int
    version: int
    state: dict[str, Any]
    updated_at: datetime

class GameStore(Protocol):
    def create(self, principal: Principal, state: dict[str, Any]) -> StoredGame: ...
    def get(self, principal: Principal, game_id: UUID) -> StoredGame | None: ...
    def list(self, principal: Principal) -> list[StoredGame]: ...
    def save(self, principal: Principal, game_id: UUID, expected_version: int,
             state: dict[str, Any]) -> StoredGame: ...
    def delete(self, principal: Principal, game_id: UUID) -> bool: ...

class RuntimeCatalogStore(Protocol):
    def get(self, namespace: str, key: str, *, owner_id: UUID | None,
            game_id: UUID | None) -> dict[str, Any] | None: ...
    def put(self, namespace: str, key: str, value: dict[str, Any], *,
            scope: Literal["global", "user", "game"],
            owner_id: UUID | None, game_id: UUID | None) -> None: ...

class MemoryStore(Protocol):
    def query(self, request: MemoryQuery) -> list[MemoryDocument]: ...
    def stage(self, intent: MemoryWriteIntent) -> None: ...

class BlobStore(Protocol):
    def put(self, key: str, payload: BinaryIO, metadata: BlobMetadata) -> BlobRef: ...
    def signed_url(self, key: str, expires_seconds: int) -> str: ...
    def delete(self, key: str) -> bool: ...

class JobQueue(Protocol):
    def enqueue(self, job: JobRequest) -> UUID: ...
    def lease(self, worker_id: str, kinds: set[str], limit: int) -> list[LeasedJob]: ...
    def complete(self, job_id: UUID, lease_token: UUID, result: dict) -> None: ...
    def fail(self, job_id: UUID, lease_token: UUID, error_code: str) -> None: ...
```

`TurnCoordinator`, `RateLimiter` e `IdentityVerifier` entram com métodos mínimos
e errors: `NotFound`, `Conflict`, `Unauthorized`, `Forbidden`, `StaleVersion`,
`LeaseHeld`, `PersistenceUnavailable`. Mensagens internas não atravessam a API.

### Configuração

```env
RPG_RUNTIME_PROFILE=legacy|local|portable|hosted
RPG_GAME_STORE=file|postgres
RPG_MEMORY_STORE=faiss|pgvector
RPG_RUNTIME_CATALOG=file|postgres
RPG_BLOB_STORE=file|supabase|s3
RPG_JOB_QUEUE=inline|postgres
RPG_RATE_LIMIT_STORE=memory|postgres
RPG_AUTH_MODE=disabled|supabase|oidc
DATABASE_URL=
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SERVICE_ROLE_KEY=        # backend/worker somente
```

O `RuntimeConfig` rejeita `SUPABASE_SERVICE_ROLE_KEY` com prefixos/arquivos
destinados ao Vite. O frontend só recebe URL e publishable key na spec de Auth.

### Política de recursos local

`doctor` imprime memória do host/Docker, espaço e portas. O baseline documentado
deve caber no Docker atual (~8 GiB), mas a spec não congela um número de RAM do
Supabase: a versão pinada é medida e o resultado fica no relatório de smoke.

## 4. Plano passo a passo

### Etapa 1 — Contratos antes dos adapters

1. **Testes** (`tests/test_infrastructure_contracts.py`): contratos exercitam
   create/get/list/save/delete, isolamento por principal, version conflict,
   cache scoped, fila inline e BlobStore temporário.
2. **Implementação:** criar Protocols/dataclasses/errors sem importar providers.
3. **Verificação:** type checks disponíveis + suíte atual verde.

### Etapa 2 — Adapter legado e fachadas

1. **Testes:** comportamento de `save_game_state`, `load_game_state`, `query_rag`
   e caches permanece compatível; principal local não cruza sandbox.
2. **Implementação:** wrappers legados e injeção em fachadas/callsites.
3. **Verificação:** snapshots de saves v4–v7 e testes atuais byte/semântica equivalentes.

### Etapa 3 — Perfis e fail-closed

1. **Testes** (`tests/test_runtime_profiles.py`): todas as combinações; `hosted`
   recusa file/FAISS/auth disabled; `legacy` recusa bind não-loopback.
2. **Implementação:** `RuntimeConfig.from_env()` e factory resetável.
3. **Verificação:** nenhuma leitura de env espalhada pelos adapters novos.

### Etapa 4 — Bootstrap local seguro

1. **Testes** (`tests/test_dev_stack.py`): CLI ausente, Docker parado, baixa RAM,
   porta ocupada, reset sem confirmação, projeto linkado e comandos descobertos.
2. **Implementação:** `scripts/dev_stack.py` + config Supabase local.
3. **Verificação:** `doctor`; `start`; `status`; `stop`; reset somente numa stack local descartável.

### Etapa 5 — Auditoria de filesystem

1. **Testes:** um turno e criação de NPC/inimigo/artefato no perfil fake hosted
   não escrevem fora do recorder; conhecimento de bestiário é scoped.
2. **Implementação:** recorder/guard e migração dos quatro callsites de cache.
3. **Verificação:** `rg` de writes mutáveis atualizado no relatório da spec.

## 5. Critérios de aceite

- [x] Stack local sobe/desce por comando Python e nunca toca alvo remoto.
- [x] `doctor` mede dependências/recursos e falha com instrução acionável.
- [x] Oito portas têm contratos e fakes; adapters legados passam todos.
- [x] Suíte padrão continua 100% offline e sem Docker.
- [x] Perfil `hosted` recusa qualquer persistência mutável em filesystem/auth desligada.
- [x] Os quatro overlays mutáveis usam `RuntimeCatalogStore` com escopo explícito.
- [x] `persistence.py`/`rag.py` preservam APIs públicas durante a transição.
- [x] Nenhum segredo Supabase aparece no bundle/frontend/log.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM — N/A; nenhum invoke novo.
- [x] Saves antigos continuam carregando pelo adapter legado.

## 6. Smoke test com LLM real

Zero LLM. O smoke é de infraestrutura local: iniciar a stack limpa, consultar
health dos serviços necessários, parar e iniciar novamente preservando o volume;
resetar somente com confirmação e demonstrar que a suíte padrão não iniciou
container algum.

## 7. Riscos & compatibilidade

- **Abstração excessiva:** contratos cobrem apenas operações já usadas ou
  requeridas pelas specs filhas; não criar ORM/repository genérico.
- **Globals existentes:** accessor central deve ser resetável; testes garantem
  que import order não prende um runtime de outra campanha.
- **Supabase CLI mutável:** versão é pinada e comandos são descobertos por help.
- **Windows/OneDrive:** volumes Docker não ficam dentro do OneDrive; scripts usam
  caminhos resolvidos e nunca removem diretórios amplos.
