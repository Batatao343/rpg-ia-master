# SPEC — Embeddings multi-provider (Gemini rebaixado a último fallback)

> **Status:** `done` (2026-07-17 — 804 offline verdes; re-index real com Jina
> executado, smoke §6 3/3: lore + regras pinados em jina, 3 queries PT-BR sem
> 429, memória de sessão round-trip. Ordem de dev: **1/8**)
> **Criada:** 2026-07-16 · **Atualizada:** 2026-07-16 (decisão do usuário:
> outro provider como primário; Gemini é caro/sem créditos — fica SÓ como
> último fallback da cadeia)
> **Depende de:** —
> **Desbloqueia:** RAG/memória de longo prazo de volta (mortos desde 2026-07-14)

---

## 1. Contexto & Objetivo

Desde 2026-07-14 TODOS os embeddings falham com 429 "prepayment credits are
depleted" (Google `gemini-embedding-001`) — RAG global (lore/regras) e memória
vetorial de sessão estão **mortos** em produção. `rag.get_embeddings()`
(rag.py:21) é hard-coded no provider Google.

Pesquisa de alternativas (2026-07-16; DeepSeek **não oferece** embeddings —
só chat, confirmado na doc oficial):

| Provider | Preço/M tokens | PT-BR/multilingual | Nota |
|---|---|---|---|
| **Jina v3** | $0.02 + **10M tokens grátis** por key | 89 línguas, forte (MTEB 65.5) | 1024 dims, 8k ctx — recomendado hosted |
| OpenAI `text-embedding-3-small` | $0.02 ($0.01 batch) | decente | `langchain-openai` já é dep do projeto |
| Google `gemini-embedding-001` | — (sem créditos) | bom | atual; volta a funcionar se recarregar |
| Cohere embed-v4 | $0.10 | excelente | mais caro, sem vantagem no nosso volume |
| **Ollama local (`bge-m3`)** | **$0** | excelente | offline, alinhado ao modo simulado; dep pesada |

Volume do projeto é minúsculo (re-index completo ≈ centenas de k tokens;
queries por turno são frases) — 10M grátis da Jina cobrem MESES. **Decisão
(usuário, 2026-07-16): Gemini é caro demais para ser primário — vira o ÚLTIMO
candidato da cadeia**, usado apenas quando nenhum outro provider tem key/dep.
Espelha a filosofia do `ROUTES` de LLM: primário barato/bom, fallback vivo.

**Regra dura (diferença vs `RoutedLLM`):** embeddings NÃO têm fallback
POR REQUEST — vetores de providers diferentes no mesmo índice FAISS são lixo
(dimensão e espaço incompatíveis). O fallback aqui é **na RESOLUÇÃO** (qual
provider está disponível ao construir/abrir índice); uma vez construído, o
índice fica **fixado** ao provider que o gerou; trocar = re-indexar. Se o
provider de um índice existente perder a key, aquele índice fica DESATIVADO
com aviso claro (nunca consultado com vetor de outro provider).

## 2. Requisitos

- **R1** — Cadeia ordenada de candidatos
  `EMBEDDING_ROUTES = ["jina", "openai", "ollama", "gemini"]` em `rag.py`:
  `get_embeddings()` resolve na inicialização o PRIMEIRO candidato com
  key/dep disponível (`JINA_API_KEY` → `OPENAI_API_KEY` → Ollama alcançável →
  `GOOGLE_API_KEY`). **Gemini é sempre o último** — só assume sem nenhum
  outro configurado (preserva zero-config de quem só tem key Google).
- **R1b** — Override por env `RPG_EMBEDDINGS=<provider>` força um candidato
  específico (pula a cadeia; análogo ao `LLM_PROVIDER`).
- **R2** — Todo índice FAISS gerado grava `embeddings_meta.json` ao lado
  (`{provider, model, dims}`). No load, o índice é consultado com o provider
  DA META (mesmo que não seja o primário da cadeia — pin por índice). Meta
  presente mas provider indisponível (key/dep sumiu) → índice DESATIVADO com
  warning claro instruindo re-index (`uv run python rag.py`) ou repor a key —
  nunca busca com vetor incompatível. Índice legado SEM meta → assume
  `gemini` (comportamento histórico).
- **R3** — Memória de sessão (`data/saves_memory/{game_id}/`): mesmo esquema
  de meta por diretório. Sessão antiga cujo provider está indisponível →
  memória vetorial daquela sessão é IGNORADA com log warning (jogo segue;
  resumo do archivist cobre) — sem crash, sem mistura. Memória NOVA é criada
  com o provider primário resolvido.
- **R4** — Nenhum candidato da cadeia disponível: comportamento atual
  preservado (embeddings desativados com aviso; jogo funciona sem RAG).
- **R5** — `reindex_global()` re-gera lore+regras com o provider ativo;
  `scripts/`/docs atualizados (`.env.example` ganha `JINA_API_KEY` e
  `RPG_EMBEDDINGS`).

### Fora de escopo

