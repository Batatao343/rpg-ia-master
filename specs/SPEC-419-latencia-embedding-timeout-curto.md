# SPEC-419 — latencia-embedding-timeout-curto

> **Status:** `approved` (dono, 13/11: "pode. e execute elas")
> **Criada:** 2026-11-13 · **Atualizada:** 2026-11-13
> **Depende de:** SPEC-039, SPEC-317 (prefetch, R5) e SPEC-356 (backoff da Jina), todas `done`
> **Desbloqueia:** nada
> **Risco:** `médio` (thread, timeout e disjuntor no caminho do turno; sem persistência, schema, API pública ou eval) → revisor Sonnet
> **Requer:** staging (smoke §6)
> **Domínios de revisão:** concorrência
> **Evidência:** teste que falha antes: um provedor Jina falso que trava até o timeout da requisição (MockTransport, teto de 3 s por tentativa) faz `embed_context_query_uncached` + `acquire_context_sources` levar ~6 s hoje (2 × 3 s). Com a spec e prazo de 0,3 s, termina em < 1 s, com o contexto vazio e sem exceção (`test_contexto_passa_dentro_do_prazo_com_provedor_travado`)

---

## 1. Contexto & Objetivo

Medição L0 no staging, 13/11 (`docs/auditorias/latencia-turno-medicao-2026-11-13.md:66`): em 2 turnos seguidos, o provedor de embeddings (Jina) travou. A etapa de contexto levou **45.737 ms** (turno 7, rota `npc_actor`) e **19.938 ms** (turno 8, `storyteller`) (`docs/auditorias/latencia-l0-2026-11-13/resultado.json:5882,5979`). Os logs mostram `provider.attempt` `embedding` `timeout` de 30.016 ms e `context.prefetch_miss` `TimeoutError`. É o pior caso medido (2 de 60 turnos). Nos outros 57 turnos o contexto ficou em ~0,3 s de mediana (tabela do mesmo arquivo, `:46`).

Causa no código:
- `rag.py:474-475`: `_build_jina` lê `EMBEDDING_TIMEOUT_SECONDS` (default `30`) e `EMBEDDING_MAX_ATTEMPTS` (default `2`). O cliente httpx é criado uma vez com esse timeout (`rag.py:357-364`) e fica no cache `_embeddings_cache` (`rag.py:571-583`). O mesmo objeto atende **consulta do turno, escrita e job**.
- `rag.py:394-461` (`_JinaEmbeddingsHTTPX._embed`): um `httpx.TimeoutException` em `:447-458` leva à 2ª tentativa com o mesmo limite de 30 s, e o backoff de runtime é 0 (`:481`).
- Caminho da consulta no turno: `services/context_builder.py:891-896` → `services/context_sources.py:49-64` (`embed_context_query`: com `turn` e sem NPC, usa o prefetch) → `:67-84` (`embed_context_query_uncached`, semáforo `RPG_EMBEDDING_MAX_CONCURRENCY`=2) → `rag.py:1018-1064` (`prepare_shared_query_vector`, que **já** captura a exceção e devolve `(None, provider, model)`).
- O prefetch (`services/context_prefetch.py:84-123`, worker único em `:50`) faz a mesma chamada em paralelo ao roteador. `take` (`:126-148`) espera `RPG_CONTEXT_PREFETCH_WAIT_S` (default 2,0 s, `:39-43`). Depois disso registra `prefetch_miss` (`:143-146`) e o chamador **embeda de novo em linha** (`context_sources.py:61-64`), pagando outra espera longa enquanto o prefetch ainda está pendurado.
- A degradação já existe e é a desejada: com `vector is None` e `embedding_provider` preenchido, os leitores devolvem `""` e não tentam a busca textual, que embedaria outra vez (`context_sources.py:103-106`). Só o tempo de espera está errado.

Objetivo (decisão do dono, 13/11): na **consulta** do turno, esperar poucos segundos e seguir sem a busca vetorial naquele turno. Depois de um travamento, pular a consulta por um tempo curto para não pagar a espera de novo no turno seguinte. Com o provedor respondendo normal, nada muda. Escrita, indexação e jobs mantêm o limite longo.

## 2. Requisitos

