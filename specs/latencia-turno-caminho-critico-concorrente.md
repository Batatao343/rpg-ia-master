# SPEC — Latência do turno: caminho crítico concorrente e derivados assíncronos

> **Status:** `draft`
> **Criada:** 2026-08-27 · **Atualizada:** 2026-08-27
> **Depende de:** `observabilidade-latencia-nos`, `streaming-turno-sse`,
> `fase-10b-turnos-duraveis-concorrencia-fila`,
> `fase-10b-pgvector-memoria-transacional` e
> `cronica-avancada-compressao-busca-semantica` (`done`)
> **Desbloqueia:** interação mais rápida sem perda de consistência; gate de
> desempenho antes do go-live
> **Relacionada, mas independente:** futura spec de concorrência E2E entre
> campanhas. Esta spec reduz a latência de **um** turno; a outra provará
> throughput de jogos distintos em paralelo.

---

## 1. Contexto & Objetivo

O turno atual percorre uma cadeia predominantemente serial:
`campaign_manager → dm_router → agente → archivist`. A API síncrona é executada
corretamente pelo thread pool do FastAPI, mas isso não encurta o caminho crítico
de uma interação. Converter funções mecanicamente para `async def` também não
cria paralelismo: só há ganho quando operações independentes de I/O são
iniciadas juntas e aguardadas num ponto de junção explícito.

A amostra disponível de nove campanhas reais válidas da matriz A (1.800 turnos)
mostra p50 por campanha entre 4,5 s e 15,9 s e p95 entre 15,9 s e 22,1 s. Os
maiores centros de custo são o agente narrativo, o arquivista e chamadas SMART
de replanejamento. O `campaign_manager` normalmente custa ~1 ms, mas um replan
real chega a 8–18 s; o arquivista aparece em todo turno e acumula média de 3,3 s.
Esses dados são provisórios até a décima campanha A terminar, quando a linha de
base deve ser recalculada e anexada à evidência da implementação.

O objetivo é reduzir o tempo entre ação e estado confirmado, sem aumentar o
número de chamadas, trocar modelos, enfraquecer validação ou permitir commits
parciais. A estratégia é: medir o caminho crítico; paralelizar apenas leituras e
decisões independentes; compartilhar o embedding de uma consulta; tornar o
pulso de mundo puro antes de sobrepô-lo ao contexto; e retirar do request apenas
memórias **derivadas**, mantendo eventos, recompensas, projeção, recibo e save no
fechamento canônico síncrono.

## 2. Requisitos

- **R1 — três métricas diferentes:** telemetria distingue `latency_ms` da
  interação, `critical_path_ms`, `work_ms`, `overlap_ms`, `queue_wait_ms` e
  throughput. Streaming percebido e paralelismo entre campanhas não podem ser
  apresentados como redução do tempo de confirmação do turno.
- **R2 — baseline reproduzível:** antes do primeiro refactor, gerar relatório
  por rota e coorte (`archive_due`, replan, viagem/descanso, combate, NPC, loot)
  com p50/p95/max, quantidade de chamadas, tokens/custo e erros. A evidência deve
  usar os dez pares válidos da matriz A e snapshots sanitizados reutilizáveis.
- **R3 — spans de estágio:** medir, no mínimo, `turn.prepare`, `plan`, `route`,
  `context.dynamic`, `context.embed`, `context.lore`, `context.session`,
  `context.npc`, `world_pulse`, `agent.llm`, `canonical_finalize`,
  `derived.enqueue` e `commit`. Logs não contêm prompt, ação, narrativa, memória
  ou identificadores de alta cardinalidade sem hash.
- **R4 — allowlist de concorrência:** somente operações independentes,
  read-only, idempotentes ou produtoras de DTO puro podem rodar em paralelo.
  Mecânica, validação/aplicação de eventos, recompensas, ordenação de mensagens,
  transição de combate e commit permanecem sequenciais.
- **R5 — preparação única do turno:** um nó Python `turn_prepare` faz uma única
  transição de relógio/continuidade e cria o snapshot imutável consumido pelas
  decisões paralelas. Nenhuma branch incrementa turno, relógio ou epoch.
