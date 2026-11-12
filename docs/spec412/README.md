# SPEC-412 — STT fora do event loop

## O que mudou
`transcribe_audio` roda `prepare_audio` e `finance.begin/admit/finish` em `asyncio.to_thread`;
`account_transcription` roda `rate_limiter.consume` em `run_in_threadpool`. Ordem financeira,
contrato HTTP e preço intactos. `asyncio.to_thread` e `run_in_threadpool` copiam o contexto: o
`ContextVar` do principal chega ao thread (provado em `tests/test_speech_to_text.py` e
`tests/test_speech_api.py`).

## Inventário de `async def` com chamada bloqueante (reconfirmado por Grep)
Rotas `async def`: `routes/billing.py` `stripe_webhook` (já usa `run_in_threadpool`) e
`account_transcription` (corrigida aqui). Pendentes, follow-up após a SPEC-410 (D3, spec própria):
- `api.py` `_rate_limit` -> `rate_limiter.consume` (psycopg por requisição).
- `api.py` `_session_boundary` -> `_boundary_principal` (`identity_verifier.verify`, `admin_connection`),
  `_owner_rate_limit` (`consume`), `_record_authfail` (`consume`).
Sem I/O bloqueante: `_rate_limit_metrics`, `services/body_limit.py` (ASGI puro). Já fora do loop:
`llm_setup.ainvoke`, `services/context_sources.py`.

## ffmpeg e Vercel
A Vercel não tem ffmpeg (`docs/spec187/README.md`, `web/src/voice/wav.ts`,
`scripts/staging/voice_smoke.py`, `scripts/staging/vercel_env.py`): o cliente envia WAV PCM16 e o
servidor só usa `wave`; formato comprimido cai em 503 `audio_decoder_unavailable`. Os 10 s do ffmpeg
só existem no perfil portable/uvicorn local.

## Concorrência por instância na Vercel
Não verificado (sem acesso à documentação nesta execução; `vercel.json` só define `maxDuration`).
Não bloqueia a spec.

## Cancelamento (R7)
`to_thread` nao interrompe o thread quando a corrotina e cancelada: ele roda ate o fim. Desenho:
`prepare_audio` fica em `to_thread` simples (nao tem efeito financeiro; `TemporaryDirectory` remove o
arquivo na saida do `with`). `begin`, `admit` e `finish` passam por `_run_to_completion`
(`asyncio.shield` + espera do thread); se a task e cancelada, ela AGUARDA o thread financeiro em
curso terminar e so entao propaga `CancelledError`. `begun` e o ordinal admitido sao marcados
dentro do thread, entao o `finally` sabe o que de fato efetivou. Se o cancelamento pegou depois do
`admit` e antes do evento, o `finally` registra o evento `unknown` daquele ordinal (o mesmo que o
codigo sincrono produzia quando o cancelamento chegava no `await` do provider) e roda `finish` 1x,
nunca concorrente com `admit`/`begin`.

| Cancelamento durante | Antes (sincrono) | Agora |
|---|---|---|
| `prepare_audio` | impossivel cancelar no meio; nada financeiro | thread termina sozinho; sem claim/reserva/ticket; temp removido; `finish` nao roda |
| `begin` | impossivel | espera `begin` terminar; `begun` marcado no thread; `finish` roda 1x sem eventos e libera a reserva (`release_pre_effect`); claim fechado; temp removido |
| `admit` | impossivel | espera `admit` terminar; ticket criado recebe evento `unknown`; `finish(events, False)` 1x depois do `admit`; temp removido |
| provider (await) | evento `unknown` + `finish` | igual |
| `finish` | impossivel | o thread de `finish` conclui (1 execucao); `CancelledError` propaga e mascara o `billing`/`SpeechError`; sem execucao dupla |

Cobertura: `test_cancelar_durante_prepare_...`, `test_cancelar_durante_begin_...`,
`test_cancelar_durante_admit_...`, `test_cancelar_durante_finish_...` (fake com `threading.Event`).

## Smoke real
Adiado: depende da SPEC-409 (rate card de STT vencido; staging 503). Não bloqueia (D1).
