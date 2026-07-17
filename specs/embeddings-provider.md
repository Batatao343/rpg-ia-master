# SPEC — Embeddings multi-provider (sair da dependência do Google)

> **Status:** `draft`
> **Criada:** 2026-07-16 · **Atualizada:** 2026-07-16
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
queries por turno são frases) — 10M grátis da Jina cobrem MESES. Decisão
proposta: **Jina primário**, Ollama como opção 100% local, Google mantido como
legado (se créditos voltarem).

**Regra dura:** embeddings NÃO têm fallback em runtime como o `RoutedLLM` —
vetores de providers diferentes no mesmo índice FAISS são lixo (dimensão e
espaço incompatíveis). Provider é **fixado por índice**; trocar = re-indexar.

## 2. Requisitos

- **R1** — `rag.get_embeddings()` resolve por env `RPG_EMBEDDINGS`
  (`jina` | `google` | `openai` | `ollama`; default `jina` se `JINA_API_KEY`
  existir, senão `google` — comportamento atual preservado).
- **R2** — Todo índice FAISS gerado grava `embeddings_meta.json` ao lado
  (`{provider, model, dims}`). No load, mismatch com o provider ativo →
  erro claro instruindo `uv run python rag.py` (global) — nunca busca com
  vetor incompatível.
- **R3** — Memória de sessão (`data/saves_memory/{game_id}/`): mesmo esquema
  de meta por diretório. Sessão antiga com provider diferente → memória
  vetorial daquela sessão é IGNORADA com log warning (jogo segue; resumo do
  archivist cobre) — sem crash, sem mistura.
- **R4** — Sem key do provider ativo: comportamento atual preservado
  (embeddings desativados com aviso; jogo funciona sem RAG).
- **R5** — `reindex_global()` re-gera lore+regras com o provider ativo;
  `scripts/`/docs atualizados (`.env.example` ganha `JINA_API_KEY` e
  `RPG_EMBEDDINGS`).

### Fora de escopo

- Fallback automático entre providers de embedding (proibido por design).
- Migrar memórias de sessão antigas (R3 as ignora).
- Reranker / mudança de chunking.

## 3. Design técnico

- **`rag.py`** — registro `_EMBEDDING_BUILDERS: dict[str, Callable]`:
  - `google`: `GoogleGenerativeAIEmbeddings("models/gemini-embedding-001")` (atual)
  - `jina`: `langchain_community.embeddings.JinaEmbeddings(model_name="jina-embeddings-v3")`
    (`JINA_API_KEY`)
  - `openai`: `langchain_openai.OpenAIEmbeddings(model="text-embedding-3-small")`
  - `ollama`: `langchain_ollama.OllamaEmbeddings(model="bge-m3")` (extra `ollama`)
  `get_embeddings()` mantém assinatura/singleton; escolhe builder por R1.
- **Meta:** `_write_meta(path)` / `_check_meta(path) -> bool` chamados em
  `ingest_file`, `add_memory_to_session`, `add_npc_memory` e nos loads
  (`query_rag`, `query_npc_memory`).
- **Deps:** `langchain-community` (já presente via langchain) p/ Jina — conferir;
  senão chamada httpx direta (API é um POST simples).
- Índices `faiss_lore_index/`/`faiss_rules_index/` são gerados — trocar
  provider exige rodar `uv run python rag.py` uma vez (documentar em
  ESTADO_ATUAL).

## 4. Plano passo a passo

### Etapa 1 — registro + meta (offline, com fake embeddings)
1. **Testes** (`tests/test_embeddings_provider.py`) — usar embedding fake
   determinístico (classe local) p/ não precisar de rede:
   `test_env_seleciona_provider` (monkeypatch env + builders);
   `test_meta_e_gravada_no_ingest`; `test_load_com_meta_divergente_falha_claro`;
   `test_sessao_antiga_sem_meta_e_ignorada_com_warning`.
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

- [ ] R1–R5 com testes
- [ ] `uv run pytest` verde (suíte completa offline, sem rede)
- [ ] Re-index global real com Jina + 3 queries de lore relevantes
- [ ] Partida nova completa (CLI, 3+ turnos reais) com archivist persistindo
  memória de sessão sem erro de embedding
- [ ] Saves antigos carregam; sessão antiga com memória Google é ignorada com
  warning (sem crash)

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