- **R6 — plano e rota em fan-out/fan-in:** após `turn_prepare`, `plan_refresh` e
  `route_intent` podem rodar juntos e devem escrever chaves disjuntas. O
  `dispatch` só inicia o agente depois das duas respostas. Em combate ativo,
  replan fica marcado como devido, mas a chamada SMART é adiada até uma borda
  segura; nunca se gasta replan no meio da resolução de combate.
- **R7 — falha de branch é explícita:** falhas esperadas de provider retornam DTO
  degradado tipado e passam pelos guards existentes. Exceção não tratada cancela
  o superstep inteiro; não pode deixar efeito externo ou estado parcial.
- **R8 — merge determinístico:** branches paralelas não escrevem a mesma chave.
  Qualquer coleção agregada é ordenada por chave estável antes de entrar no
  estado. O resultado não depende da ordem em que futures terminam.
- **R9 — um embedding por contexto:** lore global, memória de sessão e memória
  privada de NPC reutilizam o mesmo vetor da consulta quando o provider e a
  dimensão forem compatíveis. O texto não é embeddado novamente por escopo.
- **R10 — fontes de contexto paralelas:** depois de fatos dinâmicos e vetor
  estarem prontos, as buscas de lore/sessão/NPC podem rodar com concorrência
  limitada. Falha de uma fonte esvazia somente aquela fonte; filtros de
  `visibility`, `owner_id`, `game_id`, `npc_id`, namespace, versão do embedding e
  `timeline_epoch` continuam fail-closed. O join preserva ranking e orçamento
  determinísticos.
- **R11 — compatibilidade dos adapters:** FAISS local e PgVector aceitam consulta
  por vetor já calculado sem eliminar a API textual existente. Índice com
  provider/dimensão diferente recusa o vetor compartilhado e usa o caminho
  seguro documentado; nunca compara vetores incompatíveis.
- **R12 — pulso de mundo puro:** geração FAST de `WorldPulse` passa a produzir um
  `WorldPulseProposal` sem escrever RAG nem mutar `world`. Em viagem/descanso,
  contexto que não depende desse resultado pode ser adquirido em paralelo. Só
  depois do join Python limita/aplica `danger_shift`, forma o rumor e cria a
  intenção de memória canônica.
- **R13 — dependência narrativa honesta:** se o prompt final precisa do rumor ou
  do perigo atualizado, a narração só começa depois do join. A otimização
  sobrepõe aquisições independentes; não narra um mundo antes de decidir seu
  estado.
- **R14 — arquivista em duas camadas:** `canonical_finalize` processa eventos,
  recompensas, projeção, conflito, milestones, pending intents e estado do
  jogador antes da resposta. Resumo LLM, extração de fatos derivados e writes
  vetoriais não necessários ao recibo viram `memory_derivation` fora do caminho
  crítico no perfil Postgres.
- **R15 — nenhuma recompensa atrasada:** ouro, XP, item, quest, ferimento,
  inimigo, NPC em cena, relógio, evento e mensagem apresentada pertencem ao
  resultado canônico do próprio turno. O cliente recebe um recibo final coerente
  com o save; derivação assíncrona não pode corrigir mecânica posteriormente.
- **R16 — job atômico e idempotente:** commit do turno e enqueue da derivação
  ocorrem na mesma transação. Dedupe usa
  `(game_id, timeline_epoch, committed_game_version, source_hash,
  derivation_profile_version)`. Retry/restart não duplica fatos, digests ou
  embeddings.
- **R17 — ordenação e fencing da derivação:** job antigo ou de timeline
  restaurada não sobrescreve resumo/fatos mais novos. Apply exige owner/game,
  epoch, source hash e cursor/version compatíveis; resultado stale é descartado
  com código fechado e auditável.
- **R18 — frescor explícito:** o turno seguinte usa o último resumo derivado
  concluído mais `event_log`, `memory_facts` e ledger canônicos ainda não cobertos.
  O estado expõe cursor de cobertura, não finge que o digest já incorporou o
  turno atual.
- **R19 — compatibilidade local/CLI:** com persistência de arquivos e sem worker,
  derivação permanece inline por default para não perder memória ao encerrar o
  processo. Com runtime Postgres+worker, o default é queued após aceite. Uma
  implementação não pode manter dois algoritmos semânticos divergentes.