- **R1 — escopo interativo.** Um `ContextVar` de módulo novo (`services/embedding_guard.py`) marca "consulta interativa". `embed_context_query_uncached` (`services/context_sources.py:67`) entra nesse escopo em volta de `prepare_shared_query_vector`. Isso cobre o prefetch (`context_prefetch._embed` → `:78-81`), o embed em linha da história e o pack do NPC (`context_builder.py:891-896`, `npc_id` → sem prefetch). Nenhum outro chamador entra no escopo.
- **R2 — prazo total por chamada.** Dentro do escopo, `_JinaEmbeddingsHTTPX._embed` tem um orçamento total de `T` segundos (`RPG_EMBEDDING_QUERY_TIMEOUT_S`, default **6,0**, faixa aceita [0,1; 30], valor inválido → default) somando todas as tentativas. Cada tentativa recebe `timeout=httpx.Timeout(restante)` na própria requisição (`client.post(..., timeout=...)`), e não abre tentativa nova com menos de 0,1 s restante. O retry rápido de 429/5xx (`rag.py:403-415`) continua valendo dentro do orçamento. Um timeout consome o orçamento, então não há 2ª tentativa de 30 s.
- **R3 — disjuntor por instância.** Um `httpx.TimeoutException` dentro do escopo abre o disjuntor por `B` segundos (`RPG_EMBEDDING_BREAKER_S`, default **60**; `0` desliga só o disjuntor). Com o disjuntor aberto, uma chamada **dentro do escopo** levanta `EmbeddingSkipped` (subclasse de `RuntimeError`) antes de qualquer rede: não chama `_emit_embedding_attempt` e não gera evento de uso. O estado é um `float` monotônico em memória, protegido por `threading.Lock`, sem persistência. Na Vercel vale por instância (mesmo padrão de `SpeechCircuit`, `services/speech_to_text.py:113-146`). Fechamento só por tempo: vencido `B`, a próxima consulta tenta de novo, e um novo timeout reabre.
- **R4 — prefetch sem embedding duplo.** Com o modo ligado (R6), `take` (`services/context_prefetch.py:143`) espera um prefetch **já iniciado** até `max(_wait_seconds(), T + 0,5)` em vez de só `_wait_seconds()`. Prefetch que termina, com vetor ou com falha fechada, é usado. Não há segunda chamada em linha ao provedor pendurado. O ramo `not_started` (`:138-141`) não muda.
- **R5 — degradação sem exceção e medível.** O turno segue com o contexto não vetorial. `prepare_shared_query_vector` continua devolvendo `(None, provider, model)` para `EmbeddingSkipped` e timeout, e os leitores fecham (`context_sources.py:106`). Nenhuma exceção chega ao jogador. Evento novo `embedding.query_degraded` (warning) com `reason` ∈ {`timeout`, `breaker_open`}, `waited_ms` (int), `budget_ms` (int) e `breaker_s` (int), uma vez por chamada degradada, sem texto da consulta. No pulo, também `log_provider_attempt("embedding", "jina", model, "circuit_open")` (outcome já aceito, `observability/telemetry.py:151`). O catálogo `observability/events.py` é regenerado por `scripts/gen_event_catalog.py`.
- **R6 — kill switch.** `RPG_EMBEDDING_QUERY_DEADLINE` (`on`|`off`, default `on`). Com `off`, o escopo vira no-op e `take` volta a esperar só `_wait_seconds()`: o comportamento é o de antes, byte a byte (30 s × 2, sem disjuntor, sem evento novo).
- **R7 — registro das flags.** As 3 `RPG_*` novas entram em `config/flags.yaml`: `RPG_EMBEDDING_QUERY_DEADLINE` (`kind: kill_switch`, default `"on"`), `RPG_EMBEDDING_QUERY_TIMEOUT_S` (`ops`, `"6.0"`) e `RPG_EMBEDDING_BREAKER_S` (`ops`, `"60"`), todas com `spec: SPEC-419`. Cada uma ganha uma linha comentada em `.env.example`. `EMBEDDING_TIMEOUT_SECONDS`/`EMBEDDING_MAX_ATTEMPTS` não mudam (não são `RPG_*`, SPEC-356 §Fora de escopo).
- **R8 — `rag.py` não cresce.** `rag.py` tem 1.649 linhas (`tests/size_budget.json:22`). `_parse_retry_after` e `_MAX_BACKOFF_SECONDS` (`rag.py:315-332`) passam para `services/embedding_guard.py` sem mudar o comportamento e são reimportados em `rag.py` com o mesmo nome. Assim o arquivo termina com ≤ 1.649 linhas. `tests/test_size_budget.py` verde, sem `--update`.

### Fora de escopo

