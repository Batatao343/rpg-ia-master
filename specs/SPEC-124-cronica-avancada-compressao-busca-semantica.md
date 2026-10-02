# SPEC — Crônica avançada: compressão e busca semântica

> **Status:** `done` (2026-08-20 — aceite local completo; smoke real opt-in)
> **Criada:** 2026-08-17 · **Atualizada:** 2026-08-19
> **Depende de:** `fase-3.1-diario-cronica`, `polish-sessao` (`done`) ·
> `fase-10b-fundacao-local-portas-adapters` e
> `fase-10b-turnos-duraveis-concorrencia-fila` (`done`) · adapter pgvector depende de
> `fase-10b-pgvector-memoria-transacional`
> **Desbloqueia:** campanhas muito longas com diário legível e recuperação de
> acontecimentos por significado
> **Aceite local:** concluído, inclusive corpus PT-BR. O smoke SMART/embedding
> real da §6 permanece opt-in e só roda com teto de custo autorizado.

---

## 1. Contexto & Objetivo

A crônica atual registra milestones determinísticos e prosa do arquivista em
capítulos abertos por `arc_title`. O frontend já oferece busca textual local e a
API exporta `.txt`, mas todos os capítulos são enviados integralmente e a busca
só encontra palavras literais. Em campanhas longas, capítulos crescem sem uma
visão condensada e perguntas como “quando traímos o mercador do porto?” falham se
o texto usou outras palavras.

Esta spec preserva o registro bruto como fonte imutável e cria duas projeções:
um resumo navegável por capítulo e um índice semântico escopado à campanha. A
compressão nunca apaga evidência, nunca reescreve milestones mecânicos e nunca
bloqueia o turno. A busca recupera trechos e capítulos; não chama uma LLM para
inventar uma resposta sobre a própria história.

## 2. Requisitos

- **R1 — Raw imutável:** `chronicle[].entries` continua sendo a fonte da verdade.
  Compressão cria `digest` derivado e documentos de busca; não remove, combina ou
  altera `text`, `turn`, `kind` ou `event_id` originais.
- **R2 — Gatilhos fechados:** job de compressão é enfileirado quando um capítulo
  fecha ou quando o capítulo aberto ultrapassa 20 entradas ainda não cobertas
  pelo digest. O hash do conjunto de entradas impede recompressão sem mudança.
- **R3 — Fora do turno:** o commit do turno persiste raw + intenção/job. LLM de
  compressão e embedding ocorrem no worker; indisponibilidade nunca aumenta a
  latência do turno nem impede save/restore.
- **R4 — Milestones protegidos:** entradas `kind="milestone"` são copiadas para a
  estrutura factual do digest com texto original, turno e `event_id`. A LLM pode
  condensar apenas prosa e transições; não pode negar, fundir ou reinterpretar
  um evento aplicado.
- **R5 — Digest estruturado:** cada versão contém título curto, resumo em 3–8
  frases, personagens, locais, missões, itens únicos e intervalo de turnos, além
  dos milestones protegidos. IDs conhecidos permanecem IDs; nomes livres não
  ganham autoridade mecânica.
- **R6 — LLM roteada e resiliente:** compressão usa `get_llm(tier=SMART)` com
  Pydantic v2 e guard `isinstance`/`try`. `FallbackLLM`, schema inválido ou erro
  deixa o digest anterior intacto e grava falha retryable. Após tentativas, um
  digest extrativo Python mantém título, milestones e trechos inicial/final.
- **R7 — Versionamento/idempotência:** chave única
  `(game_id, timeline_epoch, chapter_id, source_hash, digest_profile_version)`.
  Retry, worker reiniciado e fechamento repetido não criam versões duplicadas.
- **R8 — Capítulo estável:** cada capítulo recebe `chapter_id` criado por Python;
  título/local não é chave. Saves antigos ganham IDs determinísticos derivados da
  posição e do conteúdo, com proteção contra colisão.
- **R9 — Índice separado:** documentos da crônica usam escopo
  `memory_scope="chronicle"`, isolado de lore, regras, memória geral da sessão e
  memória de NPC. A busca nunca retorna um fato apenas porque ele está no RAG
  geral.
