# SPEC-419 — revisão terra (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sonnet (terra), domínio concorrência · **Data:** 2026-11-13 · **Commit revisado:** `42c5795a`

## Escopo

`git diff main...HEAD` (eafb9aa9, 42c5795a): `services/embedding_guard.py` (novo), `rag.py` (`_embed`), `services/context_sources.py`, `services/context_prefetch.py`, flags, catálogo de eventos, testes. Sem staging, sem suíte completa.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | tests/test_embedding_guard.py (todos) | O vermelho na `main` dos 11 testes novos é por ImportError de `services.embedding_guard`, não por comportamento. Só `test_consumer_espera_prefetch_lento...` (test_context_prefetch.py) é vermelho por comportamento. A evidência da spec (`test_contexto_passa_dentro_do_prazo...` vermelho por tempo) não foi demonstrada. | Aceitável para o pouso; opcional: provar uma vez com um stub do módulo na main. |
| P3-1 | P3 | rag.py:~366-371 | `_sleep_before_retry` não é limitado pelo orçamento restante. Com `EMBEDDING_BACKOFF_SECONDS>0` (a CLI de reindex força 2, rag.py:1635; o runtime usa 0) um 429 com Retry-After dentro do escopo dormiria até 60 s, acima de T. Hoje inalcançável no runtime. | Dentro do escopo, usar `min(delay, remaining)` ou não dormir. |
| P3-2 | P3 | rag.py:~381-385 | `httpx.Timeout(left)` vale por fase (connect/read/write/pool), então o pior caso passa de T. A spec documenta (~2T). | Nenhuma. |
| P3-3 | P3 | rag.py:~383 | Orçamento esgotado após 5xx rápido (left < 0,1 s) levanta o `HTTPStatusError` sem evento `query_degraded`. Degradação silenciosa só nesse canto. | Opcional: emitir `_degraded("timeout"...)` ou nota na spec. |
| P3-4 | P3 | services/embedding_guard.py:_env_float, enabled | O dup_helpers acusa nomes iguais em creature_gen/shared_pool/scene_cards. Os helpers têm assinaturas e faixas próprias; não há duplicação real. | Nenhuma. |

Nenhum P0/P1.

## Conferência dos pontos pedidos

1. Vermelho→verde: ver tabela. 12/13 OK; o "FAIL" é o teste de kill switch do prefetch, que por desenho já é verde na main (guarda de regressão do comportamento antigo). Não é achado.
2. ContextVar: `interactive_query()` é aberto dentro de `embed_context_query_uncached`, na thread que executa a chamada HTTP (`prepare_shared_query_vector` → `embed_query` é síncrono, sem executor interno). O prefetch (copy_context) chama a função uncached, que seta o escopo na própria thread do worker; o escopo é resetado no `finally` (token reset de `_SCOPE` e `_DEADLINE`). `Grep interactive_query(` mostra um único chamador de produção (context_sources.py:75). O job `embed_memory`, a escrita e o reindex nunca entram no escopo, e o `check_breaker`/`note_timeout` saem se `_SCOPE` é falso (embedding_guard.py:121,133). Não há vazamento entre requisições, porque ContextVar é por thread/contexto. O estado global é só `_open_until`, sob `_LOCK`.
3. Prazo total: `deadline()` fixa `monotonic()+T` na primeira chamada do escopo, e cada tentativa usa `remaining`. Timeout levanta sem 2ª tentativa; 5xx/429 rápido faz retry dentro do orçamento. Backoff: ver P3-1.
4. Disjuntor: `time.monotonic`; `max(_open_until, now+B)` sob lock (dois timeouts simultâneos coerentes, coberto por teste); expira por tempo; `B=0` desliga. Só `httpx.TimeoutException` chama `note_timeout`: 4xx, 5xx e erro de transporte não abrem a janela (rag.py:446-449).
5. Degradação: `prepare_shared_query_vector` captura `EmbeddingSkipped`/timeout e devolve `(None, provider, model)`; evento `embedding.query_degraded` com `reason`, `waited_ms`, `budget_ms`, `breaker_s`, igual ao catálogo (events.py e EVENTOS_DE_LOG.md); sem texto da consulta (teste de log).
6. Kill switch: `enabled()` falso torna `interactive_query` no-op e `prefetch_wait` devolve a base; `_embed` com `end=None` mantém o fluxo antigo. Há teste do 30 s × 2 e do `take` com 2,0 s.
7. Flags: 3 entradas em config/flags.yaml (kill_switch/ops, spec SPEC-419), 3 linhas no .env.example; `test_flag_registry`, `test_log_event_registry` e `test_size_budget` verdes; rag.py 1643 linhas (≤ 1649).

## Evidência verificada

```
| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_context_prefetch.py::test_consumer_espera_prefetch_lento_ate_o_prazo_sem_embedding_duplo | vermelho | verde | OK |
| tests/test_context_prefetch.py::test_prefetch_espera_antiga_com_kill_switch_off | verde | verde | FAIL: nao prova a mudanca (esperado: guarda do comportamento antigo) |
| tests/test_embedding_guard.py::* (11 testes) | vermelho (import) | verde | OK |
red_green: 12/13 OK
```

## Correções aplicadas

Nenhuma (revisão).

## Pendências

P3-1 e P3-3 podem virar nota/ajuste num follow-up de baixo custo; nada bloqueia o pouso.

## Comandos rodados

```text
bash scripts/dev/red_green.sh 419 → 12/13 OK
bash scripts/dev/pt.sh (9 arquivos do escopo) → 103 passed
scripts/dev/dup_helpers.py --diff main...HEAD → só homônimos com semântica própria
```