- **R20 — paridade sync/async do roteador LLM:** `RoutedLLM.ainvoke` preserva
  exatamente candidatos, ordem, circuit breaker, transforms, adaptação
  OpenAI-compat, retries semânticos estruturados, timeout, telemetria e retorno
  final do `invoke`. Deve preferir `client.ainvoke`; provider sem async nativo usa
  executor limitado sem bloquear o event loop.
- **R21 — sem chamadas especulativas:** concorrência não inicia fallback antes de
  o candidato anterior falhar, não duplica requests, não muda tier/modelo e não
  adiciona LLM para “acelerar”. Chamadas e custo por cenário devem ser menores ou
  iguais ao baseline equivalente.
- **R22 — orçamento e backpressure:** semáforos configuráveis limitam concorrência
  por provider, embeddings e derivação. Limite 1 degrada para execução serial
  correta. Fila cheia mantém o estado canônico e sinaliza backlog; não cria
  threads/tarefas sem limite.
- **R23 — API e SSE:** POST e SSE compartilham o mesmo serviço. O evento
  `accepted` continua rápido; disconnect não cancela computação/commit. O evento
  final só sai após commit canônico; memória derivada pode terminar depois e não
  altera o recibo idempotente.
- **R24 — cancelamento transacional:** cancelamento/timeout antes do commit não
  publica escrita parcial de branch. Depois do commit, retry da mesma chave lê o
  recibo; jobs derivados seguem a política durável existente.
- **R25 — rollout reversível:** `RPG_TURN_EXECUTION=sequential|concurrent` começa
  em `sequential` durante caracterização. Após todos os gates, `concurrent` vira
  default. `RPG_DERIVATION_MODE=inline|queued` é resolvido pelo runtime; fallback
  para inline só ocorre antes do commit, nunca executa ambos.
- **R26 — equivalência de estado:** para fixtures determinísticas, serial e
  concorrente produzem estado canônico, eventos, mensagens, chamada/ordem de
  modelos e recibo iguais. Diferenças permitidas: timestamps, spans e frescor do
  derivado até o worker concluir.
- **R27 — testes sem sleeps frágeis:** concorrência é provada com barriers/events
  controlados, relógio fake e clients instrumentados. Cada risco recorrente
  recebe teste unitário/contrato: structured output async inválido, branch
  parcial, embedding duplicado, resultado stale, restore/epoch, fila cheia e
  limite de provider.
- **R28 — gate de desempenho controlado:** em fakes com latências conhecidas, o
  wall time de cada fan-out deve se aproximar do maior ramo, não da soma, com
  redução mínima de 30% nos cenários desenhados e `overlap_ms > 0`.
- **R29 — gate real pareado:** snapshots isolados cobrem replan, viagem com pulso
  e turno com arquivamento. Três repetições por modo, mesma rota/provider/teto,
  sem fallback determinístico: mediana por coorte reduz pelo menos 15%, p95
  agregado não piora mais de 5%, chamadas/custo não aumentam e não há erro ou
  violação `error`. Se ruído impedir conclusão, ampliar amostra; não afrouxar o
  gate por uma única execução.
- **R30 — não bloquear a matriz atual:** implementação e smoke real só começam
  após a matriz A estar concluída/analisada e após aprovação explícita desta
  spec. A matriz B continua reservada para validar as correções de gameplay; não
  vira benchmark improvisado desta otimização.

### Fora de escopo

- Rodar campanhas diferentes em paralelo ou certificar múltiplos workers E2E;
  isso pertence à spec separada de concorrência de go-live.
- Processar duas ações simultâneas da mesma campanha.
- Trocar DeepSeek, tiers, prompts, temperatura ou política de fallback.
- Adicionar Redis, Kafka ou serviço remoto.
- Streaming token a token ou alteração visual do frontend.
- Paralelizar parse→mecânica→narração de combate/loot, pois existe dependência de
  dados real entre essas etapas.
- Tornar toda função Python assíncrona, migrar todo driver de banco ou remover as
  APIs síncronas apenas por uniformidade.