- **Trocar de provedor de embedding** ou mudar `EMBEDDING_ROUTES`.
- **openai/ollama/gemini:** usam clientes langchain sem prazo por chamada (`rag.py:485-501`); staging e produção usam Jina. Dentro do escopo eles seguem como hoje.
- **`query_rag` e as leituras textuais** (`rag.py:1296`), inclusive na geração de NPC/inimigo no turno (`agents/npc.py:501-503`, `agents/bestiary.py:639`) e em `services/opening_threads.py:381`. A mesma função serve o job `creature_gen` (`workers/run_worker.py:225-230` → `services/creature_gen.py:1616`), e nenhum dos 2 incidentes passou por ela. Fica como decisão D1 (§8).
- **Escrita, indexação e jobs:** `add_memory_to_session`/`_faiss_add` (`rag.py:1390-1473`), job `embed_memory` (`workers/run_worker.py:129-153`, usa `embed_query` fora do escopo), `PgVectorMemoryStore.stage`, reindex (`rag.py:1641-1642`). Ficam com 30 s × 2.
- **`enrich` de 26 s** dois turnos depois (`resultado.json:6175`, "other" 26.364 ms, 3 chamadas FAST somando 18,5 s): **não coberto**, causa não isolada.
- **Espera de ~19 s de rede** entre a máquina de medição e a borda da Vercel (`latencia-turno-medicao-2026-11-13.md:60`): não é do servidor.
- Prazo no semáforo `RPG_EMBEDDING_MAX_CONCURRENCY` (`context_sources.py:73`): a espera fica limitada indiretamente (cada detentor sai em ≤ T, e o disjuntor esvazia a fila; ver Concorrência).
- Não reabre SPEC-214 (sem cache de cena, NO_GO), SPEC-143 (sem fan-out de LLM) nem SPEC-213 (arquivista inline no staging): nada aqui mexe nesses contratos.

### Invariantes

- **I1** — Provedor respondendo dentro de `T`: o mesmo vetor, o mesmo número de requisições e o mesmo texto de contexto de antes (teste: `test_resposta_normal_identica_com_e_sem_prazo`).
- **I2** — Fora do escopo (job, escrita, reindex, `query_rag`), a requisição usa o timeout do cliente (30 s), faz até `max_attempts` tentativas e ignora o disjuntor aberto (teste: `test_disjuntor_nao_afeta_job_nem_escrita`).
- **I3** — Nenhuma exceção sai de `embed_context_query_uncached` por timeout ou pulo, e os leitores devolvem `""` sem nova chamada de rede (teste: `test_contexto_passa_dentro_do_prazo_com_provedor_travado`).
- **I4** — Nenhum log ou evento contém o texto da consulta (teste: `test_logs_sem_texto_da_consulta`).
- **I5** — `RPG_EMBEDDING_QUERY_DEADLINE=off` reproduz o comportamento anterior: timeout 30, 2 tentativas, sem evento novo, `take` com 2,0 s (teste: `test_kill_switch_off_volta_ao_comportamento_antigo`).

## 3. Design técnico

**Arquivo novo — `services/embedding_guard.py`** (≤ 120 linhas; não importa `rag`):

```python
class EmbeddingSkipped(RuntimeError): ...

MAX_BACKOFF_SECONDS: float = 60.0                          # movido de rag.py:315
def parse_retry_after(value: str | None) -> float | None    # movido de rag.py:318-332, idêntico

def enabled() -> bool                                      # RPG_EMBEDDING_QUERY_DEADLINE != "off"
def query_timeout_s() -> float                             # RPG_EMBEDDING_QUERY_TIMEOUT_S, [0.1, 30], default 6.0
def breaker_s() -> float                                   # RPG_EMBEDDING_BREAKER_S, >= 0, default 60
@contextmanager
def interactive_query() -> Iterator[None]                  # seta o ContextVar só se enabled()
def deadline() -> float | None                             # monotonic()+T fixado na 1ª chamada do _embed; None fora do escopo
def check_breaker(model: str) -> None                      # aberto e no escopo -> log + raise EmbeddingSkipped
def note_timeout(started: float) -> None                   # no escopo: abre o disjuntor (se B>0) + evento reason=timeout
def prefetch_wait(base: float) -> float                    # enabled() -> max(base, T+0.5); senão base
def reset_for_tests() -> None                              # fecha o disjuntor (seam de teste, D-05)
```

Leitura de env igual a `context_prefetch._wait_seconds` (`:39-43`): `try/float/except ValueError`. Antes de criar, `Grep "def _env_float\|def env_float"`: se já houver helper, reutilize.