- Fallback automático entre providers de embedding (proibido por design).
- Migrar memórias de sessão antigas (R3 as ignora).
- Reranker / mudança de chunking.

## 3. Design técnico

- **`rag.py`** — `EMBEDDING_ROUTES: list[str]` (ordem = R1) + registro
  `_EMBEDDING_BUILDERS: dict[str, Callable]`:
  - `jina`: `langchain_community.embeddings.JinaEmbeddings(model_name="jina-embeddings-v3")`
    (`JINA_API_KEY`) — **primário**
  - `openai`: `langchain_openai.OpenAIEmbeddings(model="text-embedding-3-small")`
  - `ollama`: `langchain_ollama.OllamaEmbeddings(model="bge-m3")` (extra `ollama`)
  - `gemini`: `GoogleGenerativeAIEmbeddings("models/gemini-embedding-001")`
    (atual) — **último fallback, nunca primário**
  `get_embeddings()` mantém assinatura/singleton; resolve pela cadeia (R1/R1b)
  e loga o vencedor (`rpg.rag`: "embeddings ativos: jina"). Builder levanta em
  falha → próximo candidato (só na RESOLUÇÃO; nunca por request).
  `get_embeddings_for(provider)` novo p/ abrir índice pinado (R2/R3).
- **Meta:** `_write_meta(path)` / `_read_meta(path) -> Optional[dict]`
  chamados em `ingest_file`, `add_memory_to_session`, `add_npc_memory` e nos
  loads (`query_rag`, `query_npc_memory`).
- **Deps:** `langchain-community` (já presente via langchain) p/ Jina — conferir;
  senão chamada httpx direta (API é um POST simples).
- Índices `faiss_lore_index/`/`faiss_rules_index/` são gerados — trocar
  provider exige rodar `uv run python rag.py` uma vez (documentar em
  ESTADO_ATUAL).

## 4. Plano passo a passo

### Etapa 1 — cadeia + registro + meta (offline, com fake embeddings)
1. **Testes** (`tests/test_embeddings_provider.py`) — usar embedding fake
   determinístico (classe local) p/ não precisar de rede:
   `test_cadeia_resolve_primeiro_com_key` (JINA+GOOGLE setadas → jina vence);
   `test_gemini_so_assume_sem_nenhum_outro` (só GOOGLE_API_KEY → gemini);
   `test_override_rpg_embeddings_forca_provider`;
   `test_meta_e_gravada_no_ingest`;
   `test_indice_pinado_usa_provider_da_meta` (primário=jina, índice gemini com
   key → consulta via gemini);
   `test_meta_indisponivel_desativa_indice_com_warning`;
   `test_indice_legado_sem_meta_assume_gemini`.
2. **Implementação:** registro, meta, checks.
3. `uv run pytest` verde.

### Etapa 2 — Jina builder + docs
1. **Testes:** `test_jina_builder_sem_key_desativa` (R4).
2. **Implementação:** builder + `.env.example` + docs.
3. `uv run pytest` verde.

### Etapa 3 — re-index real
1. Com `JINA_API_KEY`: `uv run python rag.py` → índices novos com meta jina.
2. Verificação manual: `query_rag("Legião de Ferro", "lore")` devolve chunks
   relevantes em PT.

## 5. Critérios de aceite

- [x] R1–R5 com testes (`tests/test_embeddings_provider.py`, 12 casos)
- [x] `uv run pytest` verde (suíte completa offline, sem rede) — 804 passed, 1 skip
- [x] Re-index global real com Jina + 3 queries de lore relevantes — lore
  (2203 chunks) + regras pinados em jina; queries "Legião de Ferro" / "Abismo e
  entropia" retornam chunks PT-BR, zero 429
- [x] Archivist persistindo memória de sessão sem erro de embedding —
  `add_memory_to_session` + `query_rag(game_id=...)` round-trip recupera o fato
  (meta sessão = jina). *(Rate limit free = 100k tokens/min: re-index do Codex
  esgota o minuto; regras precisaram de ~70s de espera — não é erro.)*
- [x] Saves antigos carregam; sessão antiga com memória Google é ignorada com
  warning (sem crash) — coberto por `test_meta_indisponivel_desativa_indice_com_warning`
  + `test_indice_legado_sem_meta_assume_gemini`

## 6. Smoke test com LLM real

1. `RPG_EMBEDDINGS=jina uv run python rag.py` → índices + meta.
2. Turno real que dispare RAG (pergunta de lore) → sem 429, chunk citado.
3. `add_memory_to_session` num jogo novo → query da memória no turno seguinte.

## 7. Riscos & compatibilidade

- Índices antigos (Google, 768 dims) vs Jina (1024): R2 impede mistura; o
  custo é re-indexar (barato — lore local).
- Qualidade PT-BR da Jina v3: forte em benchmark; validar com as 3 queries do
  aceite antes de apagar índices antigos (guardar `faiss_*_index/` num zip até
  o aceite passar).
- Rate limit Jina free: irrelevante no nosso volume (queries por turno).
- `allow_dangerous_deserialization=True` segue obrigatório nos loads (regra
  existente do projeto).
