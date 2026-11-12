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
Cancelar a requisição durante `to_thread(prepare_audio)` deixa o thread terminar sozinho (ffmpeg
tem `timeout=10`); o `TemporaryDirectory` é removido na saída do `with`. `begun` fica falso, então
`finance.finish` não roda. Coberto por `test_cancelar_durante_prepare_...`.

## Smoke real
Adiado: depende da SPEC-409 (rate card de STT vencido; staging 503). Não bloqueia (D1).