- **R10 — Busca híbrida:** `POST /game/chronicle/search` combina similaridade
  vetorial com lexical/FTS e fusão determinística. A semântica recupera paráfrase;
  nomes/IDs/turnos exatos continuam fortes. Não há chamada de chat/geração por
  consulta.
- **R11 — Escopo inicial:** busca ocorre somente na campanha informada e do owner
  autenticado. Não pesquisa outras campanhas, outros usuários, lore secreta ou
  estado não revelado.
- **R12 — Resultado rastreável:** cada hit devolve `chapter_id`, título, trecho
  raw ou digest, turnos inicial/final, `entry_ids`/`event_ids` relacionados e
  razão apresentável (`semântico|texto exato|ambos`). A UI salta ao capítulo e
  expande os registros originais.
- **R13 — Sem vazamento:** somente texto já presente na crônica pública do
  jogador entra no índice. Prompt de compressão não recebe Codex hidden/secret,
  memória privada de NPC nem projeção não descoberta.
- **R14 — Degradação honesta:** sem embeddings, índice atrasado ou provider
  incompatível, endpoint executa busca lexical sobre raw/digests e retorna
  `mode="lexical_fallback"`; não finge resultado semântico nem retorna 500.
- **R15 — UX em camadas:** capítulo comprimido mostra digest por default, contagem
  e botão “Ver registros originais”. Capítulo pequeno/sem digest mantém a UI
  atual. Busca local antiga pode ser fallback, mas o caminho principal usa o
  endpoint quando disponível.
- **R16 — Export sem perda:** `.txt` continua exportando todas as entradas raw na
  ordem original. Pode incluir o digest antes delas com marcador claro
  “Resumo derivado”; nunca exporta somente a compressão.
- **R17 — Checkpoint e epoch:** restore volta raw/digests à versão do checkpoint e
  incrementa epoch. Jobs/vetores do futuro divergente ficam descartados pelo
  filtro de epoch; reconciliação reindexa o estado restaurado de forma idempotente.
- **R18 — Limites:** query normalizada de 2–300 caracteres; `top_k` 1–10; resposta
  limita tamanho de snippets. Prompt de compressão tem orçamento por capítulo e
  usa chunk/reduce para capítulos extremos sem truncar milestones.
- **R19 — Observabilidade:** medir backlog, capítulos raw/digeridos, entradas
  cobertas, latência/custo da compressão, embedding, busca p50/p95, fallback
  lexical e falhas. Texto da crônica/query não entra em log comum.
- **R20 — Qualidade verificável:** corpus PT-BR fixo contém paráfrases, nomes,
  negação e capítulos parecidos. Recall@5 semântico/híbrido deve superar lexical
  e atingir ≥85% no conjunto de aceite, sem hit de campanha diferente.

### Fora de escopo

- Chat “pergunte à sua crônica”, resposta generativa ou RAG conversacional.
- Busca entre todas as campanhas do usuário nesta primeira versão.
- Apagar raw para economizar espaço.
- Reescrever o estilo da crônica existente ou gerar capítulos retroativos.
- Indexar transcript completo de cada turno; somente entradas da crônica.
- Executar/migrar toda a Fase 10b nesta spec.

## 3. Design técnico

### 3.1 Estado e modelos

**Alterar `state.py`:**

```python
class ChronicleDigest(TypedDict, total=False):
    version: int
    source_hash: str
    profile_version: str
    status: str                 # pending|ready|failed|extractive_fallback
    covered_entry_count: int
    from_turn: int
    to_turn: int
    short_title: str
    summary: str
    characters: list[str]
    locations: list[str]
    quests: list[str]
    unique_items: list[str]
    milestone_entry_ids: list[str]

class ChronicleChapter(TypedDict, total=False):
    chapter_id: str
    title: str
    started_turn: int
    location: str
    entries: list[ChronicleEntry]
    digest: ChronicleDigest
```

Entradas recebem `entry_id` determinístico/UUID de domínio para rastreio. Em
migração, `chapter_id` e `entry_id` são derivados de game + ordem + hash; novos
registros são criados antes do append e persistidos normalmente.

