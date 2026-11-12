# SPEC-412 — stt-fora-do-event-loop

> **Status:** `in-review` (11/11: aprovada pelo coordenador por delegação do dono, "o resto é nois"; decisões do §8 = recomendações do autor; veto do dono segue possível) · antes `draft`
> **Criada:** 2026-11-11 · **Atualizada:** 2026-11-11
> **Depende de:** nenhuma. **Interage com** SPEC-409 (só o smoke real, §6) e SPEC-410 (o principal precisa chegar à conexão de banco dentro do thread, R4).
> **Desbloqueia:** nada (follow-up possível: SPEC de middlewares `async` com psycopg, §2 "Fora de escopo").
> **Risco:** `médio` (rota de cobrança/STT, sem mudar preço, débito, schema ou contrato HTTP) → revisor Sonnet obrigatório (AGENTS.md § Qualidade, revisão e evidência).
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`) · **REVIEW_MODEL:** Sonnet · **EVAL_AUTHORING_REQUIRED:** `false`.
> **Evidência:** teste que falha antes: com `prepare_audio` trocado por `time.sleep(0.5)`, uma corrotina "ticker" no mesmo loop não progride durante `transcribe_audio` (R1); mais testes de thread/principal (R2–R4). Os testes de STT existentes seguem verdes.

---

## 1. Contexto & Objetivo

Varredura de segurança de 11/11/2026 + revisão independente. Severidade baixa (disponibilidade): `POST /account/transcriptions` (`routes/billing.py:312`) é `async def` e executa trabalho bloqueante direto no event loop. `prepare_audio` (`services/speech_to_text.py:228`) roda dentro de `transcribe_audio` (`:296`, chamada em `:316`) e faz, para webm/ogg/mp4, `subprocess.run(ffmpeg, timeout=10)` (`:258–288`) e depois `_wav_duration` (leitura `wave`, `:201`). O WAV também bloqueia (cópia de até 8 MB, `:241–249`). Tudo antes de `finance.begin` (`:323`): saldo zero não impede o gasto de CPU. Em seguida, `finance.begin/admit/finish` (`infrastructure/speech_finance.py:28,69,80`) e o `rate_limiter.consume` do handler (`routes/billing.py:330`, psycopg em `infrastructure/postgres_turns.py:852`) também são síncronos no loop. Um usuário logado, com `RPG_SPEECH_ENABLED=1` (default `0`, `routes/billing.py:326`), pode segurar o worker ~10 s por chamada (limite: 5/min por dono, `:330–334`; 8 MB).

Por que a rota é `async` (confirmado no source): lê o corpo em streaming com `request.stream()` + `asyncio.timeout(15)` para impor o teto de 8 MB (`:365–372`) e aguarda o provider, cujo contrato é `async def transcribe` (`services/speech_to_text.py:64,70`). O "async não usado" do AGENTS.md vale para o LangGraph; esta rota e os middlewares do `api.py` são a exceção.

Onde o impacto é real: **Vercel não tem ffmpeg** (`docs/spec187/README.md:90–96`; `web/src/voice/wav.ts:1`; `scripts/staging/voice_smoke.py:4`; `scripts/staging/vercel_env.py:52`). Lá o cliente transcodifica para WAV PCM16 e o servidor só usa `wave`; formato comprimido cai em `FileNotFoundError` → 503 `audio_decoder_unavailable` (`:289–290`), sem segurar 10 s. Portanto os 10 s só existem no perfil portable/uvicorn local com ffmpeg (1 loop para todos os usuários). Na Vercel o que sobra é o WAV (dezenas de ms) e o psycopg síncrono; quantas requisições uma instância serverless atende ao mesmo tempo **não está provado no repo** (`vercel.json:7–12` só define `maxDuration`); o executor registra o que a documentação da Vercel diz, sem bloquear a spec. Objetivo: a rota deixa de parar o loop, sem mudar contrato HTTP, ordem financeira nem preço.

## 2. Requisitos

- **R1 — decodificação fora do loop.** Em `transcribe_audio`, `prepare_audio(payload, mime, Path(temp))` roda via `await asyncio.to_thread(...)`. Erros (`SpeechError` 413/422/503) propagam iguais.
- **R2 — finance fora do loop.** `finance.begin`, `finance.admit` e `finance.finish` (todas síncronas, psycopg) rodam via `asyncio.to_thread`. A ordem (prepare → begin → admit/provider → finish no `finally`) e o `begun` não mudam. O protocolo `SpeechFinance` continua síncrono (os dublês de teste não mudam).
- **R3 — rate limit do handler fora do loop.** `runtime.rate_limiter.consume(...)` em `routes/billing.py:330` roda em thread (`run_in_threadpool`, já usado no mesmo arquivo em `:230,279`). Mesma decisão, mesmo `Retry-After`, mesmo `record_block`.
- **R4 — principal atravessa a thread.** O `ContextVar` `_principal` (`infrastructure/request_context.py:11`) é visível dentro do thread de `finance.begin/admit/finish` e do `consume` (`asyncio.to_thread` e `run_in_threadpool` copiam o contexto; vira teste, pois a SPEC-410 tornará principal ausente um erro).
- **R5 — nenhuma mudança observável.** Status, códigos (`speech_*`, `audio_*`), corpo da resposta, idempotência por `operation_id`, `billing_status` e eventos de uso idênticos; os testes de STT existentes passam sem alteração de assert.
- **R6 — registro.** `docs/spec412/README.md` (curto): lista das rotas/middlewares `async` com chamada bloqueante (§3), resposta sobre ffmpeg/Vercel e a conclusão sobre cancelamento (R7).
- **R7 — cancelamento.** Cancelar a requisição (desconexão do cliente) durante `to_thread` deixa o thread terminar sozinho; o `TemporaryDirectory` pode ser removido enquanto o ffmpeg ainda roda (no máximo 10 s, `timeout=10`). Teste: `test_cancelar_durante_prepare_nao_vaza_e_finance_finish_nao_roda_sem_begin` (cancela a task em `prepare_audio` lento; `finance.finish` não é chamado porque `begun` é falso; sem exceção não tratada).

### Fora de escopo

- **(c) Reordenar para checar saldo antes do ffmpeg.** Decisão: não. `begin` não depende da duração (recebe só `request_hash` e `candidates`, `:319–323`), mas cria claim e reserva (`speech_finance.py:45–64`) e consome o `operation_id`; hoje áudio inválido nunca chega a reservar. Uma pré-checagem barata de saldo mínimo seria outra spec, e o abuso já é limitado por login + 5/min + 8 MB.
- **Semáforo de concorrência do ffmpeg.** Não é barato: `asyncio.Semaphore` de módulo quebra entre loops (testes com `asyncio.run`), e `threading.Semaphore` ocuparia threads do executor padrão, compartilhado com `llm_setup.ainvoke` (`llm_setup.py:1218`) e `context_sources` (`:218`). Reavaliar só se a Etapa 0 mostrar starvation.
- **Middlewares e handlers `async` do `api.py` com psycopg** (padrão-raiz, spec própria; ver §3).
- Mudar `SpeechFinance` para `async`, o provider, preços, rate cards (SPEC-409), `RPG_SPEECH_ENABLED`, limites de 8 MB/60 s/5 por min, formatos aceitos.

## 3. Design técnico

**Arquivos alterados.**
- `services/speech_to_text.py`: em `transcribe_audio`, `audio, duration = await asyncio.to_thread(prepare_audio, payload, mime, Path(temp))`; `await asyncio.to_thread(finance.begin, ...)`, `... finance.admit, ordinal, candidate`, e `billing = await asyncio.to_thread(finance.finish, events, text is not None)`. `asyncio` já é importado. Sem helper novo.
- `routes/billing.py`: `decision = await run_in_threadpool(runtime.rate_limiter.consume, key, limit=5, window_seconds=60)` (import local, igual ao `stripe_webhook`).
- Testes: `tests/test_speech_to_text.py` (R1, R2, R4, R7) e `tests/test_speech_api.py` (R3) com o harness existente; dublês de finance/provider já existem nesses arquivos (`test_speech_to_text.py:71`, `test_speech_api.py:67`).

**Inventário do padrão-raiz (R6; a Etapa 0 reconfirma com `Grep "async def"` em `routes api.py api_core.py services workers infrastructure`).** Rotas `async def` do projeto: só `routes/billing.py:226 stripe_webhook` (já usa `run_in_threadpool` em `:279` para `accept_event`) e `:312 account_transcription` (esta spec). Middlewares/handlers em `api.py`, onde há chamada bloqueante no loop (ainda não corrigidos):
- `api.py:931 _rate_limit` → `get_runtime().rate_limiter.consume` (`:949`), psycopg em toda requisição classificada nos perfis de banco.
- `api.py:400 _session_boundary` → `_boundary_principal` (`:538`: `identity_verifier.verify`, que consulta `app.runtime_session_active` em `infrastructure/supabase_identity.py:437`, e `admin_connection` em `:562`), `_owner_rate_limit` (`:981`, `consume` em `:994`) e `_record_authfail` (`:510`, `consume` em `:517`).
- Sem I/O bloqueante: `_rate_limit_metrics` (`:897`, memória), `_correlation_boundary` (`:700`, a confirmar), handlers de exceção (`:243–330,1017`), `services/body_limit.py` (ASGI puro). Já fora do loop: `llm_setup.py:1218`, `services/context_sources.py:204/218`.
Isto é um follow-up maior (afeta toda rota; mexe em auth), registrado em `docs/spec412/README.md` para o coordenador abrir spec.

**Assinaturas públicas:** nenhuma muda (`transcribe_audio(...) -> dict` continua `async`).

## 4. Plano passo a passo

### Etapa 0 — Confirmar (sem código de produto)
1. Reconfirmar o inventário do §3 e a leitura de `identity_verifier.verify`. Confirmar que `asyncio.to_thread` e `run_in_threadpool` copiam o contexto (documentação/teste da Etapa 1). Registrar em `docs/spec412/README.md` o que a documentação da Vercel diz sobre concorrência por instância (Fluid compute ou não) e a conclusão "ffmpeg ausente na Vercel" com as evidências do §1. Rodar `bash scripts/dev/pt.sh tests/test_speech_to_text.py tests/test_speech_api.py tests/test_speech_finance_local.py` como linha de base.

### Etapa 1 — Testes primeiro (devem falhar no código atual)
1. `tests/test_speech_to_text.py`:
   - `test_prepare_audio_nao_bloqueia_o_loop`: `monkeypatch` de `prepare_audio` por `lambda *a: (time.sleep(0.5), (wav_path, Decimal(1)))[1]`; `asyncio.gather(transcribe_audio(...com dublês), ticker())` onde `ticker` faz 5× `await asyncio.sleep(0.01)` (molde: `tests/test_turn_pipeline_concurrency.py:104–118`); asserta `ticks == 5` **antes** de a transcrição terminar (ex.: ticker registra instante; assert instante do último tick < instante do fim do `prepare_audio`).
   - `test_finance_roda_em_thread_com_principal`: finance falso grava `threading.get_ident()` e `active_principal()` em `begin`, `admit` e `finish`; dentro de `principal_scope(p)`; asserta ident ≠ do loop e principal `== p` nas três.
   - `test_cancelar_durante_prepare_...` (R7).
2. `tests/test_speech_api.py`: `test_rate_limit_do_handler_roda_em_thread_com_principal`: runtime falso com `rate_limiter.consume` que grava thread e `active_principal()`; asserta thread ≠ do loop e principal presente; e que 429 e `Retry-After` seguem iguais.
3. Verificação: os 3–4 testes novos falham; os demais verdes.

### Etapa 2 — Implementação
`to_thread` em `prepare_audio` (R1), `begin/admit/finish` (R2) e `run_in_threadpool` no `consume` (R3). Nada mais.
Verificação: `bash scripts/dev/pt.sh tests/test_speech_to_text.py tests/test_speech_api.py tests/test_speech_finance_local.py tests/test_provider_logging.py tests/test_bug_finops_wallet_jobs.py tests/test_bug_finops_wallet_jobs_local.py` verde; `ruff format --check` e `ruff check` nos arquivos tocados; `tests/test_size_budget.py` verde.

### Etapa 3 — Fechamento
`docs/spec412/README.md` (R6), `dup_helpers.py --diff main...HEAD` sem helper novo, revisão Sonnet do diff (foco: ordem financeira, `begun`/`finally`, cancelamento). Suíte completa só no pouso, pelo coordenador.

## 5. Critérios de aceite

- [x] Os testes da Etapa 1 falham antes da Etapa 2 e passam depois (saída anexada ao hand-back).
- [x] `transcribe_audio` não chama `prepare_audio`, `finance.begin/admit/finish` diretamente no loop; `routes/billing.py` não chama `rate_limiter.consume` direto em `account_transcription` (`Grep`).
- [x] Testes existentes de STT/wallet-STT verdes sem mudar nenhum assert (R5).
- [x] `docs/spec412/README.md` com inventário `async`, conclusão ffmpeg/Vercel e concorrência da Vercel.
- [x] Cancelamento em begin/admit/finish sem janela nova (rodada 2, `_run_financial`).
- [ ] `ruff format --check`, `ruff check`, `test_size_budget.py` verdes; revisão Sonnet APPROVED.
- [ ] `uv run pytest` verde (suíte completa, 1× no pouso).

## 6. Smoke test com LLM real

Não há LLM nem mudança de mapeamento de campo, preço ou provider; a mudança é de threading, provada por teste determinístico. **Dependência:** o STT está indisponível no staging até a SPEC-409 renovar o rate card de STT (venceu em 11/11, falha fechada com 503). Recomendação: **a spec fecha só com os testes** (D1); o smoke real é verificação extra e não bloqueia. Se a 409 já tiver pousado: `scripts/staging/voice_smoke.py` (WAV) uma vez, esperando 200 e `billing_status` `settled`, mais um segundo pedido simultâneo a `GET /health` durante o upload para ver que não trava. Se não tiver: registrar "smoke adiado, dependente da 409" no hand-back; a spec não fica `in-progress` por isso.

## 7. Riscos & compatibilidade

- Saves, MockLLM, quota: não afetados (o STT não usa o grafo).
- **Cancelamento:** `await to_thread(finance.finish)` num `finally` pode perder o retorno (`billing`) se a task for cancelada de novo, mas o thread conclui a escrita; antes, o `finish` síncrono era ininterruptível. Coberto por R7 e pelo teste de cancelamento existente (`test_speech_to_text.py:350`).
- **Pool de threads/conexões:** cada chamada ocupa 1 thread do executor padrão por instante (já usado por `ainvoke`); o pool psycopg tem tamanho próprio, inalterado.
- **SPEC-410:** se a estrita ligar, o thread sem principal levantaria erro; R4 trava o contrário em teste.
- Ordem financeira inalterada (R2/R5); revisor confere o `finally`.

## 8. Decisões do dono

- **D1 — Smoke real:** aceitar testes determinísticos como prova suficiente, com `voice_smoke.py` oportunista depois da SPEC-409? Recomendo sim.
- **D2 — Semáforo do ffmpeg e pré-checagem de saldo:** deixar fora (motivos no §2)? Recomendo sim; ambos só se a medição pedir.
- **D3 — Middlewares `async` do `api.py`:** abrir spec própria para `_rate_limit`/`_session_boundary` (padrão-raiz, afeta toda rota)? Recomendo sim, depois da 410, por tocar auth e principal.

## Resposta à revisão (rodada 2, status `in-review`)

- P1 (cancelar durante `admit`): `admit` roda via `_run_financial` (shield + espera do thread); o ordinal admitido e marcado no thread e o `finally` registra o evento `unknown` se faltar; `finish` 1x, depois do `admit`. Teste `test_cancelar_durante_admit_...`.
- P2 (cancelar durante `begin`): `begun` marcado dentro do thread; `finish` roda e libera a reserva. Teste `test_cancelar_durante_begin_...`.
- P2 (cancelar durante `finish`): sem execucao dupla; `CancelledError` mascara a `SpeechError`/`billing` (documentado no README, R7). Teste `test_cancelar_durante_finish_...`.
- P3: `run_in_threadpool` importado no topo de `routes/billing.py`.
- Docs: README R7 reescrito com a tabela ponto x efeito x antes x agora. Sem desvio da spec (finance continua em thread).