- Mudar regras, balanceamento, conteúdo, recompensas ou comportamento dos
  perfis de playtest.

## 3. Design técnico

### 3.1 Grafo do turno

```text
START
  ↓
terminal_guard → turn_prepare
                    ├── plan_refresh ──┐
                    └── route_intent ──┤  fan-out / fan-in
                                      ↓
                                   dispatch
                                      ↓
                           agente selecionado
                                      ↓
                           canonical_finalize
                                      ↓
                             commit + receipt
                                      ↓
                                     END

Após/na mesma transação do commit: enqueue memory_derivation.
O worker não faz parte do caminho crítico do request.
```

No LangGraph, `add_edge(["plan_refresh", "route_intent"], "dispatch")` cria a
barreira. Cada branch retorna dict parcial com campos disjuntos. Erros esperados
são valores tipados; exceção aborta o superstep transacional. A ordem de
conclusão nunca é usada como ordem narrativa.

### 3.2 Modelos e contratos

**Novo `services/turn_pipeline.py`:**

```python
@dataclass(frozen=True)
class TurnPreparation:
    game_id: str
    timeline_epoch: int
    turn: int
    base_state_version: int
    action_text: str
    action_sha256: str
    in_active_combat: bool
    replan_due: bool

class BranchStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    SKIPPED = "skipped"

@dataclass(frozen=True)
class RouteBranchResult:
    status: BranchStatus
    next_node: str
    active_npc_name: str | None = None
    loot_source: str | None = None
    combat_target: str | None = None
    error_code: str | None = None

@dataclass(frozen=True)
class PlanBranchResult:
    status: BranchStatus
    campaign_plan: dict | None = None
    needs_replan: bool = False
    chronicle_updates: tuple[dict, ...] = ()
    error_code: str | None = None

def prepare_turn(state: GameState) -> tuple[dict, TurnPreparation]: ...
def route_branch(state: GameState, prepared: TurnPreparation) -> RouteBranchResult: ...
def plan_branch(state: GameState, prepared: TurnPreparation) -> PlanBranchResult: ...
def merge_branch_results(route: RouteBranchResult,
                         plan: PlanBranchResult) -> dict: ...
```

`action_text` existe apenas no objeto efêmero e nunca entra em log. A forma
persistida continua sendo `GameState`; DTOs não criam uma segunda fonte da
verdade.

**Novo `services/context_sources.py`:**

```python
@dataclass(frozen=True)
class EmbeddedContextQuery:
    text: str
    vector: tuple[float, ...] | None
    embedding_provider: str | None
    embedding_model: str | None
    dimensions: int | None

@dataclass(frozen=True)
class ContextSourceResult:
    source: Literal["lore", "session", "npc"]
    text: str = ""
    status: Literal["ok", "empty", "degraded"] = "empty"
    error_code: str | None = None
    latency_ms: int = 0

def embed_context_query(text: str) -> EmbeddedContextQuery: ...
def acquire_context_sources(query: EmbeddedContextQuery, *, state: GameState,
                            game_id: str | None, npc_id: str | None,
                            max_workers: int) -> tuple[ContextSourceResult, ...]: ...
async def acquire_context_sources_async(query: EmbeddedContextQuery, *,
                                        state: GameState,
                                        game_id: str | None,
                                        npc_id: str | None,
                                        max_concurrency: int
                                        ) -> tuple[ContextSourceResult, ...]: ...
```

Os adapters ganham métodos de consulta por vetor pré-calculado, preservando os
métodos textuais. Resultados são sempre retornados na ordem `lore`, `session`,
`npc`, qualquer que seja a ordem de conclusão.

**Refactor `agents/world_simulator.py`:**

```python
@dataclass(frozen=True)
class WorldPulseProposal:
    rumor: str
    danger_shift: int
    status: Literal["ok", "degraded"]
    error_code: str | None = None

def propose_world_pulse(state: GameState, world: dict, factions: list,
                        intel: dict, periods: int = 1) -> WorldPulseProposal: ...
def apply_world_pulse(state: GameState, world: dict,
                      proposal: WorldPulseProposal) -> tuple[dict, str, list[dict]]: ...
```