**Novo schema Pydantic em `services/chronicle_compression.py`:**

```python
class ChronicleDigestLLM(BaseModel):
    short_title: str
    summary: str
    characters: list[str]
    locations: list[str]
    quests: list[str]
    unique_items: list[str]
```

Milestones não fazem parte do output autoritativo da LLM; Python os anexa do raw.

### 3.2 Serviços e portas

**Novos arquivos:**

- `services/chronicle_compression.py` — source hash, payload público, compressão,
  guard e fallback extrativo;
- `services/chronicle_search.py` — normalização, documentos, RRF, DTO de hit;
- `workers/chronicle_jobs.py` — handlers `compress_chronicle` e
  `embed_chronicle`;
- `infrastructure/faiss_chronicle.py` — adapter legacy em namespace físico
  `data/saves_memory/{game_id}/chronicle/`, pinado ao provider do índice;
- `infrastructure/pgvector_chronicle.py` — adapter do `MemoryStore` da 10b.5 com
  scope/owner/game/epoch/chapter;
- `scripts/reindex_chronicle.py` — `--game-id`, `--check`, `--all-local`, sem
  destruir índice válido antes de terminar o novo;
- `tests/fixtures/chronicle_search_ptbr.json` — corpus/oráculos de recall.

Porta alinhada à 10b.1:

```python
@dataclass(frozen=True)
class ChronicleDocument:
    document_id: str
    owner_id: str
    game_id: str
    timeline_epoch: int
    chapter_id: str
    source_kind: Literal["entry", "digest"]
    text: str
    from_turn: int
    to_turn: int
    metadata: dict[str, Any]

class ChronicleSearchStore(Protocol):
    def upsert(self, documents: Sequence[ChronicleDocument]) -> None: ...
    def search(self, *, owner_id: str, game_id: str, timeline_epoch: int,
               query: str, top_k: int) -> list[SearchCandidate]: ...
    def discard_after_epoch(self, *, owner_id: str, game_id: str,
                            timeline_epoch: int) -> None: ...
```

FAISS implementa compatibilidade `legacy`; pgvector/FTS é o perfil local/hosted.
Vetores de provider/modelo diferente nunca são misturados; reindex é explícito.

### 3.3 Pipeline

```text
append raw entry
→ compute chapter source_hash/covered count
→ if close or >20 uncovered: enqueue compress_chronicle atomically
→ worker builds public-only payload + protected milestones
→ SMART structured output (or extractive fallback)
→ persist digest version + enqueue embed_chronicle
→ index raw entries + digest with owner/game/epoch/chapter filters
```

Capítulo aberto com 21+ entradas pode receber digest parcial. Novas entradas não
invalidam o digest pronto: UI informa `covered_entry_count`, e novo job só ocorre
quando há mais 20 descobertas ou no fechamento. Ao fechar, o digest final cobre
todas as entradas.

### 3.4 API e frontend

```python
class ChronicleSearchRequest(BaseModel):
    game_id: UUID
    query: str = Field(min_length=2, max_length=300)
    top_k: int = Field(5, ge=1, le=10)

class ChronicleSearchHit(BaseModel):
    chapter_id: str
    chapter_title: str
    snippet: str
    source_kind: Literal["entry", "digest"]
    from_turn: int
    to_turn: int
    entry_ids: list[str]
    event_ids: list[str]
    match_kind: Literal["semantic", "lexical", "hybrid"]

class ChronicleSearchResponse(BaseModel):
    mode: Literal["hybrid", "semantic", "lexical_fallback"]
    index_current: bool
    hits: list[ChronicleSearchHit]
```

- `POST /game/chronicle/search` resolve save/owner sem permitir enumeração.
- `_chronicle_block` passa `chapter_id`, digest e contagens, mas raw continua
  disponível para expansão.
- `ChroniclePanel.tsx` troca lista longa por resumo expansível e busca backend com
  debounce/cancelamento. Resultado foca/abre capítulo e destaca entrada/turno.
- Export mantém compatibilidade e recebe query opcional `include_digests=true`.

## 4. Plano passo a passo

### Etapa 1 — IDs, migração e digest puro

