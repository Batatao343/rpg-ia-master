# SPEC-356 — embeddings-backoff-429

> **Status:** `done`
> **Criada:** 2026-10-28 · **Atualizada:** 2026-10-28
> **Depende de:** SPEC-039 (embeddings-provider)
> **Desbloqueia:** reindex global confiável com Jina

---

## 1. Contexto & Objetivo

`rag._JinaEmbeddingsHTTPX._embed` refazia a chamada na hora em status transitório
(429/5xx), sem backoff nem `Retry-After`. O reindex global (`python rag.py`) morreu com
`429 Too Many Requests` da Jina em 28/10. Em runtime (turno do jogo) não se pode dormir.

## 2. Requisitos

- **R1** — Com `backoff_seconds > 0`, antes de cada nova tentativa (429/5xx/erro de rede) dorme
  `base * 2**tentativa`, limitado a 60 s.
- **R2** — Se a resposta traz `Retry-After` (segundos ou data HTTP), ele substitui o atraso
  exponencial (também limitado a 60 s).
- **R3** — `backoff_seconds == 0` (padrão, runtime) nunca chama `time.sleep`.
- **R4** — `EMBEDDING_BACKOFF_SECONDS` (padrão 0) alimenta `_build_jina`. O CLI `python rag.py`
  faz `setdefault` de `EMBEDDING_BACKOFF_SECONDS=2` e `EMBEDDING_MAX_ATTEMPTS=6`.

### Fora de escopo

openai/ollama/gemini: usam clientes langchain com retry próprio; não há loop caseiro para
corrigir. `EMBEDDING_*` não são `RPG_*`, logo não entram em `config/flags.yaml`.

## 3. Design técnico

`rag.py`: `_parse_retry_after`, `_MAX_BACKOFF_SECONDS`, parâmetro `backoff_seconds` e método
`_sleep_before_retry` em `_JinaEmbeddingsHTTPX`; env lido em `_build_jina`; defaults no `__main__`.

## 4. Plano

Testes em `tests/test_embeddings_provider.py` (httpx MockTransport, `time.sleep` monkeypatchado):
Retry-After em segundos e em data HTTP, backoff exponencial com teto, base 0 não dorme, env.

## 5. Critérios de aceite

- [x] Testes novos + `tests/test_embeddings_provider.py` verdes (25)
- [x] Runtime (base 0) não dorme
- [ ] Revisão independente

## 6. Smoke test com LLM real

N/A (sem LLM); reindex real com Jina fica ao coordenador/dono.

## 7. Riscos & compatibilidade

Sem mudança de índice/pin. Runtime inalterado (base 0). Reindex pode levar até ~60 s por espera.