`propose_world_pulse` nunca chama `add_memory_to_session`. O terceiro retorno de
`apply_world_pulse` são intents validadas que participam do commit.

**Novo `services/turn_derivations.py`:**

```python
class MemoryDerivationJobPayload(BaseModel):
    schema_version: Literal[1] = 1
    owner_id: UUID
    game_id: UUID
    timeline_epoch: int = Field(ge=0)
    committed_game_version: int = Field(ge=1)
    canonical_turn: int = Field(ge=0)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivation_profile_version: str
    from_event_cursor: int = Field(ge=0)
    through_event_cursor: int = Field(ge=0)
    public_source: dict

class MemoryDerivationResult(BaseModel):
    source_hash: str
    narrative_summary: str
    memory_facts: list[dict]
    covered_event_cursor: int = Field(ge=0)
    status: Literal["ready", "extractive_fallback", "stale"]

def build_memory_derivation_payload(principal: Principal, state: GameState,
                                    committed_version: int
                                    ) -> MemoryDerivationJobPayload | None: ...
def derive_memory(payload: MemoryDerivationJobPayload,
                  llm: object | None = None) -> MemoryDerivationResult: ...
```

`public_source` contém somente mensagens/eventos já revelados necessários ao
resumo, com tamanho limitado e sem Codex hidden ou memória privada de NPC. O
repositório aplica resultado com compare-and-set de owner/game/epoch/cursor/hash.

### 3.3 Paridade LLM e limites

`llm_setup.RoutedLLM` ganha `async def ainvoke(self, input)`. A lógica comum de
seleção/validação/telemetria deve ser extraída para helpers compartilhados; não
se copia o loop inteiro. O fallback entre providers continua serial. Cada
request adquire um limiter por provider/modelo; o limite vem de configuração
validada, tem default conservador e pode ser 1.

O caminho síncrono usa as mesmas funções puras e adapters. Quando LangGraph
precisar oferecer ambas as formas, o nó é registrado com `RunnableLambda(func=,
afunc=)` ou equivalente suportado pela versão pinada. A spec não autoriza dois
grafos com regras diferentes.

### 3.4 Arquivos

**Novos:**

- `services/turn_pipeline.py` — preparação, DTOs e merge puro das branches.
- `services/context_sources.py` — embedding único, aquisição sync/async e join.
- `services/turn_derivations.py` — payload, extração e apply idempotente.
- `workers/memory_derivation_jobs.py` — handler registrado no worker durável.
- `scripts/benchmark_turn_pipeline.py` — benchmark controlado e comparação de
  snapshots, sem provider por default.
- `tests/test_turn_pipeline_concurrency.py` — fan-out, merge, falha e equivalência.
- `tests/test_context_sources_concurrency.py` — embedding único, escopo e ordem.
- `tests/test_llm_async_parity.py` — matriz de paridade `invoke`/`ainvoke`.
- `tests/test_memory_derivation_jobs.py` — atomicidade, stale, retry e restore.
- `tests/test_turn_latency_contract.py` — spans e gates com relógio fake.

**Alterados:**

- `main.py` — grafo com preparação, fan-out/fan-in e finalizador canônico.
- `state.py` — somente cursores/status de derivação necessários à persistência,
  com defaults migration-safe.
- `llm_setup.py` — `ainvoke`, limiters e núcleo compartilhado de tentativas.
- `services/context_builder.py` e `rag.py` — consumir aquisição compartilhada e
  consulta por vetor; preservar API antiga.
- `infrastructure/contracts.py`, adapters FAISS/PgVector e migrations — consulta
  por vetor e compare-and-set do derivado.
- `agents/campaign_manager.py` e `agents/router.py` — decisões sem mutação comum.
- `agents/storyteller.py` e `agents/world_simulator.py` — proposta pura e join.
- `agents/archivist.py` — separar finalização canônica de derivação.
- `services/turn_service.py`, `infrastructure/postgres_jobs.py` e
  `workers/run_worker.py` — enqueue transacional e handler.
- `api.py`, `game_engine.py` — selecionar caminho async/sync sem mudar contrato.
- `playtest/telemetry.py` e `playtest/report.py` — critical path, work, overlap e
  coortes.