**Arquivos alterados:**
- `rag.py`:
  - `from services.embedding_guard import MAX_BACKOFF_SECONDS as _MAX_BACKOFF_SECONDS, parse_retry_after as _parse_retry_after` no lugar das definições (`:315-332`).
  - Em `_embed` (`:394-461`): no início, `embedding_guard.check_breaker(self.model_name)` e `end = embedding_guard.deadline()`. Em cada tentativa, se `end` existir, `remaining = end - perf_counter()`; com `remaining < 0.1`, para e levanta `last_error` (ou `EmbeddingSkipped` se não houve tentativa). Senão, passa `timeout=httpx.Timeout(remaining)` ao `post`. Em `except httpx.TransportError`, se a exceção for `httpx.TimeoutException`, chama `embedding_guard.note_timeout(started)`. Sem `end`, o código atual não muda.
  - `prepare_shared_query_vector` não muda: o `except Exception` em `:1029` e `:1056` já cobre `EmbeddingSkipped`.
- `services/context_sources.py:73-78`: `with embedding_guard.interactive_query():` em volta do bloco `_limit(...)`/`span`.
- `services/context_prefetch.py:143`: `future.result(timeout=embedding_guard.prefetch_wait(_wait_seconds()))`.
- `config/flags.yaml`, `.env.example`, `observability/events.py` (regenerado): R5–R7.

**Evento** (exemplo do JSON que `log_event` grava; correlação automática):

```json
{"event": "embedding.query_degraded", "reason": "timeout", "waited_ms": 6004, "budget_ms": 6000, "breaker_s": 60, "request_id": "…"}
```

**Escolha de `T` = 6 s (dado):** nos 60 turnos da L0, a etapa de contexto (que inclui o embedding e a consulta pgvector) teve mediana ~0,32 s e p95 1,45 s. O maior valor fora dos incidentes foi 4.764 ms (turno 10, `resultado.json:6173`), ~2,4 min depois do início do turno 7, com o provedor lento mas respondendo. 6 s preserva esse turno com folga, mantém "poucos segundos" e corta o pior caso de 45,7 s para ≤ ~6 s. A divisão do 4,76 s entre embedding e pgvector não foi medida. A Etapa 0 mede a latência da Jina sem pgvector: **medido em 13/11 pelo coordenador** (30 `embed_query` reais na Jina, desta máquina, 0,3 s entre chamadas): p50 0,29 s · p95 0,50 s · máx 0,68 s (a primeira, com conexão nova). O p95 ficou abaixo de 3 s, então o default de 6 s fica.

**Escolha de `B` = 60 s:** na L0, os turnos 7 e 8 começaram com 58 s de diferença (`resultado.json:5848,5945`). Com o turno 7 limitado a ~6 s, o 8 começaria ~10–20 s depois do disparo (contexto do 7 em ~8 s + narração + 6 s de leitura), dentro da janela. Um jogador humano lê por mais tempo, então 60 s cobre em geral só o turno seguinte, e a perda de memória fica restrita a ~1 turno depois do travamento.

### Concorrência

| Evento | Estado no momento | Resultado esperado | Teste |
|---|---|---|---|
| Prefetch e embed em linha travam juntos (2 threads, mesmo provedor) | os 2 no `post` | cada um termina em ≤ T; os 2 chamam `note_timeout`, e o disjuntor fica com `max(open_until)` sob lock | `test_dois_timeouts_simultaneos_abrem_uma_janela` |
| `take` espera prefetch iniciado e travado | worker no `post` com prazo T | `take` espera até T+0,5; o prefetch termina com falha fechada, `take` devolve esse resultado e não há chamada em linha | `test_consumer_espera_prefetch_lento_ate_o_prazo_sem_embedding_duplo` |
| A soma das fases do httpx (connect + read) passa de T | `take` estoura T+0,5 | `prefetch_miss`, embed em linha; se o prefetch já disparou o disjuntor, o pulo é imediato, senão é ≤ T a mais (pior caso ~2T, documentado) | coberto pelo teste acima com `WAIT_S` pequeno |
| Disjuntor aberto e job `embed_memory`/escrita na mesma instância | fora do escopo | requisição normal, 30 s × 2 | `test_disjuntor_nao_afeta_job_nem_escrita` |
| Usuário B na mesma instância (Fluid) depois de timeout de A | disjuntor aberto | B também pula por ≤ B s (falha do provedor, não do usuário); outras instâncias pagam ≤ T uma vez | `test_disjuntor_pula_sem_rede_depois_de_timeout` |
| Fila do semáforo `RPG_EMBEDDING_MAX_CONCURRENCY` (2) com provedor travado | 2 detentores no `post` | cada detentor sai em ≤ T; depois do 1º timeout, os da fila pulam sem rede | não testado (limite derivado de R2/R3) |
| Cancelamento | N/A | turno síncrono; a thread do prefetch não é cancelada, mas fica limitada a T | — |