1. **Testes** (`tests/test_chronicle_advanced.py`): IDs estáveis, migração
   idempotente, source hash, raw intocado, milestones copiados literalmente,
   fallback extrativo e capítulo pequeno sem job.
2. **Implementação:** schema, migração e funções puras.
3. **Verificação:** testes focados verdes.

### Etapa 2 — Job assíncrono de compressão

1. **Testes:** trigger em 21 entradas/fechamento, dedupe, partial→final, guard de
   FallbackLLM, erro preserva digest anterior e job/commit atômicos.
2. **Implementação:** intents, worker e persistência por adapters.
3. **Verificação:** testes unitários + integração Postgres local.

### Etapa 3 — Índice e busca híbrida

1. **Testes** (`tests/test_chronicle_search.py`): isolamento, paráfrase, lexical
   exato, RRF estável, fallback sem embedding, restore/epoch e recall@5 ≥85%.
2. **Implementação:** stores FAISS/pgvector, indexer, endpoint e reindex CLI.
3. **Verificação:** corpus fixo e contratos de ambos adapters.

### Etapa 4 — Frontend e export

1. **Testes:** digest default/raw expansível, navegação por hit, debounce,
   fallback local, export raw completo e mobile 390 px.
2. **Implementação:** DTOs, `ChroniclePanel`, estilos e export.
3. **Verificação:** build e browser smoke.

### Etapa 5 — Operação e qualidade real

1. **Testes:** backlog/retry/redaction, capítulos extremos, provider fora e
   reindex atômico.
2. **Implementação:** métricas, alertas e documentação operacional.
3. **Verificação:** smoke real, suíte completa e relatório de recall/latência.

## 5. Critérios de aceite

- [x] Nenhuma entrada raw é removida ou reescrita pela compressão.
- [x] Capítulo fecha/ultrapassa 20 entradas sem bloquear o turno.
- [x] Milestones permanecem literais e rastreáveis ao `event_id`.
- [x] Erro de LLM produz retry/fallback extrativo, nunca perda/500.
- [x] Busca semântica/híbrida é restrita à campanha e owner atuais.
- [x] Busca não chama LLM generativa e degrada honestamente para lexical.
- [x] Corpus PT-BR atinge recall@5 ≥85% e supera baseline lexical.
- [x] Restore/checkpoint não retorna documentos de timeline futura.
- [x] UI mostra digest, expande raw e salta ao resultado em desktop/390 px.
- [x] Export continua contendo todas as entradas originais.
- [x] `cd web && npm run build` verde.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de `FallbackLLM` presente na compressão estruturada.
- [x] Saves antigos continuam carregando com IDs/digest default.

## 6. Smoke test com LLM real

1. Em campanha isolada, criar/usar capítulo com mais de 20 entradas e fechar o
   arco; confirmar que o turno termina antes do worker e raw permanece idêntico.
2. Processar o job SMART real; comparar digest com milestones/eventos e rejeitar
   qualquer contradição factual.
3. Buscar três paráfrases PT-BR que não compartilham palavras principais com as
   entradas; confirmar hits corretos e navegação ao turno.
4. Desligar embeddings e repetir uma busca exata; confirmar
   `lexical_fallback`, sem 500 ou alegação de semântica.
5. Restaurar checkpoint anterior e garantir que busca não encontra fatos do
   futuro descartado.

## 7. Riscos & compatibilidade

- **Resumo alucinado:** milestones são protegidos fora do schema da LLM, raw é
  sempre expansível e fallback extrativo evita depender de prosa sintética.
- **Índice fora de sincronia:** source hash, epoch, status `index_current` e CLI de
  reconciliação tornam atraso visível e reparável.
- **Custo:** compressão ocorre por blocos/fechamento, não por entrada; busca não
  gera texto. Embedding continua pinado por índice.
- **Payload:** manter raw no `GameResponse` pode crescer; implementação deve medir
  e, se necessário, paginar entries sem mudar a garantia de acesso. Paginação
  precisa ser registrada como ajuste da spec antes do código.
- **Dependência 10b:** fila evita colocar SMART/embedding no turno. Implementação
  anterior à fundação local-first não é autorizada por esta spec.