- `.env.example` — modos/limites documentados, sem credencial.
- `ESTADO_ATUAL.md`, `ROADMAP.md` e docs de operação — rollout e evidência.

### 3.5 Referências arquiteturais

- LangGraph documenta fan-out/fan-in, reducers, supersteps e
  `max_concurrency`: [Graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api).
- Tarefas/futures paralelas devem ser idempotentes e checkpointáveis:
  [Functional API](https://docs.langchain.com/oss/python/langgraph/use-functional-api).
- FastAPI executa rotas síncronas em thread pool; `async def` ajuda apenas quando
  há I/O aguardável real: [Async](https://fastapi.tiangolo.com/async/).
- Cancelamento estruturado e propagação de falhas usam a semântica de
  [Python `TaskGroup`](https://docs.python.org/3/library/asyncio-task.html#task-groups).

## 4. Plano passo a passo

### Etapa 1 — Caracterização e baseline

1. **Testes** (`test_turn_latency_contract.py`): spans obrigatórios, soma de
   trabalho, caminho crítico, overlap e coortes; nenhuma string sensível.
2. **Implementação:** benchmark e telemetria por estágio; congelar snapshots A.
3. **Verificação:** relatório com 10 campanhas A e baseline serial versionado.

### Etapa 2 — Paridade async do RoutedLLM

1. **Testes** (`test_llm_async_parity.py`): sucesso, build/apply/invoke error,
   circuito aberto, fallback, `include_raw`, structured `None`, três tentativas
   semânticas, provider sem `ainvoke`, cancelamento e telemetria — mesma ordem e
   resultado do sync.
2. **Implementação:** núcleo compartilhado, `ainvoke` nativo e executor limitado.
3. **Verificação:** zero request extra em toda a matriz de contratos.

### Etapa 3 — Contexto com embedding único

1. **Testes** (`test_context_sources_concurrency.py`): exatamente um embedding;
   barriers provam overlap; resultados ordenados; fonte falha isoladamente;
   segredo/owner/game/NPC/epoch/dimensão permanecem isolados.
2. **Implementação:** adapters por vetor, aquisições sync/async e join estável.
3. **Verificação:** `ContextPack` serial e concorrente idênticos byte a byte nas
   fixtures determinísticas.

### Etapa 4 — Preparação, plano e rota

1. **Testes** (`test_turn_pipeline_concurrency.py`): incremento único; branches
   iniciam antes da liberação da barrier; dispatch espera ambas; chaves
   disjuntas; replan não roda em combate; falha aborta sem efeito; equivalência
   do estado e da ordem de chamadas.
2. **Implementação:** nós puros e fan-out/fan-in atrás da feature flag.
3. **Verificação:** grafo serial e concorrente passam a mesma suíte de rotas.

### Etapa 5 — Pulso de mundo puro

1. **Testes:** proposal não muta estado/RAG; contexto sobrepõe o request FAST;
   join aplica perigo uma vez; inválido/FallbackLLM não muda mundo; intent só
   nasce da consequência aplicada por Python.
2. **Implementação:** `propose_world_pulse` + `apply_world_pulse` e integração no
   storyteller.
3. **Verificação:** viagem/descanso mantêm narrativa e estado equivalentes.

### Etapa 6 — Finalizador canônico e derivação durável

1. **Testes** (`test_memory_derivation_jobs.py`): recompensa/evento aparece no
   recibo antes do job; enqueue atômico; dedupe; retry; job fora de ordem; hash,
   version ou epoch stale; restore; fila cheia; fallback extrativo; CLI inline.
2. **Implementação:** separar `archive_node`, payload limitado, handler e CAS.
3. **Verificação:** desligar worker não impede turno; religá-lo converge sem
   duplicar fato nem sobrescrever resumo novo.

### Etapa 7 — API, SSE e cancelamento

1. **Testes:** POST/SSE compartilham resultado; disconnect+retry; timeout antes e
   depois do commit; receipt idempotente; modos inline/queued mutuamente
   exclusivos; limites de concorrência respeitados.
2. **Implementação:** integrar ao `TurnService` e runtime sem alterar schemas HTTP.
3. **Verificação:** smoke API e stack local multiworker, sem chamadas reais.

### Etapa 8 — Gates, rollout e documentação

1. **Testes/benchmark:** gates R28/R29; comparar chamadas, custo, estado e spans.
2. **Implementação:** promover `concurrent` somente se gates passarem; manter
   rollback documentado e remover código shadow em follow-up com prazo.
3. **Verificação:** suíte completa, infra local, smoke real pareado e documentação.

## 5. Critérios de aceite

- [ ] Baseline das dez campanhas A versionado por rota/coorte.
- [ ] `critical_path_ms`, `work_ms`, `overlap_ms` e estágios observáveis sem texto
  sensível.
- [ ] Plano+rota e fontes de contexto provam overlap por barriers.
- [ ] Cada ContextPack faz no máximo um embedding compatível por consulta.
- [ ] `WorldPulse` não tem side effect antes do join/aplicação Python.
- [ ] Evento, recompensa, projeção, recibo e save confirmam antes da resposta.
- [ ] Derivação queued é atômica, idempotente, ordenada e protegida por epoch.
- [ ] `RoutedLLM.invoke` e `ainvoke` passam a mesma matriz de contratos.
- [ ] Nenhum cenário aumenta número de chamadas ou custo equivalente.
- [ ] Limite de concorrência 1 mantém correção e degrada de forma serial.
- [ ] Estado/recibo serial e concorrente são equivalentes nas fixtures.
- [ ] Gate controlado R28 e gate real pareado R29 aprovados.
- [ ] Zero regressão de invariantes `error`, saves e endpoints POST/SSE/CLI.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] `uv run pytest -m infra_local` verde na stack local.
- [ ] Guards de `FallbackLLM` presentes em todo structured output novo.
- [ ] Saves antigos continuam carregando com derivação inline/default seguro.
- [ ] `ESTADO_ATUAL.md` e `ROADMAP.md` refletem evidência, default e rollback.

## 6. Smoke test com LLM real

Somente após aprovação, conclusão/análise da matriz A e com teto explícito:

1. Clonar snapshots sanitizados de três coortes: replan, viagem com pulso e
   `archive_due`; nunca reutilizar o mesmo save mutável entre modos.
2. Executar três repetições `sequential` e três `concurrent` por coorte com o
   mesmo preset real, seed, timeout e teto — 18 turnos no total.
3. Confirmar `mock=false`, provider/tier esperado, zero fallback determinístico,
   zero erro/violação e chamadas por cenário não maiores que o baseline.
4. Comparar medianas/p95 conforme R29, além do estado mecânico, eventos,
   recompensa, recibo, memória depois da drenagem do worker e spans de overlap.
5. Simular worker indisponível, confirmar turno normalmente, iniciar worker e
   verificar convergência idempotente da derivação.

## 7. Riscos & compatibilidade

- **Burst de quota:** paralelizar chamadas independentes concentra requests no
  tempo. Semáforo por provider e limite 1 são o primeiro mecanismo de segurança;
  não há fallback especulativo.
- **Merge não determinístico:** LangGraph não garante ordem de conclusão de
  branches. Campos disjuntos e sort explícito são obrigatórios.
- **Side effect órfão:** uma branch pode completar antes de outra falhar. Por isso
  nenhuma branch paralela escreve RAG, DB, arquivo ou estado externo.
- **FAISS/thread safety:** concorrência só é habilitada depois de contrato com o
  adapter; se o backend não garantir reads concorrentes, um limiter/lock local
  mantém esse escopo serial sem desabilitar os demais ganhos.
- **Resumo atrasado:** o ledger/event log canônico cobre a janela ainda não
  derivada. Cursor explícito impede perda e stale overwrite.
- **Divergência sync/async:** núcleo compartilhado e contratos de paridade são
  gate; não manter loops copiados de fallback.
- **Cancelamento:** `TaskGroup` cancela irmãos em falha não tratada, mas efeitos
  externos só existem no finalizador/commit após join bem-sucedido.
- **Processo CLI encerrado:** default inline no runtime de arquivo evita perder
  derivação sem worker durável.
- **Mudança de comportamento:** a feature flag permite A/B técnico e rollback;
  nenhuma regra narrativa/mecânica é autorizada por esta spec.