## 4. Plano passo a passo

### Etapa 0 — Confirmar e medir (sem código de produto)
1. Reconfirmar as linhas citadas no §1 e no §3. Rodar a base: `bash scripts/dev/pt.sh tests/test_embeddings_provider.py tests/test_context_prefetch.py tests/test_context_sources_concurrency.py tests/test_provider_logging.py tests/test_spec237_embedding_pricing.py`.
2. Medição da Jina do §3: feita pelo coordenador em 13/11 (p95 0,50 s; default de 6 s mantido).
3. Ler `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` § concorrência e marcar no hand-back o que se aplica.

### Etapa 1 — Testes primeiro (devem falhar no código atual)
`tests/test_embedding_guard.py` (novo; spec na docstring). Jina real com `httpx.MockTransport`, como em `tests/test_embeddings_provider.py:124-142`. O handler "travado" dorme `min(request.extensions["timeout"]["read"], 3.0)` e levanta `httpx.ReadTimeout`. Fixture autouse com `embedding_guard.reset_for_tests()`. Toda espera com teto.
- `test_contexto_passa_dentro_do_prazo_com_provedor_travado`: `T=0.3`; `rag.is_database_profile`, `rag.get_embeddings`, `rag.active_provider` → Jina falsa. `embed_context_query_uncached` + `acquire_context_sources` terminam em < 1,0 s, com `vector is None`, `embedding_provider == "jina"`, todos os resultados `text == ""` e 1 requisição. Hoje leva ~6 s.
- `test_consulta_interativa_usa_prazo_curto`: no escopo, `extensions["timeout"]["read"] <= T` e uma única tentativa no timeout.
- `test_consulta_interativa_preserva_retry_rapido_de_5xx`: 503 e depois 200, no escopo → vetor e 2 requisições.
- `test_disjuntor_pula_sem_rede_depois_de_timeout`: depois de 1 timeout no escopo, a 2ª chamada levanta `EmbeddingSkipped`, sem requisição nova e sem evento de uso, com `provider.attempt circuit_open` e `embedding.query_degraded reason=breaker_open`. Com `time.monotonic` do módulo avançado 61 s, volta à rede.
- `test_dois_timeouts_simultaneos_abrem_uma_janela`: 2 threads no escopo, ambas com timeout → um único `open_until` coerente e nenhuma exceção não tratada.
- `test_disjuntor_nao_afeta_job_nem_escrita` (I2): com o disjuntor aberto, `embed_query`/`embed_documents` fora do escopo vão à rede com `read == 30` e 2 tentativas.
- `test_resposta_normal_identica_com_e_sem_prazo` (I1): resposta 200 normal → o mesmo vetor e 1 requisição com `on` e com `off`.
- `test_kill_switch_off_volta_ao_comportamento_antigo` (I5), `test_breaker_zero_desliga_so_o_disjuntor`, `test_env_invalido_ou_fora_da_faixa_cai_no_default` (parametrizado: `"abc"`, `"0"`, `"999"`, `" 6 "`).
- `test_logs_sem_texto_da_consulta` (I4): consulta `"SEGREDO_X"`; `caplog` e eventos não contêm o texto.
`tests/test_context_prefetch.py` (existente):
- `test_consumer_espera_prefetch_lento_ate_o_prazo_sem_embedding_duplo`: `RPG_CONTEXT_PREFETCH_WAIT_S=0.1`, `T=1.0`, fake que demora 0,4 s → `calls == 1` e vetor presente. Hoje dá `calls == 2`.
- `test_prefetch_espera_antiga_com_kill_switch_off`: `off` → `calls == 2` (comportamento atual).
Verificação: os testes novos falham; os existentes seguem verdes.

### Etapa 2 — Implementação
`services/embedding_guard.py`, alterações do §3 em `rag.py`, `context_sources.py` e `context_prefetch.py`. Depois, `bash scripts/dev/py.sh scripts/gen_event_catalog.py`, entradas em `config/flags.yaml` e linhas em `.env.example`.
Verificação: `bash scripts/dev/pt.sh tests/test_embedding_guard.py tests/test_embeddings_provider.py tests/test_context_prefetch.py tests/test_context_sources_concurrency.py tests/test_provider_logging.py tests/test_spec237_embedding_pricing.py tests/test_log_event_registry.py tests/test_flag_registry.py tests/test_size_budget.py` verde; `ruff format --check` e `ruff check` nos arquivos tocados; `wc -l rag.py` ≤ 1649.

### Etapa 3 — Fechamento
`scripts/dev/dup_helpers.py --diff main...HEAD`. Revisão Sonnet com foco no domínio concorrência: lock do disjuntor, `ContextVar` no prefetch e prazo somado das tentativas. A suíte completa roda só no pouso, pelo coordenador. Smoke §6 no staging.

## 5. Critérios de aceite

- [ ] Testes da Etapa 1 falham antes e passam depois (saída no hand-back)
- [ ] I1–I5 cobertos pelos testes nomeados
- [ ] `rag.py` ≤ 1.649 linhas; `tests/test_size_budget.py`, `test_flag_registry.py` e `test_log_event_registry.py` verdes
- [ ] Nenhum chamador além de `embed_context_query_uncached` entra em `interactive_query()` (`Grep "interactive_query("`)
- [x] Medição da Jina do §3 registrada (13/11)
- [ ] Smoke §6 registrado (normal + forçado)
- [ ] `uv run pytest` verde (suíte completa offline, no pouso)
- [ ] Guard de FallbackLLM: N/A (sem `with_structured_output` novo)
- [ ] Saves antigos continuam carregando: N/A (nada persistido)

## 6. Smoke test com LLM real

No staging com DeepSeek e Jina (custo estimado ≤ US$ 0,10):
1. **Normal** (defaults): `docs/auditorias/latencia-l0-2026-11-13/l0_measure.py --sessions 1 --out <arquivo>` (15 turnos). Espera: 0 `embedding.query_degraded`, 0 erro e etapa `context` com mediana dentro de ±0,2 s da L0 (~0,32 s).
2. **Forçado:** `RPG_EMBEDDING_QUERY_TIMEOUT_S=0.1` no staging e redeploy, depois 3 turnos de história. Espera: turno 1 com `reason=timeout`, turnos 2–3 com `reason=breaker_open`, narração presente, sem erro ao jogador, `context` < 1 s nos turnos 2–3, e o job `embed_memory` concluindo normalmente (`job.*` sem falha nova).
3. **Kill switch:** `RPG_EMBEDDING_QUERY_DEADLINE=off` com o timeout forçado mantido, 1 turno. Espera: nenhum `embedding.query_degraded` (comportamento antigo). Depois, remover as duas variáveis e redeployar.

## Não rodou e por quê

- Preenchido pelo executor e pelo coordenador. Quando escrita, a spec não rodou nada: sem pytest, sem rede (regra do autor).

## 7. Riscos & compatibilidade

- **Saves:** nada persistido. O disjuntor vive só em memória.
- **MockLLM/FallbackLLM:** não tocados. Sem chave de embedding, `get_embeddings()` → `None` e o escopo é inerte.
- **Qualidade:** num travamento, o turno e até ~60 s seguintes ficam sem lore, sessão e NPC vetoriais (aceito pelo dono). O resto do pack (fatos dinâmicos, cena, NPC) não depende do vetor.
- **Lento mas respondendo acima de 6 s:** perde a memória daquele turno, quando antes esperava. Na L0, nenhum turno fora dos incidentes passou de 4,8 s, e a Etapa 0 confirma.
- **Fluid compute:** o disjuntor é compartilhado entre os usuários da mesma instância; o pulo é intencional (falha do provedor).
- **Custo:** menos chamadas à Jina num travamento (sem 2ª tentativa e sem embedding duplo no prefetch).

## 8. Decisões

- **D1 (dono, opcional):** estender o prazo curto às leituras de `query_rag` na geração de NPC e inimigo durante o turno (`agents/npc.py:501-503`, `agents/bestiary.py:639`). Recomendação: **não agora**. Elas não apareceram nos incidentes e a função também serve o job `creature_gen`. Medir antes com o evento novo e com `provider.attempt timeout` fora do escopo.
- **D2 (autor, revisável):** `T` = 6 s e `B` = 60 s pelos dados do §3. O ajuste é por env (`ops`), sem deploy de código.
- **13/11, coordenador:** D1 fica como recomendado (não estender agora); D2 mantido (6 s / 60 s). O dono aprovou a spec e a execução em 13/11 ("pode. e execute elas"); veto continua possível.
